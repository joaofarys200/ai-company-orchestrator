//! Native Phase 6 Study Modes fast-path engine.
//!
//! Handles deterministic Phase 6 state operations (readiness checks, custom flashcard
//! CRUD, SM-2 v6.0 spaced-repetition scheduling, Cornell Notes edits/annotations/Obsidian
//! Vault export, assessment/active-recall read getters, prioritized daily queues, learning
//! progress recomputation, and study session lifecycle) directly on `data/study/` atomic JSON
//! files, preserving full parity with Python `services/study_modes/*` schemas.
//!
//! LLM-backed generation routes intentionally return `Ok(None)` so `dispatch.rs` forwards
//! them to the Python `StudyWorker`.

use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, OnceLock};

use chrono::Local;
use serde_json::{json, Value};
use tokio::sync::Mutex;
use uuid::Uuid;

use crate::error::AppError;
use crate::knowledge::vault::resolve_vault_root;
use crate::permissions::path_jail::{
    ensure_confined_existing_file, is_safe_identifier, resolve_confined_path,
};
use crate::storage::atomic_fs::atomic_write_string;

// SM-2 v6.0 exact constants aligned with services/study_modes/spaced_repetition_engine.py
const MIN_EASE_FACTOR: f64 = 1.3;
const DEFAULT_EASE_FACTOR: f64 = 2.5;
const MAX_EASE_FACTOR: f64 = 3.2;
const MIN_INTERVAL_DAYS: f64 = 1.0;
const MAX_INTERVAL_DAYS: f64 = 365.0;
const MATURE_INTERVAL_THRESHOLD_DAYS: f64 = 21.0;
const ALGORITHM_VERSION: &str = "sm2-v6.0";

// Progress thresholds aligned with services/study_modes/learning_progress_engine.py
const MIN_OBS_FOR_CHAPTER_MASTERY: usize = 3;
const MIN_OBS_FOR_CONCEPT_MASTERY: usize = 2;
const MIN_FAILURES_FOR_GAP: usize = 2;

static PHASE6_ROOT_LOCKS: OnceLock<std::sync::Mutex<HashMap<PathBuf, Arc<Mutex<()>>>>> =
    OnceLock::new();

fn lock_for_root(project_root: &Path) -> Arc<Mutex<()>> {
    let map = PHASE6_ROOT_LOCKS.get_or_init(|| std::sync::Mutex::new(HashMap::new()));
    let mut guard = map.lock().unwrap_or_else(|p| p.into_inner());
    guard
        .entry(project_root.to_path_buf())
        .or_insert_with(|| Arc::new(Mutex::new(())))
        .clone()
}

fn study_storage_dir(project_root: &Path) -> PathBuf {
    project_root.join("data").join("study")
}

fn global_state_dir(study_dir: &Path) -> PathBuf {
    study_dir.join("study_modes_state")
}

fn validate_study_id(raw: &str, label: &str) -> Result<String, AppError> {
    let trimmed = raw.trim();
    if !is_safe_identifier(trimmed) {
        return Err(AppError::new(
            "INVALID_STUDY_IDENTIFIER",
            format!("Invalid {label}: expected safe identifier"),
        ));
    }
    Ok(trimmed.to_string())
}

fn now_unix_secs() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| (d.as_secs_f64() * 1000.0).round() / 1000.0)
        .unwrap_or(0.0)
}

fn now_iso_local() -> String {
    Local::now().to_rfc3339()
}

fn short_hex(len: usize) -> String {
    Uuid::new_v4()
        .simple()
        .to_string()
        .chars()
        .take(len)
        .collect()
}

fn doc_modes_dir(study_dir: &Path, clean_id: &str) -> PathBuf {
    study_dir
        .join("documents")
        .join(clean_id)
        .join("study_modes")
}

fn read_json_value_or_default(confined_root: &Path, path: &Path, default: Value) -> Value {
    let Ok(canon) = ensure_confined_existing_file(confined_root, path) else {
        return default;
    };
    let Ok(raw) = fs::read_to_string(&canon) else {
        return default;
    };
    serde_json::from_str(&raw).unwrap_or(default)
}

fn write_json_atomic(confined_root: &Path, target: &Path, value: &Value) -> Result<(), AppError> {
    let serialized = serde_json::to_string_pretty(value).map_err(|err| {
        AppError::new(
            "STUDY_MODES_SERIALIZATION_FAILED",
            format!("Failed to serialize Phase 6 payload: {err}"),
        )
    })?;
    atomic_write_string(confined_root, target, &serialized)?;
    Ok(())
}

fn round2(v: f64) -> f64 {
    (v * 100.0).round() / 100.0
}

fn round4(v: f64) -> f64 {
    (v * 10000.0).round() / 10000.0
}

fn parse_rating_quality(rating: &str, confidence: Option<i64>) -> (String, i64) {
    let normalized = rating.trim().to_ascii_uppercase();
    let conf = confidence.unwrap_or(3);
    match normalized.as_str() {
        "AGAIN" | "FAIL" | "MISSED" | "RECALL_MISS" => ("AGAIN".to_string(), 1),
        "HARD" | "PARTIAL" => (normalized, 3),
        "EASY" => ("EASY".to_string(), 5),
        _ => {
            // GOOD / RECALL_PASS
            let q = if conf <= 1 { 3 } else { 4 };
            let canonical = if normalized.is_empty() {
                "GOOD".to_string()
            } else {
                normalized
            };
            (canonical, q)
        }
    }
}

fn sanitize_path_segment(raw: &str, fallback: &str) -> String {
    let cleaned: String = raw
        .chars()
        .map(|c| match c {
            '<' | '>' | ':' | '"' | '/' | '\\' | '|' | '?' | '*' => '_',
            c if c.is_control() => ' ',
            other => other,
        })
        .collect::<String>()
        .trim()
        .trim_matches('.')
        .to_string();
    if cleaned.is_empty() {
        fallback.to_string()
    } else {
        cleaned.chars().take(120).collect()
    }
}

fn compute_readiness_value(study_dir: &Path, clean_id: &str, doc_id: &str) -> Value {
    let doc_dir = study_dir.join("documents").join(clean_id);
    let ast_path = doc_dir.join("ast.json");
    let dossier_path = doc_dir.join("reasoning_dossier.json");
    let plan_path = doc_dir.join("editorial_study_plan.json");
    let dev_path = doc_dir.join("developed_study_content.json");

    let has_ast = ast_path.is_file();
    let dossier = read_json_value_or_default(study_dir, &dossier_path, Value::Null);
    let plan = read_json_value_or_default(study_dir, &plan_path, Value::Null);
    let has_dossier = dossier.is_object();
    let has_plan = plan.is_object();
    let has_study_document =
        dev_path.is_file() || doc_dir.join("document_generation_result.json").is_file();

    let mut missing = Vec::new();
    if !has_ast {
        missing.push("ast.json");
    }
    if !has_dossier {
        missing.push("reasoning_dossier.json");
    }
    if !has_plan {
        missing.push("editorial_study_plan.json");
    }

    let cur_source_sha = dossier
        .get("source_sha256")
        .or_else(|| plan.get("metadata").and_then(|m| m.get("source_sha256")))
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    let cur_dossier_id = dossier
        .get("dossier_id")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();
    let cur_plan_id = plan
        .get("metadata")
        .and_then(|m| m.get("plan_id"))
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_string();

    let meta_path = doc_modes_dir(study_dir, clean_id).join("study_modes_meta.json");
    let meta = read_json_value_or_default(study_dir, &meta_path, Value::Null);
    let mut is_stale = false;
    let mut stale_reasons: Vec<String> = Vec::new();
    if let Some(saved_fp) = meta.get("fingerprints").and_then(Value::as_object) {
        let saved_sha = saved_fp
            .get("source_sha256")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if !cur_source_sha.is_empty() && !saved_sha.is_empty() && cur_source_sha != saved_sha {
            is_stale = true;
            stale_reasons.push("Fonte documental atualizada desde a última geração.".into());
        }
        let saved_dos = saved_fp
            .get("dossier_id")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if !cur_dossier_id.is_empty() && !saved_dos.is_empty() && cur_dossier_id != saved_dos {
            is_stale = true;
            stale_reasons.push("Dossier académico foi regenerado.".into());
        }
        let saved_plan = saved_fp
            .get("plan_id")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if !cur_plan_id.is_empty() && !saved_plan.is_empty() && cur_plan_id != saved_plan {
            is_stale = true;
            stale_reasons.push("Plano editorial foi atualizado.".into());
        }
    }

    let is_ready = has_ast && has_dossier && has_plan;
    let status = if !is_ready {
        "MISSING_ARTIFACTS"
    } else if is_stale {
        "STALE_ARTIFACTS"
    } else {
        "READY"
    };

    let actionable_message = if !is_ready {
        format!(
            "Artefactos em falta para Modos de Estudo: {}.",
            missing.join(", ")
        )
    } else if is_stale {
        stale_reasons.join(" ")
    } else {
        "Documento pronto para todos os Modos de Estudo da Fase 6.".into()
    };

    json!({
        "document_id": doc_id,
        "status": status,
        "is_ready": is_ready,
        "has_ast": has_ast,
        "has_dossier": has_dossier,
        "has_plan": has_plan,
        "has_study_document": has_study_document,
        "is_stale": is_stale,
        "stale_reasons": stale_reasons,
        "missing_artifacts": missing,
        "actionable_message": actionable_message,
        "current_fingerprints": {
            "source_sha256": cur_source_sha,
            "dossier_id": cur_dossier_id,
            "plan_id": cur_plan_id,
        },
    })
}

fn enrich_cards_with_srs(cards: &[Value], srs_states: &BTreeMap<String, Value>) -> Vec<Value> {
    cards
        .iter()
        .map(|card| {
            let mut obj = card.clone();
            let cid = card
                .get("card_id")
                .and_then(Value::as_str)
                .unwrap_or_default();
            if let Some(m) = obj.as_object_mut() {
                if let Some(st) = srs_states.get(cid) {
                    m.insert("srs".to_string(), st.clone());
                    m.insert(
                        "srs_state".to_string(),
                        st.get("learning_state")
                            .cloned()
                            .unwrap_or_else(|| json!("LEARNING")),
                    );
                } else {
                    m.insert("srs_state".to_string(), json!("NEW"));
                }
            }
            obj
        })
        .collect()
}

fn load_srs_states_map(study_dir: &Path) -> BTreeMap<String, Value> {
    let state_path = global_state_dir(study_dir).join("srs_state.json");
    let raw = read_json_value_or_default(study_dir, &state_path, json!({}));
    match raw {
        Value::Object(map) => map.into_iter().collect(),
        _ => BTreeMap::new(),
    }
}

fn record_sm2_review(
    study_dir: &Path,
    doc_id: &str,
    item_id: &str,
    item_type: &str,
    rating: &str,
    confidence: Option<i64>,
    content_difficulty: &str,
    topic: &str,
    chapter_id: &str,
    section_id: &str,
) -> Result<(Value, Value), AppError> {
    let state_dir = global_state_dir(study_dir);
    fs::create_dir_all(&state_dir).map_err(|err| {
        AppError::new(
            "STUDY_MODES_DIR_FAILED",
            format!("Failed creating study_modes_state dir: {err}"),
        )
    })?;

    let state_path = state_dir.join("srs_state.json");
    let history_path = state_dir.join("srs_history.json");

    let mut states_map = load_srs_states_map(study_dir);
    let now = now_unix_secs();
    let (_, q) = parse_rating_quality(rating, confidence);

    let prev = states_map.get(item_id).cloned().unwrap_or_else(|| {
        json!({
            "item_id": item_id,
            "item_type": item_type,
            "document_id": doc_id,
            "ease_factor": DEFAULT_EASE_FACTOR,
            "interval_days": 0.0,
            "repetitions": 0,
            "lapses": 0,
            "reviews_count": 0,
            "consecutive_success": 0,
            "consecutive_failures": 0,
            "learning_state": "NEW",
        })
    });

    let prev_ef = prev
        .get("ease_factor")
        .and_then(Value::as_f64)
        .unwrap_or(DEFAULT_EASE_FACTOR);
    let prev_interval = prev
        .get("interval_days")
        .and_then(Value::as_f64)
        .unwrap_or(0.0);
    let prev_reps = prev.get("repetitions").and_then(Value::as_i64).unwrap_or(0);
    let prev_lapses = prev.get("lapses").and_then(Value::as_i64).unwrap_or(0);
    let prev_reviews = prev
        .get("reviews_count")
        .and_then(Value::as_i64)
        .unwrap_or(0);
    let prev_cs = prev
        .get("consecutive_success")
        .and_then(Value::as_i64)
        .unwrap_or(0);
    let prev_cf = prev
        .get("consecutive_failures")
        .and_then(Value::as_i64)
        .unwrap_or(0);

    let q_f = q as f64;
    let delta_ef = 0.1 - (5.0 - q_f) * (0.08 + (5.0 - q_f) * 0.02);
    let raw_ef = prev_ef + delta_ef;

    let mut difficulty_mod = match rating.trim().to_ascii_uppercase().as_str() {
        "HARD" | "PARTIAL" => 0.92,
        "EASY" => 1.05,
        _ => 1.0,
    };
    if content_difficulty.eq_ignore_ascii_case("ADVANCED") {
        difficulty_mod *= 0.95;
    }

    let (new_cs, new_cf, new_lapses, new_reps, new_ef, new_interval, new_state_str) = if q < 3 {
        let lapse_inc = if prev_reps > 0 { 1 } else { 0 };
        let learning_state = if prev_reviews > 0 {
            "LAPSED"
        } else {
            "LEARNING"
        };
        (
            0,
            prev_cf + 1,
            prev_lapses + lapse_inc,
            0,
            round4(raw_ef.max(MIN_EASE_FACTOR)),
            MIN_INTERVAL_DAYS,
            learning_state,
        )
    } else {
        let ncs = prev_cs + 1;
        let clamped_ef = round4(raw_ef.clamp(MIN_EASE_FACTOR, MAX_EASE_FACTOR));
        let raw_int = if ncs == 1 {
            1.0
        } else if ncs == 2 {
            if q >= 4 {
                6.0
            } else {
                3.0
            }
        } else {
            let quality_bonus = if q == 3 {
                0.8
            } else if q == 5 {
                1.15
            } else {
                1.0
            };
            prev_interval.max(1.0) * clamped_ef * difficulty_mod * quality_bonus
        };
        let bounded_int = round2(raw_int.clamp(MIN_INTERVAL_DAYS, MAX_INTERVAL_DAYS));
        let learning_state = if bounded_int >= MATURE_INTERVAL_THRESHOLD_DAYS {
            "MATURE"
        } else {
            "LEARNING"
        };
        (
            ncs,
            0,
            prev_lapses,
            prev_reps + 1,
            clamped_ef,
            bounded_int,
            learning_state,
        )
    };

    let next_review_ts = now + new_interval * 86_400.0;
    let avg_conf = if let Some(c) = confidence {
        let prev_avg = prev
            .get("avg_confidence")
            .and_then(Value::as_f64)
            .unwrap_or(c as f64);
        if prev_reviews == 0 {
            c as f64
        } else {
            round2((prev_avg * prev_reviews as f64 + c as f64) / (prev_reviews + 1) as f64)
        }
    } else {
        prev.get("avg_confidence")
            .and_then(Value::as_f64)
            .unwrap_or(3.0)
    };

    let new_state = json!({
        "item_id": item_id,
        "item_type": item_type,
        "document_id": doc_id,
        "ease_factor": new_ef,
        "interval_days": new_interval,
        "repetitions": new_reps,
        "lapses": new_lapses,
        "reviews_count": prev_reviews + 1,
        "consecutive_success": new_cs,
        "consecutive_failures": new_cf,
        "learning_state": new_state_str,
        "last_rating": rating.trim().to_ascii_uppercase(),
        "last_quality": q,
        "last_confidence": confidence,
        "avg_confidence": avg_conf,
        "last_review_ts": now,
        "next_review_ts": next_review_ts,
        "algorithm_version": ALGORITHM_VERSION,
        "topic": topic,
        "chapter_id": chapter_id,
        "section_id": section_id,
    });

    states_map.insert(item_id.to_string(), new_state.clone());
    let states_obj: serde_json::Map<String, Value> = states_map.into_iter().collect();
    write_json_atomic(&state_dir, &state_path, &Value::Object(states_obj))?;

    let hist_entry = json!({
        "history_id": format!("rev_{}", short_hex(12)),
        "item_id": item_id,
        "item_type": item_type,
        "document_id": doc_id,
        "rating": rating.trim().to_ascii_uppercase(),
        "quality": q,
        "confidence": confidence,
        "ease_factor_before": prev_ef,
        "ease_factor_after": new_ef,
        "interval_days_after": new_interval,
        "learning_state_after": new_state_str,
        "timestamp": now,
        "topic": topic,
        "chapter_id": chapter_id,
        "section_id": section_id,
    });

    let mut history = match read_json_value_or_default(study_dir, &history_path, json!([])) {
        Value::Array(arr) => arr,
        _ => Vec::new(),
    };
    history.push(hist_entry.clone());
    write_json_atomic(&state_dir, &history_path, &Value::Array(history))?;

    Ok((new_state, hist_entry))
}

fn recompute_learning_progress(
    study_dir: &Path,
    clean_id: &str,
    doc_id: &str,
) -> Result<Value, AppError> {
    let modes_dir = doc_modes_dir(study_dir, clean_id);
    let deck = read_json_value_or_default(
        study_dir,
        &modes_dir.join("flashcards_deck.json"),
        Value::Null,
    );
    let cards: Vec<Value> = deck
        .get("cards")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let total_cards = cards.len();

    let srs_states = load_srs_states_map(study_dir);
    let doc_states: Vec<Value> = srs_states
        .values()
        .filter(|st| st.get("document_id").and_then(Value::as_str) == Some(doc_id))
        .cloned()
        .collect();

    let mut reviewed_cards = 0usize;
    let mut mature_cards = 0usize;
    let mut lapsed_cards = 0usize;
    let mut total_reviews = 0i64;
    let mut due_cards = 0usize;
    let now = now_unix_secs();

    #[derive(Default)]
    struct BucketStats {
        title: String,
        attempts: usize,
        successes: usize,
        failures: usize,
        lapses: usize,
        mature_items: usize,
    }

    let mut chapter_stats: BTreeMap<String, BucketStats> = BTreeMap::new();
    let mut concept_stats: BTreeMap<String, BucketStats> = BTreeMap::new();

    for card in &cards {
        let cid = card
            .get("card_id")
            .and_then(Value::as_str)
            .unwrap_or_default();
        let ch_id = card
            .get("chapter_id")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();
        let ch_title = card
            .get("chapter_title")
            .and_then(Value::as_str)
            .unwrap_or(&ch_id)
            .to_string();
        let topic = card
            .get("topic")
            .and_then(Value::as_str)
            .unwrap_or_default()
            .to_string();

        if let Some(st) = srs_states.get(cid) {
            let rev_c = st.get("reviews_count").and_then(Value::as_i64).unwrap_or(0);
            let l_state = st
                .get("learning_state")
                .and_then(Value::as_str)
                .unwrap_or("NEW");
            let next_ts = st
                .get("next_review_ts")
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            let lapses = st.get("lapses").and_then(Value::as_i64).unwrap_or(0) as usize;
            let cf = st
                .get("consecutive_failures")
                .and_then(Value::as_i64)
                .unwrap_or(0);
            let last_q = st.get("last_quality").and_then(Value::as_i64).unwrap_or(0);

            if rev_c > 0 {
                reviewed_cards += 1;
                total_reviews += rev_c;
            }
            if l_state == "MATURE" {
                mature_cards += 1;
            } else if l_state == "LAPSED" {
                lapsed_cards += 1;
            }
            if next_ts > 0.0 && next_ts <= now {
                due_cards += 1;
            }

            if !ch_id.is_empty() {
                let entry = chapter_stats.entry(ch_id).or_default();
                if entry.title.is_empty() {
                    entry.title = ch_title;
                }
                entry.attempts += rev_c.max(0) as usize;
                if l_state == "MATURE" {
                    entry.mature_items += 1;
                }
                entry.lapses += lapses;
                if last_q >= 3 {
                    entry.successes += 1;
                } else if cf > 0 {
                    entry.failures += cf as usize;
                }
            }
            if !topic.is_empty() {
                let entry = concept_stats.entry(topic.clone()).or_default();
                if entry.title.is_empty() {
                    entry.title = topic;
                }
                entry.attempts += rev_c.max(0) as usize;
                if l_state == "MATURE" {
                    entry.mature_items += 1;
                }
                entry.lapses += lapses;
                if last_q >= 3 {
                    entry.successes += 1;
                } else if cf > 0 {
                    entry.failures += cf as usize;
                }
            }
        }
    }

    let state_dir = global_state_dir(study_dir);
    let assess_attempts: Vec<Value> = match read_json_value_or_default(
        study_dir,
        &state_dir.join("assessment_attempts.json"),
        json!([]),
    ) {
        Value::Array(arr) => arr
            .into_iter()
            .filter(|a| a.get("document_id").and_then(Value::as_str) == Some(doc_id))
            .collect(),
        _ => Vec::new(),
    };
    let recall_attempts: Vec<Value> = match read_json_value_or_default(
        study_dir,
        &state_dir.join("active_recall_attempts.json"),
        json!([]),
    ) {
        Value::Array(arr) => arr
            .into_iter()
            .filter(|a| a.get("document_id").and_then(Value::as_str) == Some(doc_id))
            .collect(),
        _ => Vec::new(),
    };

    let classify_mastery =
        |obs: usize, accuracy: f64, mature_cnt: usize, min_obs: usize| -> &'static str {
            if obs == 0 {
                "UNASSESSED"
            } else if obs >= min_obs && (accuracy >= 0.85 || mature_cnt >= min_obs) {
                "MASTERED"
            } else if accuracy >= 0.65 {
                "PROFICIENT"
            } else if accuracy >= 0.4 {
                "DEVELOPING"
            } else {
                "NEEDS_REVIEW"
            }
        };

    let mut chapter_mastery = Vec::new();
    let mut knowledge_gaps = Vec::new();
    for (ch_id, st) in chapter_stats {
        let denom = (st.successes + st.failures).max(1);
        let acc = (st.successes as f64) / (denom as f64);
        let level = classify_mastery(
            st.attempts,
            acc,
            st.mature_items,
            MIN_OBS_FOR_CHAPTER_MASTERY,
        );
        if st.failures >= MIN_FAILURES_FOR_GAP || st.lapses >= MIN_FAILURES_FOR_GAP {
            knowledge_gaps.push(json!({
                "gap_id": format!("gap_ch_{}", ch_id),
                "gap_type": "CONCEPTUAL_CONFUSION",
                "target_id": ch_id,
                "target_title": st.title,
                "failures": st.failures,
                "lapses": st.lapses,
                "severity": if st.lapses >= 3 { "HIGH" } else { "MEDIUM" },
            }));
        }
        chapter_mastery.push(json!({
            "chapter_id": ch_id,
            "chapter_title": st.title,
            "observations": st.attempts,
            "accuracy": round2(acc * 100.0),
            "lapses": st.lapses,
            "mastery_level": level,
        }));
    }

    let mut concept_mastery = Vec::new();
    for (c_key, st) in concept_stats {
        let denom = (st.successes + st.failures).max(1);
        let acc = (st.successes as f64) / (denom as f64);
        let level = classify_mastery(
            st.attempts,
            acc,
            st.mature_items,
            MIN_OBS_FOR_CONCEPT_MASTERY,
        );
        if st.failures >= MIN_FAILURES_FOR_GAP {
            knowledge_gaps.push(json!({
                "gap_id": format!("gap_c_{}", short_hex(6)),
                "gap_type": "RECALL_FAILURE",
                "target_id": c_key,
                "target_title": st.title,
                "failures": st.failures,
                "severity": "MEDIUM",
            }));
        }
        concept_mastery.push(json!({
            "concept": c_key,
            "observations": st.attempts,
            "accuracy": round2(acc * 100.0),
            "mastery_level": level,
        }));
    }

    let mastery_pct = if total_cards > 0 {
        round2(((mature_cards as f64 + reviewed_cards as f64 * 0.4) / total_cards as f64) * 100.0)
            .min(100.0)
    } else {
        0.0
    };

    let progress = json!({
        "document_id": doc_id,
        "updated_at": now,
        "updated_at_iso": now_iso_local(),
        "total_cards": total_cards,
        "reviewed_cards": reviewed_cards,
        "mature_cards": mature_cards,
        "lapsed_cards": lapsed_cards,
        "due_cards": due_cards,
        "total_reviews": total_reviews,
        "tracked_srs_items": doc_states.len(),
        "assessment_attempts_count": assess_attempts.len(),
        "active_recall_attempts_count": recall_attempts.len(),
        "overall_mastery_percent": mastery_pct,
        "chapter_mastery": chapter_mastery,
        "concept_mastery": concept_mastery,
        "knowledge_gaps": knowledge_gaps,
    });

    fs::create_dir_all(&state_dir).map_err(|err| {
        AppError::new(
            "STUDY_MODES_DIR_FAILED",
            format!("Failed creating study_modes_state dir: {err}"),
        )
    })?;
    let prog_path = state_dir.join("learning_progress.json");
    let mut all_prog = match read_json_value_or_default(study_dir, &prog_path, json!({})) {
        Value::Object(map) => map,
        _ => serde_json::Map::new(),
    };
    all_prog.insert(doc_id.to_string(), progress.clone());
    write_json_atomic(&state_dir, &prog_path, &Value::Object(all_prog))?;

    Ok(progress)
}

fn build_daily_queue(
    study_dir: &Path,
    clean_id: &str,
    doc_id: &str,
    daily_new_limit: usize,
    daily_review_limit: usize,
) -> Value {
    let modes_dir = doc_modes_dir(study_dir, clean_id);
    let deck = read_json_value_or_default(
        study_dir,
        &modes_dir.join("flashcards_deck.json"),
        Value::Null,
    );
    let recall_deck = read_json_value_or_default(
        study_dir,
        &modes_dir.join("active_recall.json"),
        Value::Null,
    );

    let srs_states = load_srs_states_map(study_dir);
    let now = now_unix_secs();

    let mut lapsed_items = Vec::new();
    let mut due_items = Vec::new();
    let mut low_conf_items = Vec::new();
    let mut new_items = Vec::new();

    let mut push_candidate = |item_id: &str,
                              item_type: &str,
                              title: &str,
                              topic: &str,
                              chapter_id: &str,
                              section_id: &str| {
        if item_id.is_empty() {
            return;
        }
        let st = srs_states.get(item_id);
        let category = match st {
            None => "new",
            Some(s) => {
                let rev_c = s.get("reviews_count").and_then(Value::as_i64).unwrap_or(0);
                let l_state = s
                    .get("learning_state")
                    .and_then(Value::as_str)
                    .unwrap_or("NEW");
                let next_ts = s
                    .get("next_review_ts")
                    .and_then(Value::as_f64)
                    .unwrap_or(0.0);
                let last_conf = s
                    .get("last_confidence")
                    .and_then(Value::as_i64)
                    .unwrap_or(3);
                if rev_c == 0 && l_state == "NEW" {
                    "new"
                } else if l_state == "LAPSED" {
                    "lapsed"
                } else if next_ts <= now {
                    "due"
                } else if last_conf <= 2 {
                    "low_confidence"
                } else {
                    return;
                }
            }
        };

        let entry = json!({
            "item_id": item_id,
            "item_type": item_type,
            "queue_category": category,
            "title": title,
            "topic": topic,
            "chapter_id": chapter_id,
            "section_id": section_id,
            "srs_state": st.cloned().unwrap_or(Value::Null),
        });
        match category {
            "lapsed" => lapsed_items.push(entry),
            "due" => due_items.push(entry),
            "low_confidence" => low_conf_items.push(entry),
            _ => new_items.push(entry),
        }
    };

    if let Some(cards) = deck.get("cards").and_then(Value::as_array) {
        for c in cards {
            push_candidate(
                c.get("card_id").and_then(Value::as_str).unwrap_or_default(),
                "FLASHCARD",
                c.get("front").and_then(Value::as_str).unwrap_or_default(),
                c.get("topic").and_then(Value::as_str).unwrap_or_default(),
                c.get("chapter_id")
                    .and_then(Value::as_str)
                    .unwrap_or_default(),
                c.get("section_id")
                    .and_then(Value::as_str)
                    .unwrap_or_default(),
            );
        }
    }
    if let Some(prompts) = recall_deck.get("prompts").and_then(Value::as_array) {
        for p in prompts {
            push_candidate(
                p.get("prompt_id")
                    .and_then(Value::as_str)
                    .unwrap_or_default(),
                "ACTIVE_RECALL",
                p.get("prompt_text")
                    .or_else(|| p.get("title"))
                    .and_then(Value::as_str)
                    .unwrap_or_default(),
                p.get("topic").and_then(Value::as_str).unwrap_or_default(),
                p.get("chapter_id")
                    .and_then(Value::as_str)
                    .unwrap_or_default(),
                p.get("section_id")
                    .and_then(Value::as_str)
                    .unwrap_or_default(),
            );
        }
    }

    // Strict priority order: lapsed > due > low_confidence > new (within daily limits)
    let mut reviews_pool = Vec::new();
    reviews_pool.extend(lapsed_items);
    reviews_pool.extend(due_items);
    reviews_pool.extend(low_conf_items);
    reviews_pool.truncate(daily_review_limit);
    new_items.truncate(daily_new_limit);

    let lapsed_count = reviews_pool
        .iter()
        .filter(|x| x.get("queue_category").and_then(Value::as_str) == Some("lapsed"))
        .count();
    let due_count = reviews_pool
        .iter()
        .filter(|x| x.get("queue_category").and_then(Value::as_str) == Some("due"))
        .count();
    let low_conf_count = reviews_pool
        .iter()
        .filter(|x| x.get("queue_category").and_then(Value::as_str) == Some("low_confidence"))
        .count();
    let new_count = new_items.len();

    let mut ordered_items = reviews_pool;
    ordered_items.extend(new_items);

    json!({
        "document_id": doc_id,
        "generated_at": now,
        "generated_at_iso": now_iso_local(),
        "daily_new_limit": daily_new_limit,
        "daily_review_limit": daily_review_limit,
        "total_items": ordered_items.len(),
        "counts": {
            "lapsed": lapsed_count,
            "due": due_count,
            "low_confidence": low_conf_count,
            "new": new_count,
        },
        "items": ordered_items,
    })
}

fn export_cornell_to_vault(
    project_root: &Path,
    study_dir: &Path,
    clean_id: &str,
    doc_id: &str,
) -> Result<(String, String), AppError> {
    let cornell_path = doc_modes_dir(study_dir, clean_id).join("cornell_notes.json");
    let cornell = read_json_value_or_default(study_dir, &cornell_path, Value::Null);
    if !cornell.is_object() {
        return Err(AppError::new(
            "CORNELL_NOT_FOUND",
            format!("Notas Cornell não encontradas para '{}'.", doc_id),
        ));
    }

    let raw_title = cornell
        .get("title")
        .and_then(Value::as_str)
        .filter(|s| !s.trim().is_empty())
        .unwrap_or(doc_id);
    let raw_subject = cornell
        .get("subject")
        .and_then(Value::as_str)
        .filter(|s| !s.trim().is_empty())
        .unwrap_or("Geral");
    let global_summary = cornell
        .get("global_summary")
        .and_then(Value::as_str)
        .unwrap_or_default();

    let clean_subj = sanitize_path_segment(raw_subject, "Geral");
    let clean_title = sanitize_path_segment(raw_title, clean_id);
    let now = Local::now();
    let date_str = now.format("%Y-%m-%d").to_string();

    let mut body = String::new();
    body.push_str(&format!("# Cornell Notes — {raw_title}\n\n"));
    if !global_summary.trim().is_empty() {
        body.push_str(&format!("## Sumário Global\n{global_summary}\n\n"));
    }

    if let Some(entries) = cornell.get("entries").and_then(Value::as_array) {
        for entry in entries {
            let sec_title = entry
                .get("section_title")
                .and_then(Value::as_str)
                .unwrap_or("Secção");
            let imp_badge = if entry
                .get("is_important")
                .and_then(Value::as_bool)
                .unwrap_or(false)
            {
                " [IMPORTANTE]"
            } else {
                ""
            };
            body.push_str(&format!("## {sec_title}{imp_badge}\n\n"));

            if let Some(cues) = entry.get("cue_column").and_then(Value::as_array) {
                if !cues.is_empty() {
                    body.push_str("### Coluna de Pistas (Cues)\n");
                    for c in cues {
                        let prompt = c
                            .get("cue_prompt")
                            .and_then(Value::as_str)
                            .unwrap_or_default();
                        let hint = c
                            .get("answer_hint")
                            .and_then(Value::as_str)
                            .unwrap_or_default();
                        if !prompt.is_empty() {
                            if hint.is_empty() {
                                body.push_str(&format!("- **{prompt}**\n"));
                            } else {
                                body.push_str(&format!("- **{prompt}** — _{hint}_\n"));
                            }
                        }
                    }
                    body.push('\n');
                }
            }

            if let Some(exps) = entry.get("explanations").and_then(Value::as_array) {
                if !exps.is_empty() {
                    body.push_str("### Notas Detalhadas\n");
                    for ex in exps {
                        if let Some(t) = ex.as_str() {
                            if !t.trim().is_empty() {
                                body.push_str(&format!("- {t}\n"));
                            }
                        }
                    }
                    body.push('\n');
                }
            }

            if let Some(det) = entry.get("supporting_details").and_then(Value::as_array) {
                if !det.is_empty() {
                    body.push_str("### Detalhes de Suporte\n");
                    for d in det {
                        if let Some(t) = d.as_str() {
                            if !t.trim().is_empty() {
                                body.push_str(&format!("- {t}\n"));
                            }
                        }
                    }
                    body.push('\n');
                }
            }

            if let Some(summary) = entry.get("summary_section").and_then(Value::as_str) {
                if !summary.trim().is_empty() {
                    body.push_str(&format!("### Síntese da Secção\n{summary}\n\n"));
                }
            }

            if let Some(p_notes) = entry.get("personal_notes").and_then(Value::as_array) {
                if !p_notes.is_empty() {
                    body.push_str("### Anotações Pessoais\n");
                    for pn in p_notes {
                        let content = pn
                            .get("content")
                            .and_then(Value::as_str)
                            .unwrap_or_default();
                        if !content.trim().is_empty() {
                            body.push_str(&format!("- {content}\n"));
                        }
                    }
                    body.push('\n');
                }
            }
        }
    }

    body.push_str(&format!(
        "## Ligações Semânticas (Knowledge Graph)\n- [[{clean_subj}]]: Domínio disciplinar.\n- [[{clean_title}]]: Nota Cornell de estudo.\n"
    ));

    let frontmatter = format!(
        "---\ntype: cornell_study_note\ndomain: academic\nstatus: VALIDATED\nsource_document_id: \"{doc_id}\"\nsource_title: \"{}\"\nsubject: \"{}\"\ndate: \"{date_str}\"\ntags:\n  - study-vault\n  - cornell-notes\n  - {}\n---\n\n",
        raw_title.replace('"', "'"),
        raw_subject.replace('"', "'"),
        clean_subj.to_ascii_lowercase().replace(' ', "-")
    );
    let full_markdown = format!("{frontmatter}{body}");

    let vault_root = resolve_vault_root(project_root)?;
    let dest_dir = vault_root.join("10 - Lectures").join(&clean_subj);
    fs::create_dir_all(&dest_dir).map_err(|err| {
        AppError::new(
            "VAULT_DIR_CREATE_FAILED",
            format!("Failed creating Obsidian Lecture directory: {err}"),
        )
    })?;
    let filename = format!("{date_str} - Cornell - {clean_title}.md");
    let dest_file = resolve_confined_path(&vault_root, &dest_dir.join(&filename))?;

    if dest_file.is_file() {
        if let Ok(existing) = fs::read_to_string(&dest_file) {
            let archive_dir = dest_dir.join(".archive");
            let _ = fs::create_dir_all(&archive_dir);
            let stem = dest_file
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("cornell");
            let archive_name = format!("{stem}_{}.md", now.format("%Y%m%d_%H%M%S"));
            let _ = atomic_write_string(&vault_root, &archive_dir.join(archive_name), &existing);
        }
    }

    let written_path = atomic_write_string(&vault_root, &dest_file, &full_markdown)?;
    let normalized_path = written_path.to_string_lossy().replace('\\', "/");
    Ok((normalized_path, full_markdown))
}

fn load_sessions_map(study_dir: &Path) -> BTreeMap<String, Value> {
    let sessions_path = global_state_dir(study_dir).join("study_sessions.json");
    let raw = read_json_value_or_default(study_dir, &sessions_path, json!({}));
    match raw {
        Value::Object(map) => map.into_iter().collect(),
        _ => BTreeMap::new(),
    }
}

fn save_sessions_map(study_dir: &Path, sessions: BTreeMap<String, Value>) -> Result<(), AppError> {
    let state_dir = global_state_dir(study_dir);
    fs::create_dir_all(&state_dir).map_err(|err| {
        AppError::new(
            "STUDY_MODES_DIR_FAILED",
            format!("Failed creating study_modes_state dir: {err}"),
        )
    })?;
    let sessions_path = state_dir.join("study_sessions.json");
    let obj: serde_json::Map<String, Value> = sessions.into_iter().collect();
    write_json_atomic(&state_dir, &sessions_path, &Value::Object(obj))
}

/// Executes deterministic Phase 6 `study_mode_*` routes natively on disk.
///
/// Returns `Ok(Some(events))` when handled in Rust or `Ok(None)` when LLM generation /
/// semantic grading must be executed by Python `StudyWorker`.
pub async fn try_execute_study_modes_fast_path(
    project_root: &Path,
    msg_type: &str,
    message: &Value,
) -> Result<Option<Vec<Value>>, AppError> {
    if !msg_type.starts_with("study_mode_") {
        return Ok(None);
    }

    let study_dir = study_storage_dir(project_root);

    match msg_type {
        "study_mode_get_readiness" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let readiness = compute_readiness_value(&study_dir, &clean_id, &doc_id);
            Ok(Some(vec![json!({
                "type": "study_mode_readiness_result",
                "document_id": doc_id,
                "readiness": readiness,
            })]))
        }

        "study_mode_get_flashcards" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let deck_path = doc_modes_dir(&study_dir, &clean_id).join("flashcards_deck.json");
            let deck = read_json_value_or_default(&study_dir, &deck_path, Value::Null);
            let raw_cards: Vec<Value> = deck
                .get("cards")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();
            let srs_states = load_srs_states_map(&study_dir);
            let cards = enrich_cards_with_srs(&raw_cards, &srs_states);
            let readiness = compute_readiness_value(&study_dir, &clean_id, &doc_id);
            Ok(Some(vec![json!({
                "type": "study_mode_flashcards_result",
                "document_id": doc_id,
                "deck": deck,
                "cards": cards,
                "readiness": readiness,
            })]))
        }

        "study_mode_create_flashcard" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let front = message
                .get("front")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let back = message
                .get("back")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            if front.is_empty() || back.is_empty() {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": "Frente e verso são obrigatórios para criar flashcard.",
                })]));
            }

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;

            let modes_dir = doc_modes_dir(&study_dir, &clean_id);
            fs::create_dir_all(&modes_dir).map_err(|err| {
                AppError::new(
                    "STUDY_MODES_DIR_FAILED",
                    format!("Failed creating study_modes dir: {err}"),
                )
            })?;
            let deck_path = modes_dir.join("flashcards_deck.json");
            let mut deck = read_json_value_or_default(
                &study_dir,
                &deck_path,
                json!({
                    "deck_id": format!("deck_{}", short_hex(8)),
                    "document_id": doc_id,
                    "cards": [],
                    "generation_mode": "USER_CUSTOM",
                    "status": "COMPLETED",
                }),
            );

            let card_id = format!("fc_{}", short_hex(10));
            let card = json!({
                "card_id": card_id,
                "document_id": doc_id,
                "front": front,
                "back": back,
                "card_type": message.get("card_type").and_then(Value::as_str).unwrap_or("CONCEPT"),
                "content_difficulty": message.get("content_difficulty").and_then(Value::as_str).unwrap_or("INTERMEDIATE"),
                "question_difficulty": message.get("question_difficulty").and_then(Value::as_str).unwrap_or("MEDIUM"),
                "chapter_id": message.get("chapter_id").and_then(Value::as_str).unwrap_or_default(),
                "section_id": message.get("section_id").and_then(Value::as_str).unwrap_or_default(),
                "topic": message.get("topic").and_then(Value::as_str).unwrap_or("Personalizado"),
                "generation_mode": "USER_CUSTOM",
                "user_edited": true,
                "created_at": now_iso_local(),
            });

            if let Some(obj) = deck.as_object_mut() {
                let cards_val = obj.entry("cards".to_string()).or_insert_with(|| json!([]));
                if let Some(arr) = cards_val.as_array_mut() {
                    arr.push(card.clone());
                }
            }
            write_json_atomic(&study_dir, &deck_path, &deck)?;

            Ok(Some(vec![json!({
                "type": "study_mode_flashcard_saved",
                "document_id": doc_id,
                "flashcard": card,
            })]))
        }

        "study_mode_edit_flashcard" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let card_id = message
                .get("card_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;

            let deck_path = doc_modes_dir(&study_dir, &clean_id).join("flashcards_deck.json");
            let mut deck = read_json_value_or_default(&study_dir, &deck_path, Value::Null);
            let mut updated_card: Option<Value> = None;

            if let Some(cards) = deck.get_mut("cards").and_then(Value::as_array_mut) {
                for card in cards.iter_mut() {
                    if card.get("card_id").and_then(Value::as_str) == Some(card_id.as_str()) {
                        if let Some(obj) = card.as_object_mut() {
                            for field in ["front", "back", "topic", "question_difficulty"] {
                                if let Some(v) = message.get(field).and_then(Value::as_str) {
                                    obj.insert(field.to_string(), json!(v.trim()));
                                }
                            }
                            obj.insert("user_edited".to_string(), json!(true));
                            obj.insert("updated_at".to_string(), json!(now_iso_local()));
                        }
                        updated_card = Some(card.clone());
                        break;
                    }
                }
            }

            let Some(saved) = updated_card else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Flashcard '{}' não encontrado em '{}'.", card_id, doc_id),
                })]));
            };

            write_json_atomic(&study_dir, &deck_path, &deck)?;
            Ok(Some(vec![json!({
                "type": "study_mode_flashcard_saved",
                "document_id": doc_id,
                "flashcard": saved,
            })]))
        }

        "study_mode_delete_flashcard" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let card_id = message
                .get("card_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;

            let deck_path = doc_modes_dir(&study_dir, &clean_id).join("flashcards_deck.json");
            let mut deck = read_json_value_or_default(&study_dir, &deck_path, Value::Null);
            let mut deleted = false;
            if let Some(cards) = deck.get_mut("cards").and_then(Value::as_array_mut) {
                let before = cards.len();
                cards
                    .retain(|c| c.get("card_id").and_then(Value::as_str) != Some(card_id.as_str()));
                deleted = cards.len() < before;
            }
            if deleted {
                write_json_atomic(&study_dir, &deck_path, &deck)?;
            }

            Ok(Some(vec![json!({
                "type": "study_mode_flashcard_deleted",
                "document_id": doc_id,
                "card_id": card_id,
                "deleted": deleted,
            })]))
        }

        "study_mode_review_flashcard" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let card_id = message
                .get("card_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let rating = message
                .get("rating")
                .and_then(Value::as_str)
                .unwrap_or("GOOD")
                .to_string();
            let confidence = message.get("confidence").and_then(Value::as_i64);

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;

            let deck_path = doc_modes_dir(&study_dir, &clean_id).join("flashcards_deck.json");
            let deck = read_json_value_or_default(&study_dir, &deck_path, Value::Null);
            let card = deck
                .get("cards")
                .and_then(Value::as_array)
                .and_then(|arr| {
                    arr.iter()
                        .find(|c| {
                            c.get("card_id").and_then(Value::as_str) == Some(card_id.as_str())
                        })
                        .cloned()
                })
                .unwrap_or_else(|| json!({ "card_id": card_id, "document_id": doc_id }));

            let diff = card
                .get("content_difficulty")
                .and_then(Value::as_str)
                .unwrap_or("INTERMEDIATE");
            let topic = card
                .get("topic")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let ch_id = card
                .get("chapter_id")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let sec_id = card
                .get("section_id")
                .and_then(Value::as_str)
                .unwrap_or_default();

            let (srs_state, _) = record_sm2_review(
                &study_dir,
                &doc_id,
                &card_id,
                "FLASHCARD",
                &rating,
                confidence,
                diff,
                topic,
                ch_id,
                sec_id,
            )?;
            let progress = recompute_learning_progress(&study_dir, &clean_id, &doc_id)?;
            let mut enriched_card = card;
            if let Some(obj) = enriched_card.as_object_mut() {
                obj.insert("srs".to_string(), srs_state.clone());
                obj.insert(
                    "srs_state".to_string(),
                    srs_state
                        .get("learning_state")
                        .cloned()
                        .unwrap_or_else(|| json!("LEARNING")),
                );
            }

            Ok(Some(vec![json!({
                "type": "study_mode_flashcard_reviewed",
                "document_id": doc_id,
                "flashcard": enriched_card,
                "srs_state": srs_state,
                "progress": progress,
            })]))
        }

        "study_mode_get_cornell" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let cornell_path = doc_modes_dir(&study_dir, &clean_id).join("cornell_notes.json");
            let cornell = read_json_value_or_default(&study_dir, &cornell_path, Value::Null);
            let readiness = compute_readiness_value(&study_dir, &clean_id, &doc_id);
            Ok(Some(vec![json!({
                "type": "study_mode_cornell_result",
                "document_id": doc_id,
                "cornell": cornell,
                "readiness": readiness,
            })]))
        }

        "study_mode_edit_cornell_entry" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let section_id = message
                .get("section_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;

            let cornell_path = doc_modes_dir(&study_dir, &clean_id).join("cornell_notes.json");
            let mut cornell = read_json_value_or_default(&study_dir, &cornell_path, Value::Null);
            let mut saved_entry: Option<Value> = None;

            if let Some(entries) = cornell.get_mut("entries").and_then(Value::as_array_mut) {
                for entry in entries.iter_mut() {
                    if entry.get("section_id").and_then(Value::as_str) == Some(section_id.as_str())
                    {
                        let mut edited_fields: BTreeSet<String> = entry
                            .get("edited_fields")
                            .and_then(Value::as_array)
                            .map(|a| {
                                a.iter()
                                    .filter_map(Value::as_str)
                                    .map(str::to_string)
                                    .collect()
                            })
                            .unwrap_or_default();

                        if let Some(obj) = entry.as_object_mut() {
                            for field in [
                                "summary_section",
                                "explanations",
                                "supporting_details",
                                "cue_column",
                                "is_important",
                            ] {
                                if let Some(val) = message.get(field) {
                                    if !val.is_null() {
                                        obj.insert(field.to_string(), val.clone());
                                        edited_fields.insert(field.to_string());
                                    }
                                }
                            }
                            obj.insert("user_edited".to_string(), json!(true));
                            obj.insert(
                                "edited_fields".to_string(),
                                json!(edited_fields.into_iter().collect::<Vec<_>>()),
                            );
                            obj.insert("updated_at".to_string(), json!(now_iso_local()));
                        }
                        saved_entry = Some(entry.clone());
                        break;
                    }
                }
            }

            let Some(entry_val) = saved_entry else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Secção Cornell '{}' não encontrada em '{}'.", section_id, doc_id),
                })]));
            };

            write_json_atomic(&study_dir, &cornell_path, &cornell)?;
            Ok(Some(vec![json!({
                "type": "study_mode_cornell_entry_saved",
                "document_id": doc_id,
                "entry": entry_val,
            })]))
        }

        "study_mode_add_cornell_note" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let section_id = message
                .get("section_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let content = message
                .get("content")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let is_important = message
                .get("is_important")
                .and_then(Value::as_bool)
                .unwrap_or(false);

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;

            let cornell_path = doc_modes_dir(&study_dir, &clean_id).join("cornell_notes.json");
            let mut cornell = read_json_value_or_default(&study_dir, &cornell_path, Value::Null);
            let personal_note = json!({
                "note_id": format!("note_{}", short_hex(8)),
                "content": content,
                "is_important": is_important,
                "created_at": now_iso_local(),
            });

            let mut matched = false;
            if let Some(entries) = cornell.get_mut("entries").and_then(Value::as_array_mut) {
                for entry in entries.iter_mut() {
                    if entry.get("section_id").and_then(Value::as_str) == Some(section_id.as_str())
                    {
                        if let Some(obj) = entry.as_object_mut() {
                            let notes = obj
                                .entry("personal_notes".to_string())
                                .or_insert_with(|| json!([]));
                            if let Some(arr) = notes.as_array_mut() {
                                arr.push(personal_note.clone());
                            }
                            if is_important {
                                obj.insert("is_important".to_string(), json!(true));
                            }
                        }
                        matched = true;
                        break;
                    }
                }
            }

            if !matched {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Secção Cornell '{}' não encontrada.", section_id),
                })]));
            }

            write_json_atomic(&study_dir, &cornell_path, &cornell)?;
            Ok(Some(vec![json!({
                "type": "study_mode_cornell_note_saved",
                "document_id": doc_id,
                "section_id": section_id,
                "personal_note": personal_note,
            })]))
        }

        "study_mode_export_cornell_vault" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;

            match export_cornell_to_vault(project_root, &study_dir, &clean_id, &doc_id) {
                Ok((vault_path, markdown)) => Ok(Some(vec![json!({
                    "type": "study_mode_cornell_exported",
                    "document_id": doc_id,
                    "vault_path": vault_path,
                    "markdown": markdown,
                })])),
                Err(err) => Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": err.message,
                })])),
            }
        }

        "study_mode_get_assessments" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let assess_path = doc_modes_dir(&study_dir, &clean_id).join("assessments.json");
            let assessments = match read_json_value_or_default(&study_dir, &assess_path, json!([]))
            {
                Value::Array(arr) => arr,
                _ => Vec::new(),
            };
            let hist_path = global_state_dir(&study_dir).join("assessment_attempts.json");
            let history: Vec<Value> =
                match read_json_value_or_default(&study_dir, &hist_path, json!([])) {
                    Value::Array(arr) => arr
                        .into_iter()
                        .filter(|a| {
                            a.get("document_id").and_then(Value::as_str) == Some(doc_id.as_str())
                        })
                        .collect(),
                    _ => Vec::new(),
                };
            let readiness = compute_readiness_value(&study_dir, &clean_id, &doc_id);
            Ok(Some(vec![json!({
                "type": "study_mode_assessments_result",
                "document_id": doc_id,
                "assessments": assessments,
                "history": history,
                "readiness": readiness,
            })]))
        }

        "study_mode_get_active_recall" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let recall_path = doc_modes_dir(&study_dir, &clean_id).join("active_recall.json");
            let deck = read_json_value_or_default(&study_dir, &recall_path, Value::Null);
            let prompts = deck
                .get("prompts")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();
            let hist_path = global_state_dir(&study_dir).join("active_recall_attempts.json");
            let history: Vec<Value> =
                match read_json_value_or_default(&study_dir, &hist_path, json!([])) {
                    Value::Array(arr) => arr
                        .into_iter()
                        .filter(|a| {
                            a.get("document_id").and_then(Value::as_str) == Some(doc_id.as_str())
                        })
                        .collect(),
                    _ => Vec::new(),
                };
            let readiness = compute_readiness_value(&study_dir, &clean_id, &doc_id);
            Ok(Some(vec![json!({
                "type": "study_mode_active_recall_result",
                "document_id": doc_id,
                "prompts": prompts,
                "history": history,
                "readiness": readiness,
            })]))
        }

        "study_mode_get_daily_queue" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let daily_new = message
                .get("daily_new_limit")
                .and_then(Value::as_u64)
                .unwrap_or(15)
                .clamp(1, 200) as usize;
            let daily_review = message
                .get("daily_review_limit")
                .and_then(Value::as_u64)
                .unwrap_or(40)
                .clamp(1, 400) as usize;
            let queue = build_daily_queue(&study_dir, &clean_id, &doc_id, daily_new, daily_review);
            Ok(Some(vec![json!({
                "type": "study_mode_daily_queue_result",
                "document_id": doc_id,
                "queue": queue,
            })]))
        }

        "study_mode_get_progress" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let recompute = message
                .get("recompute")
                .and_then(Value::as_bool)
                .unwrap_or(false);

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;

            let prog_path = global_state_dir(&study_dir).join("learning_progress.json");
            let cached = read_json_value_or_default(&study_dir, &prog_path, json!({}));
            let progress = if !recompute {
                if let Some(existing) = cached.get(doc_id.as_str()).filter(|v| v.is_object()) {
                    existing.clone()
                } else {
                    recompute_learning_progress(&study_dir, &clean_id, &doc_id)?
                }
            } else {
                recompute_learning_progress(&study_dir, &clean_id, &doc_id)?
            };

            Ok(Some(vec![json!({
                "type": "study_mode_progress_result",
                "document_id": doc_id,
                "progress": progress,
            })]))
        }

        "study_mode_start_session" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let _clean_id = validate_study_id(&doc_id, "document_id")?;
            let mode = message
                .get("mode")
                .and_then(Value::as_str)
                .unwrap_or("FLASHCARD_REVIEW")
                .to_string();
            let title = message
                .get("title")
                .and_then(Value::as_str)
                .unwrap_or("Sessão de Estudo")
                .to_string();

            let mut items: Vec<Value> = message
                .get("items")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();
            let mut item_ids: Vec<String> = message
                .get("item_ids")
                .and_then(Value::as_array)
                .map(|arr| {
                    arr.iter()
                        .filter_map(Value::as_str)
                        .map(str::to_string)
                        .collect()
                })
                .unwrap_or_default();
            if items.is_empty() && !item_ids.is_empty() {
                items = item_ids
                    .iter()
                    .map(|id| json!({ "item_id": id, "item_type": "FLASHCARD" }))
                    .collect();
            } else if item_ids.is_empty() && !items.is_empty() {
                item_ids = items
                    .iter()
                    .filter_map(|it| {
                        it.get("item_id")
                            .and_then(Value::as_str)
                            .map(str::to_string)
                    })
                    .collect();
            }

            let session_id = format!("sess_{}", short_hex(12));
            let now = now_iso_local();
            let session = json!({
                "session_id": session_id,
                "document_id": doc_id,
                "mode": mode,
                "status": "IN_PROGRESS",
                "title": title,
                "items": items,
                "item_ids": item_ids,
                "current_index": 0,
                "completed_item_ids": [],
                "partial_responses": {},
                "item_outcomes": [],
                "config": message.get("config").cloned().unwrap_or_else(|| json!({})),
                "summary_stats": {},
                "started_at": now,
                "last_activity_at": now,
                "paused_at": Value::Null,
                "completed_at": Value::Null,
            });

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;
            let mut sessions = load_sessions_map(&study_dir);
            sessions.insert(session_id, session.clone());
            save_sessions_map(&study_dir, sessions)?;

            Ok(Some(vec![json!({
                "type": "study_mode_session_updated",
                "document_id": doc_id,
                "session": session,
            })]))
        }

        "study_mode_update_session" => {
            let session_id = message
                .get("session_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;
            let mut sessions = load_sessions_map(&study_dir);
            let Some(session) = sessions.get_mut(&session_id) else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Sessão de estudo '{}' não encontrada.", session_id),
                })]));
            };

            if let Some(obj) = session.as_object_mut() {
                let item_id = message
                    .get("item_id")
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .filter(|s| !s.is_empty());

                if let (Some(iid), Some(partial)) = (item_id, message.get("partial_response")) {
                    if !partial.is_null() {
                        let map = obj
                            .entry("partial_responses".to_string())
                            .or_insert_with(|| json!({}));
                        if let Some(m) = map.as_object_mut() {
                            m.insert(iid.to_string(), partial.clone());
                        }
                    }
                }
                if let Some(outcome) = message.get("outcome") {
                    if !outcome.is_null() {
                        let arr = obj
                            .entry("item_outcomes".to_string())
                            .or_insert_with(|| json!([]));
                        if let Some(list) = arr.as_array_mut() {
                            list.push(outcome.clone());
                        }
                    }
                }
                if message
                    .get("mark_completed")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
                {
                    if let Some(iid) = item_id {
                        let arr = obj
                            .entry("completed_item_ids".to_string())
                            .or_insert_with(|| json!([]));
                        if let Some(list) = arr.as_array_mut() {
                            if !list.iter().any(|x| x.as_str() == Some(iid)) {
                                list.push(json!(iid));
                            }
                        }
                    }
                }
                if let Some(next_idx) = message.get("next_index").and_then(Value::as_u64) {
                    obj.insert("current_index".to_string(), json!(next_idx));
                }
                obj.insert("last_activity_at".to_string(), json!(now_iso_local()));
            }

            let updated = session.clone();
            let doc_id = updated
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();
            save_sessions_map(&study_dir, sessions)?;

            Ok(Some(vec![json!({
                "type": "study_mode_session_updated",
                "document_id": doc_id,
                "session": updated,
            })]))
        }

        "study_mode_pause_session"
        | "study_mode_resume_session"
        | "study_mode_complete_session" => {
            let session_id = message
                .get("session_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();

            let lock = lock_for_root(project_root);
            let _guard = lock.lock().await;
            let mut sessions = load_sessions_map(&study_dir);
            let Some(session) = sessions.get_mut(&session_id) else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Sessão de estudo '{}' não encontrada.", session_id),
                })]));
            };

            let now = now_iso_local();
            if let Some(obj) = session.as_object_mut() {
                match msg_type {
                    "study_mode_pause_session" => {
                        obj.insert("status".to_string(), json!("PAUSED"));
                        obj.insert("paused_at".to_string(), json!(now));
                    }
                    "study_mode_resume_session" => {
                        obj.insert("status".to_string(), json!("IN_PROGRESS"));
                        obj.insert("paused_at".to_string(), Value::Null);
                    }
                    _ => {
                        obj.insert("status".to_string(), json!("COMPLETED"));
                        obj.insert("completed_at".to_string(), json!(now));
                        if let Some(stats) = message.get("summary_stats").filter(|v| v.is_object())
                        {
                            obj.insert("summary_stats".to_string(), stats.clone());
                        }
                    }
                }
                obj.insert("last_activity_at".to_string(), json!(now_iso_local()));
            }

            let updated = session.clone();
            let doc_id = updated
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .to_string();
            save_sessions_map(&study_dir, sessions)?;

            Ok(Some(vec![json!({
                "type": "study_mode_session_updated",
                "document_id": doc_id,
                "session": updated,
            })]))
        }

        "study_mode_list_sessions" => {
            let doc_filter = message.get("document_id").and_then(Value::as_str);
            let status_filter = message.get("status").and_then(Value::as_str);
            let mut sessions: Vec<Value> = load_sessions_map(&study_dir)
                .into_values()
                .filter(|s| {
                    doc_filter.map_or(true, |df| {
                        s.get("document_id").and_then(Value::as_str) == Some(df)
                    }) && status_filter.map_or(true, |sf| {
                        s.get("status").and_then(Value::as_str) == Some(sf)
                    })
                })
                .collect();
            sessions.sort_by(|a, b| {
                let ta = a
                    .get("last_activity_at")
                    .and_then(Value::as_str)
                    .unwrap_or_default();
                let tb = b
                    .get("last_activity_at")
                    .and_then(Value::as_str)
                    .unwrap_or_default();
                tb.cmp(ta)
            });

            Ok(Some(vec![json!({
                "type": "study_mode_sessions_list",
                "document_id": doc_filter,
                "sessions": sessions,
            })]))
        }

        // LLM synthesis/evaluation handlers stay on StudyWorker.
        _ => Ok(None),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[tokio::test]
    async fn sm2_v6_review_queue_progress_and_sessions_work_end_to_end() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();
        let study_dir = study_storage_dir(&root);
        let doc_dir = study_dir.join("documents").join("doc_p6");
        let modes_dir = doc_modes_dir(&study_dir, "doc_p6");
        fs::create_dir_all(&modes_dir).unwrap();

        fs::write(doc_dir.join("ast.json"), "{}").unwrap();
        fs::write(
            doc_dir.join("reasoning_dossier.json"),
            r#"{"dossier_id":"dos_p6","source_sha256":"sha_p6"}"#,
        )
        .unwrap();
        fs::write(
            doc_dir.join("editorial_study_plan.json"),
            r#"{"metadata":{"plan_id":"plan_p6","source_sha256":"sha_p6"}}"#,
        )
        .unwrap();

        let readiness = try_execute_study_modes_fast_path(
            &root,
            "study_mode_get_readiness",
            &json!({"document_id": "doc_p6"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(readiness[0]["readiness"]["is_ready"], true);

        let created = try_execute_study_modes_fast_path(
            &root,
            "study_mode_create_flashcard",
            &json!({
                "document_id": "doc_p6",
                "front": "What is entropy?",
                "back": "Measure of disorder",
                "topic": "Thermodynamics",
                "chapter_id": "ch_1"
            }),
        )
        .await
        .unwrap()
        .unwrap();
        let card_id = created[0]["flashcard"]["card_id"]
            .as_str()
            .unwrap()
            .to_string();

        // Review twice GOOD -> interval should advance 1.0 -> 6.0 days under SM-2 v6.0
        let r1 = try_execute_study_modes_fast_path(
            &root,
            "study_mode_review_flashcard",
            &json!({"document_id": "doc_p6", "card_id": card_id, "rating": "GOOD", "confidence": 4}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(r1[0]["srs_state"]["interval_days"], 1.0);
        assert_eq!(r1[0]["srs_state"]["consecutive_success"], 1);

        let r2 = try_execute_study_modes_fast_path(
            &root,
            "study_mode_review_flashcard",
            &json!({"document_id": "doc_p6", "card_id": card_id, "rating": "GOOD", "confidence": 5}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(r2[0]["srs_state"]["interval_days"], 6.0);
        assert_eq!(r2[0]["srs_state"]["consecutive_success"], 2);
        assert_eq!(r2[0]["progress"]["reviewed_cards"], 1);

        // Session lifecycle start -> update -> pause -> resume -> complete -> list
        let started = try_execute_study_modes_fast_path(
            &root,
            "study_mode_start_session",
            &json!({
                "document_id": "doc_p6",
                "mode": "FLASHCARD_REVIEW",
                "item_ids": [card_id],
            }),
        )
        .await
        .unwrap()
        .unwrap();
        let session_id = started[0]["session"]["session_id"]
            .as_str()
            .unwrap()
            .to_string();

        let paused = try_execute_study_modes_fast_path(
            &root,
            "study_mode_pause_session",
            &json!({"session_id": session_id}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(paused[0]["session"]["status"], "PAUSED");

        let resumed = try_execute_study_modes_fast_path(
            &root,
            "study_mode_resume_session",
            &json!({"session_id": session_id}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(resumed[0]["session"]["status"], "IN_PROGRESS");

        let completed = try_execute_study_modes_fast_path(
            &root,
            "study_mode_complete_session",
            &json!({"session_id": session_id, "summary_stats": {"reviewed": 1}}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(completed[0]["session"]["status"], "COMPLETED");

        let listed = try_execute_study_modes_fast_path(
            &root,
            "study_mode_list_sessions",
            &json!({"document_id": "doc_p6", "status": "COMPLETED"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(listed[0]["sessions"].as_array().unwrap().len(), 1);
    }

    #[tokio::test]
    async fn cornell_edit_note_and_obsidian_vault_export_work() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();
        let study_dir = study_storage_dir(&root);
        let modes_dir = doc_modes_dir(&study_dir, "doc_cn");
        fs::create_dir_all(&modes_dir).unwrap();
        fs::create_dir_all(root.join("obsidian_vault")).unwrap();

        fs::write(
            modes_dir.join("cornell_notes.json"),
            json!({
                "cornell_id": "cn_1",
                "document_id": "doc_cn",
                "title": "Física Moderna",
                "subject": "Física",
                "global_summary": "Resumo inicial",
                "entries": [{
                    "entry_id": "cn_s1",
                    "section_id": "sec_1",
                    "section_title": "Relatividade Restrita",
                    "summary_section": "Original",
                    "explanations": ["Dilatação temporal"],
                    "cue_column": [{"cue_prompt": "O que varia?", "answer_hint": "Tempo próprio"}],
                    "personal_notes": []
                }]
            })
            .to_string(),
        )
        .unwrap();

        let edited = try_execute_study_modes_fast_path(
            &root,
            "study_mode_edit_cornell_entry",
            &json!({
                "document_id": "doc_cn",
                "section_id": "sec_1",
                "summary_section": "Editado pelo estudante",
                "is_important": true
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(
            edited[0]["entry"]["summary_section"],
            "Editado pelo estudante"
        );
        assert_eq!(edited[0]["entry"]["user_edited"], true);

        let note = try_execute_study_modes_fast_path(
            &root,
            "study_mode_add_cornell_note",
            &json!({
                "document_id": "doc_cn",
                "section_id": "sec_1",
                "content": "Rever fator de Lorentz",
                "is_important": true
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(
            note[0]["personal_note"]["content"],
            "Rever fator de Lorentz"
        );

        let exported = try_execute_study_modes_fast_path(
            &root,
            "study_mode_export_cornell_vault",
            &json!({"document_id": "doc_cn"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(exported[0]["type"], "study_mode_cornell_exported");
        let vault_path = exported[0]["vault_path"].as_str().unwrap();
        assert!(Path::new(vault_path).is_file());
        assert!(exported[0]["markdown"]
            .as_str()
            .unwrap()
            .contains("Editado pelo estudante"));
    }
}

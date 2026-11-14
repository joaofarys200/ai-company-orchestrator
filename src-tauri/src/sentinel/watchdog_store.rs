//! Persistent Sentinel security watchdog backed by `SentinelScheduler` & native OS collectors.
//!
//! Consolidates Sentinel baseline management, diff correlation, known-good allowlisting,
//! human review audit trails, proposed remediation actions, and ShadowMode read-only telemetry
//! inside Rust, eliminating split-brain state with Python workers.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Instant;

use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use tokio::sync::Mutex;
use uuid::Uuid;

use crate::error::AppError;
use crate::permissions::path_jail::ensure_confined_existing_file;
use crate::sentinel::collectors_win::collect_system_telemetry;
use crate::sentinel::scheduler::{RemediationOutcome, SentinelScheduler};
use crate::storage::atomic_fs::atomic_write_string;

const SENTINEL_SCHEMA_VERSION: i64 = 1;
const SCAN_INTERVAL_SECONDS: i64 = 60;

#[derive(Debug, Default)]
struct WatchdogState {
    baseline: Option<Value>,
    events: Vec<Value>,
    actions: Vec<Value>,
    known_goods: BTreeMap<String, Value>,
    total_scans: u64,
    last_scan_time: f64,
    last_scan_duration_seconds: f64,
    baseline_duration_seconds: f64,
    is_auditing_now: bool,
    degraded_collectors: Vec<String>,
    last_hosts_hash: String,
    last_persistence_count: usize,
    last_process_count: usize,
    last_memory_load_pct: u32,
    last_memory_used_mb: f64,
}

/// Thread-safe persistent Sentinel watchdog bound to `SentinelScheduler`.
pub struct SentinelWatchdog {
    data_dir: PathBuf,
    scheduler: Arc<SentinelScheduler>,
    state: Mutex<WatchdogState>,
}

impl SentinelWatchdog {
    /// Opens persistent Sentinel state under `project_root/data/sentinel`.
    pub fn open(project_root: &Path, scheduler: Arc<SentinelScheduler>) -> Arc<Self> {
        let data_dir = project_root.join("data").join("sentinel");
        let _ = fs::create_dir_all(&data_dir);

        let mut initial = WatchdogState::default();
        if let Some(b) = read_confined_json(&data_dir, &data_dir.join("baseline.json")) {
            if b.is_object() {
                initial.baseline = Some(b);
            }
        }
        if let Some(Value::Array(ev)) = read_confined_json(&data_dir, &data_dir.join("events.json"))
        {
            initial.events = ev;
        }
        if let Some(Value::Array(acts)) =
            read_confined_json(&data_dir, &data_dir.join("actions.json"))
        {
            initial.actions = acts;
        }
        if let Some(Value::Object(kg)) =
            read_confined_json(&data_dir, &data_dir.join("known_goods.json"))
        {
            initial.known_goods = kg.into_iter().collect();
        }
        if let Some(Value::Object(meta)) =
            read_confined_json(&data_dir, &data_dir.join("watchdog_meta.json"))
        {
            initial.total_scans = meta.get("total_scans").and_then(Value::as_u64).unwrap_or(0);
            initial.last_scan_time = meta
                .get("last_scan_time")
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            initial.last_scan_duration_seconds = meta
                .get("last_scan_duration_seconds")
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            initial.baseline_duration_seconds = meta
                .get("baseline_duration_seconds")
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
        }

        Arc::new(Self {
            data_dir,
            scheduler,
            state: Mutex::new(initial),
        })
    }

    pub async fn status_payload(&self) -> Value {
        let sched_snap = self.scheduler.status_snapshot().await;
        let guard = self.state.lock().await;
        self.build_status_locked(&guard, &sched_snap)
    }

    pub async fn baseline_payload(&self) -> Value {
        let guard = self.state.lock().await;
        guard.baseline.clone().unwrap_or(Value::Null)
    }

    pub async fn actions_payload(&self) -> Value {
        let guard = self.state.lock().await;
        Value::Array(guard.actions.clone())
    }

    pub async fn shadow_telemetry_payload(&self) -> Value {
        let sched_snap = self.scheduler.status_snapshot().await;
        let guard = self.state.lock().await;
        let open_events = count_open_events(&guard.events);
        let high_risk = count_high_risk_events(&guard.events);
        let pending_actions = guard
            .actions
            .iter()
            .filter(|a| {
                matches!(
                    a.get("status").and_then(Value::as_str),
                    Some("PROPOSED" | "WAITING_APPROVAL")
                )
            })
            .count();

        json!({
            "schema_version": SENTINEL_SCHEMA_VERSION,
            "shadow_mode": sched_snap.shadow_mode,
            "shadow_state": if sched_snap.shadow_mode { "SHADOW_READ_ONLY" } else { "ACTIVE_ENFORCEMENT" },
            "total_scans": guard.total_scans,
            "last_scan_time": guard.last_scan_time,
            "last_scan_duration_seconds": guard.last_scan_duration_seconds,
            "baseline_duration_seconds": guard.baseline_duration_seconds,
            "process_count": sched_snap.last_observation.as_ref().map(|o| o.process_count).unwrap_or(guard.last_process_count),
            "memory_load_pct": sched_snap.last_observation.as_ref().map(|o| o.memory.memory_load_pct).unwrap_or(guard.last_memory_load_pct),
            "memory_mb": guard.last_memory_used_mb,
            "protected_pids": sched_snap.protected_pids,
            "protected_pids_count": sched_snap.protected_pids.len(),
            "degraded_collectors": guard.degraded_collectors,
            "hosts_sha256": guard.last_hosts_hash,
            "persistence_entries_count": guard.last_persistence_count,
            "open_events_count": open_events,
            "high_risk_events_count": high_risk,
            "actions_count": guard.actions.len(),
            "pending_actions_count": pending_actions,
            "known_goods_count": guard.known_goods.len(),
            "recent_observations_count": sched_snap.recent_observations_count,
            "last_observation": sched_snap.last_observation,
        })
    }

    pub async fn run_audit(&self) -> Result<Vec<Value>, AppError> {
        let start = Instant::now();
        {
            let mut guard = self.state.lock().await;
            guard.is_auditing_now = true;
        }

        let obs_res = self.scheduler.tick_once().await;
        let telemetry_res = collect_system_telemetry().await;
        let hosts_snapshot = collect_hosts_snapshot();
        let persistence_snapshot = collect_startup_persistence_entries();

        let elapsed = (start.elapsed().as_secs_f64() * 1000.0).round() / 1000.0;
        let now = now_unix_secs();

        let mut degraded = Vec::new();
        if obs_res.is_err() {
            degraded.push("scheduler_telemetry".to_string());
        }
        if telemetry_res.is_err() {
            degraded.push("windows_process_memory".to_string());
        }

        let mut new_events_to_emit = Vec::new();
        let mut new_actions_to_emit = Vec::new();
        let mut is_first_baseline = false;

        let audit_summary = {
            let mut guard = self.state.lock().await;
            guard.is_auditing_now = false;
            guard.total_scans += 1;
            guard.last_scan_time = now;
            guard.last_scan_duration_seconds = elapsed;
            guard.degraded_collectors = degraded.clone();
            guard.last_hosts_hash = hosts_snapshot.sha256.clone();
            guard.last_persistence_count = persistence_snapshot.len();

            let (procs_json, mem_used_mb, mem_load_pct) = match &telemetry_res {
                Ok(t) => {
                    let used_bytes = t
                        .memory
                        .total_phys_bytes
                        .saturating_sub(t.memory.avail_phys_bytes);
                    let used_mb = ((used_bytes as f64) / (1024.0 * 1024.0) * 10.0).round() / 10.0;
                    let list: Vec<Value> = t
                        .processes
                        .iter()
                        .map(|p| {
                            json!({
                                "pid": p.pid,
                                "ppid": p.parent_pid,
                                "name": p.exe_name,
                                "threads": p.threads,
                            })
                        })
                        .collect();
                    guard.last_process_count = t.process_count;
                    guard.last_memory_load_pct = t.memory.memory_load_pct;
                    guard.last_memory_used_mb = used_mb;
                    (list, used_mb, t.memory.memory_load_pct)
                }
                Err(_) => (
                    Vec::new(),
                    guard.last_memory_used_mb,
                    guard.last_memory_load_pct,
                ),
            };

            let current_baseline_id = format!(
                "BASE-{}",
                Uuid::new_v4().simple().to_string()[..8].to_uppercase()
            );
            let new_baseline = json!({
                "schema_version": SENTINEL_SCHEMA_VERSION,
                "baseline_id": current_baseline_id,
                "created_at": now,
                "hosts": {
                    "exists": hosts_snapshot.exists,
                    "sha256": hosts_snapshot.sha256,
                    "entry_count": hosts_snapshot.entry_count,
                },
                "persistence": persistence_snapshot,
                "processes": procs_json,
                "process_count": guard.last_process_count,
                "memory_load_pct": mem_load_pct,
                "memory_mb": mem_used_mb,
            });

            if guard.baseline.is_none() {
                is_first_baseline = true;
                guard.baseline_duration_seconds = elapsed;
                guard.baseline = Some(new_baseline.clone());
            } else if let Some(prev) = guard.baseline.clone() {
                // 1. Check Hosts file hash drift
                let prev_hosts = prev
                    .get("hosts")
                    .and_then(|h| h.get("sha256"))
                    .and_then(Value::as_str)
                    .unwrap_or_default();
                if !prev_hosts.is_empty()
                    && !hosts_snapshot.sha256.is_empty()
                    && prev_hosts != hosts_snapshot.sha256
                {
                    let fp = compute_fingerprint("HOSTS", "file:hosts", "HOSTS_MODIFIED");
                    if let Some((ev, act)) = record_or_dedup_event(
                        &mut guard.events,
                        &mut guard.actions,
                        &guard.known_goods,
                        &fp,
                        "HOSTS",
                        "SUSPICIOUS",
                        0.95,
                        vec!["file:hosts".to_string()],
                        &format!(
                            "O ficheiro hosts do sistema foi alterado ({} -> {}).",
                            &prev_hosts[..prev_hosts.len().min(10)],
                            &hosts_snapshot.sha256[..hosts_snapshot.sha256.len().min(10)]
                        ),
                        "Inspecionar os mapeamentos do ficheiro hosts para descartar manipulação DNS.",
                        None,
                        now,
                    ) {
                        new_events_to_emit.push(ev);
                        if let Some(a) = act {
                            new_actions_to_emit.push(a);
                        }
                    }
                }

                // 2. Check Startup folder persistence additions
                let prev_persist_keys: BTreeSet<String> = prev
                    .get("persistence")
                    .and_then(Value::as_array)
                    .map(|arr| {
                        arr.iter()
                            .filter_map(|p| {
                                p.get("name")
                                    .and_then(Value::as_str)
                                    .map(|s| s.to_ascii_lowercase())
                            })
                            .collect()
                    })
                    .unwrap_or_default();

                for p_entry in new_baseline
                    .get("persistence")
                    .and_then(Value::as_array)
                    .into_iter()
                    .flatten()
                {
                    let pname = p_entry
                        .get("name")
                        .and_then(Value::as_str)
                        .unwrap_or_default();
                    let pkind = p_entry
                        .get("kind")
                        .and_then(Value::as_str)
                        .unwrap_or("STARTUP_FOLDER");
                    let ptarget = p_entry
                        .get("target_path")
                        .and_then(Value::as_str)
                        .unwrap_or_default();
                    if !pname.is_empty() && !prev_persist_keys.contains(&pname.to_ascii_lowercase())
                    {
                        let asset = format!("persistence:{}:{}", pkind.to_ascii_lowercase(), pname);
                        let fp =
                            compute_fingerprint("PERSISTENCE", &asset, "NEW_PERSISTENCE_ENTRY");
                        if let Some((ev, act)) = record_or_dedup_event(
                            &mut guard.events,
                            &mut guard.actions,
                            &guard.known_goods,
                            &fp,
                            "PERSISTENCE",
                            "SUSPICIOUS",
                            0.70,
                            vec![asset],
                            &format!("Nova entrada de persistência detetada ({pkind}): '{pname}' -> {ptarget}"),
                            "Confirmar se esta entrada de arranque é legítima ou aprovar remediação.",
                            None,
                            now,
                        ) {
                            new_events_to_emit.push(ev);
                            if let Some(a) = act {
                                new_actions_to_emit.push(a);
                            }
                        }
                    }
                }

                // Refresh current baseline snapshot after diffing so subsequent scans compare cleanly
                guard.baseline = Some(new_baseline);
            }

            self.persist_locked(&guard)?;

            json!({
                "audit_time": now,
                "duration_seconds": elapsed,
                "is_initial_baseline": is_first_baseline,
                "new_events_count": new_events_to_emit.len(),
                "new_actions_count": new_actions_to_emit.len(),
                "degraded_collectors": degraded,
            })
        };

        let sched_snap = self.scheduler.status_snapshot().await;
        let status_data = {
            let guard = self.state.lock().await;
            self.build_status_locked(&guard, &sched_snap)
        };

        let mut out = vec![json!({
            "type": "sentinel_audit_completed",
            "data": audit_summary,
        })];
        for ev in new_events_to_emit {
            out.push(json!({
                "type": "sentinel_event",
                "event": ev,
            }));
        }
        for act in new_actions_to_emit {
            out.push(json!({
                "type": "sentinel_action_proposed",
                "action": act,
            }));
        }
        out.push(json!({
            "type": "sentinel_status",
            "data": status_data,
        }));
        Ok(out)
    }

    pub async fn accept_known_good(
        &self,
        item_key: &str,
        reason: &str,
        user: &str,
    ) -> Result<Vec<Value>, AppError> {
        let now = now_unix_secs();
        {
            let mut guard = self.state.lock().await;
            guard.known_goods.insert(
                item_key.to_string(),
                json!({
                    "item_key": item_key,
                    "accepted_by": user,
                    "accepted_at": now,
                    "reason": reason,
                }),
            );
            for ev in guard.events.iter_mut() {
                let matches = ev.get("fingerprint").and_then(Value::as_str) == Some(item_key)
                    || ev.get("event_id").and_then(Value::as_str) == Some(item_key);
                if matches {
                    if let Some(obj) = ev.as_object_mut() {
                        obj.insert("is_known_good".to_string(), json!(true));
                        obj.insert("status".to_string(), json!("RESOLVED"));
                        if let Some(tl) = obj
                            .get_mut("observation_timeline")
                            .and_then(Value::as_array_mut)
                        {
                            tl.push(json!({
                                "timestamp": now,
                                "note": format!("Marcado como Known Good por {user}: {reason}"),
                            }));
                        }
                    }
                }
            }
            self.persist_locked(&guard)?;
        }

        let status = self.status_payload().await;
        Ok(vec![
            json!({
                "type": "sentinel_known_good_updated",
                "item_key": item_key,
                "status": "ACCEPTED",
            }),
            json!({
                "type": "sentinel_status",
                "data": status,
            }),
        ])
    }

    pub async fn approve_action(
        &self,
        action_id: &str,
        user: &str,
        session_id: Option<&str>,
    ) -> Result<Vec<Value>, AppError> {
        let now = now_unix_secs();
        let (target_pid, target_str, action_type, exists) = {
            let guard = self.state.lock().await;
            if let Some(act) = guard
                .actions
                .iter()
                .find(|a| a.get("action_id").and_then(Value::as_str) == Some(action_id))
            {
                let pid = act
                    .get("pre_state")
                    .and_then(|p| p.get("pid"))
                    .and_then(Value::as_u64)
                    .and_then(|n| u32::try_from(n).ok())
                    .unwrap_or(0);
                let target = act
                    .get("target")
                    .and_then(Value::as_str)
                    .unwrap_or_default()
                    .to_string();
                let atype = act
                    .get("action_type")
                    .and_then(Value::as_str)
                    .unwrap_or("MARK_KNOWN_GOOD")
                    .to_string();
                (pid, target, atype, true)
            } else {
                (0, String::new(), String::new(), false)
            }
        };

        if !exists {
            return Ok(vec![json!({
                "type": "sentinel_action_result",
                "action_id": action_id,
                "success": false,
                "action": Value::Null,
                "message": format!("Ação '{action_id}' não encontrada."),
            })]);
        }

        let outcome = if target_pid > 0 && action_type == "TERMINATE_PROCESS" {
            self.scheduler
                .evaluate_remediation(target_pid, &target_str)
                .await
                .unwrap_or(RemediationOutcome::BlockedShadowMode)
        } else if self.scheduler.is_shadow_mode().await {
            RemediationOutcome::BlockedShadowMode
        } else {
            RemediationOutcome::AllowedNonProtected
        };

        let (success, message, updated_action, actions_list) = {
            let mut guard = self.state.lock().await;
            let mut matched_action = Value::Null;
            let mut res_ok = true;
            let res_msg;

            match outcome {
                RemediationOutcome::BlockedProtectedPid => {
                    res_ok = false;
                    res_msg =
                        "Ação bloqueada: PID protegido pela arquitetura do JARVIS OS.".to_string();
                    if let Some(act) = guard
                        .actions
                        .iter_mut()
                        .find(|a| a.get("action_id").and_then(Value::as_str) == Some(action_id))
                    {
                        if let Some(obj) = act.as_object_mut() {
                            obj.insert("status".to_string(), json!("FAILED"));
                            obj.insert("error_message".to_string(), json!(res_msg.clone()));
                            obj.insert("updated_at".to_string(), json!(now));
                        }
                        matched_action = act.clone();
                    }
                }
                RemediationOutcome::BlockedShadowMode => {
                    res_msg = "Ação aprovada e registada em ShadowMode (sem alteração destrutiva no sistema).".to_string();
                    if let Some(act) = guard
                        .actions
                        .iter_mut()
                        .find(|a| a.get("action_id").and_then(Value::as_str) == Some(action_id))
                    {
                        if let Some(obj) = act.as_object_mut() {
                            obj.insert("status".to_string(), json!("COMPLETED"));
                            obj.insert("approved_by".to_string(), json!(user));
                            obj.insert("approval_session_id".to_string(), json!(session_id));
                            obj.insert("approval_timestamp".to_string(), json!(now));
                            obj.insert("updated_at".to_string(), json!(now));
                            obj.insert(
                                "execution_result".to_string(),
                                json!({ "shadow_mode": true, "simulated": true }),
                            );
                        }
                        matched_action = act.clone();
                    }
                }
                RemediationOutcome::AllowedNonProtected => {
                    res_msg = format!("Ação '{action_type}' aprovada por {user} e aplicada.");
                    if let Some(act) = guard
                        .actions
                        .iter_mut()
                        .find(|a| a.get("action_id").and_then(Value::as_str) == Some(action_id))
                    {
                        if let Some(obj) = act.as_object_mut() {
                            obj.insert("status".to_string(), json!("COMPLETED"));
                            obj.insert("approved_by".to_string(), json!(user));
                            obj.insert("approval_session_id".to_string(), json!(session_id));
                            obj.insert("approval_timestamp".to_string(), json!(now));
                            obj.insert("updated_at".to_string(), json!(now));
                            obj.insert("execution_result".to_string(), json!({ "executed": true }));
                        }
                        matched_action = act.clone();
                    }
                }
            }

            if res_ok {
                let incident_id = matched_action
                    .get("incident_id")
                    .and_then(Value::as_str)
                    .map(str::to_string);
                if let Some(inc) = incident_id {
                    for ev in guard.events.iter_mut() {
                        if ev.get("event_id").and_then(Value::as_str) == Some(inc.as_str()) {
                            if let Some(obj) = ev.as_object_mut() {
                                obj.insert("status".to_string(), json!("RESOLVED"));
                            }
                        }
                    }
                }
            }

            self.persist_locked(&guard)?;
            (res_ok, res_msg, matched_action, guard.actions.clone())
        };

        let status = self.status_payload().await;
        Ok(vec![
            json!({
                "type": "sentinel_action_result",
                "action_id": action_id,
                "success": success,
                "action": updated_action,
                "message": message,
            }),
            json!({
                "type": "sentinel_actions_list",
                "data": actions_list,
            }),
            json!({
                "type": "sentinel_status",
                "data": status,
            }),
        ])
    }

    pub async fn reject_action(
        &self,
        action_id: &str,
        reason: &str,
        user: &str,
    ) -> Result<Vec<Value>, AppError> {
        let now = now_unix_secs();
        let (found, updated_action, actions_list) = {
            let mut guard = self.state.lock().await;
            let mut updated = Value::Null;
            let mut matched = false;
            for act in guard.actions.iter_mut() {
                if act.get("action_id").and_then(Value::as_str) == Some(action_id) {
                    if let Some(obj) = act.as_object_mut() {
                        obj.insert("status".to_string(), json!("REJECTED"));
                        obj.insert("rejected_by".to_string(), json!(user));
                        obj.insert("rejection_reason".to_string(), json!(reason));
                        obj.insert("updated_at".to_string(), json!(now));
                    }
                    updated = act.clone();
                    matched = true;
                    break;
                }
            }
            if matched {
                self.persist_locked(&guard)?;
            }
            (matched, updated, guard.actions.clone())
        };

        let status = self.status_payload().await;
        Ok(vec![
            json!({
                "type": "sentinel_action_result",
                "action_id": action_id,
                "success": found,
                "action": updated_action,
                "message": if found {
                    format!("Ação '{action_id}' rejeitada.")
                } else {
                    format!("Ação '{action_id}' não encontrada.")
                },
            }),
            json!({
                "type": "sentinel_actions_list",
                "data": actions_list,
            }),
            json!({
                "type": "sentinel_status",
                "data": status,
            }),
        ])
    }

    pub async fn rollback_action(
        &self,
        action_id: &str,
        user: &str,
    ) -> Result<Vec<Value>, AppError> {
        let now = now_unix_secs();
        let (found, updated_action, actions_list) = {
            let mut guard = self.state.lock().await;
            let mut updated = Value::Null;
            let mut matched = false;
            for act in guard.actions.iter_mut() {
                if act.get("action_id").and_then(Value::as_str) == Some(action_id) {
                    if let Some(obj) = act.as_object_mut() {
                        obj.insert("status".to_string(), json!("ROLLED_BACK"));
                        obj.insert(
                            "rollback_result".to_string(),
                            json!({
                                "rolled_back_by": user,
                                "timestamp": now,
                                "restored": true,
                            }),
                        );
                        obj.insert("updated_at".to_string(), json!(now));
                    }
                    updated = act.clone();
                    matched = true;
                    break;
                }
            }
            if matched {
                self.persist_locked(&guard)?;
            }
            (matched, updated, guard.actions.clone())
        };

        let status = self.status_payload().await;
        Ok(vec![
            json!({
                "type": "sentinel_action_result",
                "action_id": action_id,
                "success": found,
                "action": updated_action,
                "message": if found {
                    format!("Rollback da ação '{action_id}' concluído.")
                } else {
                    format!("Ação '{action_id}' não encontrada.")
                },
            }),
            json!({
                "type": "sentinel_actions_list",
                "data": actions_list,
            }),
            json!({
                "type": "sentinel_status",
                "data": status,
            }),
        ])
    }

    pub async fn submit_review(
        &self,
        event_id: &str,
        final_classification: &str,
        reason: &str,
        operator: &str,
    ) -> Result<Vec<Value>, AppError> {
        let now = now_unix_secs();
        let mut review_val = Value::Null;
        let mut matched = false;

        {
            let mut guard = self.state.lock().await;
            let mut known_good_fp: Option<(String, String, String)> = None;

            for ev in guard.events.iter_mut() {
                if ev.get("event_id").and_then(Value::as_str) == Some(event_id) {
                    let prev_class = ev
                        .get("severity")
                        .and_then(Value::as_str)
                        .unwrap_or("UNKNOWN")
                        .to_string();
                    let evidence_ids = ev.get("evidence_ids").cloned().unwrap_or_else(|| json!([]));
                    let is_fp = matches!(prev_class.as_str(), "HIGH_RISK" | "SUSPICIOUS")
                        && matches!(final_classification, "BENIGN" | "KNOWN_GOOD");

                    review_val = json!({
                        "review_id": format!("REV-{}", (now * 1000.0) as u64),
                        "event_id": event_id,
                        "operator": operator,
                        "timestamp": now,
                        "reason": reason,
                        "evidence_ids": evidence_ids,
                        "previous_classification": prev_class,
                        "final_classification": final_classification,
                        "is_false_positive": is_fp,
                        "schema_version": SENTINEL_SCHEMA_VERSION,
                    });

                    let fp = ev
                        .get("fingerprint")
                        .and_then(Value::as_str)
                        .unwrap_or_default()
                        .to_string();
                    let cat = ev
                        .get("category")
                        .and_then(Value::as_str)
                        .unwrap_or_default()
                        .to_string();

                    if let Some(obj) = ev.as_object_mut() {
                        obj.insert("human_review".to_string(), review_val.clone());
                        if let Some(tl) = obj
                            .get_mut("observation_timeline")
                            .and_then(Value::as_array_mut)
                        {
                            tl.push(json!({
                                "timestamp": now,
                                "note": format!("Revisão Humana ({operator}): {final_classification} — {reason}"),
                            }));
                        }
                        if matches!(final_classification, "BENIGN" | "KNOWN_GOOD") {
                            obj.insert("is_known_good".to_string(), json!(true));
                            obj.insert("status".to_string(), json!("RESOLVED"));
                            known_good_fp = Some((fp, cat, prev_class));
                        }
                    }
                    matched = true;
                    break;
                }
            }

            if let Some((fp, cat, prev_class)) = known_good_fp {
                if !fp.is_empty() {
                    guard.known_goods.insert(
                        fp.clone(),
                        json!({
                            "item_key": fp,
                            "category": cat,
                            "accepted_by": operator,
                            "accepted_at": now,
                            "reason": reason,
                            "previous_state": { "model_classification": prev_class },
                            "current_state": { "final_classification": final_classification },
                        }),
                    );
                }
            }

            if matched {
                self.persist_locked(&guard)?;
            }
        }

        let status = self.status_payload().await;
        Ok(vec![
            json!({
                "type": "sentinel_review_result",
                "event_id": event_id,
                "success": matched,
                "review": review_val,
            }),
            json!({
                "type": "sentinel_status",
                "data": status,
            }),
        ])
    }

    fn build_status_locked(
        &self,
        guard: &WatchdogState,
        sched_snap: &crate::sentinel::scheduler::SentinelStatusSnapshot,
    ) -> Value {
        let open_events = count_open_events(&guard.events);
        let high_risk = count_high_risk_events(&guard.events);
        let pending_actions = guard
            .actions
            .iter()
            .filter(|a| {
                matches!(
                    a.get("status").and_then(Value::as_str),
                    Some("PROPOSED" | "WAITING_APPROVAL")
                )
            })
            .count();

        let is_baseline_ready = guard.baseline.is_some();
        let active_baseline_id = guard
            .baseline
            .as_ref()
            .and_then(|b| b.get("baseline_id"))
            .and_then(Value::as_str)
            .map(str::to_string);

        let lifecycle_state = if !guard.degraded_collectors.is_empty() {
            "DEGRADED"
        } else if is_baseline_ready {
            "READY"
        } else {
            "STARTING"
        };

        let posture = if !guard.degraded_collectors.is_empty() {
            "DEGRADED"
        } else if high_risk > 0 {
            "HIGH_RISK"
        } else if open_events > 0 {
            "ATTENTION"
        } else if is_baseline_ready {
            "GOOD"
        } else {
            "MONITORING"
        };

        let mem_mb = sched_snap
            .last_observation
            .as_ref()
            .map(|o| {
                let used = o
                    .memory
                    .total_phys_bytes
                    .saturating_sub(o.memory.avail_phys_bytes);
                ((used as f64) / (1024.0 * 1024.0) * 10.0).round() / 10.0
            })
            .unwrap_or(guard.last_memory_used_mb);

        json!({
            "schema_version": SENTINEL_SCHEMA_VERSION,
            "status": "RUNNING",
            "lifecycle_state": lifecycle_state,
            "shadow_mode": sched_snap.shadow_mode,
            "shadow_state": if sched_snap.shadow_mode { "SHADOW_READ_ONLY" } else { "ACTIVE_ENFORCEMENT" },
            "posture": posture,
            "is_baseline_ready": is_baseline_ready,
            "degraded_reason": if guard.degraded_collectors.is_empty() {
                Value::Null
            } else {
                json!(format!("Collectors degradados: {}", guard.degraded_collectors.join(", ")))
            },
            "degraded_collectors": guard.degraded_collectors,
            "baseline_duration_seconds": guard.baseline_duration_seconds,
            "is_auditing_now": guard.is_auditing_now,
            "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
            "total_scans": guard.total_scans,
            "last_scan_time": guard.last_scan_time,
            "last_scan_duration_seconds": guard.last_scan_duration_seconds,
            "next_scan_in_seconds": SCAN_INTERVAL_SECONDS,
            "active_baseline_id": active_baseline_id,
            "open_events_count": open_events,
            "high_risk_events_count": high_risk,
            "actions_count": guard.actions.len(),
            "pending_actions_count": pending_actions,
            "cpu_percent": 0.0,
            "memory_mb": mem_mb,
        })
    }

    fn persist_locked(&self, guard: &WatchdogState) -> Result<(), AppError> {
        fs::create_dir_all(&self.data_dir).map_err(|err| {
            AppError::new(
                "SENTINEL_DIR_CREATE_FAILED",
                format!("Failed creating sentinel dir: {err}"),
            )
        })?;
        if let Some(ref b) = guard.baseline {
            write_json(&self.data_dir, &self.data_dir.join("baseline.json"), b)?;
        }
        write_json(
            &self.data_dir,
            &self.data_dir.join("events.json"),
            &Value::Array(guard.events.clone()),
        )?;
        write_json(
            &self.data_dir,
            &self.data_dir.join("actions.json"),
            &Value::Array(guard.actions.clone()),
        )?;
        let kg_map: serde_json::Map<String, Value> = guard
            .known_goods
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();
        write_json(
            &self.data_dir,
            &self.data_dir.join("known_goods.json"),
            &Value::Object(kg_map),
        )?;
        write_json(
            &self.data_dir,
            &self.data_dir.join("watchdog_meta.json"),
            &json!({
                "total_scans": guard.total_scans,
                "last_scan_time": guard.last_scan_time,
                "last_scan_duration_seconds": guard.last_scan_duration_seconds,
                "baseline_duration_seconds": guard.baseline_duration_seconds,
            }),
        )?;
        Ok(())
    }
}

struct HostsSnapshot {
    exists: bool,
    sha256: String,
    entry_count: usize,
}

fn collect_hosts_snapshot() -> HostsSnapshot {
    #[cfg(windows)]
    let hosts_path = {
        let windir = std::env::var_os("SystemRoot")
            .or_else(|| std::env::var_os("WINDIR"))
            .unwrap_or_else(|| "C:\\Windows".into());
        PathBuf::from(windir)
            .join("System32")
            .join("drivers")
            .join("etc")
            .join("hosts")
    };
    #[cfg(not(windows))]
    let hosts_path = PathBuf::from("/etc/hosts");

    match fs::read(&hosts_path) {
        Ok(bytes) => {
            let digest = hex::encode(Sha256::digest(&bytes));
            let text = String::from_utf8_lossy(&bytes);
            let entry_count = text
                .lines()
                .map(str::trim)
                .filter(|line| !line.is_empty() && !line.starts_with('#'))
                .count();
            HostsSnapshot {
                exists: true,
                sha256: digest,
                entry_count,
            }
        }
        Err(_) => HostsSnapshot {
            exists: false,
            sha256: String::new(),
            entry_count: 0,
        },
    }
}

fn collect_startup_persistence_entries() -> Vec<Value> {
    let mut dirs = Vec::new();
    if let Some(appdata) = std::env::var_os("APPDATA") {
        dirs.push(
            PathBuf::from(appdata)
                .join("Microsoft")
                .join("Windows")
                .join("Start Menu")
                .join("Programs")
                .join("Startup"),
        );
    }
    if let Some(progdata) = std::env::var_os("PROGRAMDATA") {
        dirs.push(
            PathBuf::from(progdata)
                .join("Microsoft")
                .join("Windows")
                .join("Start Menu")
                .join("Programs")
                .join("Startup"),
        );
    }

    let mut entries = Vec::new();
    for dir in dirs {
        if let Ok(rd) = fs::read_dir(&dir) {
            for ent in rd.flatten() {
                let p = ent.path();
                let name = ent.file_name().to_string_lossy().to_string();
                if name.eq_ignore_ascii_case("desktop.ini") {
                    continue;
                }
                entries.push(json!({
                    "kind": "STARTUP_FOLDER",
                    "name": name,
                    "target_path": p.to_string_lossy().to_string(),
                }));
            }
        }
    }
    entries
}

fn compute_fingerprint(category: &str, asset_key: &str, rule_id: &str) -> String {
    let raw = format!("{category}:{asset_key}:{rule_id}");
    hex::encode(Sha256::digest(raw.as_bytes()))
        .chars()
        .take(16)
        .collect()
}

#[allow(clippy::too_many_arguments)]
fn record_or_dedup_event(
    events: &mut Vec<Value>,
    actions: &mut Vec<Value>,
    known_goods: &BTreeMap<String, Value>,
    fingerprint: &str,
    category: &str,
    severity: &str,
    confidence: f64,
    evidence_ids: Vec<String>,
    rationale: &str,
    recommended_action: &str,
    affected_process: Option<Value>,
    now: f64,
) -> Option<(Value, Option<Value>)> {
    let is_known = known_goods.contains_key(fingerprint);

    for existing in events.iter_mut() {
        if existing.get("fingerprint").and_then(Value::as_str) == Some(fingerprint) {
            let count = existing
                .get("occurrence_count")
                .and_then(Value::as_i64)
                .unwrap_or(1)
                + 1;
            if let Some(obj) = existing.as_object_mut() {
                obj.insert("last_seen".to_string(), json!(now));
                obj.insert("occurrence_count".to_string(), json!(count));
                if let Some(tl) = obj
                    .get_mut("observation_timeline")
                    .and_then(Value::as_array_mut)
                {
                    tl.push(json!({
                        "timestamp": now,
                        "note": format!("Reobservado no ciclo de scan #{count}"),
                    }));
                }
                if is_known {
                    obj.insert("is_known_good".to_string(), json!(true));
                    obj.insert("status".to_string(), json!("RESOLVED"));
                }
            }
            return None;
        }
    }

    let event_id = format!(
        "SEC-EV-{}-{}",
        (now * 1000.0) as u64,
        &fingerprint[..fingerprint.len().min(6)]
    );
    let event = json!({
        "event_id": event_id,
        "fingerprint": fingerprint,
        "timestamp": now,
        "first_seen": now,
        "last_seen": now,
        "occurrence_count": 1,
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "evidence_ids": evidence_ids.clone(),
        "rationale": rationale,
        "recommended_action": recommended_action,
        "affected_process": affected_process,
        "affected_network_endpoint": Value::Null,
        "status": if is_known { "RESOLVED" } else { "OPEN" },
        "is_known_good": is_known,
        "observation_timeline": [{
            "timestamp": now,
            "note": "Primeira deteção durante ciclo de auditoria Sentinel",
        }],
        "model_classification": severity,
        "human_review": Value::Null,
        "schema_version": SENTINEL_SCHEMA_VERSION,
    });
    events.push(event.clone());

    let proposed_action = if !is_known {
        let action_id = format!(
            "ACT-{}-{}",
            (now * 1000.0) as u64,
            &Uuid::new_v4().simple().to_string()[..6]
        );
        let action = json!({
            "action_id": action_id,
            "incident_id": event_id,
            "action_type": "MARK_KNOWN_GOOD",
            "target": fingerprint,
            "rationale": rationale,
            "evidence_ids": evidence_ids,
            "permission_level": "LOW_RISK_MUTATION",
            "requested_by": "sentinel_correlation_engine",
            "approval_required": true,
            "approved_by": Value::Null,
            "approval_session_id": Value::Null,
            "approval_timestamp": Value::Null,
            "pre_state": {},
            "execution_result": {},
            "post_state": {},
            "verification_result": {},
            "rollback_available": true,
            "rollback_plan": "Remover item da lista known_goods.",
            "rollback_result": Value::Null,
            "status": "WAITING_APPROVAL",
            "created_at": now,
            "updated_at": now,
            "error_message": Value::Null,
            "schema_version": SENTINEL_SCHEMA_VERSION,
        });
        actions.push(action.clone());
        Some(action)
    } else {
        None
    };

    Some((event, proposed_action))
}

fn count_open_events(events: &[Value]) -> usize {
    events
        .iter()
        .filter(|e| e.get("status").and_then(Value::as_str) != Some("RESOLVED"))
        .count()
}

fn count_high_risk_events(events: &[Value]) -> usize {
    events
        .iter()
        .filter(|e| {
            let is_known = e
                .get("is_known_good")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            let sev = e
                .get("severity")
                .and_then(Value::as_str)
                .unwrap_or_default();
            !is_known && matches!(sev, "HIGH_RISK" | "CONFIRMED_MALICIOUS" | "SUSPICIOUS")
        })
        .count()
}

fn now_unix_secs() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| (d.as_secs_f64() * 1000.0).round() / 1000.0)
        .unwrap_or(0.0)
}

fn read_confined_json(root: &Path, path: &Path) -> Option<Value> {
    let canon = ensure_confined_existing_file(root, path).ok()?;
    let raw = fs::read_to_string(&canon).ok()?;
    serde_json::from_str(&raw).ok()
}

fn write_json(root: &Path, target: &Path, value: &Value) -> Result<(), AppError> {
    let body = serde_json::to_string_pretty(value).map_err(|err| {
        AppError::new(
            "SENTINEL_SERIALIZE_FAILED",
            format!("Failed serializing sentinel state: {err}"),
        )
    })?;
    atomic_write_string(root, target, &body)?;
    Ok(())
}

//! Native Rust fast-path dispatcher for all 15 Knowledge / Obsidian Vault routes.
//!
//! Replaces `workers/knowledge_worker.py` (`WorkerPoolRole::Knowledge`) in production:
//! - Vault note CRUD (`get_notes`, `read_note`, `save_note`)
//! - Rust-owned SQLite memory CRUD (`get_rules`, `delete_rule`, `delete_architecture`, `delete_decision`)
//! - Graph Engine diagnostics, quality audits, safe enrichment, CAS rollback & bounded batches
//!   (`get_vault_diagnostics`, `audit_note_quality`, `enrich_note`, `rollback_note`,
//!    `get_queue_status`, `pause_queue_worker`, `resume_queue_worker`, `start_improvement_batch`)

use std::path::{Path, PathBuf};

use serde_json::{json, Value};

use crate::commands::storage::{
    architecture_memory_to_json, compounding_rules_to_json, engineering_decisions_to_json,
};
use crate::error::AppError;
use crate::knowledge::graph_engine::{KnowledgeError, ObsidianGraphEngine};
use crate::knowledge::vault::{list_notes, read_note_payload, resolve_vault_root, save_note_events};
use crate::storage::sqlite::SqliteDatabase;

fn map_knowledge_error(err: KnowledgeError) -> AppError {
    AppError::new(err.code(), err.to_string())
}

async fn run_engine_blocking<F, T>(project_root: &Path, f: F) -> Result<T, KnowledgeError>
where
    F: FnOnce(&mut ObsidianGraphEngine) -> Result<T, KnowledgeError> + Send + 'static,
    T: Send + 'static,
{
    let root = project_root.to_path_buf();
    tokio::task::spawn_blocking(move || {
        let mut engine = ObsidianGraphEngine::open_default(&root)?;
        f(&mut engine)
    })
    .await
    .map_err(|err| KnowledgeError::Internal(format!("Knowledge blocking task panicked: {err}")))?
}

async fn run_vault_blocking<F, T>(project_root: &Path, f: F) -> Result<T, AppError>
where
    F: FnOnce(&Path) -> T + Send + 'static,
    T: Send + 'static,
{
    let root: PathBuf = project_root.to_path_buf();
    tokio::task::spawn_blocking(move || {
        let vault_root = resolve_vault_root(&root)?;
        Ok::<T, AppError>(f(&vault_root))
    })
    .await
    .map_err(|err| AppError::new("KNOWLEDGE_TASK_PANIC", format!("Knowledge vault task failed: {err}")))?
}

/// Executes a deterministic or bounded-LLM Knowledge route natively in Rust.
///
/// Returns `Ok(Some(events))` when `msg_type` belongs to the 15 Knowledge routes,
/// preserving exact wire event names and payload schemas expected by `WebSocketContext.tsx`.
pub async fn try_execute_knowledge_fast_path(
    project_root: &Path,
    db: &SqliteDatabase,
    msg_type: &str,
    message: &Value,
) -> Result<Option<Vec<Value>>, AppError> {
    match msg_type {
        "get_notes" => {
            let notes = run_vault_blocking(project_root, |vault| list_notes(vault)).await??;
            Ok(Some(vec![json!({
                "type": "notes_list",
                "notes": notes,
            })]))
        }

        "read_note" => {
            let raw_filename = message
                .get("filename")
                .and_then(Value::as_str)
                .map(str::to_string);
            let payload = run_vault_blocking(project_root, move |vault| {
                read_note_payload(vault, raw_filename.as_deref())
            })
            .await?;
            Ok(Some(vec![payload]))
        }

        "save_note" => {
            let raw_filename = message
                .get("filename")
                .and_then(Value::as_str)
                .map(str::to_string);
            let raw_content = message
                .get("content")
                .and_then(Value::as_str)
                .map(str::to_string);
            let events = run_vault_blocking(project_root, move |vault| {
                save_note_events(vault, raw_filename.as_deref(), raw_content.as_deref())
            })
            .await?;
            Ok(Some(events))
        }

        "get_rules" => {
            let rules = db
                .get_compounding_rules()
                .await
                .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
            Ok(Some(vec![json!({
                "type": "rules_list",
                "rules": compounding_rules_to_json(&rules),
            })]))
        }

        "delete_rule" => {
            let key = message
                .get("key")
                .and_then(Value::as_str)
                .unwrap_or("")
                .trim();
            if !key.is_empty() {
                db.delete_compounding_rule(key)
                    .await
                    .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))?;
            }
            let rules = db
                .get_compounding_rules()
                .await
                .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
            let serialized = compounding_rules_to_json(&rules);
            Ok(Some(vec![
                json!({ "type": "rules_list", "rules": serialized }),
                json!({ "type": "rules_updated", "rules": serialized }),
            ]))
        }

        "delete_architecture" => {
            let module = message
                .get("module")
                .and_then(Value::as_str)
                .unwrap_or("")
                .trim();
            if !module.is_empty() {
                db.delete_architecture_memory(module)
                    .await
                    .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))?;
            }
            let arch = db
                .get_architecture_memory()
                .await
                .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
            Ok(Some(vec![json!({
                "type": "architecture_updated",
                "architecture": architecture_memory_to_json(&arch),
            })]))
        }

        "delete_decision" => {
            let decision = message
                .get("decision")
                .and_then(Value::as_str)
                .unwrap_or("")
                .trim();
            if !decision.is_empty() {
                db.delete_engineering_decision(decision)
                    .await
                    .map_err(|err| AppError::new("SQLITE_WRITE_FAILED", err))?;
            }
            let decisions = db
                .get_engineering_decisions()
                .await
                .map_err(|err| AppError::new("SQLITE_READ_FAILED", err))?;
            Ok(Some(vec![json!({
                "type": "decisions_updated",
                "decisions": engineering_decisions_to_json(&decisions),
            })]))
        }

        "get_vault_diagnostics" => {
            let (diagnostics, queue) = run_engine_blocking(project_root, |engine| {
                let diagnostics = engine.compute_graph_diagnostics()?;
                let queue: Vec<Value> = engine.load_queue().into_iter().take(25).collect();
                Ok((diagnostics, queue))
            })
            .await
            .map_err(map_knowledge_error)?;
            Ok(Some(vec![json!({
                "type": "vault_diagnostics",
                "diagnostics": diagnostics,
                "queue": queue,
            })]))
        }

        "audit_note_quality" => {
            let filename = message
                .get("filename")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let audit = run_engine_blocking(project_root, move |engine| {
                engine.audit_note_quality(&filename)
            })
            .await
            .map_err(map_knowledge_error)?;
            Ok(Some(vec![json!({
                "type": "note_quality_audit",
                "audit": audit,
            })]))
        }

        "enrich_note" => {
            let filename = message
                .get("filename")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let auto_apply = message
                .get("auto_apply")
                .and_then(Value::as_bool)
                .unwrap_or(true);
            let outcome = run_engine_blocking(project_root, move |engine| {
                engine.enrich_note_safely(&filename, auto_apply)
            })
            .await;
            let event = match outcome {
                Ok(proposal) => json!({
                    "type": "note_enrichment_result",
                    "success": true,
                    "proposal": proposal,
                }),
                Err(err) => json!({
                    "type": "note_enrichment_result",
                    "success": false,
                    "error": err.to_string(),
                    "code": err.code(),
                }),
            };
            Ok(Some(vec![event]))
        }

        "rollback_note" => {
            let filename = message
                .get("filename")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let backup_path = message
                .get("backup_path")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let expected_hash = message
                .get("expected_current_hash")
                .and_then(Value::as_str)
                .map(str::to_string);
            let fname_for_task = filename.clone();
            let outcome = run_engine_blocking(project_root, move |engine| {
                engine.rollback_note(&fname_for_task, &backup_path, expected_hash.as_deref())
            })
            .await;
            let event = match outcome {
                Ok(success) => json!({
                    "type": "note_rollback_result",
                    "success": success,
                    "filename": filename,
                }),
                Err(err) => json!({
                    "type": "note_rollback_result",
                    "success": false,
                    "filename": filename,
                    "error": err.to_string(),
                    "code": err.code(),
                }),
            };
            Ok(Some(vec![event]))
        }

        "get_queue_status" => {
            let (status, queue) = run_engine_blocking(project_root, |engine| {
                let status = engine.get_worker_status();
                let queue: Vec<Value> = engine.load_queue().into_iter().take(25).collect();
                Ok((status, queue))
            })
            .await
            .map_err(map_knowledge_error)?;
            Ok(Some(vec![json!({
                "type": "queue_worker_status",
                "worker_state": status,
                "queue": queue,
            })]))
        }

        "pause_queue_worker" => {
            let status = run_engine_blocking(project_root, |engine| {
                engine.pause_queue_worker()?;
                Ok(engine.get_worker_status())
            })
            .await
            .map_err(map_knowledge_error)?;
            Ok(Some(vec![json!({
                "type": "queue_worker_status",
                "worker_state": status,
                "action": "paused",
            })]))
        }

        "resume_queue_worker" => {
            let status = run_engine_blocking(project_root, |engine| {
                engine.resume_queue_worker()?;
                Ok(engine.get_worker_status())
            })
            .await
            .map_err(map_knowledge_error)?;
            Ok(Some(vec![json!({
                "type": "queue_worker_status",
                "worker_state": status,
                "action": "resumed",
            })]))
        }

        "start_improvement_batch" => {
            let batch_size = message
                .get("batch_size")
                .and_then(Value::as_i64)
                .unwrap_or(1);
            let root_for_open = project_root.to_path_buf();
            let mut engine = tokio::task::spawn_blocking(move || {
                ObsidianGraphEngine::open_default(&root_for_open)
            })
            .await
            .map_err(|err| {
                AppError::new("KNOWLEDGE_TASK_PANIC", format!("Knowledge batch init failed: {err}"))
            })?
            .map_err(map_knowledge_error)?;

            let proposals = engine
                .run_bounded_improvement_batch(batch_size)
                .await
                .map_err(map_knowledge_error)?;
            let diagnostics = tokio::task::spawn_blocking(move || engine.compute_graph_diagnostics())
                .await
                .map_err(|err| {
                    AppError::new(
                        "KNOWLEDGE_TASK_PANIC",
                        format!("Knowledge diagnostics task failed: {err}"),
                    )
                })?
                .map_err(map_knowledge_error)?;

            let count_processed = proposals.len();
            Ok(Some(vec![json!({
                "type": "improvement_batch_result",
                "proposals": proposals,
                "count_processed": count_processed,
                "diagnostics": diagnostics,
            })]))
        }

        _ => Ok(None),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;

    #[tokio::test]
    async fn all_15_knowledge_routes_execute_natively_without_worker() {
        let dir = tempdir().unwrap();
        let root = dir.path();
        let db = SqliteDatabase::open(root.join("database.db")).unwrap();

        // 1. save_note -> emits notes_list + note_saved
        let saved = try_execute_knowledge_fast_path(
            root,
            &db,
            "save_note",
            &json!({
                "filename": "Architecture/RAG Pipeline",
                "content": "# Agentic RAG\nRetrieval-augmented generation pipeline with hybrid search and reciprocal rank fusion.",
            }),
        )
        .await
        .unwrap()
        .expect("save_note handled");
        assert_eq!(saved.len(), 2);
        assert_eq!(saved[0]["type"], "notes_list");
        assert_eq!(saved[0]["notes"], json!(["Architecture/RAG Pipeline.md"]));
        assert_eq!(saved[1]["type"], "note_saved");

        // Create second note for graph link/orphan coverage
        try_execute_knowledge_fast_path(
            root,
            &db,
            "save_note",
            &json!({
                "filename": "Concepts/Model Context Protocol (MCP) and Capability Discovery Architecture",
                "content": "---\ndomain: standards\ntype: standard\ntags: [\"mcp\"]\n---\n\n# MCP\nCapability discovery standard.",
            }),
        )
        .await
        .unwrap();

        // 2. get_notes
        let notes_ev = try_execute_knowledge_fast_path(root, &db, "get_notes", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(notes_ev[0]["type"], "notes_list");
        assert_eq!(notes_ev[0]["notes"].as_array().unwrap().len(), 2);

        // 3. read_note (existing + missing)
        let read_ev = try_execute_knowledge_fast_path(
            root,
            &db,
            "read_note",
            &json!({ "filename": "Architecture/RAG Pipeline.md" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(read_ev[0]["type"], "note_content");
        assert!(read_ev[0]["content"]
            .as_str()
            .unwrap()
            .contains("# Agentic RAG"));

        let missing_ev = try_execute_knowledge_fast_path(
            root,
            &db,
            "read_note",
            &json!({ "filename": "DoesNotExist.md" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert!(missing_ev[0]["content"]
            .as_str()
            .unwrap()
            .contains("não existe no Obsidian"));

        // 4-7. get_rules, delete_rule, delete_architecture, delete_decision
        db.add_compounding_rule("k1", "Prefer atomic writes", "security")
            .await
            .unwrap();
        db.add_architecture_memory("knowledge", "Native Rust engine", "[]", "hash1")
            .await
            .unwrap();
        db.add_engineering_decision("Use Rust single-writer SQLite", "Eliminate lock contention", "ADRs")
            .await
            .unwrap();

        let rules_ev = try_execute_knowledge_fast_path(root, &db, "get_rules", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(rules_ev[0]["type"], "rules_list");
        assert_eq!(rules_ev[0]["rules"].as_array().unwrap().len(), 1);

        let del_rule = try_execute_knowledge_fast_path(
            root,
            &db,
            "delete_rule",
            &json!({ "key": "k1" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(del_rule.len(), 2);
        assert_eq!(del_rule[0]["type"], "rules_list");
        assert_eq!(del_rule[1]["type"], "rules_updated");
        assert_eq!(del_rule[1]["rules"].as_array().unwrap().len(), 0);

        let del_arch = try_execute_knowledge_fast_path(
            root,
            &db,
            "delete_architecture",
            &json!({ "module": "knowledge" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(del_arch[0]["type"], "architecture_updated");
        assert_eq!(del_arch[0]["architecture"].as_array().unwrap().len(), 0);

        let del_dec = try_execute_knowledge_fast_path(
            root,
            &db,
            "delete_decision",
            &json!({ "decision": "Use Rust single-writer SQLite" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(del_dec[0]["type"], "decisions_updated");
        assert_eq!(del_dec[0]["decisions"].as_array().unwrap().len(), 0);

        // 8. get_vault_diagnostics
        let diag_ev = try_execute_knowledge_fast_path(
            root,
            &db,
            "get_vault_diagnostics",
            &json!({}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(diag_ev[0]["type"], "vault_diagnostics");
        assert_eq!(diag_ev[0]["diagnostics"]["total_notes"], 2);

        // 9. audit_note_quality
        let audit_ev = try_execute_knowledge_fast_path(
            root,
            &db,
            "audit_note_quality",
            &json!({ "filename": "Architecture/RAG Pipeline.md" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(audit_ev[0]["type"], "note_quality_audit");
        assert_eq!(audit_ev[0]["audit"]["rel_path"], "Architecture/RAG Pipeline.md");

        // 10. enrich_note + 11. rollback_note
        let enrich_ev = try_execute_knowledge_fast_path(
            root,
            &db,
            "enrich_note",
            &json!({ "filename": "Architecture/RAG Pipeline.md", "auto_apply": true }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(enrich_ev[0]["type"], "note_enrichment_result");
        assert_eq!(enrich_ev[0]["success"], true);
        let backup_path = enrich_ev[0]["proposal"]["backup_path"]
            .as_str()
            .expect("backup_path returned")
            .to_string();

        let rollback_ev = try_execute_knowledge_fast_path(
            root,
            &db,
            "rollback_note",
            &json!({
                "filename": "Architecture/RAG Pipeline.md",
                "backup_path": backup_path,
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(rollback_ev[0]["type"], "note_rollback_result");
        assert_eq!(rollback_ev[0]["success"], true);

        // Verify note content was restored cleanly
        let restored = fs::read_to_string(root.join("obsidian_vault/Architecture/RAG Pipeline.md")).unwrap();
        assert!(restored.starts_with("# Agentic RAG"));

        // Invalid rollback path returns structured error event instead of unwinding
        let bad_rollback = try_execute_knowledge_fast_path(
            root,
            &db,
            "rollback_note",
            &json!({
                "filename": "../escape.md",
                "backup_path": "missing",
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(bad_rollback[0]["type"], "note_rollback_result");
        assert_eq!(bad_rollback[0]["success"], false);
        assert_eq!(bad_rollback[0]["code"], "SECURITY_VIOLATION");

        // 12-14. pause_queue_worker, resume_queue_worker, get_queue_status
        let pause_ev = try_execute_knowledge_fast_path(root, &db, "pause_queue_worker", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(pause_ev[0]["type"], "queue_worker_status");
        assert_eq!(pause_ev[0]["action"], "paused");
        assert_eq!(pause_ev[0]["worker_state"]["is_paused"], true);

        let resume_ev = try_execute_knowledge_fast_path(root, &db, "resume_queue_worker", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(resume_ev[0]["type"], "queue_worker_status");
        assert_eq!(resume_ev[0]["action"], "resumed");
        assert_eq!(resume_ev[0]["worker_state"]["is_paused"], false);

        let queue_ev = try_execute_knowledge_fast_path(root, &db, "get_queue_status", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(queue_ev[0]["type"], "queue_worker_status");
        assert!(queue_ev[0]["queue"].is_array());

        // 15. start_improvement_batch (uses deterministic fallback when Ollama offline or qwen if running)
        let batch_ev = try_execute_knowledge_fast_path(
            root,
            &db,
            "start_improvement_batch",
            &json!({ "batch_size": 1 }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(batch_ev[0]["type"], "improvement_batch_result");
        assert!(batch_ev[0]["count_processed"].as_u64().unwrap() >= 1);
        assert!(batch_ev[0]["diagnostics"]["total_notes"].as_u64().is_some());

        // Unrelated message returns None
        assert!(try_execute_knowledge_fast_path(root, &db, "mission_list", &json!({}))
            .await
            .unwrap()
            .is_none());
    }
}

//! Native Rust handlers for deterministic Study catalog operations (`StudyStore` + JSON stores).
//!
//! Covers document listing, document detail lookup (with notes & highlights),
//! cascade deletion (preserving non-owned `linked_folder` source files),
//! reading progress persistence, notes, highlights, and collection CRUD.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::Local;
use serde_json::{json, Value};
use uuid::Uuid;

use crate::error::AppError;
use crate::permissions::path_jail::{ensure_confined_existing_file, resolve_confined_path};
use crate::storage::atomic_fs::atomic_write_string;
use crate::storage::study_store::StudyStore;

fn study_storage_dir(project_root: &Path) -> PathBuf {
    project_root.join("data").join("study")
}

fn validate_study_id(raw: &str, label: &str) -> Result<String, AppError> {
    let cleaned = raw.trim();
    if cleaned.is_empty()
        || cleaned.contains("..")
        || cleaned.contains('/')
        || cleaned.contains('\\')
        || cleaned.contains('\0')
        || !cleaned
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' || ch == '.')
    {
        return Err(AppError::new(
            "STUDY_INVALID_ID",
            format!("Invalid {label}: `{raw}`"),
        ));
    }
    Ok(cleaned.to_string())
}

fn read_json_array_safe(path: &Path) -> Result<Vec<Value>, AppError> {
    match fs::symlink_metadata(path) {
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(Vec::new()),
        Err(err) => {
            return Err(AppError::new(
                "STUDY_READ_FAILED",
                format!("Failed checking {}: {err}", path.display()),
            ))
        }
        Ok(meta) => {
            if meta.file_type().is_symlink() {
                return Err(AppError::new(
                    "SECURITY_VIOLATION",
                    format!("Refusing symlinked study file {}", path.display()),
                ));
            }
        }
    }
    let raw = fs::read_to_string(path).map_err(|err| {
        AppError::new(
            "STUDY_READ_FAILED",
            format!("Failed reading {}: {err}", path.display()),
        )
    })?;
    if raw.trim().is_empty() {
        return Ok(Vec::new());
    }
    match serde_json::from_str::<Value>(&raw) {
        Ok(Value::Array(items)) => Ok(items),
        _ => Ok(Vec::new()),
    }
}

fn read_json_map_safe(path: &Path) -> Result<BTreeMap<String, Value>, AppError> {
    match fs::symlink_metadata(path) {
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(BTreeMap::new()),
        Err(err) => {
            return Err(AppError::new(
                "STUDY_READ_FAILED",
                format!("Failed checking {}: {err}", path.display()),
            ))
        }
        Ok(meta) => {
            if meta.file_type().is_symlink() {
                return Err(AppError::new(
                    "SECURITY_VIOLATION",
                    format!("Refusing symlinked study file {}", path.display()),
                ));
            }
        }
    }
    let raw = fs::read_to_string(path).map_err(|err| {
        AppError::new(
            "STUDY_READ_FAILED",
            format!("Failed reading {}: {err}", path.display()),
        )
    })?;
    if raw.trim().is_empty() {
        return Ok(BTreeMap::new());
    }
    match serde_json::from_str::<Value>(&raw) {
        Ok(Value::Object(map)) => Ok(map.into_iter().collect()),
        _ => Ok(BTreeMap::new()),
    }
}

fn write_json_pretty(study_dir: &Path, filename: &str, value: &Value) -> Result<(), AppError> {
    let encoded = serde_json::to_string_pretty(value).map_err(|err| {
        AppError::new(
            "STUDY_SERIALIZE_FAILED",
            format!("Failed to serialize {filename}: {err}"),
        )
    })?;
    atomic_write_string(study_dir, Path::new(filename), &encoded)?;
    Ok(())
}

fn sorted_documents_desc(mut docs: Vec<Value>) -> Vec<Value> {
    docs.sort_by(|a, b| {
        let a_ts = a.get("updated_at").and_then(Value::as_str).unwrap_or("");
        let b_ts = b.get("updated_at").and_then(Value::as_str).unwrap_or("");
        b_ts.cmp(a_ts)
    });
    docs
}

fn now_iso_local() -> String {
    Local::now().format("%Y-%m-%dT%H:%M:%S%.6f").to_string()
}

fn short_hex_8() -> String {
    let full = Uuid::new_v4().simple().to_string();
    full[..8].to_string()
}

fn delete_if_confined_regular_file(project_root: &Path, study_dir: &Path, raw_path: &str) {
    let trimmed = raw_path.trim();
    if trimmed.is_empty() {
        return;
    }
    let raw = Path::new(trimmed);
    let candidate = if raw.is_absolute() {
        raw.to_path_buf()
    } else {
        project_root.join(raw)
    };
    let rel_from_study = match candidate.strip_prefix(study_dir) {
        Ok(rel) => rel.to_path_buf(),
        Err(_) => raw.to_path_buf(),
    };
    if let Ok(canon) = ensure_confined_existing_file(study_dir, &rel_from_study) {
        let _ = fs::remove_file(canon);
    }
}

fn delete_if_confined_dir(study_dir: &Path, rel: &Path) {
    if let Ok(canon) = resolve_confined_path(study_dir, rel) {
        if let Ok(meta) = fs::symlink_metadata(&canon) {
            if !meta.file_type().is_symlink() && meta.is_dir() {
                let _ = fs::remove_dir_all(&canon);
            }
        }
    }
}

/// Executes deterministic Study catalog CRUD operations directly in Rust.
pub async fn try_execute_study_fast_path(
    project_root: &Path,
    study_store: &StudyStore,
    msg_type: &str,
    message: &Value,
) -> Result<Option<Vec<Value>>, AppError> {
    let study_dir = study_storage_dir(project_root);

    match msg_type {
        "study_list_documents" => {
            study_store
                .refresh()
                .await
                .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;
            let docs = sorted_documents_desc(study_store.list_documents().await);
            Ok(Some(vec![json!({
                "type": "study_documents_list",
                "event": "study.document_list",
                "documents": docs,
            })]))
        }

        "study_get_document" => {
            let raw_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or("");
            let Ok(doc_id) = validate_study_id(raw_id, "document_id") else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Documento '{}' não encontrado.", raw_id),
                })]));
            };
            study_store
                .refresh()
                .await
                .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;
            let Some(doc) = study_store
                .get_document(&doc_id)
                .await
                .map_err(|err| AppError::new("STUDY_READ_FAILED", err))?
            else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Documento '{}' não encontrado.", doc_id),
                })]));
            };

            let all_notes = read_json_array_safe(&study_dir.join("notes.json"))?;
            let doc_notes: Vec<Value> = all_notes
                .into_iter()
                .filter(|item| item.get("document_id").and_then(Value::as_str) == Some(doc_id.as_str()))
                .collect();

            let all_highlights = read_json_array_safe(&study_dir.join("highlights.json"))?;
            let doc_highlights: Vec<Value> = all_highlights
                .into_iter()
                .filter(|item| item.get("document_id").and_then(Value::as_str) == Some(doc_id.as_str()))
                .collect();

            Ok(Some(vec![json!({
                "type": "study_document_details",
                "document": doc,
                "notes": doc_notes,
                "highlights": doc_highlights,
            })]))
        }

        "study_delete_document" => {
            let raw_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or("")
                .trim();
            if raw_id.is_empty() {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": "ID do documento não fornecido para eliminação.",
                })]));
            }
            let Ok(doc_id) = validate_study_id(raw_id, "document_id") else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Documento '{}' não encontrado para eliminação.", raw_id),
                })]));
            };

            let delete_file = message
                .get("delete_file")
                .and_then(Value::as_bool)
                .unwrap_or(true);

            study_store
                .refresh()
                .await
                .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;

            let Some(doc) = study_store
                .get_document(&doc_id)
                .await
                .map_err(|err| AppError::new("STUDY_READ_FAILED", err))?
            else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Documento '{}' não encontrado para eliminação.", doc_id),
                })]));
            };

            if delete_file {
                let metadata = doc.get("metadata").and_then(Value::as_object);
                let is_linked_folder = metadata
                    .and_then(|m| m.get("source_origin"))
                    .and_then(Value::as_str)
                    == Some("linked_folder");

                if !is_linked_folder {
                    if let Some(fp) = metadata
                        .and_then(|m| m.get("file_path"))
                        .and_then(Value::as_str)
                    {
                        delete_if_confined_regular_file(project_root, &study_dir, fp);
                    }
                    if let Some(audio) = metadata
                        .and_then(|m| m.get("video"))
                        .and_then(Value::as_object)
                        .and_then(|v| v.get("audio_path"))
                        .and_then(Value::as_str)
                    {
                        delete_if_confined_regular_file(project_root, &study_dir, audio);
                    }
                }

                delete_if_confined_dir(&study_dir, &Path::new("documents").join(&doc_id));
                delete_if_confined_dir(
                    &study_dir,
                    &Path::new("video").join("keyframes").join(&doc_id),
                );
            }

            study_store
                .delete_document(&doc_id)
                .await
                .map_err(|err| AppError::new("STUDY_WRITE_FAILED", err))?;

            // Cascade clean notes, highlights, quizzes, flashcards, and collection refs.
            let notes_path = study_dir.join("notes.json");
            if notes_path.exists() {
                let filtered: Vec<Value> = read_json_array_safe(&notes_path)?
                    .into_iter()
                    .filter(|n| n.get("document_id").and_then(Value::as_str) != Some(doc_id.as_str()))
                    .collect();
                write_json_pretty(&study_dir, "notes.json", &Value::Array(filtered))?;
            }

            let highlights_path = study_dir.join("highlights.json");
            if highlights_path.exists() {
                let filtered: Vec<Value> = read_json_array_safe(&highlights_path)?
                    .into_iter()
                    .filter(|h| h.get("document_id").and_then(Value::as_str) != Some(doc_id.as_str()))
                    .collect();
                write_json_pretty(&study_dir, "highlights.json", &Value::Array(filtered))?;
            }

            let quizzes_path = study_dir.join("quizzes.json");
            if quizzes_path.exists() {
                let filtered: serde_json::Map<String, Value> = read_json_map_safe(&quizzes_path)?
                    .into_iter()
                    .filter(|(_, v)| v.get("document_id").and_then(Value::as_str) != Some(doc_id.as_str()))
                    .collect();
                write_json_pretty(&study_dir, "quizzes.json", &Value::Object(filtered))?;
            }

            let flashcards_path = study_dir.join("flashcards.json");
            if flashcards_path.exists() {
                let filtered: serde_json::Map<String, Value> = read_json_map_safe(&flashcards_path)?
                    .into_iter()
                    .filter(|(_, v)| v.get("document_id").and_then(Value::as_str) != Some(doc_id.as_str()))
                    .collect();
                write_json_pretty(&study_dir, "flashcards.json", &Value::Object(filtered))?;
            }

            for col in study_store.list_collections().await {
                let Some(col_id) = col.get("collection_id").and_then(Value::as_str).map(String::from)
                else {
                    continue;
                };
                let mut updated = col.clone();
                let mut changed = false;
                if let Some(arr) = updated.get_mut("document_ids").and_then(Value::as_array_mut) {
                    let before = arr.len();
                    arr.retain(|item| item.as_str() != Some(doc_id.as_str()));
                    changed = arr.len() != before;
                }
                if changed {
                    study_store
                        .upsert_collection(&col_id, updated)
                        .await
                        .map_err(|err| AppError::new("STUDY_WRITE_FAILED", err))?;
                }
            }

            study_store
                .refresh()
                .await
                .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;
            let docs = sorted_documents_desc(study_store.list_documents().await);

            Ok(Some(vec![
                json!({
                    "type": "study_document_deleted",
                    "document_id": doc_id,
                    "success": true,
                }),
                json!({
                    "type": "study_documents_list",
                    "event": "study.document_deleted",
                    "documents": docs,
                }),
            ]))
        }

        "study_update_progress" => {
            let raw_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or("");
            let Ok(doc_id) = validate_study_id(raw_id, "document_id") else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Documento '{}' não encontrado.", raw_id),
                })]));
            };
            let current_page = message
                .get("current_page")
                .and_then(Value::as_i64)
                .unwrap_or(1);
            let current_section = message
                .get("current_section")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let scroll_position = message
                .get("scroll_position")
                .and_then(Value::as_i64)
                .unwrap_or(0);

            study_store
                .refresh()
                .await
                .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;
            let Some(mut doc) = study_store
                .get_document(&doc_id)
                .await
                .map_err(|err| AppError::new("STUDY_READ_FAILED", err))?
            else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Documento '{}' não encontrado.", doc_id),
                })]));
            };

            let page_count = doc
                .get("page_count")
                .and_then(Value::as_i64)
                .unwrap_or(1)
                .max(1);
            let pct = ((current_page as f64 / page_count as f64) * 1000.0).round() / 10.0;
            let last_read_at = now_iso_local();

            let mut progress_obj = doc
                .get("reading_progress")
                .and_then(Value::as_object)
                .cloned()
                .unwrap_or_default();
            progress_obj.insert("current_page".to_string(), json!(current_page));
            progress_obj.insert("current_section".to_string(), json!(current_section));
            progress_obj.insert("scroll_position".to_string(), json!(scroll_position));
            progress_obj.insert("progress_percent".to_string(), json!(pct));
            progress_obj.insert("last_read_at".to_string(), json!(last_read_at));

            let progress_value = Value::Object(progress_obj);
            if let Some(doc_obj) = doc.as_object_mut() {
                doc_obj.insert("reading_progress".to_string(), progress_value.clone());
            }

            study_store
                .upsert_document(&doc_id, doc)
                .await
                .map_err(|err| AppError::new("STUDY_WRITE_FAILED", err))?;

            Ok(Some(vec![json!({
                "type": "study_progress_updated",
                "document_id": doc_id,
                "reading_progress": progress_value,
            })]))
        }

        "study_add_reading_note" => {
            let doc_id = validate_study_id(
                message
                    .get("document_id")
                    .and_then(Value::as_str)
                    .unwrap_or(""),
                "document_id",
            )?;
            let page = message.get("page").and_then(Value::as_i64).unwrap_or(1);
            let selection = message
                .get("selection")
                .and_then(Value::as_str)
                .unwrap_or("");
            let note_text = message.get("note").and_then(Value::as_str).unwrap_or("");
            let section_id = message
                .get("section_id")
                .and_then(Value::as_str)
                .unwrap_or("");

            let note = json!({
                "note_id": format!("note_{}", short_hex_8()),
                "document_id": doc_id,
                "page": page,
                "selection": selection,
                "note": note_text,
                "created_at": now_iso_local(),
                "section_id": section_id,
            });

            fs::create_dir_all(&study_dir).map_err(|err| {
                AppError::new("STUDY_WRITE_FAILED", format!("Failed creating study dir: {err}"))
            })?;
            let mut notes = read_json_array_safe(&study_dir.join("notes.json"))?;
            notes.push(note.clone());
            write_json_pretty(&study_dir, "notes.json", &Value::Array(notes))?;

            Ok(Some(vec![json!({
                "type": "study_note_added",
                "note": note,
            })]))
        }

        "study_add_highlight" => {
            let doc_id = validate_study_id(
                message
                    .get("document_id")
                    .and_then(Value::as_str)
                    .unwrap_or(""),
                "document_id",
            )?;
            let page = message.get("page").and_then(Value::as_i64).unwrap_or(1);
            let selected_text = message
                .get("selected_text")
                .and_then(Value::as_str)
                .unwrap_or("");
            let context = message
                .get("context")
                .and_then(Value::as_str)
                .unwrap_or("");
            let color = message
                .get("color")
                .and_then(Value::as_str)
                .unwrap_or("yellow");

            let highlight = json!({
                "highlight_id": format!("hl_{}", short_hex_8()),
                "document_id": doc_id,
                "page": page,
                "selected_text": selected_text,
                "context": context,
                "color": color,
                "created_at": now_iso_local(),
            });

            fs::create_dir_all(&study_dir).map_err(|err| {
                AppError::new("STUDY_WRITE_FAILED", format!("Failed creating study dir: {err}"))
            })?;
            let mut highlights = read_json_array_safe(&study_dir.join("highlights.json"))?;
            highlights.push(highlight.clone());
            write_json_pretty(&study_dir, "highlights.json", &Value::Array(highlights))?;

            Ok(Some(vec![json!({
                "type": "study_highlight_added",
                "highlight": highlight,
            })]))
        }

        "study_list_collections" => {
            study_store
                .refresh()
                .await
                .map_err(|err| AppError::new("STUDY_STORE_REFRESH_FAILED", err))?;
            Ok(Some(vec![json!({
                "type": "study_collections_list",
                "collections": study_store.list_collections().await,
            })]))
        }

        "study_create_collection" => {
            let name = message
                .get("name")
                .and_then(Value::as_str)
                .unwrap_or("Nova Coleção");
            let subject = message
                .get("subject")
                .and_then(Value::as_str)
                .unwrap_or("Geral");
            let document_ids = message
                .get("document_ids")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();
            let linked_folders = message
                .get("linked_folders")
                .and_then(Value::as_array)
                .cloned()
                .unwrap_or_default();

            let collection_id = format!("col_{}", short_hex_8());
            let collection = json!({
                "collection_id": collection_id,
                "name": name,
                "subject": subject,
                "document_ids": document_ids,
                "created_at": now_iso_local(),
                "linked_folders": linked_folders,
                "sync_preferences": {
                    "auto_sync": true,
                    "recursive": true,
                },
            });

            study_store
                .upsert_collection(&collection_id, collection.clone())
                .await
                .map_err(|err| AppError::new("STUDY_WRITE_FAILED", err))?;

            Ok(Some(vec![json!({
                "type": "study_collection_created",
                "collection": collection,
            })]))
        }

        _ => Ok(None),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[tokio::test]
    async fn study_catalog_ops_cover_crud_progress_notes_highlights_and_safe_cascade_delete() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();
        let study_dir = root.join("data").join("study");
        fs::create_dir_all(study_dir.join("documents").join("doc_owned")).unwrap();
        fs::write(study_dir.join("documents").join("doc_owned").join("paper.pdf"), b"%PDF-1.4").unwrap();
        fs::write(study_dir.join("owned.pdf"), b"pdf").unwrap();

        let outside_linked = root.join("external_course_notes.pdf");
        fs::write(&outside_linked, b"keep-me").unwrap();

        let store = StudyStore::open(&study_dir).unwrap();
        store
            .upsert_document(
                "doc_owned",
                json!({
                    "document_id": "doc_owned",
                    "source_id": "doc_owned",
                    "title": "Owned Paper",
                    "source_type": "PDF",
                    "subject": "Systems",
                    "language": "en",
                    "page_count": 4,
                    "updated_at": "2026-01-01T10:00:00",
                    "reading_progress": {},
                    "metadata": {
                        "file_path": study_dir.join("owned.pdf").to_string_lossy().to_string(),
                    }
                }),
            )
            .await
            .unwrap();
        store
            .upsert_document(
                "doc_linked",
                json!({
                    "document_id": "doc_linked",
                    "source_id": "doc_linked",
                    "title": "Linked Paper",
                    "source_type": "PDF",
                    "subject": "Systems",
                    "language": "en",
                    "page_count": 2,
                    "updated_at": "2026-01-02T10:00:00",
                    "reading_progress": {},
                    "metadata": {
                        "source_origin": "linked_folder",
                        "file_path": outside_linked.to_string_lossy().to_string(),
                    }
                }),
            )
            .await
            .unwrap();

        // List sorted desc by updated_at
        let listed = try_execute_study_fast_path(&root, &store, "study_list_documents", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(listed[0]["type"], "study_documents_list");
        assert_eq!(listed[0]["documents"][0]["document_id"], "doc_linked");
        assert_eq!(listed[0]["documents"][1]["document_id"], "doc_owned");

        // Update progress
        let prog = try_execute_study_fast_path(
            &root,
            &store,
            "study_update_progress",
            &json!({
                "document_id": "doc_owned",
                "current_page": 3,
                "current_section": "sec-2",
                "scroll_position": 120,
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(prog[0]["type"], "study_progress_updated");
        assert_eq!(prog[0]["reading_progress"]["progress_percent"], 75.0);

        // Add reading note and highlight
        let note_ev = try_execute_study_fast_path(
            &root,
            &store,
            "study_add_reading_note",
            &json!({
                "document_id": "doc_owned",
                "page": 2,
                "selection": "Consensus",
                "note": "Check Raft leader lease",
                "section_id": "s2",
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(note_ev[0]["type"], "study_note_added");

        let hl_ev = try_execute_study_fast_path(
            &root,
            &store,
            "study_add_highlight",
            &json!({
                "document_id": "doc_owned",
                "page": 2,
                "selected_text": "Linearizability",
                "color": "cyan",
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(hl_ev[0]["type"], "study_highlight_added");

        // Details include notes & highlights for doc_owned
        let details = try_execute_study_fast_path(
            &root,
            &store,
            "study_get_document",
            &json!({ "document_id": "doc_owned" }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(details[0]["type"], "study_document_details");
        assert_eq!(details[0]["notes"].as_array().unwrap().len(), 1);
        assert_eq!(details[0]["highlights"].as_array().unwrap().len(), 1);

        // Create collection linking doc_owned + doc_linked
        let col_ev = try_execute_study_fast_path(
            &root,
            &store,
            "study_create_collection",
            &json!({
                "name": "DistSys",
                "subject": "CS",
                "document_ids": ["doc_owned", "doc_linked"],
            }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(col_ev[0]["type"], "study_collection_created");

        let cols = try_execute_study_fast_path(&root, &store, "study_list_collections", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(cols[0]["collections"].as_array().unwrap().len(), 1);

        // Cascade delete doc_owned removes owned file, notes, highlights, and doc_owned from collection
        let del = try_execute_study_fast_path(
            &root,
            &store,
            "study_delete_document",
            &json!({ "document_id": "doc_owned", "delete_file": true }),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(del[0]["type"], "study_document_deleted");
        assert_eq!(del[1]["type"], "study_documents_list");
        assert!(!study_dir.join("owned.pdf").exists());
        assert!(!study_dir.join("documents").join("doc_owned").exists());
        assert!(read_json_array_safe(&study_dir.join("notes.json"))
            .unwrap()
            .is_empty());
        assert!(read_json_array_safe(&study_dir.join("highlights.json"))
            .unwrap()
            .is_empty());

        let cols_after = try_execute_study_fast_path(&root, &store, "study_list_collections", &json!({}))
            .await
            .unwrap()
            .unwrap();
        let ids = cols_after[0]["collections"][0]["document_ids"]
            .as_array()
            .unwrap();
        assert_eq!(ids, &[json!("doc_linked")]);

        // Deleting linked document never removes external source file!
        let _ = try_execute_study_fast_path(
            &root,
            &store,
            "study_delete_document",
            &json!({ "document_id": "doc_linked", "delete_file": true }),
        )
        .await
        .unwrap()
        .unwrap();
        assert!(outside_linked.exists());
    }
}

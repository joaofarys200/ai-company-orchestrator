//! Native Rust handlers for deterministic Study catalog operations (`StudyStore` + JSON stores).
//!
//! Covers document listing, document detail lookup (with notes & highlights),
//! cascade deletion (preserving non-owned `linked_folder` source files),
//! reading progress persistence, notes, highlights, and collection CRUD.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{Duration, Local};
use serde_json::{json, Value};
use uuid::Uuid;

use crate::error::AppError;
use crate::permissions::path_jail::{ensure_confined_existing_file, resolve_confined_path};
use crate::storage::atomic_fs::{atomic_write_string, read_bounded_bytes};
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
                .filter(|item| {
                    item.get("document_id").and_then(Value::as_str) == Some(doc_id.as_str())
                })
                .collect();

            let all_highlights = read_json_array_safe(&study_dir.join("highlights.json"))?;
            let doc_highlights: Vec<Value> = all_highlights
                .into_iter()
                .filter(|item| {
                    item.get("document_id").and_then(Value::as_str) == Some(doc_id.as_str())
                })
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
                    .filter(|n| {
                        n.get("document_id").and_then(Value::as_str) != Some(doc_id.as_str())
                    })
                    .collect();
                write_json_pretty(&study_dir, "notes.json", &Value::Array(filtered))?;
            }

            let highlights_path = study_dir.join("highlights.json");
            if highlights_path.exists() {
                let filtered: Vec<Value> = read_json_array_safe(&highlights_path)?
                    .into_iter()
                    .filter(|h| {
                        h.get("document_id").and_then(Value::as_str) != Some(doc_id.as_str())
                    })
                    .collect();
                write_json_pretty(&study_dir, "highlights.json", &Value::Array(filtered))?;
            }

            let quizzes_path = study_dir.join("quizzes.json");
            if quizzes_path.exists() {
                let filtered: serde_json::Map<String, Value> = read_json_map_safe(&quizzes_path)?
                    .into_iter()
                    .filter(|(_, v)| {
                        v.get("document_id").and_then(Value::as_str) != Some(doc_id.as_str())
                    })
                    .collect();
                write_json_pretty(&study_dir, "quizzes.json", &Value::Object(filtered))?;
            }

            let flashcards_path = study_dir.join("flashcards.json");
            if flashcards_path.exists() {
                let filtered: serde_json::Map<String, Value> =
                    read_json_map_safe(&flashcards_path)?
                        .into_iter()
                        .filter(|(_, v)| {
                            v.get("document_id").and_then(Value::as_str) != Some(doc_id.as_str())
                        })
                        .collect();
                write_json_pretty(&study_dir, "flashcards.json", &Value::Object(filtered))?;
            }

            for col in study_store.list_collections().await {
                let Some(col_id) = col
                    .get("collection_id")
                    .and_then(Value::as_str)
                    .map(String::from)
                else {
                    continue;
                };
                let mut updated = col.clone();
                let mut changed = false;
                if let Some(arr) = updated
                    .get_mut("document_ids")
                    .and_then(Value::as_array_mut)
                {
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
                AppError::new(
                    "STUDY_WRITE_FAILED",
                    format!("Failed creating study dir: {err}"),
                )
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
            let context = message.get("context").and_then(Value::as_str).unwrap_or("");
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
                AppError::new(
                    "STUDY_WRITE_FAILED",
                    format!("Failed creating study dir: {err}"),
                )
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

        "study_get_document_file" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let _clean_id = validate_study_id(&doc_id, "document_id")?;
            let Some(doc) = study_store
                .get_document(&doc_id)
                .await
                .map_err(|err| AppError::new("STUDY_STORE_READ_FAILED", err))?
            else {
                return Ok(Some(vec![json!({
                    "type": "study_document_file_result",
                    "document_id": doc_id,
                    "error": format!("Documento '{}' não encontrado.", doc_id),
                })]));
            };

            let raw_stored = doc
                .get("stored_path")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim();
            let filename = doc
                .get("filename")
                .and_then(Value::as_str)
                .filter(|s| !s.trim().is_empty())
                .map(str::to_string)
                .or_else(|| {
                    if raw_stored.is_empty() {
                        None
                    } else {
                        Path::new(raw_stored)
                            .file_name()
                            .and_then(|n| n.to_str())
                            .map(str::to_string)
                    }
                })
                .unwrap_or_else(|| format!("{doc_id}.bin"));

            if raw_stored.is_empty() {
                return Ok(Some(vec![json!({
                    "type": "study_document_file_result",
                    "document_id": doc_id,
                    "filename": filename,
                    "error": "O documento não possui ficheiro local associado.",
                })]));
            }

            let resolved = resolve_existing_study_file(project_root, &study_dir, raw_stored);
            let Some(canon_path) = resolved else {
                return Ok(Some(vec![json!({
                    "type": "study_document_file_result",
                    "document_id": doc_id,
                    "filename": filename,
                    "error": "Ficheiro não encontrado ou fora da diretoria permitida.",
                })]));
            };

            match read_bounded_bytes(project_root, &canon_path, MAX_DOCUMENT_FILE_BYTES) {
                Ok(bytes) => {
                    let encoded = encode_base64(&bytes);
                    Ok(Some(vec![json!({
                        "type": "study_document_file_result",
                        "document_id": doc_id,
                        "content_base64": encoded,
                        "filename": filename,
                    })]))
                }
                Err(err) => Ok(Some(vec![json!({
                    "type": "study_document_file_result",
                    "document_id": doc_id,
                    "filename": filename,
                    "error": err.message,
                })])),
            }
        }

        "study_get_document_ast" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let ast_path = study_dir.join("documents").join(&clean_id).join("ast.json");
            if !ast_path.is_file() {
                // Keep cold PyMuPDF PDF extraction and lazy fallback on StudyWorker.
                return Ok(None);
            }
            let ast = read_json_object_file_safe(&study_dir, &ast_path)?;
            if ast.is_null() {
                return Ok(None);
            }
            Ok(Some(vec![json!({
                "type": "study_document_ast_result",
                "document_id": doc_id,
                "ast": ast,
            })]))
        }

        "study_get_academic_reasoning" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let dossier_path = study_dir
                .join("documents")
                .join(&clean_id)
                .join("reasoning_dossier.json");
            let dossier = if dossier_path.is_file() {
                let parsed = read_json_object_file_safe(&study_dir, &dossier_path)?;
                if parsed.is_object() {
                    parsed
                } else {
                    Value::Null
                }
            } else {
                Value::Null
            };
            Ok(Some(vec![json!({
                "type": "study_academic_reasoning_result",
                "document_id": doc_id,
                "dossier": dossier,
            })]))
        }

        "study_get_editorial_plan" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let doc_dir = study_dir.join("documents").join(&clean_id);
            let plan_path = doc_dir.join("editorial_study_plan.json");
            let dossier_path = doc_dir.join("reasoning_dossier.json");

            let plan = if plan_path.is_file() {
                let parsed = read_json_object_file_safe(&study_dir, &plan_path)?;
                if parsed.is_object() {
                    parsed
                } else {
                    Value::Null
                }
            } else {
                Value::Null
            };

            let dossier = if dossier_path.is_file() {
                let parsed = read_json_object_file_safe(&study_dir, &dossier_path)?;
                if parsed.is_object() {
                    parsed
                } else {
                    Value::Null
                }
            } else {
                Value::Null
            };

            let plan_status = compute_editorial_plan_status(&doc_id, &plan, &dossier);
            Ok(Some(vec![json!({
                "type": "study_editorial_plan_result",
                "document_id": doc_id,
                "plan": plan,
                "plan_status": plan_status,
            })]))
        }

        "study_get_generated_document_status" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let status = compute_generated_document_status(&study_dir, &clean_id, &doc_id)?;
            Ok(Some(vec![json!({
                "type": "study_generated_document_status_result",
                "document_id": doc_id,
                "status": status,
            })]))
        }

        "study_get_generated_document_file" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let fmt = message
                .get("format")
                .and_then(Value::as_str)
                .unwrap_or("pdf")
                .trim()
                .to_ascii_lowercase();
            let version = message.get("version").and_then(Value::as_i64);
            let event = build_generated_document_file_event(
                project_root,
                &study_dir,
                &clean_id,
                &doc_id,
                &fmt,
                version,
            )?;
            Ok(Some(vec![event]))
        }

        "study_review_flashcard" => {
            let card_id = message
                .get("card_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let rating = message
                .get("rating")
                .or_else(|| message.get("action"))
                .and_then(Value::as_str)
                .unwrap_or("Good")
                .trim()
                .to_string();
            if card_id.is_empty() {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": "card_id é obrigatório para rever flashcard.",
                })]));
            }
            let cards = study_store
                .list_flashcards(None)
                .await
                .map_err(|err| AppError::new("STUDY_STORE_READ_FAILED", err))?;
            let Some(mut card) = cards
                .into_iter()
                .find(|c| c.get("card_id").and_then(Value::as_str) == Some(card_id.as_str()))
            else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Flashcard '{}' não encontrado.", card_id),
                })]));
            };

            apply_legacy_flashcard_review(&mut card, &rating);
            study_store
                .upsert_flashcard(&card_id, card.clone())
                .await
                .map_err(|err| AppError::new("STUDY_STORE_WRITE_FAILED", err))?;

            Ok(Some(vec![json!({
                "type": "study_flashcard_reviewed",
                "flashcard": card,
            })]))
        }

        "study_get_course_details" => {
            let cid = message
                .get("collection_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let _clean_cid = validate_study_id(&cid, "collection_id")?;
            let collections = study_store.list_collections().await;
            let Some(col) = collections
                .into_iter()
                .find(|c| c.get("collection_id").and_then(Value::as_str) == Some(cid.as_str()))
            else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Disciplina '{}' não encontrada.", cid),
                })]));
            };

            let doc_ids: Vec<String> = col
                .get("document_ids")
                .and_then(Value::as_array)
                .map(|arr| {
                    arr.iter()
                        .filter_map(Value::as_str)
                        .map(str::to_string)
                        .collect()
                })
                .unwrap_or_default();

            let all_docs = study_store.list_documents().await;
            let mut materials = Vec::new();
            for doc in all_docs {
                let did = doc
                    .get("document_id")
                    .and_then(Value::as_str)
                    .unwrap_or_default();
                let doc_col = doc
                    .get("metadata")
                    .and_then(|m| m.get("collection_id"))
                    .and_then(Value::as_str);
                if doc_ids.iter().any(|x| x == did) || doc_col == Some(cid.as_str()) {
                    materials.push(doc);
                }
            }
            let materials = sorted_documents_desc(materials);
            Ok(Some(vec![json!({
                "type": "study_course_details",
                "collection_id": cid,
                "name": col.get("name").and_then(Value::as_str).unwrap_or_default(),
                "subject": col.get("subject").and_then(Value::as_str).unwrap_or("Geral"),
                "linked_folders": col.get("linked_folders").cloned().unwrap_or_else(|| json!([])),
                "materials": materials,
            })]))
        }

        "study_update_video_progress" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let _clean_id = validate_study_id(&doc_id, "document_id")?;
            let timestamp = message
                .get("timestamp")
                .and_then(Value::as_f64)
                .unwrap_or(0.0)
                .max(0.0);
            let progress_percent = message.get("progress_percent").and_then(Value::as_f64);

            let Some(mut doc) = study_store
                .get_document(&doc_id)
                .await
                .map_err(|err| AppError::new("STUDY_STORE_READ_FAILED", err))?
            else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Documento de vídeo '{}' não encontrado.", doc_id),
                })]));
            };

            let now = now_iso_local();
            if !doc.get("metadata").map_or(false, Value::is_object) {
                if let Some(obj) = doc.as_object_mut() {
                    obj.insert("metadata".to_string(), json!({}));
                }
            }
            let pct = progress_percent
                .map(|p| p.clamp(0.0, 100.0))
                .unwrap_or_else(|| {
                    doc.get("completion_percentage")
                        .and_then(Value::as_f64)
                        .unwrap_or(0.0)
                });
            let progress_obj = json!({
                "last_timestamp": timestamp,
                "timestamp": timestamp,
                "progress_percent": pct,
                "updated_at": now,
            });
            if let Some(obj) = doc.as_object_mut() {
                if progress_percent.is_some() {
                    obj.insert("completion_percentage".to_string(), json!(pct));
                }
                if let Some(meta) = obj.get_mut("metadata").and_then(Value::as_object_mut) {
                    meta.insert("video_progress".to_string(), progress_obj.clone());
                    if progress_percent.is_some() {
                        meta.insert("progress_percent".to_string(), json!(pct));
                    }
                }
            }
            study_store
                .upsert_document(&doc_id, doc)
                .await
                .map_err(|err| AppError::new("STUDY_STORE_WRITE_FAILED", err))?;

            Ok(Some(vec![json!({
                "type": "study_video_progress_updated",
                "document_id": doc_id,
                "progress": progress_obj,
            })]))
        }

        "study_search_video_transcript" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let query = message
                .get("query")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();

            let Some(doc) = study_store
                .get_document(&doc_id)
                .await
                .map_err(|err| AppError::new("STUDY_STORE_READ_FAILED", err))?
            else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Documento '{}' não encontrado.", doc_id),
                })]));
            };

            let (occurrences, results) =
                search_transcript_segments(&study_dir, &clean_id, &doc, &query);
            Ok(Some(vec![json!({
                "type": "study_search_video_transcript_result",
                "document_id": doc_id,
                "query": query,
                "occurrences": occurrences,
                "results": results,
            })]))
        }

        "study_get_video_context" => {
            let doc_id = message
                .get("document_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim()
                .to_string();
            let clean_id = validate_study_id(&doc_id, "document_id")?;
            let timestamp = message
                .get("timestamp")
                .and_then(Value::as_f64)
                .unwrap_or(0.0)
                .max(0.0);

            let Some(doc) = study_store
                .get_document(&doc_id)
                .await
                .map_err(|err| AppError::new("STUDY_STORE_READ_FAILED", err))?
            else {
                return Ok(Some(vec![json!({
                    "type": "study_error",
                    "message": format!("Documento '{}' não encontrado.", doc_id),
                })]));
            };

            let context = build_video_context_snapshot(&study_dir, &clean_id, &doc, timestamp);
            Ok(Some(vec![json!({
                "type": "study_video_context_result",
                "document_id": doc_id,
                "timestamp": timestamp,
                "context": context,
            })]))
        }

        _ => Ok(None),
    }
}

const MAX_DOCUMENT_FILE_BYTES: usize = 64 * 1024 * 1024;
const BASE64_ALPHABET: &[u8; 64] =
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/// Pure-Rust RFC 4648 base64 encoder avoiding any extra crate dependency.
pub(crate) fn encode_base64(input: &[u8]) -> String {
    if input.is_empty() {
        return String::new();
    }
    let mut out = String::with_capacity(((input.len() + 2) / 3) * 4);
    for chunk in input.chunks(3) {
        let b0 = chunk[0] as usize;
        let b1 = if chunk.len() > 1 {
            chunk[1] as usize
        } else {
            0
        };
        let b2 = if chunk.len() > 2 {
            chunk[2] as usize
        } else {
            0
        };
        let triple = (b0 << 16) | (b1 << 8) | b2;
        out.push(BASE64_ALPHABET[(triple >> 18) & 0x3F] as char);
        out.push(BASE64_ALPHABET[(triple >> 12) & 0x3F] as char);
        if chunk.len() > 1 {
            out.push(BASE64_ALPHABET[(triple >> 6) & 0x3F] as char);
        } else {
            out.push('=');
        }
        if chunk.len() > 2 {
            out.push(BASE64_ALPHABET[triple & 0x3F] as char);
        } else {
            out.push('=');
        }
    }
    out
}

pub(crate) fn resolve_existing_study_file(
    project_root: &Path,
    study_dir: &Path,
    raw_path: &str,
) -> Option<PathBuf> {
    let trimmed = raw_path.trim();
    if trimmed.is_empty() {
        return None;
    }
    let candidate = Path::new(trimmed);
    if candidate.is_absolute() {
        return ensure_confined_existing_file(study_dir, candidate)
            .ok()
            .or_else(|| ensure_confined_existing_file(project_root, candidate).ok());
    }
    let under_study = study_dir.join(candidate);
    if let Ok(canon) = ensure_confined_existing_file(study_dir, &under_study) {
        return Some(canon);
    }
    let under_root = project_root.join(candidate);
    ensure_confined_existing_file(project_root, &under_root).ok()
}

pub(crate) fn read_json_object_file_safe(
    study_dir: &Path,
    target: &Path,
) -> Result<Value, AppError> {
    let Ok(canon) = ensure_confined_existing_file(study_dir, target) else {
        return Ok(Value::Null);
    };
    let raw = match fs::read_to_string(&canon) {
        Ok(content) => content,
        Err(err) => {
            return Err(AppError::new(
                "STUDY_FILE_READ_FAILED",
                format!("Failed reading {}: {err}", canon.display()),
            ))
        }
    };
    Ok(serde_json::from_str(&raw).unwrap_or(Value::Null))
}

fn compute_editorial_plan_status(doc_id: &str, plan: &Value, dossier: &Value) -> Value {
    if !plan.is_object() {
        return json!({
            "document_id": doc_id,
            "has_dossier": dossier.is_object(),
            "has_plan": false,
            "status": if dossier.is_object() { "NOT_GENERATED" } else { "WAITING_DOSSIER" },
            "is_up_to_date": false,
            "reason": if dossier.is_object() {
                "Plano editorial ainda não gerado."
            } else {
                "Aguarda conclusão do Dossier Académico."
            },
            "validation_status": Value::Null,
            "updated_at": Value::Null,
        });
    }

    let meta = plan.get("metadata").unwrap_or(&Value::Null);
    let plan_status_str = meta
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("COMPLETED");
    let validation_status = plan
        .get("qa_report")
        .and_then(|q| q.get("validation_status"))
        .cloned()
        .unwrap_or(Value::Null);
    let updated_at = meta.get("created_at").cloned().unwrap_or(Value::Null);

    let mut is_up_to_date = plan_status_str == "COMPLETED";
    let mut reason = "Plano editorial atualizado.".to_string();

    if dossier.is_object() {
        let dossier_id = dossier
            .get("dossier_id")
            .and_then(Value::as_str)
            .unwrap_or_default();
        let plan_dossier_id = meta
            .get("dossier_id")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if !dossier_id.is_empty() && !plan_dossier_id.is_empty() && dossier_id != plan_dossier_id {
            is_up_to_date = false;
            reason = "Dossier académico mais recente disponível.".to_string();
        } else {
            let d_sha = dossier
                .get("source_sha256")
                .and_then(Value::as_str)
                .unwrap_or_default();
            let p_sha = meta
                .get("source_sha256")
                .and_then(Value::as_str)
                .unwrap_or_default();
            if !d_sha.is_empty() && !p_sha.is_empty() && d_sha != p_sha {
                is_up_to_date = false;
                reason = "Fonte documental alterada desde o último plano.".to_string();
            }
        }
    }

    json!({
        "document_id": doc_id,
        "has_dossier": dossier.is_object(),
        "has_plan": true,
        "status": if is_up_to_date { plan_status_str } else { "STALE" },
        "is_up_to_date": is_up_to_date,
        "reason": reason,
        "validation_status": validation_status,
        "updated_at": updated_at,
    })
}

fn compute_generated_document_status(
    study_dir: &Path,
    clean_id: &str,
    doc_id: &str,
) -> Result<Value, AppError> {
    let doc_dir = study_dir.join("documents").join(clean_id);
    let result_path = doc_dir.join("document_generation_result.json");
    let dev_path = doc_dir.join("developed_study_content.json");
    let plan_path = doc_dir.join("editorial_study_plan.json");

    let plan = if plan_path.is_file() {
        read_json_object_file_safe(study_dir, &plan_path)?
    } else {
        Value::Null
    };
    let gen_result = if result_path.is_file() {
        read_json_object_file_safe(study_dir, &result_path)?
    } else {
        Value::Null
    };
    let dev_content = if dev_path.is_file() {
        read_json_object_file_safe(study_dir, &dev_path)?
    } else {
        Value::Null
    };

    let has_plan = plan.is_object();
    let has_result = gen_result.is_object();
    let mut is_stale = false;
    let mut stale_reasons: Vec<String> = Vec::new();

    if has_plan && dev_content.is_object() {
        let plan_id = plan
            .get("metadata")
            .and_then(|m| m.get("plan_id"))
            .and_then(Value::as_str)
            .unwrap_or_default();
        let dev_plan_id = dev_content
            .get("plan_id")
            .and_then(Value::as_str)
            .unwrap_or_default();
        if !plan_id.is_empty() && !dev_plan_id.is_empty() && plan_id != dev_plan_id {
            is_stale = true;
            stale_reasons
                .push("O plano editorial foi atualizado após a geração do documento.".into());
        }
    }

    let pdf_available =
        find_generated_artifact_path(study_dir, clean_id, &gen_result, "pdf", None).is_some();
    let docx_available =
        find_generated_artifact_path(study_dir, clean_id, &gen_result, "docx", None).is_some();

    let raw_status = gen_result
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or_else(|| {
            if has_result {
                "COMPLETED"
            } else if has_plan {
                "READY"
            } else {
                "NOT_STARTED"
            }
        });

    let effective_status = if is_stale && has_result {
        "STALE"
    } else {
        raw_status
    };

    Ok(json!({
        "document_id": doc_id,
        "has_plan": has_plan,
        "has_result": has_result,
        "has_developed_content": dev_content.is_object(),
        "status": effective_status,
        "is_stale": is_stale,
        "stale_reasons": stale_reasons,
        "pdf_available": pdf_available,
        "docx_available": docx_available,
        "result": if has_result { gen_result } else { Value::Null },
    }))
}

fn find_generated_artifact_path(
    study_dir: &Path,
    clean_id: &str,
    gen_result: &Value,
    fmt: &str,
    version: Option<i64>,
) -> Option<PathBuf> {
    let doc_dir = study_dir.join("documents").join(clean_id);
    if let Some(target_v) = version {
        if let Some(versions) = gen_result.get("versions").and_then(Value::as_array) {
            for v in versions {
                if v.get("version").and_then(Value::as_i64) == Some(target_v) {
                    let key = if fmt == "docx" {
                        "docx_path"
                    } else {
                        "pdf_path"
                    };
                    if let Some(p) = v.get(key).and_then(Value::as_str) {
                        if let Some(canon) = resolve_existing_study_file(study_dir, &doc_dir, p) {
                            return Some(canon);
                        }
                    }
                }
            }
        }
    }

    let key = if fmt == "docx" {
        "docx_path"
    } else {
        "pdf_path"
    };
    if let Some(p) = gen_result.get(key).and_then(Value::as_str) {
        if let Some(canon) = resolve_existing_study_file(study_dir, &doc_dir, p) {
            return Some(canon);
        }
    }
    if let Some(artifacts) = gen_result.get("artifacts").and_then(Value::as_object) {
        if let Some(p) = artifacts.get(fmt).and_then(Value::as_str) {
            if let Some(canon) = resolve_existing_study_file(study_dir, &doc_dir, p) {
                return Some(canon);
            }
        }
    }

    let candidates = [
        doc_dir.join(format!("generated_study_document.{fmt}")),
        doc_dir.join(format!("generated_document.{fmt}")),
        doc_dir
            .join("output")
            .join(format!("generated_study_document.{fmt}")),
    ];
    for c in candidates {
        if let Ok(canon) = ensure_confined_existing_file(&doc_dir, &c) {
            return Some(canon);
        }
    }
    None
}

fn build_generated_document_file_event(
    project_root: &Path,
    study_dir: &Path,
    clean_id: &str,
    doc_id: &str,
    fmt: &str,
    version: Option<i64>,
) -> Result<Value, AppError> {
    let mime = match fmt {
        "pdf" => "application/pdf",
        "docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        _ => {
            return Ok(json!({
                "type": "study_generated_document_file_result",
                "document_id": doc_id,
                "format": fmt,
                "filename": format!("{clean_id}.{fmt}"),
                "file_path": "",
                "size_bytes": 0,
                "mime_type": "application/octet-stream",
                "base64_data": "",
                "error": format!("Formato '{}' não suportado. Use 'pdf' ou 'docx'.", fmt),
            }));
        }
    };

    let doc_dir = study_dir.join("documents").join(clean_id);
    let result_path = doc_dir.join("document_generation_result.json");
    let gen_result = if result_path.is_file() {
        read_json_object_file_safe(study_dir, &result_path)?
    } else {
        Value::Null
    };

    let Some(artifact_path) =
        find_generated_artifact_path(study_dir, clean_id, &gen_result, fmt, version)
    else {
        return Ok(json!({
            "type": "study_generated_document_file_result",
            "document_id": doc_id,
            "format": fmt,
            "filename": format!("{clean_id}.{fmt}"),
            "file_path": "",
            "size_bytes": 0,
            "mime_type": mime,
            "base64_data": "",
            "error": format!("Ficheiro {} gerado não encontrado para '{}'.", fmt.to_uppercase(), doc_id),
        }));
    };

    let bytes = read_bounded_bytes(project_root, &artifact_path, MAX_DOCUMENT_FILE_BYTES)?;
    let filename = artifact_path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("documento.pdf")
        .to_string();
    let encoded = encode_base64(&bytes);

    Ok(json!({
        "type": "study_generated_document_file_result",
        "document_id": doc_id,
        "format": fmt,
        "filename": filename,
        "file_path": artifact_path.to_string_lossy().to_string(),
        "size_bytes": bytes.len(),
        "mime_type": mime,
        "base64_data": encoded,
    }))
}

fn apply_legacy_flashcard_review(card: &mut Value, rating: &str) {
    let mut reps = card
        .get("repetitions")
        .and_then(Value::as_i64)
        .unwrap_or(0)
        .max(0);
    let mut ef = card
        .get("ease_factor")
        .and_then(Value::as_f64)
        .unwrap_or(2.5);
    let mut interval_days = card
        .get("interval_days")
        .and_then(Value::as_f64)
        .unwrap_or(1.0);

    match rating.trim().to_ascii_lowercase().as_str() {
        "again" | "fail" | "missed" => {
            reps = 0;
            interval_days = 1.0;
            ef = (ef - 0.20).max(1.3);
        }
        "hard" => {
            if reps == 0 {
                interval_days = 1.0;
            } else {
                interval_days = (interval_days * 1.2).max(1.0);
            }
            reps += 1;
            ef = (ef - 0.14).max(1.3);
        }
        "easy" => {
            if reps == 0 {
                interval_days = 4.0;
            } else if reps == 1 {
                interval_days = 6.0 * ef;
            } else {
                interval_days = (interval_days * ef * 1.3).max(1.0);
            }
            reps += 1;
            ef = (ef + 0.15).min(3.0);
        }
        _ => {
            // "Good"
            if reps == 0 {
                interval_days = 1.0;
            } else if reps == 1 {
                interval_days = 6.0;
            } else {
                interval_days = (interval_days * ef).max(1.0);
            }
            reps += 1;
        }
    }

    let interval_days = (interval_days * 100.0).round() / 100.0;
    let ef = (ef * 10000.0).round() / 10000.0;
    let now = Local::now();
    let next_review = now + Duration::seconds((interval_days * 86_400.0).round() as i64);

    if let Some(obj) = card.as_object_mut() {
        obj.insert("repetitions".to_string(), json!(reps));
        obj.insert("ease_factor".to_string(), json!(ef));
        obj.insert("interval_days".to_string(), json!(interval_days));
        obj.insert("last_reviewed".to_string(), json!(now.to_rfc3339()));
        obj.insert("next_review".to_string(), json!(next_review.to_rfc3339()));
        obj.insert(
            "next_review_at".to_string(),
            json!(next_review.to_rfc3339()),
        );
        obj.insert("last_rating".to_string(), json!(rating));
    }
}

fn load_video_segments(study_dir: &Path, clean_id: &str, doc: &Value) -> Vec<Value> {
    if let Some(arr) = doc
        .get("metadata")
        .and_then(|m| m.get("transcript_segments"))
        .and_then(Value::as_array)
    {
        if !arr.is_empty() {
            return arr.clone();
        }
    }
    let transcript_path = study_dir
        .join("documents")
        .join(clean_id)
        .join("transcript.json");
    if let Ok(parsed) = read_json_object_file_safe(study_dir, &transcript_path) {
        if let Some(arr) = parsed.as_array() {
            return arr.clone();
        }
        if let Some(arr) = parsed.get("segments").and_then(Value::as_array) {
            return arr.clone();
        }
    }
    Vec::new()
}

fn search_transcript_segments(
    study_dir: &Path,
    clean_id: &str,
    doc: &Value,
    query: &str,
) -> (usize, Vec<Value>) {
    let needle = query.trim().to_lowercase();
    if needle.is_empty() {
        return (0, Vec::new());
    }
    let segments = load_video_segments(study_dir, clean_id, doc);
    let mut matches = Vec::new();
    let mut total_occurrences = 0usize;
    for seg in segments {
        let text = seg.get("text").and_then(Value::as_str).unwrap_or_default();
        let lower = text.to_lowercase();
        let count = lower.match_indices(&needle).count();
        if count > 0 {
            total_occurrences += count;
            let start = seg
                .get("start")
                .or_else(|| seg.get("timestamp"))
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            let end = seg.get("end").and_then(Value::as_f64).unwrap_or(start);
            matches.push(json!({
                "start": start,
                "end": end,
                "timestamp": start,
                "text": text,
                "occurrences": count,
            }));
        }
    }
    (total_occurrences, matches)
}

fn build_video_context_snapshot(
    study_dir: &Path,
    clean_id: &str,
    doc: &Value,
    timestamp: f64,
) -> Value {
    let segments = load_video_segments(study_dir, clean_id, doc);
    let mut nearby_segments = Vec::new();
    for seg in segments {
        let start = seg
            .get("start")
            .or_else(|| seg.get("timestamp"))
            .and_then(Value::as_f64)
            .unwrap_or(0.0);
        let end = seg
            .get("end")
            .and_then(Value::as_f64)
            .unwrap_or(start + 10.0);
        if end >= timestamp - 30.0 && start <= timestamp + 30.0 {
            nearby_segments.push(seg);
        }
    }

    let video_notes = doc
        .get("metadata")
        .and_then(|m| m.get("video_notes"))
        .cloned()
        .unwrap_or_else(|| json!([]));
    let key_frames = doc
        .get("metadata")
        .and_then(|m| m.get("key_frames"))
        .cloned()
        .unwrap_or_else(|| json!([]));

    json!({
        "document_id": doc.get("document_id").cloned().unwrap_or_else(|| json!(clean_id)),
        "title": doc.get("title").cloned().unwrap_or_else(|| json!("")),
        "timestamp": timestamp,
        "transcript_window": nearby_segments,
        "video_notes": video_notes,
        "key_frames": key_frames,
    })
}

#[cfg(test)]
mod b3_catalog_tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn base64_matches_rfc4648_vectors() {
        assert_eq!(encode_base64(b""), "");
        assert_eq!(encode_base64(b"f"), "Zg==");
        assert_eq!(encode_base64(b"fo"), "Zm8=");
        assert_eq!(encode_base64(b"foo"), "Zm9v");
        assert_eq!(encode_base64(b"foob"), "Zm9vYg==");
        assert_eq!(encode_base64(b"fooba"), "Zm9vYmE=");
        assert_eq!(encode_base64(b"foobar"), "Zm9vYmFy");
    }

    #[tokio::test]
    async fn fast_path_handles_file_reasoning_plan_status_course_and_video() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();
        let study_dir = study_storage_dir(&root);
        let doc_dir = study_dir.join("documents").join("doc_b3");
        fs::create_dir_all(&doc_dir).unwrap();

        let pdf_file = doc_dir.join("source.pdf");
        fs::write(&pdf_file, b"%PDF-1.4\nhello").unwrap();
        fs::write(
            doc_dir.join("reasoning_dossier.json"),
            r#"{"dossier_id":"dos_1","source_sha256":"abc123"}"#,
        )
        .unwrap();
        fs::write(
            doc_dir.join("editorial_study_plan.json"),
            r#"{"metadata":{"plan_id":"plan_1","dossier_id":"dos_1","source_sha256":"abc123","status":"COMPLETED","created_at":"2026-11-14T10:00:00Z"},"qa_report":{"validation_status":"PASSED"}}"#,
        )
        .unwrap();

        let store = StudyStore::open(&study_dir).unwrap();
        store
            .upsert_document(
                "doc_b3",
                json!({
                    "document_id": "doc_b3",
                    "title": "B3 Test Doc",
                    "filename": "source.pdf",
                    "stored_path": pdf_file.to_string_lossy().to_string(),
                    "created_at": "2026-11-14T10:00:00Z",
                    "metadata": {
                        "transcript_segments": [
                            {"start": 10.0, "end": 18.0, "text": "Quantum entanglement in optics"},
                            {"start": 45.0, "end": 55.0, "text": "Classical mechanics review"}
                        ]
                    }
                }),
            )
            .await
            .unwrap();
        store
            .upsert_collection(
                "col_b3",
                json!({
                    "collection_id": "col_b3",
                    "name": "Physics I",
                    "subject": "Physics",
                    "document_ids": ["doc_b3"],
                    "linked_folders": []
                }),
            )
            .await
            .unwrap();
        store
            .upsert_flashcard(
                "fc_1",
                json!({
                    "card_id": "fc_1",
                    "document_id": "doc_b3",
                    "repetitions": 1,
                    "ease_factor": 2.5,
                    "interval_days": 1.0
                }),
            )
            .await
            .unwrap();

        let ast_miss = try_execute_study_fast_path(
            &root,
            &store,
            "study_get_document_ast",
            &json!({"document_id": "doc_b3"}),
        )
        .await
        .unwrap();
        assert!(ast_miss.is_none());

        fs::write(
            doc_dir.join("ast.json"),
            r#"{"document_id":"doc_b3","sections":[]}"#,
        )
        .unwrap();
        let ast_hit = try_execute_study_fast_path(
            &root,
            &store,
            "study_get_document_ast",
            &json!({"document_id": "doc_b3"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(ast_hit[0]["type"], "study_document_ast_result");
        assert_eq!(ast_hit[0]["ast"]["document_id"], "doc_b3");

        let file_res = try_execute_study_fast_path(
            &root,
            &store,
            "study_get_document_file",
            &json!({"document_id": "doc_b3"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(file_res[0]["type"], "study_document_file_result");
        assert_eq!(
            file_res[0]["content_base64"],
            encode_base64(b"%PDF-1.4\nhello")
        );

        let plan_res = try_execute_study_fast_path(
            &root,
            &store,
            "study_get_editorial_plan",
            &json!({"document_id": "doc_b3"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(plan_res[0]["plan_status"]["is_up_to_date"], true);

        let gen_status = try_execute_study_fast_path(
            &root,
            &store,
            "study_get_generated_document_status",
            &json!({"document_id": "doc_b3"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(gen_status[0]["status"]["status"], "READY");

        let reviewed = try_execute_study_fast_path(
            &root,
            &store,
            "study_review_flashcard",
            &json!({"card_id": "fc_1", "rating": "Good"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(reviewed[0]["flashcard"]["interval_days"], 6.0);
        assert_eq!(reviewed[0]["flashcard"]["repetitions"], 2);

        let course = try_execute_study_fast_path(
            &root,
            &store,
            "study_get_course_details",
            &json!({"collection_id": "col_b3"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(course[0]["name"], "Physics I");
        assert_eq!(course[0]["materials"].as_array().unwrap().len(), 1);

        let search = try_execute_study_fast_path(
            &root,
            &store,
            "study_search_video_transcript",
            &json!({"document_id": "doc_b3", "query": "quantum"}),
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(search[0]["occurrences"], 1);
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
        fs::write(
            study_dir
                .join("documents")
                .join("doc_owned")
                .join("paper.pdf"),
            b"%PDF-1.4",
        )
        .unwrap();
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

        let cols_after =
            try_execute_study_fast_path(&root, &store, "study_list_collections", &json!({}))
                .await
                .unwrap()
                .unwrap();
        let ids = cols_after[0]["collections"][0]["document_ids"]
            .as_array()
            .unwrap();
        assert_eq!(ids.as_slice(), &[json!("doc_linked")]);

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

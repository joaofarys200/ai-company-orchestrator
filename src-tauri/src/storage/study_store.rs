//! Atomic JSON catalog store for Study Engine (`documents.json`, `collections.json`, `flashcards.json`).
//!
//! Preserves all dynamic Python-side study fields using `BTreeMap<String, Value>`, performs
//! forensic `.corrupt.<ts>.<pid>.bak` backup before recovering malformed JSON, and persists
//! updates through `atomic_fs::atomic_write_string`.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};
use tokio::sync::RwLock;

use crate::permissions::path_jail::is_safe_identifier;
use crate::storage::atomic_fs::atomic_write_string;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct StudyCatalogSnapshot {
    pub documents: BTreeMap<String, Value>,
    pub collections: BTreeMap<String, Value>,
    pub flashcards: BTreeMap<String, Value>,
}

pub struct StudyStore {
    root_dir: PathBuf,
    state: Arc<RwLock<StudyCatalogSnapshot>>,
}

impl std::fmt::Debug for StudyStore {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("StudyStore")
            .field("root_dir", &self.root_dir)
            .finish()
    }
}

impl StudyStore {
    /// Opens `data/study` catalog directory, loading existing JSON stores safely.
    pub fn open(study_dir: impl AsRef<Path>) -> Result<Self, String> {
        let root_dir = study_dir.as_ref().to_path_buf();
        std::fs::create_dir_all(&root_dir).map_err(|e| {
            format!(
                "Failed to initialize StudyStore root {}: {e}",
                root_dir.display()
            )
        })?;
        let canonical = dunce::canonicalize(&root_dir).unwrap_or(root_dir);
        let initial = Self::load_all(&canonical)?;
        Ok(Self {
            root_dir: canonical,
            state: Arc::new(RwLock::new(initial)),
        })
    }

    pub fn root_dir(&self) -> &Path {
        &self.root_dir
    }

    fn load_all(root_dir: &Path) -> Result<StudyCatalogSnapshot, String> {
        Ok(StudyCatalogSnapshot {
            documents: read_json_map_safe(&root_dir.join("documents.json"))?,
            collections: read_json_map_safe(&root_dir.join("collections.json"))?,
            flashcards: read_json_map_safe(&root_dir.join("flashcards.json"))?,
        })
    }

    /// Reloads all catalog files from disk cleanly (e.g. after Python study worker mutation).
    pub async fn refresh(&self) -> Result<StudyCatalogSnapshot, String> {
        let snapshot = Self::load_all(&self.root_dir)?;
        let mut guard = self.state.write().await;
        *guard = snapshot.clone();
        Ok(snapshot)
    }

    pub async fn list_documents(&self) -> Vec<Value> {
        let guard = self.state.read().await;
        guard.documents.values().cloned().collect()
    }

    pub async fn get_document(&self, document_id: &str) -> Result<Option<Value>, String> {
        validate_id(document_id, "document_id")?;
        let guard = self.state.read().await;
        Ok(guard.documents.get(document_id).cloned())
    }

    pub async fn upsert_document(&self, document_id: &str, payload: Value) -> Result<(), String> {
        validate_id(document_id, "document_id")?;
        let mut obj = ensure_json_object(payload, "document")?;
        obj.insert(
            "document_id".to_string(),
            Value::String(document_id.to_string()),
        );

        let mut guard = self.state.write().await;
        guard
            .documents
            .insert(document_id.to_string(), Value::Object(obj));
        persist_map_atomic(&self.root_dir, "documents.json", &guard.documents)
    }

    pub async fn delete_document(&self, document_id: &str) -> Result<bool, String> {
        validate_id(document_id, "document_id")?;
        let mut guard = self.state.write().await;
        let removed = guard.documents.remove(document_id).is_some();
        if removed {
            persist_map_atomic(&self.root_dir, "documents.json", &guard.documents)?;
        }
        Ok(removed)
    }

    pub async fn list_collections(&self) -> Vec<Value> {
        let guard = self.state.read().await;
        guard.collections.values().cloned().collect()
    }

    pub async fn upsert_collection(
        &self,
        collection_id: &str,
        payload: Value,
    ) -> Result<(), String> {
        validate_id(collection_id, "collection_id")?;
        let mut obj = ensure_json_object(payload, "collection")?;
        obj.insert(
            "collection_id".to_string(),
            Value::String(collection_id.to_string()),
        );

        let mut guard = self.state.write().await;
        guard
            .collections
            .insert(collection_id.to_string(), Value::Object(obj));
        persist_map_atomic(&self.root_dir, "collections.json", &guard.collections)
    }

    pub async fn delete_collection(&self, collection_id: &str) -> Result<bool, String> {
        validate_id(collection_id, "collection_id")?;
        let mut guard = self.state.write().await;
        let removed = guard.collections.remove(collection_id).is_some();
        if removed {
            persist_map_atomic(&self.root_dir, "collections.json", &guard.collections)?;
        }
        Ok(removed)
    }

    pub async fn list_flashcards(&self, document_id: Option<&str>) -> Result<Vec<Value>, String> {
        if let Some(doc_id) = document_id {
            validate_id(doc_id, "document_id")?;
        }
        let guard = self.state.read().await;
        Ok(guard
            .flashcards
            .values()
            .filter(|card| match document_id {
                Some(doc_id) => card.get("document_id").and_then(Value::as_str) == Some(doc_id),
                None => true,
            })
            .cloned()
            .collect())
    }

    pub async fn upsert_flashcard(&self, card_id: &str, payload: Value) -> Result<(), String> {
        validate_id(card_id, "card_id")?;
        let mut obj = ensure_json_object(payload, "flashcard")?;
        obj.insert("card_id".to_string(), Value::String(card_id.to_string()));

        let mut guard = self.state.write().await;
        guard
            .flashcards
            .insert(card_id.to_string(), Value::Object(obj));
        persist_map_atomic(&self.root_dir, "flashcards.json", &guard.flashcards)
    }
}

fn validate_id(id: &str, label: &str) -> Result<(), String> {
    if !is_safe_identifier(id) {
        return Err(format!("SECURITY_VIOLATION: invalid {label}: {id:?}"));
    }
    Ok(())
}

fn ensure_json_object(value: Value, label: &str) -> Result<Map<String, Value>, String> {
    match value {
        Value::Object(map) => Ok(map),
        _ => Err(format!("Expected JSON object for {label}")),
    }
}

fn persist_map_atomic(
    root_dir: &Path,
    filename: &str,
    map: &BTreeMap<String, Value>,
) -> Result<(), String> {
    let serialized = serde_json::to_string_pretty(map)
        .map_err(|e| format!("Failed to serialize {filename}: {e}"))?;
    atomic_write_string(root_dir, filename, &serialized).map_err(|err| err.to_string())
}

fn read_json_map_safe(path: &Path) -> Result<BTreeMap<String, Value>, String> {
    match std::fs::symlink_metadata(path) {
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Ok(BTreeMap::new()),
        Err(err) => {
            return Err(format!(
                "I/O error checking study file {}: {err}",
                path.display()
            ))
        }
        Ok(meta) => {
            if meta.file_type().is_symlink() {
                return Err(format!(
                    "SECURITY_VIOLATION: refusing symlinked study store {}",
                    path.display()
                ));
            }
        }
    }

    let raw = std::fs::read_to_string(path)
        .map_err(|e| format!("Failed reading study file {}: {e}", path.display()))?;

    if raw.trim().is_empty() {
        quarantine_corrupt_file(path)?;
        return Ok(BTreeMap::new());
    }

    match serde_json::from_str::<Value>(&raw) {
        Ok(Value::Object(map)) => Ok(map.into_iter().collect()),
        Ok(_) | Err(_) => {
            quarantine_corrupt_file(path)?;
            Ok(BTreeMap::new())
        }
    }
}

fn quarantine_corrupt_file(path: &Path) -> Result<(), String> {
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    let pid = std::process::id();
    let name = path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("study.json");

    let mut idx = 0usize;
    let backup_path = loop {
        let suffix = if idx == 0 {
            format!("{name}.corrupt.{ts}.{pid}.bak")
        } else {
            format!("{name}.corrupt.{ts}.{pid}.{idx}.bak")
        };
        let cand = path.with_file_name(suffix);
        if !cand.exists() {
            break cand;
        }
        idx += 1;
    };

    std::fs::rename(path, &backup_path).map_err(|e| {
        format!(
            "Failed to quarantine corrupt study file {} -> {}: {e}",
            path.display(),
            backup_path.display()
        )
    })?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use tempfile::tempdir;

    #[tokio::test]
    async fn study_store_roundtrips_documents_collections_flashcards_and_quarantines_corrupt_json() {
        let dir = tempdir().expect("create tempdir");
        std::fs::write(dir.path().join("documents.json"), "{not-valid-json")
            .expect("seed corrupt json");

        let store = StudyStore::open(dir.path()).expect("open StudyStore with corrupt backup");
        assert!(store.list_documents().await.is_empty());

        let backups: Vec<_> = std::fs::read_dir(dir.path())
            .unwrap()
            .filter_map(|e| e.ok())
            .filter(|e| e.file_name().to_string_lossy().contains(".corrupt."))
            .collect();
        assert_eq!(backups.len(), 1, "expected forensic corrupt backup");

        store
            .upsert_document(
                "doc_01",
                json!({
                    "title": "Distributed Systems",
                    "subject": "CS",
                    "custom_nested": { "pages": 42 }
                }),
            )
            .await
            .expect("upsert document");
        store
            .upsert_collection(
                "col_01",
                json!({
                    "name": "Architecture",
                    "document_ids": ["doc_01"]
                }),
            )
            .await
            .expect("upsert collection");
        store
            .upsert_flashcard(
                "fc_01",
                json!({
                    "document_id": "doc_01",
                    "front": "What is WAL?",
                    "back": "Write-Ahead Logging"
                }),
            )
            .await
            .expect("upsert flashcard");

        // Re-open fresh instance from disk to assert durable persistence & unknown field preservation.
        let reloaded = StudyStore::open(dir.path()).expect("reload StudyStore");
        let doc = reloaded
            .get_document("doc_01")
            .await
            .unwrap()
            .expect("doc present");
        assert_eq!(doc["custom_nested"]["pages"], 42);
        assert_eq!(reloaded.list_collections().await.len(), 1);
        assert_eq!(
            reloaded.list_flashcards(Some("doc_01")).await.unwrap().len(),
            1
        );

        // Traversal identifiers must be blocked.
        assert!(reloaded.get_document("../secret").await.is_err());
        assert!(reloaded.delete_document("doc_01").await.unwrap());
        assert!(reloaded.list_documents().await.is_empty());
    }
}

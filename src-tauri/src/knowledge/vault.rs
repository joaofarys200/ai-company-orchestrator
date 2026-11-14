//! Confined Obsidian Vault note CRUD & artifact-protection guards.

use std::fs;
use std::path::{Component, Path, PathBuf};

use serde_json::{json, Value};

use crate::error::AppError;
use crate::permissions::path_jail::{ensure_confined_existing_file, resolve_confined_path};
use crate::storage::atomic_fs::{atomic_write_string, read_bounded_bytes};

const MAX_NOTE_BYTES: usize = 8 * 1024 * 1024;

const CODE_ARTIFACT_SUFFIXES: &[&str] = &[
    ".py", ".js", ".jsx", ".ts", ".tsx", ".css", ".html", ".htm", ".json", ".yaml", ".yml",
    ".toml", ".sql", ".sh", ".bat", ".ps1", ".env",
];

/// Resolves the authorized Obsidian vault root (honoring `OBSIDIAN_VAULT_PATH` when set).
pub fn resolve_vault_root(project_root: &Path) -> Result<PathBuf, AppError> {
    let raw = match std::env::var("OBSIDIAN_VAULT_PATH") {
        Ok(val) if !val.trim().is_empty() => PathBuf::from(val.trim()),
        _ => project_root.join("obsidian_vault"),
    };
    fs::create_dir_all(&raw).map_err(|err| {
        AppError::new(
            "VAULT_DIR_FAILED",
            format!("Failed to initialize obsidian_vault directory: {err}"),
        )
    })?;
    dunce::canonicalize(&raw).map_err(|err| {
        AppError::new(
            "VAULT_CANON_FAILED",
            format!("Failed to canonicalize obsidian_vault directory: {err}"),
        )
    })
}

/// Returns `true` when `filename` looks like source code / sandbox artifact rather than a Markdown note.
pub fn obsidian_path_looks_like_code_artifact(filename: &str) -> bool {
    let normalized = filename.trim().replace('\\', "/");
    let stripped = normalized.trim_start_matches('/').to_ascii_lowercase();
    if stripped.is_empty() {
        return false;
    }
    if stripped.starts_with("sandbox_dir/") || stripped.starts_with("sandbox/") {
        return true;
    }
    let leaf = stripped.rsplit('/').next().unwrap_or("");
    let stem_or_leaf = leaf.strip_suffix(".md").unwrap_or(leaf);
    CODE_ARTIFACT_SUFFIXES
        .iter()
        .any(|ext| stem_or_leaf.ends_with(ext))
}

/// Normalizes a relative Markdown note filename and rejects traversal or invalid segments.
pub fn normalize_note_rel_path(filename: &str, ensure_md: bool) -> Result<String, AppError> {
    if filename.contains('\0') {
        return Err(AppError::new("INVALID_NOTE_PATH", "Caminho de nota inválido."));
    }
    let replaced = filename.trim().replace('\\', "/");
    let trimmed = replaced.trim_start_matches('/');
    if trimmed.is_empty() {
        return Err(AppError::new("INVALID_NOTE_PATH", "Nome da nota em falta."));
    }
    if trimmed.contains(':') {
        return Err(AppError::new(
            "VAULT_SECURITY_VIOLATION",
            "Acesso fora da pasta do Obsidian não permitido.",
        ));
    }
    let rel_path = Path::new(trimmed);
    for comp in rel_path.components() {
        if matches!(comp, Component::ParentDir | Component::RootDir | Component::Prefix(_)) {
            return Err(AppError::new(
                "VAULT_SECURITY_VIOLATION",
                "Acesso fora da pasta do Obsidian não permitido.",
            ));
        }
    }
    let lower = trimmed.to_ascii_lowercase();
    let final_rel = if ensure_md && !lower.ends_with(".md") {
        format!("{trimmed}.md")
    } else {
        trimmed.to_string()
    };
    Ok(final_rel)
}

/// Lists all Markdown notes under `vault_root` (excluding `.obsidian` and `.history`), sorted cleanly.
pub fn list_notes(vault_root: &Path) -> Result<Vec<String>, AppError> {
    if !vault_root.exists() {
        return Ok(Vec::new());
    }
    let canon_root = dunce::canonicalize(vault_root).map_err(|err| {
        AppError::new(
            "VAULT_CANON_FAILED",
            format!("Failed to canonicalize vault root: {err}"),
        )
    })?;

    let mut notes = Vec::new();
    let mut stack = vec![canon_root.clone()];
    while let Some(dir) = stack.pop() {
        let Ok(entries) = fs::read_dir(&dir) else {
            continue;
        };
        for entry in entries.flatten() {
            let path = entry.path();
            let Ok(meta) = fs::symlink_metadata(&path) else {
                continue;
            };
            if meta.file_type().is_symlink() {
                continue;
            }
            let name = entry.file_name().to_string_lossy().to_string();
            if meta.is_dir() {
                if name == ".obsidian" || name == ".history" {
                    continue;
                }
                stack.push(path);
            } else if meta.is_file() && name.to_ascii_lowercase().ends_with(".md") {
                if let Ok(rel) = path.strip_prefix(&canon_root) {
                    notes.push(rel.to_string_lossy().replace('\\', "/"));
                }
            }
        }
    }
    notes.sort();
    Ok(notes)
}

/// Reads a single Markdown note inside `vault_root` matching Python `read_note` semantics.
pub fn read_note_payload(vault_root: &Path, raw_filename: Option<&str>) -> Value {
    let filename = raw_filename.unwrap_or("");
    let content = match normalize_note_rel_path(filename, true) {
        Err(err) => format!("Erro ao ler nota: {}", err.message),
        Ok(rel) => match ensure_confined_existing_file(vault_root, Path::new(&rel)) {
            Err(err) => {
                if err.code == "NOT_FOUND" {
                    format!("Erro: A nota '{filename}' não existe no Obsidian.")
                } else {
                    format!("Erro ao ler nota: {}", err.message)
                }
            }
            Ok(canon) => match read_bounded_bytes(vault_root, &canon, MAX_NOTE_BYTES) {
                Ok(bytes) => String::from_utf8_lossy(&bytes).into_owned(),
                Err(err) => format!("Erro ao ler nota: {}", err.message),
            },
        },
    };
    json!({
        "type": "note_content",
        "filename": raw_filename.map(|s| json!(s)).unwrap_or(Value::Null),
        "content": content,
    })
}

/// Atomically writes a Markdown note inside `vault_root` and returns `[notes_list, note_saved]`.
pub fn save_note_events(
    vault_root: &Path,
    raw_filename: Option<&str>,
    raw_content: Option<&str>,
) -> Vec<Value> {
    let fname_display = raw_filename.map(|s| json!(s)).unwrap_or(Value::Null);
    let save_err = |msg: String| -> Value {
        json!({
            "type": "note_saved",
            "filename": fname_display.clone(),
            "result": msg,
        })
    };

    let result_msg = (|| -> Result<String, String> {
        let Some(fname) = raw_filename.map(str::trim).filter(|s| !s.is_empty()) else {
            return Err("Erro ao escrever nota: filename em falta.".to_string());
        };
        let Some(content) = raw_content else {
            return Err("Erro ao escrever nota: content em falta.".to_string());
        };
        if obsidian_path_looks_like_code_artifact(fname) {
            return Err(
                "Erro ao escrever nota: caminho parece artefacto de codigo/sandbox. \
                 Usa write_file para apps, frontend, backend e ficheiros da sandbox."
                    .to_string(),
            );
        }
        let rel = normalize_note_rel_path(fname, true).map_err(|e| format!("Erro ao escrever nota: {}", e.message))?;
        let target = resolve_confined_path(vault_root, Path::new(&rel))
            .map_err(|e| format!("Erro ao escrever nota: {}", e.message))?;
        atomic_write_string(vault_root, &target, content)
            .map_err(|e| format!("Erro ao escrever nota: {}", e.message))?;
        Ok(format!(
            "Nota '{fname}' guardada com sucesso no Obsidian ({} bytes).",
            content.len()
        ))
    })();

    let msg = match result_msg {
        Ok(m) | Err(m) => m,
    };
    let notes = list_notes(vault_root).unwrap_or_default();
    vec![
        json!({
            "type": "notes_list",
            "notes": notes,
        }),
        save_err(msg),
    ]
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn vault_blocks_traversal_and_code_artifacts_while_supporting_roundtrip() {
        let dir = tempdir().unwrap();
        let vault = resolve_vault_root(dir.path()).unwrap();

        // Artifact rejection
        assert!(obsidian_path_looks_like_code_artifact("backend/server.py"));
        assert!(obsidian_path_looks_like_code_artifact("sandbox/index.html.md"));
        assert!(!obsidian_path_looks_like_code_artifact("00 - Architecture/Rust Core.md"));

        let blocked_save = save_note_events(&vault, Some("../escape.md"), Some("secret"));
        assert!(blocked_save[1]["result"]
            .as_str()
            .unwrap()
            .contains("fora da pasta"));
        assert!(!dir.path().join("escape.md").exists());

        let artifact_save = save_note_events(&vault, Some("app.tsx"), Some("code"));
        assert!(artifact_save[1]["result"]
            .as_str()
            .unwrap()
            .contains("artefacto de codigo"));

        // Valid write + read + list
        let ok_save = save_note_events(&vault, Some("Concepts/Rust Core"), Some("# Rust Core\nContent"));
        assert!(ok_save[1]["result"]
            .as_str()
            .unwrap()
            .contains("guardada com sucesso"));
        assert_eq!(ok_save[0]["notes"], json!(["Concepts/Rust Core.md"]));

        let read = read_note_payload(&vault, Some("Concepts/Rust Core"));
        assert_eq!(read["content"], "# Rust Core\nContent");
    }
}

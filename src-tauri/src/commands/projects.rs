use std::path::{Path, PathBuf};

use serde::Serialize;
use sha2::{Digest, Sha256};
use tauri::State;

use crate::commands::media::RuntimeServices;
use crate::error::AppError;
use crate::permissions::path_jail::resolve_confined_path;
use crate::storage::atomic_fs::{atomic_write_string, read_bounded_bytes};

const MAX_PROJECT_FILE_READ_BYTES: usize = 8 * 1024 * 1024;
const PROTECTED_FILENAMES: &[&str] = &[
    ".env",
    "database.db",
    "database.db-wal",
    "database.db-shm",
    "state.db",
    "state.db-wal",
    "state.db-shm",
    "rho.db",
    "rho.db-wal",
    "rho.db-shm",
];

#[derive(Debug, Clone, Serialize)]
pub struct ConfinedFileReadResult {
    pub ok: bool,
    pub path: String,
    pub content: String,
    pub sha256: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ConfinedFileWriteResult {
    pub ok: bool,
    pub path: String,
    pub sha256: String,
}

pub fn compute_sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

fn ensure_not_protected_target(path: &Path) -> Result<(), AppError> {
    for component in path.components() {
        let seg = component.as_os_str().to_string_lossy().to_ascii_lowercase();
        if seg == ".git" || PROTECTED_FILENAMES.contains(&seg.as_str()) {
            return Err(AppError::new(
                "SECURITY_VIOLATION",
                format!("Access to protected runtime file segment `{seg}` is denied"),
            ));
        }
    }
    Ok(())
}

fn resolve_target_root(project_root: &Path, root_subpath: Option<&str>) -> Result<PathBuf, AppError> {
    match root_subpath.map(str::trim).filter(|s| !s.is_empty()) {
        Some(sub) => {
            let candidate = resolve_confined_path(project_root, Path::new(sub))?;
            ensure_not_protected_target(&candidate)?;
            Ok(candidate)
        }
        None => Ok(project_root.to_path_buf()),
    }
}

pub fn read_confined_project_file_impl(
    project_root: &Path,
    root_subpath: Option<&str>,
    relative_path: &str,
) -> Result<ConfinedFileReadResult, AppError> {
    let root = resolve_target_root(project_root, root_subpath)?;
    let target = Path::new(relative_path);
    ensure_not_protected_target(target)?;
    let bytes = read_bounded_bytes(&root, target, MAX_PROJECT_FILE_READ_BYTES)?;
    let sha256 = compute_sha256_hex(&bytes);
    let content = String::from_utf8(bytes)
        .map_err(|err| AppError::new("INVALID_UTF8", format!("File is not valid UTF-8: {err}")))?;
    let canon = resolve_confined_path(&root, target)?;
    Ok(ConfinedFileReadResult {
        ok: true,
        path: canon.to_string_lossy().to_string(),
        content,
        sha256,
    })
}

pub fn write_confined_project_file_impl(
    project_root: &Path,
    root_subpath: Option<&str>,
    relative_path: &str,
    content: &str,
    expected_sha256: Option<&str>,
) -> Result<ConfinedFileWriteResult, AppError> {
    let root = resolve_target_root(project_root, root_subpath)?;
    let target = Path::new(relative_path);
    ensure_not_protected_target(target)?;

    if let Some(expected) = expected_sha256.map(str::trim).filter(|s| !s.is_empty()) {
        let existing_bytes = read_bounded_bytes(&root, target, MAX_PROJECT_FILE_READ_BYTES)?;
        let actual_sha = compute_sha256_hex(&existing_bytes);
        if !actual_sha.eq_ignore_ascii_case(expected) {
            return Err(AppError::new(
                "SHA256_CONFLICT",
                format!(
                    "Optimistic concurrency mismatch for `{relative_path}`: expected {expected}, found {actual_sha}"
                ),
            ));
        }
    }

    let written_path = atomic_write_string(&root, target, content)?;
    let sha256 = compute_sha256_hex(content.as_bytes());
    Ok(ConfinedFileWriteResult {
        ok: true,
        path: written_path.to_string_lossy().to_string(),
        sha256,
    })
}

#[tauri::command]
pub async fn confined_read_file(
    services: State<'_, RuntimeServices>,
    root_subpath: Option<String>,
    relative_path: String,
) -> Result<ConfinedFileReadResult, AppError> {
    let root = services.project_root.clone();
    tokio::task::spawn_blocking(move || {
        read_confined_project_file_impl(&root, root_subpath.as_deref(), &relative_path)
    })
    .await
    .map_err(|err| AppError::new("TASK_JOIN_FAILED", err.to_string()))?
}

#[tauri::command]
pub async fn confined_write_file(
    services: State<'_, RuntimeServices>,
    root_subpath: Option<String>,
    relative_path: String,
    content: String,
    expected_sha256: Option<String>,
) -> Result<ConfinedFileWriteResult, AppError> {
    let root = services.project_root.clone();
    tokio::task::spawn_blocking(move || {
        write_confined_project_file_impl(
            &root,
            root_subpath.as_deref(),
            &relative_path,
            &content,
            expected_sha256.as_deref(),
        )
    })
    .await
    .map_err(|err| AppError::new("TASK_JOIN_FAILED", err.to_string()))?
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    #[test]
    fn confined_write_and_read_enforces_sha256_and_blocks_protected_files() {
        let dir = TempDir::new().unwrap();
        let root = dir.path();
        fs::create_dir_all(root.join("sandbox_workspace")).unwrap();

        let written = write_confined_project_file_impl(
            root,
            Some("sandbox_workspace"),
            "app/index.html",
            "<h1>Hello</h1>",
            None,
        )
        .unwrap();
        assert!(written.ok);

        let read_back =
            read_confined_project_file_impl(root, Some("sandbox_workspace"), "app/index.html")
                .unwrap();
        assert_eq!(read_back.content, "<h1>Hello</h1>");
        assert_eq!(read_back.sha256, written.sha256);

        let conflict = write_confined_project_file_impl(
            root,
            Some("sandbox_workspace"),
            "app/index.html",
            "<h1>Updated</h1>",
            Some(&"0".repeat(64)),
        );
        assert_eq!(conflict.unwrap_err().code, "SHA256_CONFLICT");

        let ok_update = write_confined_project_file_impl(
            root,
            Some("sandbox_workspace"),
            "app/index.html",
            "<h1>Updated</h1>",
            Some(&written.sha256),
        );
        assert!(ok_update.is_ok());

        for blocked in ["database.db", ".env", "../escape.txt", ".git/config"] {
            assert!(
                write_confined_project_file_impl(root, None, blocked, "x", None).is_err(),
                "expected write to blocked target {blocked} to fail"
            );
        }
    }
}

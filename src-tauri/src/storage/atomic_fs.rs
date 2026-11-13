use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use tempfile::NamedTempFile;

use crate::error::AppError;
use crate::permissions::path_jail::{ensure_confined_existing_file, resolve_confined_path};

/// Atomically writes `data` to a target file strictly confined under `root`.
///
/// Writes into a sibling temporary file in the same parent directory, flushes and calls
/// `sync_all()`, then atomically persists over `dest`.
pub fn atomic_write_bytes(root: &Path, target: &Path, data: &[u8]) -> Result<PathBuf, AppError> {
    let dest = resolve_confined_path(root, target)?;
    let parent = dest.parent().ok_or_else(|| {
        AppError::new(
            "INVALID_TARGET_PARENT",
            "Target path has no parent directory.",
        )
    })?;

    // Re-check destination directory confinement if missing directories must be created.
    if !parent.exists() {
        fs::create_dir_all(parent).map_err(|err| {
            AppError::new(
                "DIR_CREATE_FAILED",
                format!("Failed to create target parent directory: {err}"),
            )
        })?;
    }

    // Re-resolve after directory creation to reject symlinked parents.
    let canon_dest = resolve_confined_path(root, &dest)?;
    let canon_parent = canon_dest.parent().ok_or_else(|| {
        AppError::new(
            "INVALID_TARGET_PARENT",
            "Canonical target path has no parent directory.",
        )
    })?;

    let mut temp = NamedTempFile::new_in(canon_parent).map_err(|err| {
        AppError::new(
            "TEMP_FILE_CREATE_FAILED",
            format!("Failed to create temporary file: {err}"),
        )
    })?;

    temp.write_all(data).map_err(|err| {
        AppError::new(
            "ATOMIC_WRITE_FAILED",
            format!("Failed to write temporary payload: {err}"),
        )
    })?;
    temp.flush().map_err(|err| {
        AppError::new(
            "ATOMIC_FLUSH_FAILED",
            format!("Failed to flush temporary payload: {err}"),
        )
    })?;
    temp.as_file().sync_all().map_err(|err| {
        AppError::new(
            "ATOMIC_SYNC_FAILED",
            format!("Failed to sync temporary payload to disk: {err}"),
        )
    })?;

    temp.persist(&canon_dest).map_err(|err| {
        AppError::new(
            "ATOMIC_PERSIST_FAILED",
            format!("Failed to atomically replace target file: {}", err.error),
        )
    })?;

    Ok(canon_dest)
}

/// Atomically writes UTF-8 text to a target file strictly confined under `root`.
pub fn atomic_write_string(
    root: &Path,
    target: &Path,
    content: &str,
) -> Result<PathBuf, AppError> {
    atomic_write_bytes(root, target, content.as_bytes())
}

/// Safely reads up to `max_bytes` from an existing non-symlink regular file confined inside `root`.
pub fn read_bounded_bytes(
    root: &Path,
    target: &Path,
    max_bytes: usize,
) -> Result<Vec<u8>, AppError> {
    let canon = ensure_confined_existing_file(root, target)?;
    let file = File::open(&canon).map_err(|err| {
        AppError::new(
            "FILE_OPEN_FAILED",
            format!("Failed to open confined file: {err}"),
        )
    })?;

    let meta = file.metadata().map_err(|err| {
        AppError::new(
            "FILE_METADATA_FAILED",
            format!("Failed to inspect file metadata: {err}"),
        )
    })?;

    if meta.len() > max_bytes as u64 {
        return Err(AppError::new(
            "FILE_TOO_LARGE",
            format!(
                "File exceeds configured maximum byte limit ({} > {}).",
                meta.len(),
                max_bytes
            ),
        ));
    }

    let cap = (meta.len() as usize).min(max_bytes);
    let mut buf = Vec::with_capacity(cap);
    let mut limited = file.take((max_bytes as u64).saturating_add(1));
    limited.read_to_end(&mut buf).map_err(|err| {
        AppError::new(
            "FILE_READ_FAILED",
            format!("Failed to read confined file: {err}"),
        )
    })?;

    if buf.len() > max_bytes {
        return Err(AppError::new(
            "FILE_TOO_LARGE",
            format!("File grew beyond maximum byte limit ({max_bytes})."),
        ));
    }

    Ok(buf)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::tempdir;

    #[test]
    fn atomic_write_and_overwrite_leaves_no_temp_artifacts() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();

        let p1 = atomic_write_string(&root, Path::new("nested/state.json"), r#"{"v":1}"#).unwrap();
        assert_eq!(fs::read_to_string(&p1).unwrap(), r#"{"v":1}"#);

        let p2 = atomic_write_string(&root, Path::new("nested/state.json"), r#"{"v":2}"#).unwrap();
        assert_eq!(p1, p2);
        assert_eq!(fs::read_to_string(&p2).unwrap(), r#"{"v":2}"#);

        let entries: Vec<_> = fs::read_dir(root.join("nested"))
            .unwrap()
            .filter_map(|e| e.ok())
            .collect();
        assert_eq!(entries.len(), 1);

        let loaded = read_bounded_bytes(&root, Path::new("nested/state.json"), 1024).unwrap();
        assert_eq!(loaded, br#"{"v":2}"#);
    }

    #[test]
    fn atomic_write_blocks_traversal_and_win32_reserved_names() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();

        let err = atomic_write_string(&root, Path::new("../escape.txt"), "bad").unwrap_err();
        assert_eq!(err.code, "PATH_TRAVERSAL_BLOCKED");

        let err2 = atomic_write_string(&root, Path::new("sub/CON.txt"), "bad").unwrap_err();
        assert_eq!(err2.code, "WIN32_RESERVED_NAME");
    }

    #[test]
    fn read_bounded_bytes_enforces_size_limit() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();
        atomic_write_bytes(&root, Path::new("big.bin"), &[7u8; 64]).unwrap();

        let err = read_bounded_bytes(&root, Path::new("big.bin"), 32).unwrap_err();
        assert_eq!(err.code, "FILE_TOO_LARGE");

        let ok = read_bounded_bytes(&root, Path::new("big.bin"), 64).unwrap();
        assert_eq!(ok.len(), 64);
    }
}

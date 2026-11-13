use std::fs;
use std::path::{Component, Path, PathBuf};

use crate::error::AppError;

const WIN32_RESERVED_NAMES: &[&str] = &[
    "con", "prn", "aux", "nul", "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8",
    "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ValidatedOpenTarget {
    Url(String),
    LocalPath(PathBuf),
}

fn looks_like_project_root(dir: &Path) -> bool {
    dir.join("package.json").is_file()
        && (dir.join("src-tauri").is_dir() || dir.join("server.py").is_file())
}

/// Resolves the canonical workspace root without relying on arbitrary CWD state.
pub fn resolve_project_root() -> PathBuf {
    if let Some(explicit) = std::env::var_os("JARVIS_PROJECT_ROOT") {
        let candidate = PathBuf::from(explicit);
        if candidate.is_dir() {
            if let Ok(canon) = dunce::canonicalize(&candidate) {
                return canon;
            }
        }
    }

    if let Ok(exe) = std::env::current_exe() {
        for ancestor in exe.ancestors() {
            if looks_like_project_root(ancestor) {
                if let Ok(canon) = dunce::canonicalize(ancestor) {
                    return canon;
                }
            }
        }
    }

    if let Some(manifest_dir) = option_env!("CARGO_MANIFEST_DIR") {
        if let Some(parent) = Path::new(manifest_dir).parent() {
            if looks_like_project_root(parent) {
                if let Ok(canon) = dunce::canonicalize(parent) {
                    return canon;
                }
            }
        }
    }

    std::env::current_dir()
        .and_then(dunce::canonicalize)
        .unwrap_or_else(|_| PathBuf::from("."))
}

/// Default local roots allowed for OS file/folder opening and confined shell operations.
pub fn default_open_roots(project_root: &Path) -> Vec<PathBuf> {
    let mut roots = vec![
        project_root.to_path_buf(),
        project_root.join("data"),
        project_root.join("obsidian_vault"),
        project_root.join("workspace"),
    ];
    let temp = std::env::temp_dir();
    roots.push(dunce::canonicalize(&temp).unwrap_or(temp));
    roots
}

/// Returns true if any path segment matches a Win32 reserved DOS device name.
pub fn has_win32_reserved_name(path: &Path) -> bool {
    for component in path.components() {
        if let Component::Normal(segment) = component {
            let text = segment.to_string_lossy();
            let trimmed = text.trim_end_matches(['.', ' ']);
            let stem = trimmed.split('.').next().unwrap_or("");
            let lower = stem.to_ascii_lowercase();
            if WIN32_RESERVED_NAMES.contains(&lower.as_str()) {
                return true;
            }
        }
    }
    false
}

/// Validates syntactic safety before canonical resolution (rejects null bytes, `..`, reserved device names).
pub fn validate_syntactic_path_safety(raw: &str, candidate: &Path) -> Result<(), AppError> {
    if raw.trim().is_empty() || raw.contains('\0') {
        return Err(AppError::new(
            "INVALID_PATH",
            "Path must not be empty or contain null bytes.",
        ));
    }

    for component in candidate.components() {
        if matches!(component, Component::ParentDir) {
            return Err(AppError::new(
                "PATH_TRAVERSAL_BLOCKED",
                "Parent directory traversal ('..') is forbidden.",
            ));
        }
    }

    if has_win32_reserved_name(candidate) {
        return Err(AppError::new(
            "WIN32_RESERVED_NAME",
            "Win32 reserved device names are forbidden.",
        ));
    }

    Ok(())
}

/// Confines a path strictly inside `root`, supporting existing and pre-creation targets and guarding against symlinks.
pub fn resolve_confined_path(root: &Path, target: &Path) -> Result<PathBuf, AppError> {
    let raw_display = target.to_string_lossy();
    validate_syntactic_path_safety(&raw_display, target)?;

    let canon_root = dunce::canonicalize(root).map_err(|err| {
        AppError::new(
            "ROOT_UNAVAILABLE",
            format!("Allowed root could not be canonicalized: {err}"),
        )
    })?;

    let joined = if target.is_absolute() {
        target.to_path_buf()
    } else {
        canon_root.join(target)
    };

    validate_syntactic_path_safety(&joined.to_string_lossy(), &joined)?;

    if joined.exists() {
        if let Ok(meta) = fs::symlink_metadata(&joined) {
            if meta.file_type().is_symlink() {
                let canon_link = dunce::canonicalize(&joined).map_err(|_| {
                    AppError::new("SYMLINK_ESCAPE", "Unable to resolve symbolic link safely.")
                })?;
                if !canon_link.starts_with(&canon_root) {
                    return Err(AppError::new(
                        "PATH_JAIL_VIOLATION",
                        "Symlink target resolves outside allowed root.",
                    ));
                }
            }
        }
        let canon = dunce::canonicalize(&joined).map_err(|err| {
            AppError::new(
                "PATH_CANONICALIZATION_FAILED",
                format!("Failed to canonicalize target path: {err}"),
            )
        })?;
        if !canon.starts_with(&canon_root) {
            return Err(AppError::new(
                "PATH_JAIL_VIOLATION",
                "Target path resolves outside allowed root.",
            ));
        }
        return Ok(canon);
    }

    // Pre-creation verification: find deepest existing ancestor and verify confinement
    let mut suffix_segments: Vec<std::ffi::OsString> = Vec::new();
    let mut cursor = joined.as_path();
    while !cursor.exists() {
        let name = cursor.file_name().ok_or_else(|| {
            AppError::new(
                "PATH_JAIL_VIOLATION",
                "Non-existent path has no existing confined ancestor.",
            )
        })?;
        suffix_segments.push(name.to_os_string());
        cursor = cursor.parent().ok_or_else(|| {
            AppError::new(
                "PATH_JAIL_VIOLATION",
                "Non-existent path escaped root hierarchy.",
            )
        })?;
    }

    let canon_ancestor = dunce::canonicalize(cursor).map_err(|err| {
        AppError::new(
            "PATH_CANONICALIZATION_FAILED",
            format!("Failed to canonicalize existing ancestor: {err}"),
        )
    })?;
    if !canon_ancestor.starts_with(&canon_root) {
        return Err(AppError::new(
            "PATH_JAIL_VIOLATION",
            "Target ancestor resolves outside allowed root.",
        ));
    }

    let mut rebuilt = canon_ancestor;
    for seg in suffix_segments.into_iter().rev() {
        rebuilt.push(seg);
    }
    if has_win32_reserved_name(&rebuilt) || !rebuilt.starts_with(&canon_root) {
        return Err(AppError::new(
            "PATH_JAIL_VIOLATION",
            "Constructed target path failed confinement.",
        ));
    }
    Ok(rebuilt)
}

/// Validates a URI or local filesystem path before invoking OS `opener`.
pub fn validate_open_target(
    allowed_roots: &[PathBuf],
    raw_target: &str,
) -> Result<ValidatedOpenTarget, AppError> {
    let trimmed = raw_target.trim();
    if trimmed.is_empty()
        || trimmed.contains('\0')
        || trimmed.contains('\r')
        || trimmed.contains('\n')
    {
        return Err(AppError::new(
            "INVALID_OPEN_TARGET",
            "Open target must not be empty or contain control characters.",
        ));
    }

    // Detect Windows drive letter path (e.g. C:\foo or C:/foo) before URL scheme check
    let bytes = trimmed.as_bytes();
    let is_windows_drive_path = bytes.len() >= 2
        && bytes[0].is_ascii_alphabetic()
        && bytes[1] == b':';

    if !is_windows_drive_path {
        if let Some(colon_idx) = trimmed.find(':') {
            let scheme = trimmed[..colon_idx].to_ascii_lowercase();
            let valid_scheme_chars = !scheme.is_empty()
                && scheme
                    .chars()
                    .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '+' | '-' | '.'));
            if valid_scheme_chars {
                if (scheme == "http" || scheme == "https") && !trimmed.contains('\\') {
                    let prefix = format!("{scheme}://");
                    if trimmed.to_ascii_lowercase().starts_with(&prefix) && trimmed.len() > prefix.len() {
                        return Ok(ValidatedOpenTarget::Url(trimmed.to_string()));
                    }
                }
                return Err(AppError::new(
                    "DISALLOWED_URL_SCHEME",
                    format!("URI scheme '{scheme}' is not permitted."),
                ));
            }
        }
    }

    let candidate = Path::new(trimmed);
    for root in allowed_roots {
        if !root.exists() {
            continue;
        }
        if let Ok(resolved) = resolve_confined_path(root, candidate) {
            if resolved.exists() {
                return Ok(ValidatedOpenTarget::LocalPath(resolved));
            }
        }
    }

    Err(AppError::new(
        "PATH_JAIL_VIOLATION",
        "Target path is outside allowed roots or does not exist.",
    ))
}


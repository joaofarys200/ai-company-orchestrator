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

/// Separation between mutable user/runtime state (`data_root`, e.g. `%LOCALAPPDATA%\JarvisOS`)
/// and immutable application resources (`resource_root`, e.g. `%ProgramFiles%\JARVIS OS`).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AppPaths {
    pub data_root: PathBuf,
    pub resource_root: PathBuf,
    pub is_packaged: bool,
}

fn looks_like_project_root(dir: &Path) -> bool {
    dir.join("package.json").is_file()
        && (dir.join("src-tauri").is_dir() || dir.join("server.py").is_file())
}

fn looks_like_resource_root(dir: &Path) -> bool {
    dir.join("workers").join("worker_boot.py").is_file()
        || dir
            .join("_up_")
            .join("workers")
            .join("worker_boot.py")
            .is_file()
}

fn normalize_or_create_dir(path: &Path, create: bool) -> PathBuf {
    if create {
        let _ = fs::create_dir_all(path);
    }
    dunce::canonicalize(path).unwrap_or_else(|_| path.to_path_buf())
}

/// Ensures standard writable subdirectories exist under `data_root`.
pub fn ensure_writable_data_subdirs(data_root: &Path) {
    let _ = fs::create_dir_all(data_root.join("data").join("study"));
    let _ = fs::create_dir_all(data_root.join("data").join("sentinel"));
    let _ = fs::create_dir_all(data_root.join("obsidian_vault"));
    let _ = fs::create_dir_all(data_root.join("workspace"));
    let _ = fs::create_dir_all(data_root.join(".jarvis"));
}

/// Detects whether the current executable is running directly inside a developer repository checkout.
/// Release builds intentionally ignore compile-time `CARGO_MANIFEST_DIR` so installed MSI/NSIS
/// binaries never resolve back to the build machine's checkout directory.
pub fn detect_dev_checkout_root() -> Option<PathBuf> {
    if let Ok(exe) = std::env::current_exe() {
        for ancestor in exe.ancestors() {
            if looks_like_project_root(ancestor) {
                if let Ok(canon) = dunce::canonicalize(ancestor) {
                    return Some(canon);
                }
            }
        }
    }

    #[cfg(debug_assertions)]
    if let Some(manifest_dir) = option_env!("CARGO_MANIFEST_DIR") {
        if let Some(parent) = Path::new(manifest_dir).parent() {
            if looks_like_project_root(parent) {
                if let Ok(canon) = dunce::canonicalize(parent) {
                    return Some(canon);
                }
            }
        }
    }

    None
}

/// Pure, deterministic resolver for `data_root` vs `resource_root` across dev, CI override,
/// and installed Windows MSI/NSIS desktop environments.
pub fn resolve_app_paths_with_overrides(
    explicit_project_root: Option<&Path>,
    explicit_data_dir: Option<&Path>,
    explicit_resource_dir: Option<&Path>,
    dev_checkout_root: Option<&Path>,
    resource_dir_hint: Option<&Path>,
    local_app_data_base: Option<&Path>,
) -> AppPaths {
    let resolve_resource = |fallback: &Path| -> PathBuf {
        if let Some(exp_res) = explicit_resource_dir {
            if exp_res.is_dir() {
                return normalize_or_create_dir(exp_res, false);
            }
        }
        if let Some(hint) = resource_dir_hint {
            if hint.is_dir() && (looks_like_resource_root(hint) || dev_checkout_root.is_none()) {
                let candidate = if hint
                    .join("_up_")
                    .join("workers")
                    .join("worker_boot.py")
                    .is_file()
                {
                    hint.join("_up_")
                } else {
                    hint.to_path_buf()
                };
                return normalize_or_create_dir(&candidate, false);
            }
        }
        if looks_like_resource_root(fallback) {
            return normalize_or_create_dir(fallback, false);
        }
        if let Some(dev) = dev_checkout_root {
            if dev.is_dir() {
                return normalize_or_create_dir(dev, false);
            }
        }
        normalize_or_create_dir(fallback, false)
    };

    // 1. Explicit `JARVIS_PROJECT_ROOT` override (used by dev scripts and CI smoke tests).
    if let Some(proj) = explicit_project_root {
        let proj_norm = normalize_or_create_dir(proj, true);
        let data_root = match explicit_data_dir {
            Some(d) => normalize_or_create_dir(d, true),
            None => proj_norm.clone(),
        };
        let resource_root = resolve_resource(&proj_norm);
        return AppPaths {
            data_root,
            resource_root,
            is_packaged: false,
        };
    }

    // 2. Explicit `JARVIS_DATA_DIR` override without `JARVIS_PROJECT_ROOT` (packaged data override).
    if let Some(data_dir) = explicit_data_dir {
        let data_root = normalize_or_create_dir(data_dir, true);
        ensure_writable_data_subdirs(&data_root);
        let fallback_res = resource_dir_hint
            .or(dev_checkout_root)
            .unwrap_or(data_root.as_path());
        let resource_root = resolve_resource(fallback_res);
        return AppPaths {
            data_root,
            resource_root,
            is_packaged: true,
        };
    }

    // 3. Running inside a developer checkout (`package.json` + `src-tauri/` in exe ancestors).
    if let Some(dev_root) = dev_checkout_root {
        let canon_dev = normalize_or_create_dir(dev_root, false);
        let resource_root = match explicit_resource_dir {
            Some(r) if r.is_dir() => normalize_or_create_dir(r, false),
            _ => canon_dev.clone(),
        };
        return AppPaths {
            data_root: canon_dev,
            resource_root,
            is_packaged: false,
        };
    }

    // 4. Packaged installed desktop mode (MSI / NSIS): writable state lives in `%LOCALAPPDATA%\JarvisOS`.
    let raw_data_root = if let Some(local_base) = local_app_data_base {
        local_base.join("JarvisOS")
    } else if let Some(hint) = resource_dir_hint {
        hint.to_path_buf()
    } else {
        std::env::temp_dir().join("JarvisOS")
    };
    let data_root = normalize_or_create_dir(&raw_data_root, true);
    ensure_writable_data_subdirs(&data_root);

    let exe_dir_buf = std::env::current_exe()
        .ok()
        .and_then(|e| e.parent().map(|p| p.to_path_buf()));
    let fallback_res = resource_dir_hint
        .or(exe_dir_buf.as_deref())
        .unwrap_or(data_root.as_path());
    let resource_root = resolve_resource(fallback_res);

    AppPaths {
        data_root,
        resource_root,
        is_packaged: true,
    }
}

fn non_empty_env_path(var_name: &str) -> Option<PathBuf> {
    std::env::var_os(var_name)
        .filter(|v| !v.is_empty())
        .map(PathBuf::from)
}

/// Resolves application `data_root` and `resource_root` using environment overrides,
/// Tauri path hints (`resource_dir`, `app_local_data_dir`), and `%LOCALAPPDATA%\JarvisOS`.
pub fn resolve_app_paths(
    resource_dir_hint: Option<&Path>,
    app_local_data_hint: Option<&Path>,
) -> AppPaths {
    let explicit_project_root = non_empty_env_path("JARVIS_PROJECT_ROOT");
    let explicit_data_dir = non_empty_env_path("JARVIS_DATA_DIR");
    let explicit_resource_dir = non_empty_env_path("JARVIS_RESOURCE_ROOT");
    let dev_checkout = detect_dev_checkout_root();

    let env_local_appdata = non_empty_env_path("LOCALAPPDATA").or_else(|| {
        app_local_data_hint
            .and_then(|p| p.parent().map(|parent| parent.to_path_buf()))
            .or_else(|| app_local_data_hint.map(|p| p.to_path_buf()))
    });

    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|e| e.parent().map(|p| p.to_path_buf()));
    let effective_resource_hint = resource_dir_hint.or(exe_dir.as_deref());

    resolve_app_paths_with_overrides(
        explicit_project_root.as_deref(),
        explicit_data_dir.as_deref(),
        explicit_resource_dir.as_deref(),
        dev_checkout.as_deref(),
        effective_resource_hint,
        env_local_appdata.as_deref(),
    )
}

/// Resolves the canonical writable workspace/data root without relying on arbitrary CWD state.
pub fn resolve_project_root() -> PathBuf {
    resolve_app_paths(None, None).data_root
}

/// Resolves the canonical read-only resource/code root (`workers/`, bundled assets).
pub fn resolve_resource_root() -> PathBuf {
    resolve_app_paths(None, None).resource_root
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
    let is_windows_drive_path =
        bytes.len() >= 2 && bytes[0].is_ascii_alphabetic() && bytes[1] == b':';

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
                    if trimmed.to_ascii_lowercase().starts_with(&prefix)
                        && trimmed.len() > prefix.len()
                    {
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

/// Validates a path identifier (`doc_id`, `frame_id`, etc.) against traversal, separators, and reserved names.
pub fn is_safe_identifier(value: &str) -> bool {
    if value.is_empty()
        || value.len() > 128
        || value == "."
        || value == ".."
        || value.contains("..")
    {
        return false;
    }
    if !value
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | '.'))
    {
        return false;
    }
    !has_win32_reserved_name(Path::new(value))
}

/// Returns true if a canonical path points inside OS-protected system directories.
pub fn is_blocked_system_path(canon: &Path) -> bool {
    let lower = canon
        .to_string_lossy()
        .replace('\\', "/")
        .to_ascii_lowercase();
    #[cfg(windows)]
    {
        for prefix in [
            "c:/windows",
            "c:/program files",
            "c:/program files (x86)",
            "c:/programdata",
        ] {
            if lower == prefix || lower.starts_with(&format!("{prefix}/")) {
                return true;
            }
        }
    }
    #[cfg(not(windows))]
    {
        for prefix in ["/etc", "/bin", "/sbin", "/usr", "/proc", "/sys", "/dev"] {
            if lower == prefix || lower.starts_with(&format!("{prefix}/")) {
                return true;
            }
        }
    }
    let _ = lower;
    false
}

/// Resolves an existing regular file strictly confined inside `root`, rejecting any symlink along the relative path.
pub fn ensure_confined_existing_file(root: &Path, target: &Path) -> Result<PathBuf, AppError> {
    let canon_root = dunce::canonicalize(root).map_err(|err| {
        AppError::new(
            "ROOT_UNAVAILABLE",
            format!("Allowed root could not be canonicalized: {err}"),
        )
    })?;
    let canon_target = resolve_confined_path(&canon_root, target)?;

    // Reject symlinks on the target or any intermediate directory below canon_root.
    let rel = canon_target.strip_prefix(&canon_root).map_err(|_| {
        AppError::new(
            "PATH_JAIL_VIOLATION",
            "Target path resolves outside allowed root.",
        )
    })?;

    let raw_rel_opt = if target.is_absolute() {
        target
            .strip_prefix(&canon_root)
            .ok()
            .or_else(|| target.strip_prefix(root).ok())
    } else {
        Some(target)
    };

    if let Some(raw_rel) = raw_rel_opt {
        let mut raw_cursor = canon_root.clone();
        for comp in raw_rel.components() {
            if let Component::Normal(seg) = comp {
                raw_cursor.push(seg);
                let meta = fs::symlink_metadata(&raw_cursor)
                    .map_err(|_| AppError::new("NOT_FOUND", "Target path does not exist."))?;
                if meta.file_type().is_symlink() {
                    return Err(AppError::new(
                        "SYMLINK_BLOCKED",
                        "Symbolic links are not permitted.",
                    ));
                }
            }
        }
    }

    let mut cursor = canon_root;
    for comp in rel.components() {
        cursor.push(comp);
        let meta = fs::symlink_metadata(&cursor)
            .map_err(|_| AppError::new("NOT_FOUND", "Target path does not exist."))?;
        if meta.file_type().is_symlink() {
            return Err(AppError::new(
                "SYMLINK_BLOCKED",
                "Symbolic links are not permitted.",
            ));
        }
    }

    let meta = fs::symlink_metadata(&canon_target)
        .map_err(|_| AppError::new("NOT_FOUND", "Target file does not exist."))?;
    if meta.file_type().is_symlink() || !meta.is_file() {
        return Err(AppError::new(
            "NOT_A_REGULAR_FILE",
            "Target must be a regular non-symlink file.",
        ));
    }

    Ok(canon_target)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn packaged_mode_separates_localappdata_from_readonly_resource_dir() {
        let dir = tempdir().unwrap();
        let resource_dir = dir.path().join("ProgramFiles").join("JARVIS OS");
        fs::create_dir_all(resource_dir.join("workers")).unwrap();
        fs::write(
            resource_dir.join("workers").join("worker_boot.py"),
            b"# boot",
        )
        .unwrap();

        let local_app_data = dir.path().join("AppData").join("Local");
        fs::create_dir_all(&local_app_data).unwrap();

        let paths = resolve_app_paths_with_overrides(
            None,
            None,
            None,
            None,
            Some(&resource_dir),
            Some(&local_app_data),
        );

        assert!(paths.is_packaged);
        assert_eq!(
            paths.resource_root,
            dunce::canonicalize(&resource_dir).unwrap()
        );
        let expected_data = dunce::canonicalize(local_app_data.join("JarvisOS")).unwrap();
        assert_eq!(paths.data_root, expected_data);
        assert!(paths.data_root.join("data").join("study").is_dir());
        assert!(paths.data_root.join("data").join("sentinel").is_dir());
        assert!(paths.data_root.join("obsidian_vault").is_dir());
        assert!(paths.data_root.join("workspace").is_dir());
        assert!(!resource_dir.join("data").exists());
        assert!(!resource_dir.join("database.db").exists());
    }

    #[test]
    fn dev_checkout_and_explicit_override_resolve_deterministically() {
        let dir = tempdir().unwrap();
        let dev_root = dir.path().join("repo");
        fs::create_dir_all(dev_root.join("src-tauri")).unwrap();
        fs::create_dir_all(dev_root.join("workers")).unwrap();
        fs::write(dev_root.join("package.json"), b"{}").unwrap();
        fs::write(dev_root.join("workers").join("worker_boot.py"), b"# boot").unwrap();

        let dev_paths =
            resolve_app_paths_with_overrides(None, None, None, Some(&dev_root), None, None);
        let canon_dev = dunce::canonicalize(&dev_root).unwrap();
        assert!(!dev_paths.is_packaged);
        assert_eq!(dev_paths.data_root, canon_dev);
        assert_eq!(dev_paths.resource_root, canon_dev);

        let smoke_root = dir.path().join("smoke_state");
        let override_paths = resolve_app_paths_with_overrides(
            Some(&smoke_root),
            None,
            None,
            Some(&dev_root),
            Some(&dev_root),
            None,
        );
        assert!(!override_paths.is_packaged);
        assert_eq!(
            override_paths.data_root,
            dunce::canonicalize(&smoke_root).unwrap()
        );
        assert_eq!(override_paths.resource_root, canon_dev);
    }
}

//! Native Rust fast-path handlers for deterministic IDE Project, Planner, and AST routes.
//!
//! Covers all 10 deterministic project workspace operations (`list_projects`,
//! `create_project`, `delete_project`, `open_project`, `save_project_file`,
//! `create_project_file`, `rename_project_file`, `delete_project_file`,
//! `run_project`, `stop_project`) plus `get_planner_state` and `get_ast_state`.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::sync::Arc;
use std::time::UNIX_EPOCH;

use chrono::Utc;
use rusqlite::{Connection, OpenFlags};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use tauri::{AppHandle, Emitter};

use crate::commands::media::RuntimeServices;
use crate::error::AppError;
use crate::permissions::path_jail::{ensure_confined_existing_file, resolve_confined_path};
use crate::process::preview_server::{PreviewOutputSink, PreviewServerHandle};
use crate::storage::atomic_fs::{atomic_write_bytes, atomic_write_string};

const MAX_VIEW_FILE_BYTES: usize = 500_000;

const TEXT_FILE_SUFFIXES: &[&str] = &[
    ".css", ".html", ".htm", ".js", ".jsx", ".json", ".md", ".mjs", ".cjs", ".py", ".toml", ".ts",
    ".tsx", ".txt", ".yaml", ".yml",
];

const IGNORED_DIRECTORIES: &[&str] = &[
    ".git",
    ".jarvis",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "out",
    "venv",
];

fn projects_root_dir(workspace_root: &Path) -> PathBuf {
    workspace_root.join("workspace").join("projects")
}

fn project_metadata_root_dir(workspace_root: &Path) -> PathBuf {
    workspace_root.join("workspace").join(".jarvis").join("projects")
}

fn matches_project_id_pattern(value: &str) -> bool {
    let bytes = value.as_bytes();
    if bytes.is_empty() || bytes.len() > 80 || !bytes[0].is_ascii_alphanumeric() {
        return false;
    }
    bytes
        .iter()
        .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-'))
}

fn validate_project_id(raw: &str) -> Result<String, AppError> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err(AppError::new("PROJECT_INVALID_ID", "project_id obrigatorio."));
    }

    let mut clean_id = if matches_project_id_pattern(trimmed) {
        trimmed.to_string()
    } else {
        let mapped: String = trimmed
            .chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-') {
                    c
                } else {
                    '-'
                }
            })
            .collect();
        let trimmed_edges = mapped.trim_matches(|c| matches!(c, '.' | '_' | '-'));
        let mut collapsed = String::with_capacity(trimmed_edges.len());
        let mut prev_dash = false;
        for c in trimmed_edges.chars() {
            if c == '-' {
                if !prev_dash {
                    collapsed.push(c);
                }
                prev_dash = true;
            } else {
                prev_dash = false;
                collapsed.push(c);
            }
        }
        if !matches_project_id_pattern(&collapsed) {
            return Err(AppError::new("PROJECT_INVALID_ID", "project_id invalido."));
        }
        collapsed
    };

    if clean_id.len() > 80 {
        clean_id.truncate(80);
    }

    let lower = clean_id.to_ascii_lowercase();
    if lower.contains("obsidian") || matches!(lower.as_str(), "sandbox" | "sandbox_dir") {
        return Err(AppError::new(
            "PROJECT_INVALID_ID",
            "Este diretorio nao pode ser usado como projeto IDE.",
        ));
    }

    Ok(clean_id)
}

fn resolve_existing_project_dir(workspace_root: &Path, clean_id: &str) -> Result<PathBuf, AppError> {
    let base = projects_root_dir(workspace_root);
    if !base.is_dir() {
        return Err(AppError::new(
            "PROJECT_NOT_FOUND",
            format!("Projeto '{clean_id}' nao existe."),
        ));
    }
    let resolved = resolve_confined_path(&base, Path::new(clean_id))?;
    if !resolved.is_dir() {
        return Err(AppError::new(
            "PROJECT_NOT_FOUND",
            format!("Projeto '{clean_id}' nao existe."),
        ));
    }
    if fs::symlink_metadata(&resolved)
        .map(|m| m.file_type().is_symlink())
        .unwrap_or(false)
    {
        return Err(AppError::new(
            "SYMLINK_BLOCKED",
            "Projeto simbólico não permitido.",
        ));
    }
    Ok(resolved)
}

fn project_metadata_dir(workspace_root: &Path, clean_id: &str) -> PathBuf {
    project_metadata_root_dir(workspace_root).join(clean_id)
}

fn is_ignored_dir_name(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    IGNORED_DIRECTORIES
        .iter()
        .any(|ignored| ignored.eq_ignore_ascii_case(&lower))
}

fn is_allowed_text_suffix(path: &str) -> bool {
    let lower = path.to_ascii_lowercase();
    TEXT_FILE_SUFFIXES.iter().any(|suffix| lower.ends_with(suffix))
}

fn normalize_rel_file_path(raw: &str) -> Result<String, AppError> {
    let normalized = raw.replace('\\', "/").trim_matches('/').to_string();
    if normalized.is_empty()
        || normalized.contains('\0')
        || normalized.contains(':')
        || normalized.starts_with('/')
    {
        return Err(AppError::new("INVALID_PATH", "Caminho de ficheiro invalido."));
    }
    let segments: Vec<&str> = normalized.split('/').collect();
    if segments.iter().any(|seg| seg.is_empty() || *seg == "." || *seg == "..") {
        return Err(AppError::new("INVALID_PATH", "Caminho de ficheiro invalido."));
    }
    if segments.len() > 1
        && segments[..segments.len() - 1]
            .iter()
            .any(|seg| is_ignored_dir_name(seg))
    {
        return Err(AppError::new(
            "PROJECT_PATH_BLOCKED",
            "Edicao de diretorios gerados ou dependencias nao permitida.",
        ));
    }
    if !is_allowed_text_suffix(&normalized) {
        return Err(AppError::new(
            "PROJECT_UNSUPPORTED_FILE",
            "O editor apenas permite ficheiros de texto suportados.",
        ));
    }
    Ok(normalized)
}

fn resolve_project_text_file(
    project_dir: &Path,
    relative_path: &str,
    must_exist: bool,
) -> Result<(PathBuf, String), AppError> {
    let normalized = normalize_rel_file_path(relative_path)?;
    let target = resolve_confined_path(project_dir, Path::new(&normalized))?;
    if let Ok(meta) = fs::symlink_metadata(&target) {
        if meta.file_type().is_symlink() {
            return Err(AppError::new(
                "SYMLINK_BLOCKED",
                "Edicao de links simbolicos nao permitida.",
            ));
        }
    }
    if must_exist {
        let canon = ensure_confined_existing_file(project_dir, Path::new(&normalized))?;
        return Ok((canon, normalized));
    }
    Ok((target, normalized))
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    hex::encode(hasher.finalize())
}

fn read_json_value_safe(path: &Path) -> Option<Value> {
    let meta = fs::symlink_metadata(path).ok()?;
    if meta.file_type().is_symlink() || !meta.is_file() {
        return None;
    }
    let raw = fs::read_to_string(path).ok()?;
    serde_json::from_str::<Value>(&raw).ok()
}

fn get_display_name(workspace_root: &Path, project_id: &str, project_dir: &Path) -> String {
    let ctx_path = project_metadata_dir(workspace_root, project_id).join("project_context.json");
    if let Some(ctx) = read_json_value_safe(&ctx_path) {
        if let Some(name) = ctx.get("project_name").and_then(Value::as_str) {
            let trimmed = name.trim();
            if !trimmed.is_empty() {
                return trimmed.to_string();
            }
        }
    }

    if let Some(pkg) = read_json_value_safe(&project_dir.join("package.json")) {
        if let Some(desc) = pkg.get("description").and_then(Value::as_str) {
            if let Some(stripped) = desc.strip_prefix("Projeto ") {
                let t = stripped.trim();
                if !t.is_empty() {
                    return t.to_string();
                }
            }
        }
        if let Some(name) = pkg.get("name").and_then(Value::as_str) {
            let trimmed = name.trim();
            if !trimmed.is_empty() {
                return trimmed.to_string();
            }
        }
    }

    let readme_path = project_dir.join("README.md");
    if let Ok(raw) = fs::read_to_string(&readme_path) {
        if let Some(first_line) = raw.lines().next() {
            if let Some(heading) = first_line.trim().strip_prefix("# ") {
                let h = heading.trim();
                if !h.is_empty() {
                    return h.to_string();
                }
            }
        }
    }

    project_id.to_string()
}

fn list_projects_payload(workspace_root: &Path) -> Vec<Value> {
    let root = projects_root_dir(workspace_root);
    if !root.is_dir() {
        return Vec::new();
    }
    let Ok(entries) = fs::read_dir(&root) else {
        return Vec::new();
    };
    let mut dirs: Vec<(String, PathBuf)> = Vec::new();
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if fs::symlink_metadata(&path)
            .map(|m| m.file_type().is_symlink() || !m.is_dir())
            .unwrap_or(true)
        {
            continue;
        }
        if !matches_project_id_pattern(&name) {
            continue;
        }
        let lower = name.to_ascii_lowercase();
        if lower.contains("obsidian") || matches!(lower.as_str(), "sandbox" | "sandbox_dir") {
            continue;
        }
        dirs.push((name, path));
    }
    dirs.sort_by(|a, b| a.0.to_ascii_lowercase().cmp(&b.0.to_ascii_lowercase()));

    dirs.into_iter()
        .map(|(project_id, dir_path)| {
            let display = get_display_name(workspace_root, &project_id, &dir_path);
            let real_path = dunce::canonicalize(&dir_path)
                .unwrap_or(dir_path)
                .to_string_lossy()
                .to_string();
            json!({
                "project_id": project_id,
                "project_name": display,
                "root_path": real_path,
            })
        })
        .collect()
}

fn collect_project_files(
    root: &Path,
    current: &Path,
    files: &mut BTreeMap<String, String>,
    hashes: &mut BTreeMap<String, String>,
) {
    let Ok(read_dir) = fs::read_dir(current) else {
        return;
    };
    let mut subdirs: Vec<PathBuf> = Vec::new();
    let mut regular_files: Vec<PathBuf> = Vec::new();

    for entry in read_dir.flatten() {
        let path = entry.path();
        let meta = match fs::symlink_metadata(&path) {
            Ok(m) if !m.file_type().is_symlink() => m,
            _ => continue,
        };
        let name = entry.file_name().to_string_lossy().to_string();
        if meta.is_dir() {
            if !is_ignored_dir_name(&name) {
                subdirs.push(path);
            }
        } else if meta.is_file() {
            regular_files.push(path);
        }
    }

    subdirs.sort();
    regular_files.sort();

    for file_path in regular_files {
        let name = file_path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or_default();
        if !is_allowed_text_suffix(name) {
            continue;
        }
        let Ok(meta) = fs::metadata(&file_path) else {
            continue;
        };
        if meta.len() as usize > MAX_VIEW_FILE_BYTES {
            continue;
        }
        let Ok(raw_bytes) = fs::read(&file_path) else {
            continue;
        };
        let Ok(rel) = file_path.strip_prefix(root) else {
            continue;
        };
        let rel_str = rel.to_string_lossy().replace('\\', "/");
        hashes.insert(rel_str.clone(), sha256_hex(&raw_bytes));
        let body = raw_bytes
            .strip_prefix(&[0xEF, 0xBB, 0xBF])
            .unwrap_or(&raw_bytes);
        let decoded = String::from_utf8_lossy(body).into_owned();
        files.insert(rel_str, decoded);
    }

    for subdir in subdirs {
        collect_project_files(root, &subdir, files, hashes);
    }
}

fn preserve_line_endings(original_body: &[u8], content: &str) -> String {
    let crlf = original_body.windows(2).filter(|w| *w == b"\r\n").count();
    let lf = original_body.iter().filter(|b| **b == b'\n').count().saturating_sub(crlf);
    let cr = original_body.iter().filter(|b| **b == b'\r').count().saturating_sub(crlf);

    let newline = if crlf > 0 && lf == 0 && cr == 0 {
        "\r\n"
    } else if lf > 0 && crlf == 0 && cr == 0 {
        "\n"
    } else if cr > 0 && crlf == 0 && lf == 0 {
        "\r"
    } else {
        return content.to_string();
    };

    content
        .replace("\r\n", "\n")
        .replace('\r', "\n")
        .replace('\n', newline)
}

fn detect_project_stack_and_scripts(
    project_dir: &Path,
    files: &BTreeMap<String, String>,
) -> (Value, Vec<String>, Vec<String>, Vec<String>, BTreeMap<String, String>, Vec<String>) {
    let pkg_json = read_json_value_safe(&project_dir.join("package.json")).unwrap_or(Value::Null);

    let mut stack: BTreeSet<String> = BTreeSet::new();
    let mut frameworks: BTreeSet<String> = BTreeSet::new();
    let mut managers: BTreeSet<String> = BTreeSet::new();
    let mut scripts: BTreeMap<String, String> = BTreeMap::new();
    let mut entrypoints: Vec<String> = Vec::new();

    if files.keys().any(|k| k.ends_with(".py")) || project_dir.join("requirements.txt").is_file() {
        stack.insert("Python".to_string());
    }
    if project_dir.join("package.json").is_file() {
        stack.insert("Node".to_string());
        managers.insert("npm".to_string());
    }
    if files.keys().any(|k| k.ends_with(".html") || k.ends_with(".htm")) {
        stack.insert("HTML/JavaScript".to_string());
    }
    if files.keys().any(|k| k.ends_with(".ts") || k.ends_with(".tsx")) {
        stack.insert("TypeScript".to_string());
    }
    if files.keys().any(|k| k.ends_with(".rs")) || project_dir.join("Cargo.toml").is_file() {
        stack.insert("Rust".to_string());
        managers.insert("Cargo".to_string());
    }
    if project_dir.join("requirements.txt").is_file() {
        managers.insert("pip".to_string());
    }

    if let Some(script_map) = pkg_json.get("scripts").and_then(Value::as_object) {
        for (k, v) in script_map {
            if let Some(s) = v.as_str() {
                scripts.insert(k.clone(), s.to_string());
            }
        }
    }

    for dep_section in ["dependencies", "devDependencies"] {
        if let Some(deps) = pkg_json.get(dep_section).and_then(Value::as_object) {
            if deps.contains_key("react") {
                frameworks.insert("React".to_string());
            }
            if deps.contains_key("vite") {
                frameworks.insert("Vite".to_string());
            }
            if deps.contains_key("next") {
                frameworks.insert("Next.js".to_string());
            }
            if deps.contains_key("express") {
                frameworks.insert("Express".to_string());
            }
        }
    }

    for candidate in [
        "index.html",
        "app.js",
        "main.js",
        "app.py",
        "main.py",
        "src/main.ts",
        "src/main.tsx",
        "src/index.js",
        "src/index.tsx",
    ] {
        if files.contains_key(candidate) {
            entrypoints.push(candidate.to_string());
        }
    }

    (
        pkg_json,
        stack.into_iter().collect(),
        frameworks.into_iter().collect(),
        managers.into_iter().collect(),
        scripts,
        entrypoints,
    )
}

fn load_symbols_index(workspace_root: &Path, project_id: &str) -> Value {
    let idx_path = project_metadata_dir(workspace_root, project_id).join("symbols_index.json");
    match read_json_value_safe(&idx_path) {
        Some(Value::Object(obj)) if !obj.is_empty() => Value::Object(obj),
        _ => json!({}),
    }
}

fn build_project_context_events(
    workspace_root: &Path,
    project_id: &str,
) -> Result<Vec<Value>, AppError> {
    let clean_id = validate_project_id(project_id)?;
    let proj_dir = resolve_existing_project_dir(workspace_root, &clean_id)?;
    let meta_dir = project_metadata_dir(workspace_root, &clean_id);

    let mut files = BTreeMap::new();
    let mut hashes = BTreeMap::new();
    collect_project_files(&proj_dir, &proj_dir, &mut files, &mut hashes);

    let (pkg_json, stack, frameworks, package_managers, package_scripts, entrypoints) =
        detect_project_stack_and_scripts(&proj_dir, &files);

    let display_name = pkg_json
        .get("name")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(str::to_string)
        .unwrap_or_else(|| get_display_name(workspace_root, &clean_id, &proj_dir));

    let existing_ctx = read_json_value_safe(&meta_dir.join("project_context.json"));
    let diagnostics = existing_ctx
        .as_ref()
        .and_then(|c| c.get("diagnostics"))
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    let ast_index = existing_ctx
        .as_ref()
        .and_then(|c| c.get("ast_index"))
        .cloned()
        .unwrap_or_else(|| json!({}));
    let last_indexed_at = existing_ctx
        .as_ref()
        .and_then(|c| c.get("last_indexed_at"))
        .cloned()
        .unwrap_or(Value::Null);

    let suggested_commands: Vec<Value> = ["lint", "build", "test", "typecheck", "check"]
        .iter()
        .filter(|k| package_scripts.contains_key(**k))
        .map(|k| {
            json!({
                "kind": k,
                "command": format!("npm run {k}"),
                "source": "package.json",
            })
        })
        .collect();

    let source_roots: Vec<String> = ["src", "app", "backend", "frontend"]
        .iter()
        .filter(|dir| proj_dir.join(dir).is_dir())
        .map(|d| d.to_string())
        .collect();

    let canon_root = dunce::canonicalize(&proj_dir)
        .unwrap_or_else(|_| proj_dir.clone())
        .to_string_lossy()
        .to_string();

    let context_obj = json!({
        "project_id": clean_id,
        "root_path": canon_root,
        "project_name": display_name,
        "python_executable": Value::Null,
        "runtime_source": "unavailable",
        "runtime_version": Value::Null,
        "stack": stack,
        "frameworks": frameworks,
        "package_managers": package_managers,
        "entrypoints": entrypoints,
        "source_roots": source_roots,
        "package_scripts": package_scripts,
        "suggested_commands": suggested_commands,
        "git_state": { "is_repo": proj_dir.join(".git").exists() },
        "ast_index": ast_index,
        "last_indexed_at": last_indexed_at,
        "diagnostics": diagnostics,
    });

    let symbols = load_symbols_index(workspace_root, &clean_id);
    let arch_snapshot = read_json_value_safe(&meta_dir.join("architecture_snapshot.json"));

    let mut payload_event = json!({
        "type": "project_context",
        "context": context_obj,
        "files": files,
        "file_hashes": hashes,
        "symbols": symbols,
    });
    if let (Some(obj), Some(snap)) = (payload_event.as_object_mut(), &arch_snapshot) {
        obj.insert("architecture_snapshot".to_string(), snap.clone());
    }

    let ast_data = match &symbols {
        Value::Object(map) if !map.is_empty() => Value::Object(map.clone()),
        _ => Value::Null,
    };

    let mut events = vec![
        payload_event,
        json!({
            "type": "ast_state",
            "project_id": clean_id,
            "data": ast_data,
        }),
    ];

    if let Some(snap) = arch_snapshot {
        events.push(json!({
            "type": "architecture_snapshot",
            "project_id": clean_id,
            "data": snap,
        }));
    }

    Ok(events)
}

fn load_latest_coding_session(workspace_root: &Path, project_id: &str) -> Value {
    let sessions_dir = project_metadata_dir(workspace_root, project_id).join("coding_sessions");
    if !sessions_dir.is_dir() {
        return Value::Null;
    }
    let Ok(entries) = fs::read_dir(&sessions_dir) else {
        return Value::Null;
    };
    let mut best: Option<(u128, PathBuf)> = None;
    for entry in entries.flatten() {
        let session_file = entry.path().join("session.json");
        if let Ok(meta) = fs::symlink_metadata(&session_file) {
            if meta.file_type().is_symlink() || !meta.is_file() {
                continue;
            }
            let modified = meta
                .modified()
                .ok()
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_nanos())
                .unwrap_or(0);
            if best.as_ref().map(|(ts, _)| modified > *ts).unwrap_or(true) {
                best = Some((modified, session_file));
            }
        }
    }
    best.and_then(|(_, path)| read_json_value_safe(&path))
        .unwrap_or(Value::Null)
}

fn load_mission_from_state_db(db_path: &Path, mission_id: &str) -> Option<Value> {
    let conn = Connection::open_with_flags(
        db_path,
        OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
    )
    .ok()?;
    let mut stmt = conn
        .prepare(
            "SELECT mission_id, project_id, title, objective, description, status, \
             current_phase, progress, metadata_json, created_at, updated_at, started_at, \
             completed_at, version FROM missions WHERE mission_id = ?1 LIMIT 1",
        )
        .ok()?;
    stmt.query_row([mission_id], |row| {
        let metadata_raw: String = row.get(8)?;
        let metadata: Value = serde_json::from_str(&metadata_raw).unwrap_or_else(|_| json!({}));
        let mut obj = serde_json::Map::new();
        obj.insert("mission_id".into(), Value::String(row.get(0)?));
        obj.insert("project_id".into(), Value::String(row.get(1)?));
        obj.insert("title".into(), Value::String(row.get(2)?));
        obj.insert("objective".into(), Value::String(row.get(3)?));
        obj.insert("description".into(), Value::String(row.get(4)?));
        obj.insert("status".into(), Value::String(row.get(5)?));
        obj.insert("current_phase".into(), Value::String(row.get(6)?));
        obj.insert("progress".into(), json!(row.get::<_, f64>(7)?));
        obj.insert("metadata".into(), metadata.clone());
        obj.insert("created_at".into(), Value::String(row.get(9)?));
        obj.insert("updated_at".into(), Value::String(row.get(10)?));
        obj.insert(
            "started_at".into(),
            row.get::<_, Option<String>>(11)?
                .map(Value::String)
                .unwrap_or(Value::Null),
        );
        obj.insert(
            "completed_at".into(),
            row.get::<_, Option<String>>(12)?
                .map(Value::String)
                .unwrap_or(Value::Null),
        );
        obj.insert("version".into(), json!(row.get::<_, i64>(13)?));

        for field in [
            "project_name",
            "project_path",
            "execution_id",
            "current_stage",
            "last_event_at",
            "last_event_sequence",
        ] {
            if let Some(val) = metadata.get(field) {
                obj.insert(field.into(), val.clone());
            }
        }
        Ok(Value::Object(obj))
    })
    .ok()
}

fn list_missions_for_project(workspace_root: &Path, project_id: &str) -> Vec<Value> {
    let missions_dir = project_metadata_dir(workspace_root, project_id).join("missions");
    if !missions_dir.is_dir() {
        return Vec::new();
    }
    let Ok(entries) = fs::read_dir(&missions_dir) else {
        return Vec::new();
    };
    let mut results = Vec::new();
    for entry in entries.flatten() {
        let dir_path = entry.path();
        if !dir_path.is_dir() {
            continue;
        }
        let mission_id = entry.file_name().to_string_lossy().to_string();
        let db_path = dir_path.join("state.db");
        let loaded = if db_path.is_file() {
            load_mission_from_state_db(&db_path, &mission_id)
                .or_else(|| read_json_value_safe(&dir_path.join("mission.json")))
        } else {
            read_json_value_safe(&dir_path.join("mission.json"))
        };
        if let Some(m) = loaded {
            results.push(m);
        }
    }
    results.sort_by(|a, b| {
        let ua = a.get("updated_at").and_then(Value::as_str).unwrap_or("");
        let ub = b.get("updated_at").and_then(Value::as_str).unwrap_or("");
        ub.cmp(ua)
    });
    results
}

fn read_persistent_plan_state(workspace_root: &Path) -> Value {
    let plan_path = workspace_root.join(".jarvis_plan.json");
    let Some(plan_val) = read_json_value_safe(&plan_path) else {
        return Value::Null;
    };
    let Some(obj) = plan_val.as_object() else {
        return Value::Null;
    };
    let status = obj
        .get("status")
        .and_then(Value::as_str)
        .unwrap_or("")
        .trim()
        .to_ascii_uppercase();
    if matches!(status.as_str(), "NONE" | "DONE" | "COMPLETED") {
        return Value::Null;
    }
    let goal = obj.get("goal").and_then(Value::as_str).unwrap_or("").trim();
    let has_steps = obj
        .get("steps")
        .and_then(Value::as_array)
        .map(|arr| !arr.is_empty())
        .unwrap_or(false);
    if goal.is_empty() && !has_steps {
        return Value::Null;
    }
    plan_val
}

fn render_web_app_files(clean_id: &str, display_name: &str) -> Vec<(&'static str, String)> {
    let index_html = format!(
        "<!DOCTYPE html>\n<html lang=\"pt\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>{display_name}</title>\n    <link rel=\"stylesheet\" href=\"styles.css\">\n</head>\n<body>\n    <div id=\"app\">\n        <h1>{display_name}</h1>\n        <p>Projeto criado via JARVIS OS.</p>\n    </div>\n    <script src=\"app.js\"></script>\n</body>\n</html>"
    );
    let styles_css = "body {\n    font-family: system-ui, -apple-system, sans-serif;\n    background: #0d1117;\n    color: #e6edf3;\n    padding: 2rem;\n}"
        .to_string();
    let app_js = format!("console.log('Iniciado {display_name}');");
    let package_json = serde_json::to_string_pretty(&json!({
        "name": clean_id,
        "version": "1.0.0",
        "description": format!("Projeto {display_name}"),
        "main": "app.js",
        "scripts": {
            "start": "node app.js"
        }
    }))
    .unwrap_or_else(|_| "{}".to_string());

    vec![
        ("index.html", index_html),
        ("styles.css", styles_css),
        ("app.js", app_js),
        ("package.json", package_json),
    ]
}

fn system_event(content: impl Into<String>) -> Value {
    json!({
        "type": "system",
        "content": content.into(),
    })
}

fn check_no_symlink_components(base: &Path, candidate_rel: &Path) -> Result<(), AppError> {
    let mut cursor = base.to_path_buf();
    for comp in candidate_rel.components() {
        if let Component::Normal(seg) = comp {
            cursor.push(seg);
            if let Ok(meta) = fs::symlink_metadata(&cursor) {
                if meta.file_type().is_symlink() {
                    return Err(AppError::new(
                        "SYMLINK_BLOCKED",
                        "Links simbolicos nao sao permitidos neste caminho.",
                    ));
                }
            }
        }
    }
    Ok(())
}

/// Core testable implementation of all 12 deterministic Project / Planner / AST WebSocket routes.
pub async fn execute_project_message(
    workspace_root: &Path,
    preview: &PreviewServerHandle,
    msg_type: &str,
    message: &Value,
    preview_sink: Option<PreviewOutputSink>,
) -> Result<Option<Vec<Value>>, AppError> {
    match msg_type {
        "get_planner_state" => Ok(Some(vec![json!({
            "type": "planner_state",
            "data": read_persistent_plan_state(workspace_root),
        })])),

        "get_ast_state" => {
            let pid = message
                .get("project_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .or_else(|| preview.selected_project_id());

            let ast_data = if let Some(raw_pid) = pid {
                match validate_project_id(&raw_pid) {
                    Ok(clean) => match load_symbols_index(workspace_root, &clean) {
                        Value::Object(map) if !map.is_empty() => Value::Object(map),
                        _ => Value::Null,
                    },
                    Err(_) => Value::Null,
                }
            } else {
                Value::Null
            };

            Ok(Some(vec![json!({
                "type": "ast_state",
                "data": ast_data,
            })]))
        }

        "list_projects" => Ok(Some(vec![json!({
            "type": "projects_list",
            "projects": list_projects_payload(workspace_root),
        })])),

        "create_project" => {
            let raw_id = message
                .get("project_id")
                .and_then(Value::as_str)
                .unwrap_or("");
            let clean_id = match validate_project_id(raw_id) {
                Ok(id) => id,
                Err(err) => {
                    return Ok(Some(vec![system_event(format!(
                        "Erro ao criar projeto: {}",
                        err.message
                    ))]));
                }
            };

            let base_projects = projects_root_dir(workspace_root);
            if let Err(err) = fs::create_dir_all(&base_projects) {
                return Ok(Some(vec![system_event(format!(
                    "Erro ao criar projeto: {err}"
                ))]));
            }
            let target_proj = base_projects.join(&clean_id);
            if target_proj.exists() {
                return Ok(Some(vec![system_event(format!(
                    "Erro ao criar projeto: O projeto '{clean_id}' ja existe."
                ))]));
            }
            if let Err(err) = fs::create_dir_all(&target_proj) {
                return Ok(Some(vec![system_event(format!(
                    "Erro ao criar projeto: {err}"
                ))]));
            }

            let display_name = message
                .get("project_name")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .unwrap_or_else(|| clean_id.clone());
            let template = message
                .get("template")
                .and_then(Value::as_str)
                .map(str::trim);

            if template == Some("web-app") {
                for (name, content) in render_web_app_files(&clean_id, &display_name) {
                    atomic_write_string(&target_proj, &target_proj.join(name), &content)?;
                }
            } else {
                let readme = format!("# {display_name}\n\nProjeto criado via JARVIS OS.\n");
                atomic_write_string(&target_proj, &target_proj.join("README.md"), &readme)?;
            }

            let meta_dir = project_metadata_dir(workspace_root, &clean_id);
            fs::create_dir_all(&meta_dir).map_err(|err| {
                AppError::new("PROJECT_META_FAILED", format!("Failed creating meta dir: {err}"))
            })?;
            let ctx_json = serde_json::to_string_pretty(&json!({
                "project_id": clean_id,
                "project_name": display_name,
                "created_at": Utc::now().to_rfc3339(),
            }))
            .unwrap_or_else(|_| "{}".to_string());
            atomic_write_string(&meta_dir, &meta_dir.join("project_context.json"), &ctx_json)?;

            preview.set_selected_project_id(Some(clean_id.clone()));
            let mut events = build_project_context_events(workspace_root, &clean_id)?;
            events.push(json!({
                "type": "projects_list",
                "projects": list_projects_payload(workspace_root),
            }));
            events.push(system_event(format!(
                "Projeto '{display_name}' criado com sucesso."
            )));
            Ok(Some(events))
        }

        "open_project" => {
            let raw_id = message
                .get("project_id")
                .and_then(Value::as_str)
                .unwrap_or("");
            let clean_id = match validate_project_id(raw_id) {
                Ok(id) => id,
                Err(err) => return Ok(Some(vec![system_event(err.message)])),
            };
            if let Err(err) = resolve_existing_project_dir(workspace_root, &clean_id) {
                return Ok(Some(vec![system_event(err.message)]));
            }

            let mut events = vec![json!({
                "type": "project_intake_status",
                "project_id": clean_id,
                "status": "ANALYZING_PROJECT",
            })];
            events.extend(build_project_context_events(workspace_root, &clean_id)?);
            events.push(json!({
                "type": "coding_session",
                "data": load_latest_coding_session(workspace_root, &clean_id),
            }));
            events.push(json!({
                "type": "mission_list",
                "project_id": clean_id,
                "missions": list_missions_for_project(workspace_root, &clean_id),
            }));
            preview.set_selected_project_id(Some(clean_id.clone()));
            events.push(json!({
                "type": "project_intake_status",
                "project_id": clean_id,
                "status": "READY",
            }));
            Ok(Some(events))
        }

        "delete_project" => {
            let raw_id = message
                .get("project_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .or_else(|| preview.selected_project_id())
                .unwrap_or_default();

            let clean_id = match validate_project_id(&raw_id) {
                Ok(id) => id,
                Err(err) => {
                    return Ok(Some(vec![
                        json!({
                            "type": "project_delete_error",
                            "project_id": raw_id,
                            "error": err.message,
                        }),
                        system_event(format!("Erro ao eliminar projeto: {}", err.message)),
                    ]));
                }
            };

            let _ = preview.stop_project_preview().await;
            let was_active = preview.selected_project_id().as_deref() == Some(clean_id.as_str());

            let proj_root = match resolve_existing_project_dir(workspace_root, &clean_id) {
                Ok(p) => p,
                Err(err) => {
                    return Ok(Some(vec![
                        json!({
                            "type": "project_delete_error",
                            "project_id": clean_id,
                            "error": err.message,
                        }),
                        system_event(format!("Erro ao eliminar projeto: {}", err.message)),
                    ]));
                }
            };

            if let Err(err) = fs::remove_dir_all(&proj_root) {
                return Ok(Some(vec![
                    json!({
                        "type": "project_delete_error",
                        "project_id": clean_id,
                        "error": err.to_string(),
                    }),
                    system_event(format!("Erro ao eliminar projeto: {err}")),
                ]));
            }

            let meta_dir = project_metadata_dir(workspace_root, &clean_id);
            if meta_dir.is_dir() {
                let _ = fs::remove_dir_all(&meta_dir);
            }
            if was_active {
                preview.set_selected_project_id(None);
            }

            Ok(Some(vec![
                json!({
                    "type": "project_deleted",
                    "ok": true,
                    "project_id": clean_id,
                    "was_active": was_active,
                }),
                json!({
                    "type": "projects_list",
                    "projects": list_projects_payload(workspace_root),
                }),
                system_event(format!("Projeto '{clean_id}' eliminado com sucesso.")),
            ]))
        }

        "save_project_file" => {
            let raw_id = message
                .get("project_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .or_else(|| preview.selected_project_id())
                .unwrap_or_default();
            let filename = message
                .get("filename")
                .and_then(Value::as_str)
                .unwrap_or("");
            let content = message.get("content").and_then(Value::as_str);
            let expected_hash = message
                .get("expected_sha256")
                .and_then(Value::as_str)
                .unwrap_or("")
                .trim()
                .to_ascii_lowercase();

            let err_event = |err_msg: String| {
                Ok(Some(vec![json!({
                    "type": "project_file_save_result",
                    "ok": false,
                    "project_id": raw_id,
                    "filename": filename,
                    "error": err_msg,
                })]))
            };

            let clean_id = match validate_project_id(&raw_id) {
                Ok(id) => id,
                Err(err) => return err_event(err.message),
            };
            let proj_dir = match resolve_existing_project_dir(workspace_root, &clean_id) {
                Ok(p) => p,
                Err(err) => return err_event(err.message),
            };
            let (target, norm) = match resolve_project_text_file(&proj_dir, filename, true) {
                Ok(v) => v,
                Err(err) => return err_event(err.message),
            };
            if expected_hash.len() != 64
                || !expected_hash.bytes().all(|b| matches!(b, b'0'..=b'9' | b'a'..=b'f'))
            {
                return err_event("Hash original do ficheiro em falta ou invalido.".to_string());
            }
            let Some(text_content) = content else {
                return err_event("O editor apenas permite guardar ficheiros de texto.".to_string());
            };
            if text_content.contains('\0') {
                return err_event("O editor apenas permite guardar ficheiros de texto.".to_string());
            }
            let current_bytes = match fs::read(&target) {
                Ok(b) => b,
                Err(err) => return err_event(err.to_string()),
            };
            if sha256_hex(&current_bytes) != expected_hash {
                return err_event(
                    "O ficheiro mudou no disco desde que foi aberto. Reabra o projeto antes de guardar."
                        .to_string(),
                );
            }

            let has_bom = current_bytes.starts_with(&[0xEF, 0xBB, 0xBF]);
            let body = if has_bom {
                &current_bytes[3..]
            } else {
                &current_bytes[..]
            };
            let normalized = preserve_line_endings(body, text_content);
            let mut out_bytes = Vec::with_capacity(normalized.len() + 3);
            if has_bom {
                out_bytes.extend_from_slice(&[0xEF, 0xBB, 0xBF]);
            }
            out_bytes.extend_from_slice(normalized.as_bytes());
            if out_bytes.len() > MAX_VIEW_FILE_BYTES {
                return err_event(format!(
                    "O ficheiro excede o limite de edicao manual de {MAX_VIEW_FILE_BYTES} bytes."
                ));
            }
            if let Err(err) = atomic_write_bytes(&proj_dir, &target, &out_bytes) {
                return err_event(err.message);
            }

            preview.set_selected_project_id(Some(clean_id.clone()));
            let new_hash = sha256_hex(&out_bytes);
            let mut events = vec![json!({
                "type": "project_file_save_result",
                "ok": true,
                "project_id": clean_id,
                "filename": norm,
                "sha256": new_hash,
                "size_bytes": out_bytes.len(),
            })];
            events.extend(build_project_context_events(workspace_root, &clean_id)?);
            Ok(Some(events))
        }

        "create_project_file" => {
            let raw_id = message
                .get("project_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .or_else(|| preview.selected_project_id())
                .unwrap_or_default();
            let filename = message
                .get("filename")
                .and_then(Value::as_str)
                .unwrap_or("");
            let content = message
                .get("content")
                .and_then(Value::as_str)
                .unwrap_or("");

            let err_event = |err_msg: String| {
                Ok(Some(vec![json!({
                    "type": "project_file_save_result",
                    "ok": false,
                    "project_id": raw_id,
                    "filename": filename,
                    "error": err_msg,
                })]))
            };

            let clean_id = match validate_project_id(&raw_id) {
                Ok(id) => id,
                Err(err) => return err_event(err.message),
            };
            let proj_dir = match resolve_existing_project_dir(workspace_root, &clean_id) {
                Ok(p) => p,
                Err(err) => return err_event(err.message),
            };
            let (target, norm) = match resolve_project_text_file(&proj_dir, filename, false) {
                Ok(v) => v,
                Err(err) => return err_event(err.message),
            };
            if let Err(err) = check_no_symlink_components(&proj_dir, Path::new(&norm)) {
                return err_event(err.message);
            }
            if target.exists() {
                return err_event(format!("O ficheiro '{norm}' ja existe neste projeto."));
            }
            if content.contains('\0') {
                return err_event("O editor apenas permite criar ficheiros de texto.".to_string());
            }
            let raw_bytes = content.as_bytes();
            if raw_bytes.len() > MAX_VIEW_FILE_BYTES {
                return err_event(format!(
                    "O ficheiro excede o limite de edicao manual de {MAX_VIEW_FILE_BYTES} bytes."
                ));
            }
            if let Err(err) = atomic_write_bytes(&proj_dir, &target, raw_bytes) {
                return err_event(err.message);
            }

            preview.set_selected_project_id(Some(clean_id.clone()));
            let mut events = vec![json!({
                "type": "project_file_save_result",
                "ok": true,
                "project_id": clean_id,
                "filename": norm,
                "sha256": sha256_hex(raw_bytes),
                "size_bytes": raw_bytes.len(),
            })];
            events.extend(build_project_context_events(workspace_root, &clean_id)?);
            Ok(Some(events))
        }

        "rename_project_file" => {
            let raw_id = message
                .get("project_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .or_else(|| preview.selected_project_id())
                .unwrap_or_default();
            let old_filename = message
                .get("old_filename")
                .and_then(Value::as_str)
                .unwrap_or("");
            let new_filename = message
                .get("new_filename")
                .and_then(Value::as_str)
                .unwrap_or("");

            let err_event = |err_msg: String| {
                let chosen = if new_filename.trim().is_empty() {
                    old_filename
                } else {
                    new_filename
                };
                Ok(Some(vec![json!({
                    "type": "project_file_save_result",
                    "ok": false,
                    "project_id": raw_id,
                    "filename": chosen,
                    "error": err_msg,
                })]))
            };

            let clean_id = match validate_project_id(&raw_id) {
                Ok(id) => id,
                Err(err) => return err_event(err.message),
            };
            let proj_dir = match resolve_existing_project_dir(workspace_root, &clean_id) {
                Ok(p) => p,
                Err(err) => return err_event(err.message),
            };
            let (src, old_norm) = match resolve_project_text_file(&proj_dir, old_filename, true) {
                Ok(v) => v,
                Err(err) => return err_event(err.message),
            };
            let (dst, new_norm) = match resolve_project_text_file(&proj_dir, new_filename, false) {
                Ok(v) => v,
                Err(err) => return err_event(err.message),
            };
            if let Err(err) = check_no_symlink_components(&proj_dir, Path::new(&new_norm)) {
                return err_event(err.message);
            }
            if dst.exists() {
                return err_event(format!("Ja existe um ficheiro em '{new_norm}'."));
            }
            if let Some(parent) = dst.parent() {
                if let Err(err) = fs::create_dir_all(parent) {
                    return err_event(err.to_string());
                }
            }
            if let Err(err) = fs::rename(&src, &dst) {
                return err_event(err.to_string());
            }

            preview.set_selected_project_id(Some(clean_id.clone()));
            let mut events = build_project_context_events(workspace_root, &clean_id)?;
            events.push(system_event(format!(
                "Ficheiro '{old_norm}' movido para '{new_norm}'."
            )));
            Ok(Some(events))
        }

        "delete_project_file" => {
            let raw_id = message
                .get("project_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .or_else(|| preview.selected_project_id())
                .unwrap_or_default();
            let filename = message
                .get("filename")
                .and_then(Value::as_str)
                .unwrap_or("");

            let err_event = |err_msg: String| {
                Ok(Some(vec![
                    json!({
                        "type": "project_file_delete_error",
                        "project_id": raw_id,
                        "filename": filename,
                        "error": err_msg,
                    }),
                    system_event(format!("Erro ao eliminar ficheiro: {err_msg}")),
                ]))
            };

            let clean_id = match validate_project_id(&raw_id) {
                Ok(id) => id,
                Err(err) => return err_event(err.message),
            };
            let proj_dir = match resolve_existing_project_dir(workspace_root, &clean_id) {
                Ok(p) => p,
                Err(err) => return err_event(err.message),
            };
            let (target, norm) = match resolve_project_text_file(&proj_dir, filename, true) {
                Ok(v) => v,
                Err(err) => return err_event(err.message),
            };
            if let Err(err) = fs::remove_file(&target) {
                return err_event(err.to_string());
            }

            let mut events = vec![json!({
                "type": "project_file_deleted",
                "ok": true,
                "project_id": clean_id,
                "filename": norm,
                "deleted": true,
            })];
            events.extend(build_project_context_events(workspace_root, &clean_id)?);
            events.push(system_event(format!(
                "Ficheiro '{norm}' eliminado com sucesso."
            )));
            Ok(Some(events))
        }

        "run_project" => {
            let raw_id = message
                .get("project_id")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .or_else(|| preview.selected_project_id())
                .unwrap_or_default();

            if raw_id.is_empty() {
                return Ok(Some(vec![system_event(
                    "Selecione um projeto antes de iniciar o preview.",
                )]));
            }

            let clean_id = match validate_project_id(&raw_id) {
                Ok(id) => id,
                Err(err) => {
                    return Ok(Some(vec![
                        system_event(err.message),
                        json!({
                            "type": "project_status",
                            "project_id": raw_id,
                            "running": false,
                            "preview_url": "",
                        }),
                    ]));
                }
            };
            let proj_dir = match resolve_existing_project_dir(workspace_root, &clean_id) {
                Ok(p) => p,
                Err(err) => {
                    return Ok(Some(vec![
                        system_event(err.message),
                        json!({
                            "type": "project_status",
                            "project_id": clean_id,
                            "running": false,
                            "preview_url": "",
                        }),
                    ]));
                }
            };

            let mut events = vec![json!({
                "type": "project_output",
                "project_id": clean_id,
                "content": format!("[Project] A preparar preview de {clean_id}...\n"),
            })];

            let has_live_sink = preview_sink.is_some();
            let outcome = preview
                .start_project_preview(&clean_id, &proj_dir, preview_sink)
                .await?;

            if !has_live_sink {
                for line in outcome.output_lines {
                    events.push(json!({
                        "type": "project_output",
                        "project_id": outcome.project_id,
                        "content": line,
                    }));
                }
            }
            events.push(json!({
                "type": "project_status",
                "project_id": outcome.project_id,
                "running": outcome.running,
                "preview_url": outcome.preview_url,
            }));
            Ok(Some(events))
        }

        "stop_project" => {
            let _ = preview.stop_project_preview().await;
            Ok(Some(vec![
                json!({
                    "type": "project_status",
                    "running": false,
                    "preview_url": "about:blank",
                }),
                json!({
                    "type": "project_output",
                    "content": "[Sandbox] Execução interrompida.\n",
                }),
            ]))
        }

        _ => Ok(None),
    }
}

/// Tauri dispatcher entrypoint binding `app.emit("jarvis:event", ...)` for live preview logs.
pub async fn try_execute_project_fast_path(
    app: &AppHandle,
    services: &RuntimeServices,
    msg_type: &str,
    message: &Value,
) -> Result<Option<Vec<Value>>, AppError> {
    let sink: PreviewOutputSink = {
        let app_handle = app.clone();
        Arc::new(move |ev| {
            let _ = app_handle.emit("jarvis:event", &ev);
        })
    };
    execute_project_message(
        &services.project_root,
        &services.preview,
        msg_type,
        message,
        Some(sink),
    )
    .await
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[tokio::test]
    async fn project_dispatch_covers_crud_save_conflict_planner_ast_and_preview() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();
        let preview = PreviewServerHandle::start(None).await.unwrap();

        // 1. Planner state (none -> active -> done normalized to null)
        let evs = execute_project_message(&root, &preview, "get_planner_state", &json!({}), None)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(evs[0]["type"], "planner_state");
        assert!(evs[0]["data"].is_null());

        fs::write(
            root.join(".jarvis_plan.json"),
            r#"{"status":"IN_PROGRESS","goal":"Ship Rust","steps":["A"]}"#,
        )
        .unwrap();
        let evs = execute_project_message(&root, &preview, "get_planner_state", &json!({}), None)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(evs[0]["data"]["goal"], "Ship Rust");

        fs::write(
            root.join(".jarvis_plan.json"),
            r#"{"status":"COMPLETED","goal":"Ship Rust","steps":["A"]}"#,
        )
        .unwrap();
        let evs = execute_project_message(&root, &preview, "get_planner_state", &json!({}), None)
            .await
            .unwrap()
            .unwrap();
        assert!(evs[0]["data"].is_null());

        // 2. Create project (`web-app`) and verify list_projects + open_project + AST
        let evs = execute_project_message(
            &root,
            &preview,
            "create_project",
            &json!({"project_id": "demo-app", "project_name": "Demo App", "template": "web-app"}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        assert!(evs.iter().any(|e| e["type"] == "project_context"
            && e["context"]["project_id"] == "demo-app"
            && e["files"]["index.html"].as_str().unwrap().contains("Demo App")));
        assert!(evs.iter().any(|e| e["type"] == "projects_list"
            && e["projects"][0]["project_id"] == "demo-app"));

        // Seed coding_session + mission state.db & symbols_index.json and verify open_project + get_ast_state
        let meta = project_metadata_dir(&root, "demo-app");
        let sess_dir = meta.join("coding_sessions").join("cs_1");
        fs::create_dir_all(&sess_dir).unwrap();
        fs::write(
            sess_dir.join("session.json"),
            r#"{"session_id":"cs_1","project_id":"demo-app","status":"APPLIED"}"#,
        )
        .unwrap();
        fs::write(
            meta.join("symbols_index.json"),
            r#"{"app.js":{"classes":[],"functions":[{"name":"boot","line":1}]}}"#,
        )
        .unwrap();
        let mission_dir = meta.join("missions").join("m_1");
        fs::create_dir_all(&mission_dir).unwrap();
        let mconn = Connection::open(mission_dir.join("state.db")).unwrap();
        mconn
            .execute(
                "CREATE TABLE missions (mission_id TEXT PRIMARY KEY, project_id TEXT, title TEXT, \
                 objective TEXT, description TEXT, status TEXT, current_phase TEXT, progress REAL, \
                 metadata_json TEXT, created_at TEXT, updated_at TEXT, started_at TEXT, completed_at TEXT, version INTEGER)",
                [],
            )
            .unwrap();
        mconn
            .execute(
                "INSERT INTO missions VALUES ('m_1','demo-app','Test','Obj','Desc','READY','PLAN',0.5,'{}','t1','t2',NULL,NULL,1)",
                [],
            )
            .unwrap();
        drop(mconn);

        let opened = execute_project_message(
            &root,
            &preview,
            "open_project",
            &json!({"project_id": "demo-app"}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        assert!(opened
            .iter()
            .any(|e| e["type"] == "coding_session" && e["data"]["session_id"] == "cs_1"));
        assert!(opened
            .iter()
            .any(|e| e["type"] == "mission_list" && e["missions"][0]["mission_id"] == "m_1"));
        assert!(opened.iter().any(|e| e["type"] == "ast_state"
            && e["data"]["app.js"]["functions"][0]["name"] == "boot"));

        let ast_evs = execute_project_message(&root, &preview, "get_ast_state", &json!({}), None)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(ast_evs[0]["type"], "ast_state");
        assert_eq!(ast_evs[0]["data"]["app.js"]["functions"][0]["name"], "boot");

        // 3. Create, save (with CRLF+BOM preservation + SHA conflict check), rename, delete project file
        let c_evs = execute_project_message(
            &root,
            &preview,
            "create_project_file",
            &json!({"project_id": "demo-app", "filename": "src/helper.js", "content": "\u{feff}line1\r\nline2"}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        let created_sha = c_evs[0]["sha256"].as_str().unwrap().to_string();
        assert_eq!(c_evs[0]["ok"], true);

        // Wrong SHA must fail cleanly
        let bad_save = execute_project_message(
            &root,
            &preview,
            "save_project_file",
            &json!({"project_id": "demo-app", "filename": "src/helper.js", "content": "x", "expected_sha256": "0".repeat(64)}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(bad_save[0]["ok"], false);

        // Correct SHA preserves BOM + CRLF
        let good_save = execute_project_message(
            &root,
            &preview,
            "save_project_file",
            &json!({"project_id": "demo-app", "filename": "src/helper.js", "content": "a\nb", "expected_sha256": created_sha}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(good_save[0]["ok"], true);
        let disk_bytes = fs::read(root.join("workspace/projects/demo-app/src/helper.js")).unwrap();
        assert_eq!(disk_bytes, b"\xef\xbb\xbfa\r\nb");

        // Traversal blocked cleanly
        let trav = execute_project_message(
            &root,
            &preview,
            "create_project_file",
            &json!({"project_id": "demo-app", "filename": "../escape.txt", "content": "no"}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(trav[0]["ok"], false);

        let ren = execute_project_message(
            &root,
            &preview,
            "rename_project_file",
            &json!({"project_id": "demo-app", "old_filename": "src/helper.js", "new_filename": "src/util.js"}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        assert!(ren.iter().any(|e| e["type"] == "project_context" && e["files"]["src/util.js"].is_string()));

        let del_f = execute_project_message(
            &root,
            &preview,
            "delete_project_file",
            &json!({"project_id": "demo-app", "filename": "src/util.js"}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(del_f[0]["type"], "project_file_deleted");
        assert_eq!(del_f[0]["ok"], true);

        // 4. Run & stop preview
        let run_evs = execute_project_message(
            &root,
            &preview,
            "run_project",
            &json!({"project_id": "demo-app"}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        assert!(run_evs.iter().any(|e| e["type"] == "project_status"
            && e["running"] == true
            && e["preview_url"].as_str().unwrap().contains("/index.html")));

        let stop_evs = execute_project_message(&root, &preview, "stop_project", &json!({}), None)
            .await
            .unwrap()
            .unwrap();
        assert_eq!(stop_evs[0]["running"], false);

        // 5. Delete project
        let del_p = execute_project_message(
            &root,
            &preview,
            "delete_project",
            &json!({"project_id": "demo-app"}),
            None,
        )
        .await
        .unwrap()
        .unwrap();
        assert_eq!(del_p[0]["type"], "project_deleted");
        assert_eq!(del_p[0]["was_active"], true);
        assert!(preview.selected_project_id().is_none());

        preview.shutdown();
    }
}

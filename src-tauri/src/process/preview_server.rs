use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::sync::{Arc, Mutex, RwLock};
use std::time::Duration;

use axum::body::Body;
use axum::extract::{Path as AxumPath, Request, State};
use axum::middleware::{self, Next};
use axum::response::Response;
use axum::routing::get;
use axum::Router;
use http::{header, HeaderMap, HeaderValue, Method, StatusCode};
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::{oneshot, Mutex as AsyncMutex};

use crate::error::AppError;
use crate::permissions::path_jail::ensure_confined_existing_file;
use crate::process::command_guard::{build_sanitized_env, validate_command_argv};
use crate::process::job_object::{JobObject, WORKER_CREATION_FLAGS};
use crate::protocol::http_common::{
    content_type_for_ext, has_suspicious_path_traversal, is_valid_loopback_host, plain_error,
    stream_file_with_range,
};

#[derive(Clone)]
struct PreviewState {
    port: u16,
    active_root: Arc<RwLock<Option<PathBuf>>>,
}

struct ActivePreviewChild {
    project_id: String,
    child: Child,
    _job: Option<JobObject>,
}

/// Callback invoked for streaming stdout/stderr lines from an active preview process.
pub type PreviewOutputSink = Arc<dyn Fn(Value) + Send + Sync>;

/// Result of launching a native or static project preview.
#[derive(Debug, Clone)]
pub struct PreviewLaunchOutcome {
    pub project_id: String,
    pub running: bool,
    pub preview_url: Option<String>,
    pub output_lines: Vec<String>,
}

/// Isolated static HTTP preview server for sandboxed project IDE iframes.
///
/// Runs on its own ephemeral loopback port so its HTML origin is completely separate from
/// both the main Tauri shell and the authenticated media loopback server, and tracks the
/// selected IDE project + guarded child process (if any).
pub struct PreviewServerHandle {
    port: u16,
    base_url: String,
    active_root: Arc<RwLock<Option<PathBuf>>>,
    active_project_id: Arc<RwLock<Option<String>>>,
    active_child: Arc<AsyncMutex<Option<ActivePreviewChild>>>,
    shutdown_tx: Arc<Mutex<Option<oneshot::Sender<()>>>>,
}

impl PreviewServerHandle {
    /// Binds to an ephemeral `127.0.0.1:0` listener and starts serving static preview assets.
    pub async fn start(initial_root: Option<PathBuf>) -> Result<Self, AppError> {
        let initial_canon = initial_root
            .filter(|p| p.is_dir())
            .and_then(|p| dunce::canonicalize(&p).ok());
        let active_root = Arc::new(RwLock::new(initial_canon));

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
            .await
            .map_err(|err| {
                AppError::new(
                    "PREVIEW_BIND_FAILED",
                    format!("Failed to bind isolated preview server: {err}"),
                )
            })?;

        let port = listener
            .local_addr()
            .map_err(|err| {
                AppError::new(
                    "PREVIEW_ADDR_FAILED",
                    format!("Failed to read preview listener port: {err}"),
                )
            })?
            .port();

        let base_url = format!("http://127.0.0.1:{port}");
        let state = PreviewState {
            port,
            active_root: Arc::clone(&active_root),
        };

        let app = build_router(state);
        let (shutdown_tx, shutdown_rx) = oneshot::channel::<()>();

        tokio::spawn(async move {
            let _ = axum::serve(listener, app)
                .with_graceful_shutdown(async move {
                    let _ = shutdown_rx.await;
                })
                .await;
        });

        Ok(Self {
            port,
            base_url,
            active_root,
            active_project_id: Arc::new(RwLock::new(None)),
            active_child: Arc::new(AsyncMutex::new(None)),
            shutdown_tx: Arc::new(Mutex::new(Some(shutdown_tx))),
        })
    }

    pub fn port(&self) -> u16 {
        self.port
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    /// Updates or clears the active workspace root directory served by the preview server.
    pub fn set_workspace_root(&self, root: Option<PathBuf>) -> Result<(), AppError> {
        let next = match root {
            Some(path) => {
                if !path.is_dir() {
                    return Err(AppError::new(
                        "PREVIEW_ROOT_INVALID",
                        "Preview workspace root must be an existing directory.",
                    ));
                }
                Some(dunce::canonicalize(&path).map_err(|err| {
                    AppError::new(
                        "PREVIEW_ROOT_INVALID",
                        format!("Failed to canonicalize preview workspace root: {err}"),
                    )
                })?)
            }
            None => None,
        };

        let mut guard = self
            .active_root
            .write()
            .map_err(|_| AppError::new("LOCK_POISONED", "Preview root lock poisoned."))?;
        *guard = next;
        Ok(())
    }

    pub fn selected_project_id(&self) -> Option<String> {
        self.active_project_id
            .read()
            .ok()
            .and_then(|guard| guard.clone())
    }

    pub fn set_selected_project_id(&self, project_id: Option<String>) {
        if let Ok(mut guard) = self.active_project_id.write() {
            *guard = project_id;
        }
    }

    /// Stops any active preview child process (and its Job Object tree) and clears the static root.
    pub async fn stop_project_preview(&self) -> Option<String> {
        let mut stopped_pid = None;
        {
            let mut guard = self.active_child.lock().await;
            if let Some(mut active) = guard.take() {
                stopped_pid = Some(active.project_id.clone());
                let _ = active.child.start_kill();
                let _ = tokio::time::timeout(Duration::from_millis(500), active.child.wait()).await;
            }
        }
        let _ = self.set_workspace_root(None);
        stopped_pid
    }

    /// Launches either an isolated static HTTP preview (on `PreviewServerHandle`) or a
    /// guarded child dev/server process (`npm run` / `python -u`) bound via `JobObject`.
    pub async fn start_project_preview(
        &self,
        project_id: &str,
        project_root: &Path,
        sink: Option<PreviewOutputSink>,
    ) -> Result<PreviewLaunchOutcome, AppError> {
        self.stop_project_preview().await;
        self.set_selected_project_id(Some(project_id.to_string()));

        let canon_root = dunce::canonicalize(project_root).map_err(|err| {
            AppError::new(
                "PREVIEW_ROOT_INVALID",
                format!("Failed to canonicalize project root: {err}"),
            )
        })?;
        if !canon_root.is_dir() {
            return Err(AppError::new(
                "PREVIEW_ROOT_INVALID",
                format!("Projeto '{project_id}' nao existe."),
            ));
        }

        let mut output_lines = Vec::new();
        let emit_line = |line: String, out: &mut Vec<String>| {
            out.push(line.clone());
            if let Some(cb) = &sink {
                cb(json!({
                    "type": "project_output",
                    "project_id": project_id,
                    "content": line,
                }));
            }
        };

        let preview_index = find_preview_index(&canon_root);
        let package_dir = find_package_dir(&canon_root);
        let python_entry = find_python_entry(&canon_root);

        if let Some(pkg_dir) = package_dir {
            let pkg_json_path = pkg_dir.join("package.json");
            let pkg_raw = std::fs::read_to_string(&pkg_json_path).unwrap_or_default();
            let pkg_json: Value = serde_json::from_str(&pkg_raw).unwrap_or(Value::Null);
            let script_name = select_package_script(&pkg_json);
            let rel_loc = pkg_dir
                .strip_prefix(&canon_root)
                .ok()
                .map(|p| {
                    let s = p.to_string_lossy().replace('\\', "/");
                    if s.is_empty() {
                        ".".to_string()
                    } else {
                        s
                    }
                })
                .unwrap_or_else(|| ".".to_string());

            let has_node_modules = pkg_dir.join("node_modules").is_dir();
            let has_deps = pkg_json
                .get("dependencies")
                .and_then(Value::as_object)
                .map(|o| !o.is_empty())
                .unwrap_or(false)
                || pkg_json
                    .get("devDependencies")
                    .and_then(Value::as_object)
                    .map(|o| !o.is_empty())
                    .unwrap_or(false);

            // Simple web-app projects (`index.html` + `"start": "node app.js"` without deps/node_modules)
            // serve cleanly over our isolated loopback PreviewServerHandle without needing external ports.
            if script_name.as_deref() == Some("start")
                && !has_node_modules
                && !has_deps
                && preview_index.is_some()
            {
                let (serve_root, url_suffix) = preview_index.unwrap();
                self.set_workspace_root(Some(serve_root))?;
                let preview_url = format!("{}/{}", self.base_url(), url_suffix);
                emit_line(
                    format!("[Project] Preview estatico isolado ativo em {preview_url}\n"),
                    &mut output_lines,
                );
                return Ok(PreviewLaunchOutcome {
                    project_id: project_id.to_string(),
                    running: true,
                    preview_url: Some(preview_url),
                    output_lines,
                });
            }

            if script_name.is_none() {
                if let Some((serve_root, url_suffix)) = preview_index {
                    self.set_workspace_root(Some(serve_root))?;
                    let preview_url = format!("{}/{}", self.base_url(), url_suffix);
                    emit_line(
                        format!("[Project] Preview estatico: {preview_url}\n"),
                        &mut output_lines,
                    );
                    return Ok(PreviewLaunchOutcome {
                        project_id: project_id.to_string(),
                        running: true,
                        preview_url: Some(preview_url),
                        output_lines,
                    });
                }
                emit_line(
                    "[Project] package.json sem script de preview, dev ou start.\n".to_string(),
                    &mut output_lines,
                );
                return Ok(PreviewLaunchOutcome {
                    project_id: project_id.to_string(),
                    running: false,
                    preview_url: None,
                    output_lines,
                });
            }

            let script = script_name.unwrap();
            if !script
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '-' | ':'))
            {
                return Err(AppError::new(
                    "SECURITY_VIOLATION",
                    format!("Nome de script invalido: `{script}`"),
                ));
            }
            if !has_node_modules && has_deps {
                emit_line(
                    format!(
                        "[Project] Dependencias em falta em {rel_loc} (node_modules ausente); a tentar executar 'npm run {script}' diretamente.\n"
                    ),
                    &mut output_lines,
                );
            } else {
                emit_line(
                    format!(
                        "[Project] package.json detetado em {rel_loc}. A iniciar script '{script}'...\n"
                    ),
                    &mut output_lines,
                );
            }

            let argv = vec!["npm".to_string(), "run".to_string(), script.clone()];
            self.spawn_guarded_preview_process(
                project_id,
                &canon_root,
                &pkg_dir,
                &argv,
                sink.clone(),
            )
            .await?;

            let expected_port = if matches!(script.as_str(), "dev" | "preview") {
                5173
            } else {
                3000
            };
            let candidate_url = format!("http://127.0.0.1:{expected_port}/");
            if wait_for_port_ready("127.0.0.1", expected_port, Duration::from_secs(4)).await {
                emit_line(
                    format!("[Project] Servidor pronto e a escutar em {candidate_url}\n"),
                    &mut output_lines,
                );
            }

            return Ok(PreviewLaunchOutcome {
                project_id: project_id.to_string(),
                running: true,
                preview_url: Some(candidate_url),
                output_lines,
            });
        }

        if let Some(py_script) = python_entry {
            let script_dir = py_script
                .parent()
                .map(Path::to_path_buf)
                .unwrap_or_else(|| canon_root.clone());
            let script_name = py_script
                .file_name()
                .and_then(|s| s.to_str())
                .unwrap_or("main.py")
                .to_string();
            let rel_script = py_script
                .strip_prefix(&canon_root)
                .unwrap_or(&py_script)
                .to_string_lossy()
                .replace('\\', "/");

            emit_line(
                format!("[Project] Python detetado: {rel_script}. A iniciar 'python -u {script_name}'...\n"),
                &mut output_lines,
            );
            let argv = vec!["python".to_string(), "-u".to_string(), script_name];
            self.spawn_guarded_preview_process(
                project_id,
                &canon_root,
                &script_dir,
                &argv,
                sink,
            )
            .await?;

            return Ok(PreviewLaunchOutcome {
                project_id: project_id.to_string(),
                running: true,
                preview_url: None,
                output_lines,
            });
        }

        if let Some((serve_root, url_suffix)) = preview_index {
            self.set_workspace_root(Some(serve_root))?;
            let preview_url = format!("{}/{}", self.base_url(), url_suffix);
            emit_line(
                format!("[Project] Preview estatico isolado ativo em {preview_url}\n"),
                &mut output_lines,
            );
            return Ok(PreviewLaunchOutcome {
                project_id: project_id.to_string(),
                running: true,
                preview_url: Some(preview_url),
                output_lines,
            });
        }

        emit_line(
            "[Project] Nenhum ficheiro index.html ou servidor web encontrado no projeto.\n"
                .to_string(),
            &mut output_lines,
        );
        Ok(PreviewLaunchOutcome {
            project_id: project_id.to_string(),
            running: false,
            preview_url: None,
            output_lines,
        })
    }

    async fn spawn_guarded_preview_process(
        &self,
        project_id: &str,
        workspace_root: &Path,
        cwd: &Path,
        argv: &[String],
        sink: Option<PreviewOutputSink>,
    ) -> Result<(), AppError> {
        let validated = validate_command_argv(argv, workspace_root, Some(cwd))
            .map_err(|err| AppError::new("PREVIEW_COMMAND_BLOCKED", err))?;

        let mut cmd = Command::new(&validated.program);
        cmd.args(&validated.args)
            .current_dir(&validated.working_dir)
            .env_clear()
            .envs(build_sanitized_env())
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        #[cfg(windows)]
        cmd.creation_flags(WORKER_CREATION_FLAGS);

        let mut child = cmd.spawn().map_err(|err| {
            AppError::new(
                "PREVIEW_SPAWN_FAILED",
                format!("Failed to start preview process `{}`: {err}", validated.program),
            )
        })?;

        let job = if let Some(pid) = child.id() {
            match JobObject::new(Some(1024 * 1024 * 1024)) {
                Ok(job) => {
                    if job.assign_pid(pid).is_ok() {
                        Some(job)
                    } else {
                        None
                    }
                }
                Err(_) => None,
            }
        } else {
            None
        };

        if let Some(stdout) = child.stdout.take() {
            let pid_str = project_id.to_string();
            let sink_out = sink.clone();
            tokio::spawn(async move {
                let mut reader = BufReader::new(stdout).lines();
                while let Ok(Some(line)) = reader.next_line().await {
                    if let Some(cb) = &sink_out {
                        cb(json!({
                            "type": "project_output",
                            "project_id": pid_str,
                            "content": format!("{line}\n"),
                        }));
                    }
                }
            });
        }
        if let Some(stderr) = child.stderr.take() {
            let pid_str = project_id.to_string();
            let sink_err = sink;
            tokio::spawn(async move {
                let mut reader = BufReader::new(stderr).lines();
                while let Ok(Some(line)) = reader.next_line().await {
                    if let Some(cb) = &sink_err {
                        cb(json!({
                            "type": "project_output",
                            "project_id": pid_str,
                            "content": format!("{line}\n"),
                        }));
                    }
                }
            });
        }

        let mut guard = self.active_child.lock().await;
        *guard = Some(ActivePreviewChild {
            project_id: project_id.to_string(),
            child,
            _job: job,
        });
        Ok(())
    }

    /// Signals the background Axum server and any active preview child to shut down gracefully.
    pub fn shutdown(&self) {
        if let Ok(mut guard) = self.active_child.try_lock() {
            if let Some(mut active) = guard.take() {
                let _ = active.child.start_kill();
            }
        }
        if let Ok(mut guard) = self.active_root.write() {
            *guard = None;
        }
        if let Ok(mut guard) = self.active_project_id.write() {
            *guard = None;
        }
        if let Ok(mut guard) = self.shutdown_tx.lock() {
            if let Some(tx) = guard.take() {
                let _ = tx.send(());
            }
        }
    }
}

fn build_router(state: PreviewState) -> Router {
    Router::new()
        .route("/", get(handle_preview_index))
        .route("/{*subpath}", get(handle_preview_subpath))
        .layer(middleware::from_fn_with_state(state.clone(), preview_guard))
        .with_state(state)
}

async fn preview_guard(
    State(state): State<PreviewState>,
    req: Request,
    next: Next,
) -> Response {
    let host = req.headers().get(header::HOST).and_then(|v| v.to_str().ok());
    if !is_valid_loopback_host(host, state.port) {
        return plain_error(StatusCode::FORBIDDEN, "Forbidden host");
    }

    if has_suspicious_path_traversal(req.uri().path()) {
        return plain_error(StatusCode::FORBIDDEN, "Forbidden path");
    }

    let method = req.method().clone();
    if method == Method::OPTIONS {
        return Response::builder()
            .status(StatusCode::NO_CONTENT)
            .header(header::X_CONTENT_TYPE_OPTIONS, "nosniff")
            .body(Body::empty())
            .unwrap_or_else(|_| Response::new(Body::empty()));
    }

    if !matches!(method, Method::GET | Method::HEAD) {
        return plain_error(StatusCode::METHOD_NOT_ALLOWED, "Method not allowed");
    }

    let mut response = next.run(req).await;
    response.headers_mut().insert(
        header::X_CONTENT_TYPE_OPTIONS,
        HeaderValue::from_static("nosniff"),
    );
    response.headers_mut().insert(
        header::CACHE_CONTROL,
        HeaderValue::from_static("no-store"),
    );
    response
}

async fn handle_preview_index(
    State(state): State<PreviewState>,
    method: Method,
    headers: HeaderMap,
) -> Response {
    serve_preview_relative(&state, "index.html", &method, &headers).await
}

async fn handle_preview_subpath(
    State(state): State<PreviewState>,
    AxumPath(subpath): AxumPath<String>,
    method: Method,
    headers: HeaderMap,
) -> Response {
    let clean = subpath.trim_start_matches('/');
    let rel = if clean.is_empty() {
        "index.html"
    } else {
        clean
    };
    serve_preview_relative(&state, rel, &method, &headers).await
}

async fn serve_preview_relative(
    state: &PreviewState,
    raw_rel: &str,
    method: &Method,
    headers: &HeaderMap,
) -> Response {
    if raw_rel.contains('\\') || raw_rel.contains(':') || has_suspicious_path_traversal(raw_rel) {
        return plain_error(StatusCode::FORBIDDEN, "Forbidden preview path");
    }

    let root_opt = match state.active_root.read() {
        Ok(guard) => guard.clone(),
        Err(_) => return plain_error(StatusCode::INTERNAL_SERVER_ERROR, "State lock error"),
    };
    let Some(root) = root_opt else {
        return plain_error(StatusCode::NOT_FOUND, "No preview workspace configured");
    };

    let rel_path = Path::new(raw_rel);
    let canon = match ensure_confined_existing_file(&root, rel_path) {
        Ok(file) => file,
        Err(err) if err.code == "NOT_FOUND" => {
            // Try directory index fallback only inside confined relative subpath
            let index_fallback = rel_path.join("index.html");
            match ensure_confined_existing_file(&root, &index_fallback) {
                Ok(index_file) => index_file,
                Err(_) => return plain_error(StatusCode::NOT_FOUND, "Preview asset not found"),
            }
        }
        Err(_) => return plain_error(StatusCode::FORBIDDEN, "Forbidden preview path"),
    };

    let ext = canon
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| format!(".{}", e.to_ascii_lowercase()))
        .unwrap_or_default();
    let mime = content_type_for_ext(&ext);
    let range_hdr = headers.get(header::RANGE).and_then(|v| v.to_str().ok());
    stream_file_with_range(&canon, mime, method, range_hdr).await
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::http_common::test_send_raw_http as send_raw_http;
    use std::fs;
    use tempfile::tempdir;

    #[tokio::test]
    async fn preview_server_isolates_workspace_and_blocks_traversal_and_host_spoof() {
        let dir = tempdir().unwrap();
        let base = dunce::canonicalize(dir.path()).unwrap();
        let proj = base.join("project_a");
        fs::create_dir_all(&proj).unwrap();
        fs::write(proj.join("index.html"), "<h1>Preview OK</h1>").unwrap();
        fs::write(base.join("outside_secret.txt"), "top-secret").unwrap();

        let preview = PreviewServerHandle::start(Some(proj.clone())).await.unwrap();
        let port = preview.port();

        // 1. Index serves cleanly with nosniff + no-store
        let (st, head, body) = send_raw_http(
            port,
            &format!("GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 200);
        assert!(head.to_ascii_lowercase().contains("x-content-type-options: nosniff"));
        assert!(head.to_ascii_lowercase().contains("cache-control: no-store"));
        assert_eq!(body, b"<h1>Preview OK</h1>");

        // 2. Host spoof blocked -> 403
        let (st, _, _) = send_raw_http(
            port,
            "GET / HTTP/1.1\r\nHost: attacker.local:80\r\nConnection: close\r\n\r\n",
        )
        .await;
        assert_eq!(st, 403);

        // 3. Traversal blocked -> 403
        let (st, _, _) = send_raw_http(
            port,
            &format!("GET /%2e%2e/outside_secret.txt HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 403);

        // 4. Clearing workspace returns 404 safely
        preview.set_workspace_root(None).unwrap();
        let (st, _, _) = send_raw_http(
            port,
            &format!("GET /index.html HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 404);

        preview.shutdown();
    }

    #[tokio::test]
    async fn preview_server_starts_static_webapp_without_node_modules_and_stops_cleanly() {
        let dir = tempdir().unwrap();
        let proj = dunce::canonicalize(dir.path()).unwrap().join("demo-web");
        fs::create_dir_all(&proj).unwrap();
        fs::write(proj.join("index.html"), "<html><body>Demo Web</body></html>").unwrap();
        fs::write(proj.join("styles.css"), "body { color: #fff; }").unwrap();
        fs::write(proj.join("app.js"), "console.log('demo');").unwrap();
        fs::write(
            proj.join("package.json"),
            r#"{"name":"demo-web","scripts":{"start":"node app.js"}}"#,
        )
        .unwrap();

        let preview = PreviewServerHandle::start(None).await.unwrap();
        let outcome = preview
            .start_project_preview("demo-web", &proj, None)
            .await
            .unwrap();
        assert!(outcome.running);
        assert_eq!(
            outcome.preview_url.as_deref(),
            Some(format!("{}/index.html", preview.base_url()).as_str())
        );
        assert_eq!(preview.selected_project_id().as_deref(), Some("demo-web"));

        let (st, _, body) = send_raw_http(
            preview.port(),
            &format!(
                "GET /index.html HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
                preview.port()
            ),
        )
        .await;
        assert_eq!(st, 200);
        assert_eq!(body, b"<html><body>Demo Web</body></html>");

        preview.stop_project_preview().await;
        let (st_after, _, _) = send_raw_http(
            preview.port(),
            &format!(
                "GET /index.html HTTP/1.1\r\nHost: 127.0.0.1:{}\r\nConnection: close\r\n\r\n",
                preview.port()
            ),
        )
        .await;
        assert_eq!(st_after, 404);
        preview.shutdown();
    }
}

fn select_package_script(pkg_json: &Value) -> Option<String> {
    let scripts = pkg_json.get("scripts")?.as_object()?;
    for candidate in ["preview", "dev", "start"] {
        if let Some(cmd) = scripts.get(candidate).and_then(Value::as_str) {
            if !cmd.trim().is_empty() {
                return Some(candidate.to_string());
            }
        }
    }
    None
}

fn is_ignored_layout_dir(name: &str) -> bool {
    matches!(
        name,
        "__pycache__" | "node_modules" | ".git" | ".jarvis" | "venv" | ".venv" | "dist"
    )
}

fn collect_layout_files(
    dir: &Path,
    depth: usize,
    max_depth: usize,
    out: &mut Vec<PathBuf>,
) {
    if depth > max_depth {
        return;
    }
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if path.is_dir() {
            if !is_ignored_layout_dir(&name) {
                collect_layout_files(&path, depth + 1, max_depth, out);
            }
        } else if path.is_file() {
            out.push(path);
        }
    }
}

fn find_preview_index(root: &Path) -> Option<(PathBuf, String)> {
    let mut files = Vec::new();
    collect_layout_files(root, 0, 5, &mut files);
    let mut candidates: Vec<PathBuf> = files
        .into_iter()
        .filter(|p| p.file_name().and_then(|n| n.to_str()) == Some("index.html"))
        .collect();
    if candidates.is_empty() {
        return None;
    }
    candidates.sort_by_key(|p| {
        let rel = p
            .strip_prefix(root)
            .unwrap_or(p)
            .to_string_lossy()
            .replace('\\', "/");
        let pref = if rel == "index.html" {
            0usize
        } else if rel.contains("client/") || rel.contains("frontend/") || rel.contains("public/") {
            1usize
        } else {
            2usize
        };
        (pref, rel)
    });
    let chosen = candidates.into_iter().next()?;
    let rel = chosen
        .strip_prefix(root)
        .unwrap_or(&chosen)
        .to_string_lossy()
        .replace('\\', "/");
    Some((root.to_path_buf(), rel))
}

fn find_package_dir(root: &Path) -> Option<PathBuf> {
    let mut files = Vec::new();
    collect_layout_files(root, 0, 2, &mut files);
    let mut pkg_dirs: Vec<PathBuf> = files
        .into_iter()
        .filter(|p| p.file_name().and_then(|n| n.to_str()) == Some("package.json"))
        .filter_map(|p| p.parent().map(Path::to_path_buf))
        .collect();
    pkg_dirs.sort();
    pkg_dirs.into_iter().next()
}

fn find_python_entry(root: &Path) -> Option<PathBuf> {
    let mut files = Vec::new();
    collect_layout_files(root, 0, 2, &mut files);
    let mut candidates: Vec<PathBuf> = files
        .into_iter()
        .filter(|p| {
            matches!(
                p.file_name().and_then(|n| n.to_str()),
                Some("app.py" | "main.py")
            )
        })
        .collect();
    candidates.sort();
    candidates.into_iter().next()
}

async fn wait_for_port_ready(host: &str, port: u16, timeout: Duration) -> bool {
    let target = format!("{host}:{port}");
    let deadline = tokio::time::Instant::now() + timeout;
    while tokio::time::Instant::now() < deadline {
        let target_clone = target.clone();
        let connected = tokio::task::spawn_blocking(move || {
            let Ok(addr) = target_clone.parse::<SocketAddr>() else {
                return false;
            };
            TcpStream::connect_timeout(&addr, Duration::from_millis(250)).is_ok()
        })
        .await
        .unwrap_or(false);
        if connected {
            return true;
        }
        tokio::time::sleep(Duration::from_millis(150)).await;
    }
    false
}


use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, RwLock};

use axum::body::Body;
use axum::extract::{Path as AxumPath, Request, State};
use axum::middleware::{self, Next};
use axum::response::Response;
use axum::routing::get;
use axum::Router;
use http::{header, HeaderMap, HeaderValue, Method, StatusCode};
use tokio::sync::oneshot;

use crate::error::AppError;
use crate::permissions::path_jail::ensure_confined_existing_file;
use crate::protocol::http_common::{
    content_type_for_ext, has_suspicious_path_traversal, is_valid_loopback_host, plain_error,
    stream_file_with_range,
};

#[derive(Clone)]
struct PreviewState {
    port: u16,
    active_root: Arc<RwLock<Option<PathBuf>>>,
}

/// Isolated static HTTP preview server for sandboxed project IDE iframes.
///
/// Runs on its own ephemeral loopback port so its HTML origin is completely separate from
/// both the main Tauri shell and the authenticated media loopback server.
pub struct PreviewServerHandle {
    port: u16,
    base_url: String,
    active_root: Arc<RwLock<Option<PathBuf>>>,
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

    /// Signals the background Axum server to shut down gracefully.
    pub fn shutdown(&self) {
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
}


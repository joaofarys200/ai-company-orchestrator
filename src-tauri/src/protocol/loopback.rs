use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};

use axum::extract::{Path as AxumPath, Request, State};
use axum::middleware::{self, Next};
use axum::response::Response;
use axum::routing::get;
use axum::Router;
use hmac::{Hmac, Mac};
use http::{header, HeaderMap, Method, StatusCode};
use rand::rngs::OsRng;
use rand::RngCore;
use serde::Serialize;
use serde_json::Value;
use sha2::Sha256;
use tokio::sync::oneshot;

use crate::error::AppError;
use crate::permissions::path_jail::{
    ensure_confined_existing_file, is_blocked_system_path, is_safe_identifier,
    resolve_confined_path,
};
use crate::protocol::http_common::{
    attach_cors_and_security_headers, content_type_for_ext, has_suspicious_path_traversal,
    is_allowed_desktop_origin, is_valid_loopback_host, plain_error, stream_file_with_range,
};

type HmacSha256 = Hmac<Sha256>;

const DEFAULT_TICKET_TTL_SECS: u64 = 60;
const PDF_EXTENSIONS: &[&str] = &[".pdf"];
const VIDEO_EXTENSIONS: &[&str] = &[
    ".mp4", ".webm", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".flv", ".mpg", ".mpeg",
];
const FRAME_EXTENSIONS: &[&str] = &[".jpg", ".jpeg", ".png", ".webp"];
const SAFE_DATA_STUDY_EXTENSIONS: &[&str] = &[
    ".pdf", ".mp4", ".webm", ".mkv", ".mov", ".avi", ".wmv", ".m4v", ".wav", ".mp3", ".m4a",
    ".ogg", ".flac", ".jpg", ".jpeg", ".png", ".webp", ".docx", ".pptx",
];

#[derive(Debug, Clone, Serialize)]
pub struct LoopbackConfig {
    pub base_url: String,
    pub token: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub preview_base_url: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MediaTicketResponse {
    pub ticket: String,
    pub base_url: String,
    pub expires_at_ms: u64,
}

#[derive(Clone)]
struct LoopbackState {
    project_root: PathBuf,
    port: u16,
    token: String,
    hmac_key: [u8; 32],
}

/// Running handle for the authenticated Rust loopback media and static helper server.
pub struct LoopbackHandle {
    state: LoopbackState,
    base_url: String,
    shutdown_tx: Arc<Mutex<Option<oneshot::Sender<()>>>>,
}

impl LoopbackHandle {
    /// Binds to an ephemeral `127.0.0.1:0` port and spawns the authenticated Axum server.
    pub async fn start(project_root: PathBuf) -> Result<Self, AppError> {
        let canon_root = dunce::canonicalize(&project_root).unwrap_or(project_root);

        let mut token_bytes = [0u8; 32];
        let mut hmac_key = [0u8; 32];
        OsRng.fill_bytes(&mut token_bytes);
        OsRng.fill_bytes(&mut hmac_key);
        let token = hex::encode(token_bytes);

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0")
            .await
            .map_err(|err| {
                AppError::new(
                    "LOOPBACK_BIND_FAILED",
                    format!("Failed to bind loopback TCP listener: {err}"),
                )
            })?;

        let port = listener
            .local_addr()
            .map_err(|err| {
                AppError::new(
                    "LOOPBACK_ADDR_FAILED",
                    format!("Failed to inspect bound loopback port: {err}"),
                )
            })?
            .port();

        let base_url = format!("http://127.0.0.1:{port}");
        let state = LoopbackState {
            project_root: canon_root,
            port,
            token,
            hmac_key,
        };

        let app = build_router(state.clone());
        let (shutdown_tx, shutdown_rx) = oneshot::channel::<()>();

        tokio::spawn(async move {
            let _ = axum::serve(listener, app)
                .with_graceful_shutdown(async move {
                    let _ = shutdown_rx.await;
                })
                .await;
        });

        Ok(Self {
            state,
            base_url,
            shutdown_tx: Arc::new(Mutex::new(Some(shutdown_tx))),
        })
    }

    pub fn port(&self) -> u16 {
        self.state.port
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn token(&self) -> &str {
        &self.state.token
    }

    pub fn config(&self, preview_base_url: Option<String>) -> LoopbackConfig {
        LoopbackConfig {
            base_url: self.base_url.clone(),
            token: self.state.token.clone(),
            preview_base_url,
        }
    }

    /// Mints an HMAC-SHA256 media capability ticket scoped strictly to `doc_id`.
    pub fn issue_media_ticket(
        &self,
        doc_id: &str,
        ttl_secs: Option<u64>,
    ) -> Result<MediaTicketResponse, AppError> {
        let now = now_ms()?;
        let ttl_ms = ttl_secs.unwrap_or(DEFAULT_TICKET_TTL_SECS).saturating_mul(1000);
        self.issue_media_ticket_with_expiry(doc_id, now.saturating_add(ttl_ms))
    }

    pub(crate) fn issue_media_ticket_with_expiry(
        &self,
        doc_id: &str,
        expires_at_ms: u64,
    ) -> Result<MediaTicketResponse, AppError> {
        if !is_safe_identifier(doc_id) {
            return Err(AppError::new(
                "INVALID_DOC_ID",
                "Document identifier contains forbidden characters.",
            ));
        }
        let mut nonce = [0u8; 16];
        OsRng.fill_bytes(&mut nonce);
        let nonce_hex = hex::encode(nonce);
        let payload = format!("{doc_id}:{expires_at_ms}:{nonce_hex}");
        let sig_hex = sign_hmac_hex(&self.state.hmac_key, &payload);

        Ok(MediaTicketResponse {
            ticket: format!("{expires_at_ms}.{nonce_hex}.{sig_hex}"),
            base_url: self.base_url.clone(),
            expires_at_ms,
        })
    }

    /// Signals the background Axum server to terminate gracefully.
    pub fn shutdown(&self) {
        if let Ok(mut guard) = self.shutdown_tx.lock() {
            if let Some(tx) = guard.take() {
                let _ = tx.send(());
            }
        }
    }
}

fn build_router(state: LoopbackState) -> Router {
    Router::new()
        .route("/healthz", get(handle_healthz))
        .route("/pdf.worker.min.mjs", get(handle_pdf_worker))
        .route("/api/study/documents", get(handle_list_documents))
        .route("/api/study/document/{doc_id}/file", get(handle_doc_file))
        .route("/api/study/document/{doc_id}/video", get(handle_doc_video))
        .route(
            "/api/study/document/{doc_id}/media/{frame_id}",
            get(handle_doc_media),
        )
        .route("/data/study/{*subpath}", get(handle_data_study))
        .layer(middleware::from_fn_with_state(state.clone(), security_guard))
        .with_state(state)
}

async fn security_guard(
    State(state): State<LoopbackState>,
    req: Request,
    next: Next,
) -> Response {
    let headers = req.headers();
    let host = headers.get(header::HOST).and_then(|v| v.to_str().ok());
    if !is_valid_loopback_host(host, state.port) {
        return plain_error(StatusCode::FORBIDDEN, "Forbidden host");
    }

    let raw_path = req.uri().path();
    if has_suspicious_path_traversal(raw_path) {
        return plain_error(StatusCode::FORBIDDEN, "Forbidden path");
    }

    if let Some(sec_fetch) = headers
        .get("sec-fetch-site")
        .and_then(|v| v.to_str().ok())
    {
        if sec_fetch.trim().eq_ignore_ascii_case("cross-site") {
            return plain_error(StatusCode::FORBIDDEN, "Cross-site request blocked");
        }
    }

    let origin_header = headers
        .get(header::ORIGIN)
        .and_then(|v| v.to_str().ok())
        .map(|s| s.trim().trim_end_matches('/').to_string());

    if let Some(ref orig) = origin_header {
        if !is_allowed_desktop_origin(orig, Some(state.port)) {
            return plain_error(StatusCode::FORBIDDEN, "Forbidden origin");
        }
    }

    let method = req.method().clone();
    if method == Method::OPTIONS {
        let mut resp = Response::builder()
            .status(StatusCode::NO_CONTENT)
            .body(axum::body::Body::empty())
            .unwrap_or_else(|_| Response::new(axum::body::Body::empty()));
        attach_cors_and_security_headers(resp.headers_mut(), origin_header.as_deref());
        return resp;
    }

    if !matches!(method, Method::GET | Method::HEAD) {
        return plain_error(StatusCode::METHOD_NOT_ALLOWED, "Method not allowed");
    }

    let mut response = next.run(req).await;
    attach_cors_and_security_headers(response.headers_mut(), origin_header.as_deref());
    response
}

async fn handle_healthz() -> Response {
    let payload = r#"{"status":"ok","shell":"tauri-loopback"}"#;
    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, "application/json; charset=utf-8")
        .header(header::CONTENT_LENGTH, payload.len().to_string())
        .header(header::CACHE_CONTROL, "no-store")
        .body(axum::body::Body::from(payload))
        .unwrap_or_else(|_| Response::new(axum::body::Body::empty()))
}

async fn handle_pdf_worker(
    State(state): State<LoopbackState>,
    method: Method,
    headers: HeaderMap,
    req_uri: http::Uri,
) -> Response {
    if let Some(err_resp) = authorize_general_request(&state, &headers, req_uri.query(), None) {
        return err_resp;
    }

    let dist_candidate = state.project_root.join("frontend").join("dist").join("pdf.worker.min.mjs");
    let pub_candidate = state.project_root.join("frontend").join("public").join("pdf.worker.min.mjs");

    let resolved = ensure_confined_existing_file(
        &state.project_root.join("frontend").join("dist"),
        Path::new("pdf.worker.min.mjs"),
    )
    .or_else(|_| {
        ensure_confined_existing_file(
            &state.project_root.join("frontend").join("public"),
            Path::new("pdf.worker.min.mjs"),
        )
    });

    let _ = (dist_candidate, pub_candidate);
    match resolved {
        Ok(canon) => stream_file_with_range(
            &canon,
            "application/javascript; charset=utf-8",
            &method,
            headers.get(header::RANGE).and_then(|v| v.to_str().ok()),
        )
        .await,
        Err(_) => plain_error(StatusCode::NOT_FOUND, "pdf.worker.min.mjs not found"),
    }
}

async fn handle_list_documents(
    State(state): State<LoopbackState>,
    method: Method,
    headers: HeaderMap,
    req_uri: http::Uri,
) -> Response {
    if let Some(err_resp) = authorize_general_request(&state, &headers, req_uri.query(), None) {
        return err_resp;
    }

    let study_dir = state.project_root.join("data").join("study");
    let docs_list = load_documents_catalog(&study_dir)
        .map(|map| {
            map.as_object()
                .map(|obj| obj.values().cloned().collect::<Vec<Value>>())
                .unwrap_or_default()
        })
        .unwrap_or_default();

    let body_bytes = serde_json::to_vec(&docs_list).unwrap_or_else(|_| b"[]".to_vec());
    let len = body_bytes.len();
    let body = if method == Method::HEAD {
        axum::body::Body::empty()
    } else {
        axum::body::Body::from(body_bytes)
    };

    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, "application/json; charset=utf-8")
        .header(header::CONTENT_LENGTH, len.to_string())
        .header(header::CACHE_CONTROL, "no-store")
        .body(body)
        .unwrap_or_else(|_| Response::new(axum::body::Body::empty()))
}

async fn handle_doc_file(
    State(state): State<LoopbackState>,
    AxumPath(doc_id): AxumPath<String>,
    method: Method,
    headers: HeaderMap,
    req_uri: http::Uri,
) -> Response {
    if !is_safe_identifier(&doc_id) {
        return plain_error(StatusCode::FORBIDDEN, "Invalid document identifier");
    }
    if let Some(err_resp) = authorize_doc_request(&state, &headers, req_uri.query(), &doc_id) {
        return err_resp;
    }

    let Some(canon) = resolve_cataloged_media(
        &state.project_root,
        &doc_id,
        None,
        PDF_EXTENSIONS,
        false,
    ) else {
        return plain_error(StatusCode::NOT_FOUND, "PDF not found");
    };

    let range_hdr = headers.get(header::RANGE).and_then(|v| v.to_str().ok());
    stream_file_with_range(&canon, "application/pdf", &method, range_hdr).await
}

async fn handle_doc_video(
    State(state): State<LoopbackState>,
    AxumPath(doc_id): AxumPath<String>,
    method: Method,
    headers: HeaderMap,
    req_uri: http::Uri,
) -> Response {
    if !is_safe_identifier(&doc_id) {
        return plain_error(StatusCode::FORBIDDEN, "Invalid document identifier");
    }
    if let Some(err_resp) = authorize_doc_request(&state, &headers, req_uri.query(), &doc_id) {
        return err_resp;
    }

    let study_dir = state.project_root.join("data").join("study");
    let raw_mode = req_uri
        .query()
        .map(|q| url::form_urlencoded::parse(q.as_bytes()).any(|(k, v)| k == "raw" && v == "1"))
        .unwrap_or(false);

    if !raw_mode {
        let cache_dir = study_dir.join("videos_cache");
        let cached_rel = PathBuf::from(format!("{doc_id}.mp4"));
        if let Ok(canon_cached) = ensure_confined_existing_file(&cache_dir, &cached_rel) {
            let range_hdr = headers.get(header::RANGE).and_then(|v| v.to_str().ok());
            return stream_file_with_range(&canon_cached, "video/mp4", &method, range_hdr).await;
        }
    }

    let Some(canon) = resolve_cataloged_media(
        &state.project_root,
        &doc_id,
        Some("videos"),
        VIDEO_EXTENSIONS,
        true,
    ) else {
        return plain_error(StatusCode::NOT_FOUND, "Video not found");
    };

    let ext = canon
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| format!(".{}", e.to_ascii_lowercase()))
        .unwrap_or_else(|| ".mp4".to_string());
    let mime = content_type_for_ext(&ext);
    let range_hdr = headers.get(header::RANGE).and_then(|v| v.to_str().ok());
    stream_file_with_range(&canon, mime, &method, range_hdr).await
}

async fn handle_doc_media(
    State(state): State<LoopbackState>,
    AxumPath((doc_id, frame_id)): AxumPath<(String, String)>,
    method: Method,
    headers: HeaderMap,
    req_uri: http::Uri,
) -> Response {
    if !is_safe_identifier(&doc_id) || !is_safe_identifier(&frame_id) {
        return plain_error(StatusCode::FORBIDDEN, "Invalid media identifier");
    }
    if let Some(err_resp) = authorize_doc_request(&state, &headers, req_uri.query(), &doc_id) {
        return err_resp;
    }

    let study_dir = state.project_root.join("data").join("study");
    let keyframes_root = study_dir.join("keyframes");
    let mut resolved_media: Option<PathBuf> = None;

    if let Some(catalog) = load_documents_catalog(&study_dir) {
        if let Some(entry) = catalog.get(&doc_id) {
            if let Some(keyframes) = entry
                .get("metadata")
                .and_then(|m| m.get("video"))
                .and_then(|v| v.get("keyframes"))
                .and_then(|k| k.as_array())
            {
                for kf in keyframes {
                    let matches_id = kf.get("frame_id").and_then(|v| v.as_str()) == Some(&frame_id);
                    if let (true, Some(img_raw)) =
                        (matches_id, kf.get("image_path").and_then(|v| v.as_str()))
                    {
                        let img_path = Path::new(img_raw);
                        let cand = if img_path.is_absolute() {
                            img_path.to_path_buf()
                        } else {
                            state.project_root.join(img_path)
                        };
                        if let Ok(canon) = ensure_confined_existing_file(&study_dir, &cand) {
                            resolved_media = Some(canon);
                            break;
                        }
                    }
                }
            }
        }
    }

    if resolved_media.is_none() && keyframes_root.is_dir() {
        if let Ok(doc_kf_dir) = resolve_confined_path(&keyframes_root, Path::new(&doc_id)) {
            if doc_kf_dir.is_dir() {
                for ext in FRAME_EXTENSIONS {
                    let cand_name = format!("{frame_id}{ext}");
                    if let Ok(canon) =
                        ensure_confined_existing_file(&doc_kf_dir, Path::new(&cand_name))
                    {
                        resolved_media = Some(canon);
                        break;
                    }
                }
            }
        }
    }

    let Some(canon) = resolved_media else {
        return plain_error(StatusCode::NOT_FOUND, "Media frame not found");
    };

    let ext = canon
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| format!(".{}", e.to_ascii_lowercase()))
        .unwrap_or_else(|| ".jpg".to_string());
    let range_hdr = headers.get(header::RANGE).and_then(|v| v.to_str().ok());
    stream_file_with_range(&canon, content_type_for_ext(&ext), &method, range_hdr).await
}

async fn handle_data_study(
    State(state): State<LoopbackState>,
    AxumPath(subpath): AxumPath<String>,
    method: Method,
    headers: HeaderMap,
    req_uri: http::Uri,
) -> Response {
    let clean_subpath = subpath.trim_start_matches('/');
    if clean_subpath.is_empty()
        || clean_subpath.contains('\\')
        || clean_subpath.contains(':')
        || has_suspicious_path_traversal(clean_subpath)
    {
        return plain_error(StatusCode::FORBIDDEN, "Forbidden study path");
    }

    // Extract optional scoped doc_id from `/data/study/<subdir>/<doc_id>/...` when ticket auth is used.
    let inferred_doc_id = infer_doc_id_from_study_subpath(clean_subpath);
    if let Some(err_resp) = authorize_general_request(
        &state,
        &headers,
        req_uri.query(),
        inferred_doc_id.as_deref(),
    ) {
        return err_resp;
    }

    let study_root = state.project_root.join("data").join("study");
    let canon = match ensure_confined_existing_file(&study_root, Path::new(clean_subpath)) {
        Ok(p) => p,
        Err(err) if err.code == "NOT_FOUND" => {
            return plain_error(StatusCode::NOT_FOUND, "Study asset not found");
        }
        Err(_) => return plain_error(StatusCode::FORBIDDEN, "Forbidden study path"),
    };

    let ext = canon
        .extension()
        .and_then(|e| e.to_str())
        .map(|e| format!(".{}", e.to_ascii_lowercase()))
        .unwrap_or_default();
    if !SAFE_DATA_STUDY_EXTENSIONS.contains(&ext.as_str()) {
        return plain_error(StatusCode::FORBIDDEN, "Forbidden file type");
    }

    let range_hdr = headers.get(header::RANGE).and_then(|v| v.to_str().ok());
    stream_file_with_range(&canon, content_type_for_ext(&ext), &method, range_hdr).await
}

fn infer_doc_id_from_study_subpath(subpath: &str) -> Option<String> {
    let mut parts = subpath.split('/');
    let first = parts.next()?;
    let second = parts.next()?;
    if matches!(first, "keyframes" | "frames" | "videos" | "videos_cache")
        && is_safe_identifier(second)
    {
        Some(second.to_string())
    } else {
        None
    }
}

fn extract_bearer_or_header_token(headers: &HeaderMap) -> Option<String> {
    if let Some(auth) = headers.get(header::AUTHORIZATION).and_then(|v| v.to_str().ok()) {
        let trimmed = auth.trim();
        if trimmed.len() > 7 && trimmed[..7].eq_ignore_ascii_case("bearer ") {
            return Some(trimmed[7..].trim().to_string());
        }
        return Some(String::new());
    }
    if let Some(xtok) = headers.get("x-jarvis-token").and_then(|v| v.to_str().ok()) {
        return Some(xtok.trim().to_string());
    }
    None
}

fn extract_query_param(query: Option<&str>, key_name: &str) -> Option<String> {
    let q = query?;
    for (k, v) in url::form_urlencoded::parse(q.as_bytes()) {
        if k == key_name {
            return Some(v.into_owned());
        }
    }
    None
}

fn authorize_doc_request(
    state: &LoopbackState,
    headers: &HeaderMap,
    query: Option<&str>,
    doc_id: &str,
) -> Option<Response> {
    if let Some(supplied) = extract_bearer_or_header_token(headers) {
        if constant_time_str_eq(&state.hmac_key, &supplied, &state.token) {
            return None;
        }
        return Some(plain_error(StatusCode::UNAUTHORIZED, "Unauthorized"));
    }

    if let Some(ticket) = extract_query_param(query, "ticket") {
        if verify_media_ticket(&state.hmac_key, &ticket, doc_id).is_ok() {
            return None;
        }
        return Some(plain_error(StatusCode::FORBIDDEN, "Invalid or expired media ticket"));
    }

    if let Some(qtok) = extract_query_param(query, "token") {
        if constant_time_str_eq(&state.hmac_key, &qtok, &state.token) {
            return None;
        }
        return Some(plain_error(StatusCode::UNAUTHORIZED, "Unauthorized"));
    }

    Some(plain_error(StatusCode::UNAUTHORIZED, "Authentication required"))
}

fn authorize_general_request(
    state: &LoopbackState,
    headers: &HeaderMap,
    query: Option<&str>,
    scoped_doc_id: Option<&str>,
) -> Option<Response> {
    if let Some(supplied) = extract_bearer_or_header_token(headers) {
        if constant_time_str_eq(&state.hmac_key, &supplied, &state.token) {
            return None;
        }
        return Some(plain_error(StatusCode::UNAUTHORIZED, "Unauthorized"));
    }

    if let Some(qtok) = extract_query_param(query, "token") {
        if constant_time_str_eq(&state.hmac_key, &qtok, &state.token) {
            return None;
        }
        return Some(plain_error(StatusCode::UNAUTHORIZED, "Unauthorized"));
    }

    if let Some(ticket) = extract_query_param(query, "ticket") {
        if let Some(doc_id) = scoped_doc_id {
            if verify_media_ticket(&state.hmac_key, &ticket, doc_id).is_ok() {
                return None;
            }
        }
        return Some(plain_error(StatusCode::FORBIDDEN, "Invalid or expired media ticket"));
    }

    Some(plain_error(StatusCode::UNAUTHORIZED, "Authentication required"))
}

fn sign_hmac_hex(hmac_key: &[u8; 32], payload: &str) -> String {
    let mut mac = HmacSha256::new_from_slice(hmac_key).expect("HMAC supports 32-byte keys");
    mac.update(payload.as_bytes());
    hex::encode(mac.finalize().into_bytes())
}

fn constant_time_str_eq(hmac_key: &[u8; 32], candidate: &str, expected: &str) -> bool {
    let mut expected_mac =
        HmacSha256::new_from_slice(hmac_key).expect("HMAC supports 32-byte keys");
    expected_mac.update(expected.as_bytes());
    let expected_tag = expected_mac.finalize().into_bytes();

    let mut cand_mac = HmacSha256::new_from_slice(hmac_key).expect("HMAC supports 32-byte keys");
    cand_mac.update(candidate.as_bytes());
    cand_mac.verify_slice(&expected_tag).is_ok()
}

fn verify_media_ticket(
    hmac_key: &[u8; 32],
    ticket: &str,
    expected_doc_id: &str,
) -> Result<(), &'static str> {
    let parts: Vec<&str> = ticket.split('.').collect();
    if parts.len() != 3 {
        return Err("malformed");
    }
    let exp_ms: u64 = parts[0].parse().map_err(|_| "bad_expiry")?;
    let nonce_hex = parts[1];
    let sig_hex = parts[2];

    if nonce_hex.len() != 32 || !nonce_hex.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("bad_nonce");
    }

    let now = now_ms().map_err(|_| "clock_error")?;
    if now > exp_ms {
        return Err("expired");
    }

    let sig_bytes = hex::decode(sig_hex).map_err(|_| "bad_sig_hex")?;
    let payload = format!("{expected_doc_id}:{exp_ms}:{nonce_hex}");
    let mut mac = HmacSha256::new_from_slice(hmac_key).map_err(|_| "hmac_init")?;
    mac.update(payload.as_bytes());
    mac.verify_slice(&sig_bytes).map_err(|_| "bad_hmac")
}

fn now_ms() -> Result<u64, AppError> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .map_err(|err| AppError::new("SYSTEM_CLOCK_ERROR", err.to_string()))
}

fn load_documents_catalog(study_dir: &Path) -> Option<Value> {
    let docs_path = ensure_confined_existing_file(study_dir, Path::new("documents.json")).ok()?;
    let content = fs::read_to_string(docs_path).ok()?;
    let val: Value = serde_json::from_str(&content).ok()?;
    if val.is_object() {
        Some(val)
    } else {
        None
    }
}

fn has_allowed_extension(path: &Path, allowed_exts: &[&str]) -> bool {
    let Some(ext) = path.extension().and_then(|e| e.to_str()) else {
        return false;
    };
    let lower = format!(".{}", ext.to_ascii_lowercase());
    allowed_exts.contains(&lower.as_str())
}

fn resolve_cataloged_media(
    project_root: &Path,
    doc_id: &str,
    fallback_subdir: Option<&str>,
    allowed_exts: &[&str],
    check_video_nested: bool,
) -> Option<PathBuf> {
    let study_dir = project_root.join("data").join("study");
    let catalog = load_documents_catalog(&study_dir)?;
    let entry = catalog.get(doc_id)?;

    let raw_fp = entry
        .get("metadata")
        .and_then(|m| {
            m.get("file_path").and_then(|v| v.as_str()).or_else(|| {
                if check_video_nested {
                    m.get("video")
                        .and_then(|v| v.get("file_path"))
                        .and_then(|v| v.as_str())
                } else {
                    None
                }
            })
        });

    if let Some(fp_str) = raw_fp {
        let p = Path::new(fp_str);
        let candidate = if p.is_absolute() {
            p.to_path_buf()
        } else {
            project_root.join(p)
        };
        if let Ok(meta) = fs::symlink_metadata(&candidate) {
            if !meta.file_type().is_symlink() && meta.is_file() {
                if let Ok(canon) = dunce::canonicalize(&candidate) {
                    if !is_blocked_system_path(&canon)
                        && has_allowed_extension(&canon, allowed_exts)
                    {
                        if let Ok(canon_meta) = fs::symlink_metadata(&canon) {
                            if !canon_meta.file_type().is_symlink() && canon_meta.is_file() {
                                return Some(canon);
                            }
                        }
                    }
                }
            }
        }
    }

    if let Some(stripped) = doc_id.strip_prefix("doc_") {
        let hash_prefix = stripped
            .strip_prefix("vid_")
            .or_else(|| stripped.strip_prefix("aud_"))
            .unwrap_or(stripped);
        if hash_prefix.len() >= 8 {
            let search_dir = match fallback_subdir {
                Some(sub) => resolve_confined_path(&study_dir, Path::new(sub)).ok()?,
                None => dunce::canonicalize(&study_dir).ok()?,
            };
            if let Ok(entries) = fs::read_dir(&search_dir) {
                for item in entries.flatten() {
                    let name = item.file_name();
                    if name.to_string_lossy().starts_with(hash_prefix) {
                        if let Ok(canon) = ensure_confined_existing_file(&search_dir, &item.path()) {
                            if has_allowed_extension(&canon, allowed_exts) {
                                return Some(canon);
                            }
                        }
                    }
                }
            }
        }
    }

    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::http_common::test_send_raw_http as send_raw_http;
    use std::fs;
    use tempfile::tempdir;

    fn setup_fixture_project() -> (tempfile::TempDir, PathBuf) {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();
        let study_dir = root.join("data").join("study");
        fs::create_dir_all(study_dir.join("keyframes").join("doc_alpha")).unwrap();

        let pdf_path = study_dir.join("sample.pdf");
        fs::write(&pdf_path, b"0123456789ABCDEF").unwrap();
        fs::write(study_dir.join("notes.txt"), b"blocked-ext").unwrap();
        fs::write(study_dir.join("secret.json"), br#"{"secret":true}"#).unwrap();
        fs::write(root.join("outside.pdf"), b"outside").unwrap();
        fs::write(
            study_dir.join("keyframes").join("doc_alpha").join("kf1.jpg"),
            b"JPGDATA",
        )
        .unwrap();

        let docs_json = serde_json::json!({
            "doc_alpha": {
                "id": "doc_alpha",
                "metadata": {
                    "file_path": pdf_path.to_string_lossy().to_string()
                }
            },
            "doc_beta": {
                "id": "doc_beta",
                "metadata": {
                    "file_path": pdf_path.to_string_lossy().to_string()
                }
            }
        });
        fs::write(
            study_dir.join("documents.json"),
            serde_json::to_vec(&docs_json).unwrap(),
        )
        .unwrap();

        (dir, root)
    }

    #[tokio::test]
    async fn loopback_enforces_auth_tickets_ranges_and_security_guards() {
        let (_dir, root) = setup_fixture_project();
        let handle = LoopbackHandle::start(root).await.unwrap();
        let port = handle.port();

        // 1. /healthz works with valid Host
        let (st, head, body) = send_raw_http(
            port,
            &format!("GET /healthz HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 200);
        assert!(head.to_ascii_lowercase().contains("x-content-type-options: nosniff"));
        assert!(String::from_utf8_lossy(&body).contains("tauri-loopback"));

        // 2. DNS-rebinding Host spoof -> 403
        let (st, _, _) = send_raw_http(
            port,
            "GET /healthz HTTP/1.1\r\nHost: evil.com:8080\r\nConnection: close\r\n\r\n",
        )
        .await;
        assert_eq!(st, 403);

        // 3. Disallowed Origin -> 403
        let (st, _, _) = send_raw_http(
            port,
            &format!("GET /healthz HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nOrigin: https://evil.com\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 403);

        // 4. POST method -> 405
        let (st, _, _) = send_raw_http(
            port,
            &format!("POST /healthz HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 405);

        // 5. Missing auth on media route -> 401
        let (st, _, _) = send_raw_http(
            port,
            &format!("GET /api/study/document/doc_alpha/file HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 401);

        // 6. Wrong Bearer token -> 401
        let (st, _, _) = send_raw_http(
            port,
            &format!("GET /api/study/document/doc_alpha/file HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer deadbeef\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 401);

        // 7. Scoped ticket issued for doc_alpha: works for 200 full, 206 partial, 416 bad range, HEAD
        let ticket = handle.issue_media_ticket("doc_alpha", Some(60)).unwrap();
        let (st, _, body) = send_raw_http(
            port,
            &format!("GET /api/study/document/doc_alpha/file?ticket={} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nOrigin: tauri://localhost\r\nConnection: close\r\n\r\n", ticket.ticket),
        )
        .await;
        assert_eq!(st, 200);
        assert_eq!(body, b"0123456789ABCDEF");

        let (st, head, body) = send_raw_http(
            port,
            &format!("GET /api/study/document/doc_alpha/file?ticket={} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nRange: bytes=2-6\r\nConnection: close\r\n\r\n", ticket.ticket),
        )
        .await;
        assert_eq!(st, 206);
        assert!(head.contains("bytes 2-6/16"));
        assert_eq!(body, b"23456");

        let (st, head, body) = send_raw_http(
            port,
            &format!("HEAD /api/study/document/doc_alpha/file?ticket={} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n", ticket.ticket),
        )
        .await;
        assert_eq!(st, 200);
        assert!(head.to_ascii_lowercase().contains("content-length: 16"));
        assert!(body.is_empty());

        let (st, head, _) = send_raw_http(
            port,
            &format!("GET /api/study/document/doc_alpha/file?ticket={} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nRange: bytes=99-120\r\nConnection: close\r\n\r\n", ticket.ticket),
        )
        .await;
        assert_eq!(st, 416);
        assert!(head.contains("bytes */16"));

        // 8. Cross-document replay of doc_alpha ticket on doc_beta -> 403
        let (st, _, _) = send_raw_http(
            port,
            &format!("GET /api/study/document/doc_beta/file?ticket={} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n", ticket.ticket),
        )
        .await;
        assert_eq!(st, 403);

        // 9. Expired ticket -> 403
        let expired = handle.issue_media_ticket_with_expiry("doc_alpha", 1).unwrap();
        let (st, _, _) = send_raw_http(
            port,
            &format!("GET /api/study/document/doc_alpha/file?ticket={} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n", expired.ticket),
        )
        .await;
        assert_eq!(st, 403);

        // 10. Bearer token on /data/study allows safe asset, blocks unsafe extension (.json), blocks traversal
        let tok = handle.token();
        let (st, _, body) = send_raw_http(
            port,
            &format!("GET /data/study/keyframes/doc_alpha/kf1.jpg HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {tok}\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 200);
        assert_eq!(body, b"JPGDATA");

        let (st, _, _) = send_raw_http(
            port,
            &format!("GET /data/study/secret.json HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {tok}\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 403);

        let (st, _, _) = send_raw_http(
            port,
            &format!("GET /data/study/%2e%2e/outside.pdf HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nAuthorization: Bearer {tok}\r\nConnection: close\r\n\r\n"),
        )
        .await;
        assert_eq!(st, 403);

        handle.shutdown();
    }
}


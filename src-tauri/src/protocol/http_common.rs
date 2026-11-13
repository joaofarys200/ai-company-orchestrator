use std::io::SeekFrom;
use std::path::Path;

use axum::body::Body;
use axum::response::Response;
use http::{header, HeaderMap, HeaderValue, Method, StatusCode};
use tokio::io::{AsyncReadExt, AsyncSeekExt};
use tokio_util::io::ReaderStream;
use url::Url;

/// Checks that the HTTP `Host` header strictly names loopback with the bound listener port.
pub fn is_valid_loopback_host(host_header: Option<&str>, expected_port: u16) -> bool {
    let Some(raw) = host_header else {
        return false;
    };
    let h = raw.trim().to_ascii_lowercase();
    h == format!("127.0.0.1:{expected_port}")
        || h == format!("localhost:{expected_port}")
        || h == format!("[::1]:{expected_port}")
}

/// Validates an incoming `Origin` header against trusted desktop / loopback shell origins.
pub fn is_allowed_desktop_origin(origin_raw: &str, loopback_port: Option<u16>) -> bool {
    let trimmed = origin_raw.trim().trim_end_matches('/');
    let Ok(parsed) = Url::parse(trimmed) else {
        return false;
    };

    let scheme = parsed.scheme();
    let Some(host) = parsed.host_str() else {
        return false;
    };
    let host_lower = host.to_ascii_lowercase();
    let port = parsed.port();

    match scheme {
        "tauri" => host_lower == "localhost" && port.is_none(),
        "http" | "https" => {
            if host_lower == "tauri.localhost" && port.is_none() {
                return true;
            }
            if scheme == "http"
                && (host_lower == "localhost" || host_lower == "127.0.0.1" || host_lower == "[::1]")
            {
                if port == Some(5173) {
                    return true;
                }
                if let Some(lp) = loopback_port {
                    if port == Some(lp) {
                        return true;
                    }
                }
            }
            false
        }
        _ => false,
    }
}

/// Rejects path traversal tokens (`..`, encoded `%2e%2e`, backslashes, or null bytes) in raw URI paths.
pub fn has_suspicious_path_traversal(raw_path: &str) -> bool {
    let lower = raw_path.to_ascii_lowercase();
    lower.contains("..")
        || lower.contains("%2e%2e")
        || lower.contains("%2e.")
        || lower.contains(".%2e")
        || lower.contains('\\')
        || lower.contains("%5c")
        || lower.contains('\0')
        || lower.contains("%00")
}

/// Maps an extension (lowercase with leading dot) to a strict MIME type.
pub fn content_type_for_ext(ext: &str) -> &'static str {
    match ext.to_ascii_lowercase().as_str() {
        ".html" | ".htm" => "text/html; charset=utf-8",
        ".js" | ".mjs" => "application/javascript; charset=utf-8",
        ".css" => "text/css; charset=utf-8",
        ".json" => "application/json; charset=utf-8",
        ".svg" => "image/svg+xml",
        ".txt" | ".md" => "text/plain; charset=utf-8",
        ".pdf" => "application/pdf",
        ".mp4" => "video/mp4",
        ".webm" => "video/webm",
        ".mkv" => "video/x-matroska",
        ".mov" => "video/quicktime",
        ".avi" => "video/x-msvideo",
        ".wmv" => "video/x-ms-wmv",
        ".m4v" => "video/x-m4v",
        ".wav" => "audio/wav",
        ".mp3" => "audio/mpeg",
        ".m4a" => "audio/mp4",
        ".ogg" => "audio/ogg",
        ".flac" => "audio/flac",
        ".jpg" | ".jpeg" => "image/jpeg",
        ".png" => "image/png",
        ".webp" => "image/webp",
        ".gif" => "image/gif",
        ".ico" => "image/x-icon",
        ".woff2" => "font/woff2",
        ".woff" => "font/woff",
        ".docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx" => "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        _ => "application/octet-stream",
    }
}

/// Builds a `plain/text` HTTP error response with `X-Content-Type-Options: nosniff`.
pub fn plain_error(status: StatusCode, message: &'static str) -> Response {
    Response::builder()
        .status(status)
        .header(header::CONTENT_TYPE, "text/plain; charset=utf-8")
        .header(header::X_CONTENT_TYPE_OPTIONS, "nosniff")
        .header(header::CACHE_CONTROL, "no-store")
        .body(Body::from(message))
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

/// Attaches safe security and optional CORS headers to an outgoing response.
pub fn attach_cors_and_security_headers(headers: &mut HeaderMap, allowed_origin: Option<&str>) {
    headers.insert(
        header::X_CONTENT_TYPE_OPTIONS,
        HeaderValue::from_static("nosniff"),
    );
    if let Some(origin) = allowed_origin {
        if let Ok(origin_val) = HeaderValue::from_str(origin) {
            headers.insert(header::ACCESS_CONTROL_ALLOW_ORIGIN, origin_val);
            headers.insert(header::VARY, HeaderValue::from_static("Origin"));
            headers.insert(
                header::ACCESS_CONTROL_ALLOW_METHODS,
                HeaderValue::from_static("GET, HEAD, OPTIONS"),
            );
            headers.insert(
                header::ACCESS_CONTROL_ALLOW_HEADERS,
                HeaderValue::from_static("Authorization, Content-Type, Range, X-Jarvis-Token"),
            );
            headers.insert(
                header::ACCESS_CONTROL_EXPOSE_HEADERS,
                HeaderValue::from_static("Content-Length, Content-Range, Accept-Ranges"),
            );
        }
    }
}

/// Streams a non-symlink regular file with optional RFC 9110 single-range (`206 Partial Content`) support.
pub async fn stream_file_with_range(
    canon_path: &Path,
    content_type: &str,
    method: &Method,
    range_header: Option<&str>,
) -> Response {
    let meta = match tokio::fs::symlink_metadata(canon_path).await {
        Ok(m) if !m.file_type().is_symlink() && m.is_file() => m,
        _ => return plain_error(StatusCode::NOT_FOUND, "File not found"),
    };

    let file_size = meta.len();

    if let Some(raw_range) = range_header {
        let parsed = http_range_header::parse_range_header(raw_range)
            .and_then(|r| r.validate(file_size));
        let ranges = match parsed {
            Ok(list) if list.len() == 1 => list,
            _ => {
                return Response::builder()
                    .status(StatusCode::RANGE_NOT_SATISFIABLE)
                    .header(header::CONTENT_RANGE, format!("bytes */{file_size}"))
                    .header(header::ACCEPT_RANGES, "bytes")
                    .header(header::X_CONTENT_TYPE_OPTIONS, "nosniff")
                    .header(header::CACHE_CONTROL, "no-store")
                    .body(Body::empty())
                    .unwrap_or_else(|_| Response::new(Body::empty()));
            }
        };

        let range = &ranges[0];
        let start = *range.start();
        let end = *range.end();
        let content_len = end.saturating_sub(start).saturating_add(1);

        let body = if *method == Method::HEAD || content_len == 0 {
            Body::empty()
        } else {
            let mut file = match tokio::fs::File::open(canon_path).await {
                Ok(f) => f,
                Err(_) => return plain_error(StatusCode::NOT_FOUND, "File not found"),
            };
            if file.seek(SeekFrom::Start(start)).await.is_err() {
                return plain_error(
                    StatusCode::INTERNAL_SERVER_ERROR,
                    "Failed to seek media file",
                );
            }
            let limited = file.take(content_len);
            Body::from_stream(ReaderStream::with_capacity(limited, 64 * 1024))
        };

        return Response::builder()
            .status(StatusCode::PARTIAL_CONTENT)
            .header(header::CONTENT_TYPE, content_type)
            .header(
                header::CONTENT_RANGE,
                format!("bytes {start}-{end}/{file_size}"),
            )
            .header(header::CONTENT_LENGTH, content_len.to_string())
            .header(header::ACCEPT_RANGES, "bytes")
            .header(header::CACHE_CONTROL, "no-store")
            .header(header::X_CONTENT_TYPE_OPTIONS, "nosniff")
            .body(body)
            .unwrap_or_else(|_| Response::new(Body::empty()));
    }

    let body = if *method == Method::HEAD || file_size == 0 {
        Body::empty()
    } else {
        let file = match tokio::fs::File::open(canon_path).await {
            Ok(f) => f,
            Err(_) => return plain_error(StatusCode::NOT_FOUND, "File not found"),
        };
        Body::from_stream(ReaderStream::with_capacity(file, 64 * 1024))
    };

    Response::builder()
        .status(StatusCode::OK)
        .header(header::CONTENT_TYPE, content_type)
        .header(header::CONTENT_LENGTH, file_size.to_string())
        .header(header::ACCEPT_RANGES, "bytes")
        .header(header::CACHE_CONTROL, "no-store")
        .header(header::X_CONTENT_TYPE_OPTIONS, "nosniff")
        .body(body)
        .unwrap_or_else(|_| Response::new(Body::empty()))
}

#[cfg(test)]
pub(crate) async fn test_send_raw_http(port: u16, req: &str) -> (u16, String, Vec<u8>) {
    use std::time::Duration;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpStream;

    tokio::task::yield_now().await;
    let mut stream = TcpStream::connect(("127.0.0.1", port))
        .await
        .expect("connect to local axum test server");
    stream.write_all(req.as_bytes()).await.unwrap();
    stream.flush().await.unwrap();

    // Wait for server response EOF (server closes via `Connection: close`) without half-closing early.
    let mut buf = Vec::new();
    tokio::time::timeout(Duration::from_secs(5), stream.read_to_end(&mut buf))
        .await
        .expect("timed out reading HTTP response")
        .expect("read HTTP response bytes");

    let sep = buf.windows(4).position(|w| w == b"\r\n\r\n").unwrap_or_else(|| {
        panic!(
            "valid HTTP response headers (got {} bytes: {:?})",
            buf.len(),
            String::from_utf8_lossy(&buf)
        )
    });
    let head = String::from_utf8_lossy(&buf[..sep]).to_string();
    let body = buf[(sep + 4)..].to_vec();

    let status: u16 = head
        .lines()
        .next()
        .and_then(|l| l.split_whitespace().nth(1))
        .and_then(|s| s.parse().ok())
        .expect("HTTP status code");
    (status, head, body)
}


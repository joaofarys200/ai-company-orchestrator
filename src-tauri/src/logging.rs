//! Thread-safe rotating file logging and secret redaction for JARVIS OS processes.
//!
//! Logs are written under `<workspace_root>/logs/` (which resolves to
//! `%LOCALAPPDATA%\JarvisOS\logs\` in installed Windows builds) so background
//! workers and auxiliary tools stay completely diagnosable without allocating
//! visible console windows.

use std::collections::HashSet;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

use chrono::{SecondsFormat, Utc};
use serde_json::{json, Map, Value};

pub const DEFAULT_LOG_MAX_BYTES: u64 = 5 * 1024 * 1024;
pub const DEFAULT_LOG_MAX_BACKUPS: usize = 4;

const SENSITIVE_CLI_FLAGS: &[&str] = &[
    "--api-key",
    "--apikey",
    "--token",
    "--access-token",
    "--refresh-token",
    "--secret",
    "--password",
    "--passwd",
    "--auth",
    "--auth-token",
    "--bearer",
    "--client-secret",
    "--private-key",
    "--key",
];

const SENSITIVE_NAME_MARKERS: &[&str] = &[
    "API_KEY",
    "APIKEY",
    "SECRET",
    "TOKEN",
    "PASSWORD",
    "PASSWD",
    "PRIVATE_KEY",
    "CREDENTIAL",
    "AUTH",
];

const SECRET_TOKEN_PREFIXES: &[&str] = &[
    "github_pat_",
    "AIza",
    "sk-",
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "xoxb-",
    "xoxp-",
    "xoxa-",
    "xoxr-",
    "hf_",
    "glpat-",
];

/// Resolves the canonical log directory for a workspace root (`<root>/logs`),
/// honoring `JARVIS_LOG_DIR` when explicitly configured.
pub fn resolve_logs_dir(workspace_root: &Path) -> PathBuf {
    if let Some(raw) = std::env::var_os("JARVIS_LOG_DIR") {
        if !raw.is_empty() {
            return PathBuf::from(raw);
        }
    }
    workspace_root.join("logs")
}

fn is_sensitive_key_name(key: &str) -> bool {
    let upper = key.trim().to_ascii_uppercase().replace('-', "_");
    SENSITIVE_NAME_MARKERS
        .iter()
        .any(|marker| upper.contains(marker))
}

fn is_token_char(b: u8) -> bool {
    b.is_ascii_alphanumeric() || matches!(b, b'_' | b'-' | b'.' | b'+' | b'/' | b'=')
}

fn looks_like_inline_secret_value(val: &str) -> bool {
    let trimmed = val.trim_matches(|c| matches!(c, '"' | '\'' | ',' | ';'));
    if trimmed.is_empty() || trimmed == "[REDACTED]" {
        return false;
    }
    SECRET_TOKEN_PREFIXES
        .iter()
        .any(|prefix| trimmed.starts_with(prefix) && trimmed.len() > prefix.len() + 4)
}

fn redact_secret_prefixes_in_text(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let bytes = text.as_bytes();
    let mut i = 0;

    while i < bytes.len() {
        let rest = &text[i..];

        let mut matched_prefix: Option<&str> = None;
        for prefix in SECRET_TOKEN_PREFIXES {
            if rest.starts_with(prefix) {
                matched_prefix = Some(prefix);
                break;
            }
        }
        if let Some(prefix) = matched_prefix {
            let mut end = i + prefix.len();
            while end < bytes.len() && is_token_char(bytes[end]) {
                end += 1;
            }
            if end - (i + prefix.len()) >= 8 {
                out.push_str("[REDACTED]");
                i = end;
                continue;
            }
        }

        // Redact `Bearer <secret>` / `Basic <secret>` (case-insensitive).
        if rest.len() > 7 {
            let lower_7 = rest.get(..7).map(|s| s.to_ascii_lowercase());
            let lower_6 = rest.get(..6).map(|s| s.to_ascii_lowercase());
            if lower_7.as_deref() == Some("bearer ") {
                out.push_str(&text[i..i + 7]);
                let mut end = i + 7;
                while end < bytes.len() && is_token_char(bytes[end]) {
                    end += 1;
                }
                if end > i + 7 {
                    out.push_str("[REDACTED]");
                    i = end;
                    continue;
                }
            } else if lower_6.as_deref() == Some("basic ") {
                out.push_str(&text[i..i + 6]);
                let mut end = i + 6;
                while end < bytes.len() && is_token_char(bytes[end]) {
                    end += 1;
                }
                if end > i + 6 {
                    out.push_str("[REDACTED]");
                    i = end;
                    continue;
                }
            }
        }

        // Redact URL embedded credentials: `scheme://user:pass@host`.
        if let Some(after_scheme) = rest.strip_prefix("://") {
            let mut authority_end = after_scheme.len();
            for (idx, ch) in after_scheme.char_indices() {
                if matches!(ch, '/' | '?' | '#' | ' ' | '\t' | '\r' | '\n' | '"' | '\'') {
                    authority_end = idx;
                    break;
                }
            }
            let authority = &after_scheme[..authority_end];
            if let Some(at_idx) = authority.find('@') {
                let userinfo = &authority[..at_idx];
                if let Some(colon_idx) = userinfo.find(':') {
                    out.push_str("://");
                    out.push_str(&userinfo[..=colon_idx]);
                    out.push_str("[REDACTED]@");
                    out.push_str(&authority[at_idx + 1..]);
                    i += 3 + authority_end;
                    continue;
                }
            }
        }

        let Some(ch) = rest.chars().next() else {
            break;
        };
        out.push(ch);
        i += ch.len_utf8();
    }

    out
}

fn redact_sensitive_key_assignments(text: &str) -> String {
    let mut result = String::with_capacity(text.len());
    for part in text.split_inclusive(|c: char| c.is_whitespace()) {
        let trailing_ws_len = part.len() - part.trim_end().len();
        let (token, ws) = part.split_at(part.len() - trailing_ws_len);

        if let Some((raw_key, _raw_val)) = token.split_once('=') {
            let clean_key = raw_key.trim_matches(|c| matches!(c, '"' | '\'' | '-' | '{' | '['));
            if is_sensitive_key_name(clean_key) {
                result.push_str(raw_key);
                result.push_str("=[REDACTED]");
                result.push_str(ws);
                continue;
            }
        }
        result.push_str(token);
        result.push_str(ws);
    }
    result
}

/// Redacts API keys, bearer tokens, passwords, and sensitive key=value pairs from free-form text.
pub fn redact_sensitive_text(input: &str) -> String {
    if input.is_empty() {
        return String::new();
    }
    let single_line = input.replace(['\r', '\n'], " ");
    let step1 = redact_secret_prefixes_in_text(&single_line);
    redact_sensitive_key_assignments(&step1)
}

/// Redacts sensitive values from command-line argument vectors before logging.
pub fn redact_args<S: AsRef<str>>(args: &[S]) -> Vec<String> {
    let sensitive_flags: HashSet<&'static str> = SENSITIVE_CLI_FLAGS.iter().copied().collect();
    let mut out = Vec::with_capacity(args.len());
    let mut hide_next = false;

    for raw in args {
        let arg = raw.as_ref();
        if hide_next {
            out.push("[REDACTED]".to_string());
            hide_next = false;
            continue;
        }

        let lower = arg.to_ascii_lowercase();
        if sensitive_flags.contains(lower.as_str()) {
            out.push(arg.to_string());
            hide_next = true;
            continue;
        }

        if let Some((flag_part, val_part)) = arg.split_once('=') {
            let flag_lower = flag_part.to_ascii_lowercase();
            let clean_flag = flag_lower.trim_start_matches('-');
            if sensitive_flags.contains(flag_lower.as_str())
                || is_sensitive_key_name(clean_flag)
                || looks_like_inline_secret_value(val_part)
            {
                out.push(format!("{flag_part}=[REDACTED]"));
                continue;
            }
        }

        out.push(redact_sensitive_text(arg));
    }

    out
}

/// Size-rotated thread-safe file logger.
#[derive(Debug, Clone)]
pub struct RotatingFileLogger {
    path: PathBuf,
    max_bytes: u64,
    max_backups: usize,
    lock: Arc<Mutex<()>>,
}

impl RotatingFileLogger {
    pub fn new(path: PathBuf, max_bytes: u64, max_backups: usize) -> Self {
        Self {
            path,
            max_bytes: max_bytes.max(1024),
            max_backups,
            lock: Arc::new(Mutex::new(())),
        }
    }

    pub fn for_stream(logs_dir: &Path, filename: &str) -> Self {
        Self::new(
            logs_dir.join(filename),
            DEFAULT_LOG_MAX_BYTES,
            DEFAULT_LOG_MAX_BACKUPS,
        )
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn write_line(&self, raw_line: &str) {
        let Ok(_guard) = self.lock.lock() else {
            return;
        };
        if let Some(parent) = self.path.parent() {
            let _ = fs::create_dir_all(parent);
        }

        let sanitized = redact_sensitive_text(raw_line);
        let projected_add = sanitized.len() as u64 + 1;
        let current_len = fs::metadata(&self.path).map(|m| m.len()).unwrap_or(0);
        if current_len > 0 && current_len.saturating_add(projected_add) > self.max_bytes {
            self.rotate_locked();
        }

        if let Ok(mut file) = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.path)
        {
            let _ = writeln!(file, "{sanitized}");
            let _ = file.flush();
        }
    }

    pub fn log_event(&self, event: &str, fields: Value) {
        let ts = Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true);
        let mut payload = match fields {
            Value::Object(map) => map,
            other => {
                let mut m = Map::new();
                m.insert("detail".to_string(), other);
                m
            }
        };
        payload.entry("starter".to_string()).or_insert_with(|| {
            Value::String(
                std::env::current_exe()
                    .ok()
                    .and_then(|p| p.file_name().map(|n| n.to_string_lossy().into_owned()))
                    .unwrap_or_else(|| "jarvis-os.exe".to_string()),
            )
        });
        payload
            .entry("starter_pid".to_string())
            .or_insert_with(|| json!(std::process::id()));
        let sanitized_value = sanitize_json_value(Value::Object(payload));
        let json_str = serde_json::to_string(&sanitized_value).unwrap_or_else(|_| "{}".into());
        self.write_line(&format!("[{ts}] [{event}] {json_str}"));
    }

    pub fn log_stream_line(&self, stream: &str, pid: Option<u32>, line: &str) {
        let ts = Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true);
        let sanitized = redact_sensitive_text(line);
        match pid {
            Some(p) => self.write_line(&format!("[{ts}] [{stream} pid={p}] {sanitized}")),
            None => self.write_line(&format!("[{ts}] [{stream}] {sanitized}")),
        }
    }

    fn rotate_locked(&self) {
        if self.max_backups == 0 {
            let _ = fs::remove_file(&self.path);
            return;
        }
        let base_str = self.path.to_string_lossy();
        let oldest = PathBuf::from(format!("{base_str}.{}", self.max_backups));
        let _ = fs::remove_file(&oldest);

        for idx in (1..self.max_backups).rev() {
            let src = PathBuf::from(format!("{base_str}.{idx}"));
            let dst = PathBuf::from(format!("{base_str}.{}", idx + 1));
            if src.exists() {
                let _ = fs::remove_file(&dst);
                let _ = fs::rename(&src, &dst);
            }
        }

        if self.path.exists() {
            let first = PathBuf::from(format!("{base_str}.1"));
            let _ = fs::remove_file(&first);
            let _ = fs::rename(&self.path, &first);
        }
    }
}

fn sanitize_json_value(val: Value) -> Value {
    match val {
        Value::String(s) => Value::String(redact_sensitive_text(&s)),
        Value::Array(arr) => Value::Array(arr.into_iter().map(sanitize_json_value).collect()),
        Value::Object(map) => {
            let mut next = Map::with_capacity(map.len());
            for (k, v) in map {
                if is_sensitive_key_name(&k) && !matches!(v, Value::Null) {
                    next.insert(k, Value::String("[REDACTED]".to_string()));
                } else {
                    next.insert(k, sanitize_json_value(v));
                }
            }
            Value::Object(next)
        }
        other => other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redact_sensitive_text_masks_keys_tokens_and_urls() {
        let sample = "GEMINI_API_KEY=AIzaSyAbCdEf1234567890XYZ Authorization=Bearer my_secret_token_999 https://alice:hunter2@example.com/hook sk-live-secret-abcdef123456";
        let redacted = redact_sensitive_text(sample);
        assert!(!redacted.contains("AIzaSyAbCdEf1234567890XYZ"));
        assert!(!redacted.contains("my_secret_token_999"));
        assert!(!redacted.contains("hunter2"));
        assert!(!redacted.contains("sk-live-secret-abcdef123456"));
        assert!(redacted.contains("GEMINI_API_KEY=[REDACTED]"));
        assert!(redacted.contains("https://alice:[REDACTED]@example.com/hook"));
    }

    #[test]
    fn redact_args_masks_sensitive_flags_and_values() {
        let args = [
            "-u",
            "worker_boot.py",
            "--api-key",
            "secret-value-123",
            "--token=ghp_1234567890abcdef",
            "GEMINI_API_KEY=AIzaSy1234567890123456",
            "--worker",
            "ai",
        ];
        let cleaned = redact_args(&args);
        assert_eq!(cleaned[0], "-u");
        assert_eq!(cleaned[2], "--api-key");
        assert_eq!(cleaned[3], "[REDACTED]");
        assert_eq!(cleaned[4], "--token=[REDACTED]");
        assert_eq!(cleaned[5], "GEMINI_API_KEY=[REDACTED]");
        assert_eq!(cleaned[7], "ai");
    }

    #[test]
    fn rotating_file_logger_rotates_and_scrubs_secrets() {
        let dir = std::env::temp_dir().join(format!("jarvis_log_rot_test_{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("workers.log");
        let logger = RotatingFileLogger::new(path.clone(), 1024, 2);

        for i in 0..40 {
            logger.write_line(&format!(
                "entry={i} payload=0123456789abcdefghijklmnopqrstuvwxyz GEMINI_API_KEY=AIzaSySecretKey{i:04}0000"
            ));
        }

        assert!(path.exists(), "primary log file must exist");
        assert!(
            dir.join("workers.log.1").exists(),
            "first rotated backup must exist"
        );
        assert!(
            dir.join("workers.log.2").exists(),
            "second rotated backup must exist"
        );
        assert!(
            !dir.join("workers.log.3").exists(),
            "backups beyond max_backups must not accumulate"
        );

        let content = fs::read_to_string(&path).unwrap();
        assert!(!content.contains("AIzaSySecretKey"));
        assert!(content.contains("GEMINI_API_KEY=[REDACTED]"));

        let _ = fs::remove_dir_all(&dir);
    }
}

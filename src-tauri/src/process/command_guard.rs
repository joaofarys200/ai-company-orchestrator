//! Shell-free command tokenizer, closed executable allowlist, and secret-isolated runner.
//!
//! Replaces legacy regex/substring blocklists (`workspace_policy.py`) and PowerShell
//! `powershell -Command "& { ... }"` execution with direct `CreateProcess` argv execution.

use std::collections::{BTreeMap, HashSet};
use std::path::{Path, PathBuf};
use std::process::Stdio;
use std::time::Duration;

use serde::Serialize;
use tokio::io::AsyncReadExt;
use tokio::process::Command;

use crate::permissions::path_jail::{
    is_blocked_system_path, resolve_confined_path,
};
use crate::process::job_object::WORKER_CREATION_FLAGS;

pub const MAX_COMMAND_OUTPUT_BYTES: usize = 512 * 1024; // 512 KiB per stream

const ALLOWED_EXECUTABLES: &[&str] = &[
    "python",
    "python3",
    "pytest",
    "npm",
    "npx",
    "node",
    "tsc",
    "vite",
    "cargo",
    "rustc",
    "git",
];

const SAFE_GIT_SUBCOMMANDS: &[&str] = &["status", "diff", "log", "show", "branch", "rev-parse"];

const SAFE_ENV_KEYS: &[&str] = &[
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "SYSTEMDRIVE",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "LANG",
    "LC_ALL",
    "TERM",
    "VIRTUAL_ENV",
    "NODE_ENV",
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ValidatedCommand {
    pub program: String,
    pub args: Vec<String>,
    pub working_dir: PathBuf,
}

#[derive(Debug, Clone, Serialize)]
pub struct GuardedCommandOutput {
    pub exit_code: Option<i32>,
    pub timed_out: bool,
    pub stdout: String,
    pub stderr: String,
    pub truncated: bool,
}

/// Tokenizes a command string cleanly without shell interpretation, rejecting unclosed quotes,
/// control characters, subshells, pipelines, and redirection metacharacters.
pub fn tokenize_command_line(raw: &str) -> Result<Vec<String>, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Err("Command cannot be empty".to_string());
    }
    if trimmed.contains('\0') || trimmed.contains('\r') || trimmed.contains('\n') {
        return Err("SECURITY_VIOLATION: control characters or multi-line scripts blocked".to_string());
    }

    let mut tokens = Vec::new();
    let mut current = String::new();
    let mut quote: Option<char> = None;
    let chars: Vec<char> = trimmed.chars().collect();
    let mut i = 0usize;

    while i < chars.len() {
        let ch = chars[i];
        match quote {
            Some(q) => {
                if ch == q {
                    quote = None;
                } else if q == '"' && (ch == '$' || ch == '`') {
                    return Err(format!(
                        "SECURITY_VIOLATION: shell expansion character `{ch}` blocked inside quotes"
                    ));
                } else {
                    current.push(ch);
                }
            }
            None => {
                if ch == '"' || ch == '\'' {
                    quote = Some(ch);
                } else if ch.is_whitespace() {
                    if !current.is_empty() {
                        tokens.push(std::mem::take(&mut current));
                    }
                } else if matches!(ch, '|' | '&' | ';' | '>' | '<' | '`' | '(' | ')' | '{' | '}' | '$') {
                    return Err(format!(
                        "SECURITY_VIOLATION: shell metacharacter `{ch}` rejected"
                    ));
                } else {
                    current.push(ch);
                }
            }
        }
        i += 1;
    }

    if quote.is_some() {
        return Err("Invalid command syntax: unclosed quote".to_string());
    }
    if !current.is_empty() {
        tokens.push(current);
    }
    if tokens.is_empty() {
        return Err("Command produced zero argv tokens".to_string());
    }
    Ok(tokens)
}

fn normalize_executable_stem(program: &str) -> Result<String, String> {
    if program.contains('/') || program.contains('\\') || program.contains(':') {
        return Err(format!(
            "SECURITY_VIOLATION: explicit executable paths are not allowed (`{program}`); use bare allowlisted binary name"
        ));
    }
    let lower = program.trim().to_ascii_lowercase();
    let stem = lower
        .strip_suffix(".exe")
        .or_else(|| lower.strip_suffix(".cmd"))
        .or_else(|| lower.strip_suffix(".bat"))
        .unwrap_or(&lower);
    Ok(stem.to_string())
}

fn looks_like_path_token(arg: &str) -> bool {
    arg.contains("..")
        || arg.contains('/')
        || arg.contains('\\')
        || arg.contains(':')
        || (arg.len() >= 2 && arg.as_bytes()[1] == b':')
}

/// Validates argv and confines `cwd` strictly inside `workspace_root`.
pub fn validate_command_argv(
    argv: &[String],
    workspace_root: &Path,
    requested_cwd: Option<&Path>,
) -> Result<ValidatedCommand, String> {
    if argv.is_empty() {
        return Err("Command argv cannot be empty".to_string());
    }

    let raw_prog = argv[0].trim();
    let stem = normalize_executable_stem(raw_prog)?;
    if !ALLOWED_EXECUTABLES.contains(&stem.as_str()) {
        return Err(format!(
            "SECURITY_VIOLATION: executable `{raw_prog}` is not in closed allowlist"
        ));
    }

    let args = argv[1..].to_vec();
    if stem == "git" {
        let sub = args.first().map(|s| s.as_str()).unwrap_or("");
        if !SAFE_GIT_SUBCOMMANDS.contains(&sub) {
            return Err(format!(
                "SECURITY_VIOLATION: git subcommand `{sub}` is restricted by command guard"
            ));
        }
    }

    // Block arbitrary inline interpreter execution (`python -c`, `node -e`, `node --eval`)
    if stem == "python" || stem == "python3" {
        if args.iter().any(|a| a == "-c" || a.starts_with("-c")) {
            return Err("SECURITY_VIOLATION: inline `python -c` execution is blocked".to_string());
        }
    }
    if stem == "node" {
        if args
            .iter()
            .any(|a| a == "-e" || a == "--eval" || a == "-p" || a == "--print")
        {
            return Err("SECURITY_VIOLATION: inline `node -e` execution is blocked".to_string());
        }
    }

    let canonical_root = dunce::canonicalize(workspace_root).map_err(|e| {
        format!(
            "Invalid workspace root {}: {e}",
            workspace_root.display()
        )
    })?;
    let working_dir = match requested_cwd {
        Some(rel_or_abs) => resolve_confined_path(&canonical_root, rel_or_abs)
            .map_err(|e| e.to_string())?,
        None => canonical_root.clone(),
    };

    for arg in &args {
        if arg.contains('\0') {
            return Err("SECURITY_VIOLATION: null byte in argument".to_string());
        }
        if arg.contains("..") {
            return Err(format!(
                "SECURITY_VIOLATION: path traversal sequence `..` blocked in `{arg}`"
            ));
        }
        if looks_like_path_token(arg) && !arg.starts_with("http://") && !arg.starts_with("https://") {
            let candidate = Path::new(arg);
            if is_blocked_system_path(candidate) {
                return Err(format!(
                    "SECURITY_VIOLATION: access to protected system path `{arg}` blocked"
                ));
            }
            resolve_confined_path(&working_dir, candidate).map_err(|e| e.to_string())?;
        }
    }

    let resolved_program = if cfg!(windows) {
        match stem.as_str() {
            "npm" => "npm.cmd".to_string(),
            "npx" => "npx.cmd".to_string(),
            _ => raw_prog.to_string(),
        }
    } else {
        raw_prog.to_string()
    };

    Ok(ValidatedCommand {
        program: resolved_program,
        args,
        working_dir,
    })
}

/// Validates a raw command string using `tokenize_command_line` + `validate_command_argv`.
pub fn validate_command_string(
    raw: &str,
    workspace_root: &Path,
    requested_cwd: Option<&Path>,
) -> Result<ValidatedCommand, String> {
    let tokens = tokenize_command_line(raw)?;
    validate_command_argv(&tokens, workspace_root, requested_cwd)
}

/// Builds a sanitized child environment preserving OS basics while scrubbing secret tokens.
pub fn build_sanitized_env() -> BTreeMap<String, String> {
    let allow: HashSet<&str> = SAFE_ENV_KEYS.iter().copied().collect();
    let mut env = BTreeMap::new();
    for (k, v) in std::env::vars() {
        if allow.contains(k.to_ascii_uppercase().as_str()) {
            env.insert(k, v);
        }
    }
    env.insert("PYTHONUNBUFFERED".to_string(), "1".to_string());
    env.insert("PYTHONIOENCODING".to_string(), "utf-8".to_string());
    env.insert("PYTHONDONTWRITEBYTECODE".to_string(), "1".to_string());
    env
}

async fn read_capped<R: tokio::io::AsyncRead + Unpin>(
    mut stream: R,
    limit: usize,
) -> (String, bool) {
    let mut buf = Vec::new();
    let mut chunk = [0u8; 4096];
    let mut truncated = false;
    loop {
        match stream.read(&mut chunk).await {
            Ok(0) | Err(_) => break,
            Ok(n) => {
                let remaining = limit.saturating_sub(buf.len());
                if remaining == 0 {
                    truncated = true;
                    break;
                }
                let take = n.min(remaining);
                buf.extend_from_slice(&chunk[..take]);
                if take < n {
                    truncated = true;
                    break;
                }
            }
        }
    }
    (String::from_utf8_lossy(&buf).into_owned(), truncated)
}

/// Executes a validated command directly (`CreateProcess` with `CREATE_NO_WINDOW`, scrubbed env,
/// strict timeout, and bounded stdout/stderr). Never invokes a command shell.
pub async fn execute_guarded_command(
    validated: &ValidatedCommand,
    timeout: Duration,
) -> Result<GuardedCommandOutput, String> {
    let mut cmd = Command::new(&validated.program);
    cmd.args(&validated.args)
        .current_dir(&validated.working_dir)
        .env_clear()
        .envs(build_sanitized_env())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);

    #[cfg(windows)]
    {
        cmd.creation_flags(WORKER_CREATION_FLAGS);
    }

    let mut child = cmd.spawn().map_err(|e| {
        format!(
            "Failed to spawn `{}` cleanly: {e}",
            validated.program
        )
    })?;

    let stdout_pipe = child.stdout.take().expect("stdout piped");
    let stderr_pipe = child.stderr.take().expect("stderr piped");
    let out_task = tokio::spawn(read_capped(stdout_pipe, MAX_COMMAND_OUTPUT_BYTES));
    let err_task = tokio::spawn(read_capped(stderr_pipe, MAX_COMMAND_OUTPUT_BYTES));

    let mut timed_out = false;
    let status_opt = match tokio::time::timeout(timeout, child.wait()).await {
        Ok(res) => Some(res.map_err(|e| format!("Wait failed: {e}"))?),
        Err(_) => {
            timed_out = true;
            let _ = child.kill().await;
            let _ = child.wait().await;
            None
        }
    };

    let (stdout, out_trunc) = out_task.await.unwrap_or_default();
    let (stderr, err_trunc) = err_task.await.unwrap_or_default();

    Ok(GuardedCommandOutput {
        exit_code: status_opt.and_then(|s| s.code()),
        timed_out,
        stdout,
        stderr,
        truncated: out_trunc || err_trunc,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn command_guard_rejects_shells_metacharacters_traversal_and_inline_eval() {
        let dir = tempdir().expect("create tempdir");
        let root = dir.path();

        for blocked in [
            "",
            "powershell -NoProfile -Command \"Get-Process\"",
            "cmd /c dir",
            "bash -c ls",
            "python --version && whoami",
            "python app.py | findstr secret",
            "python ../outside.py",
            "python C:\\Windows\\System32\\calc.exe",
            "python -c \"import os; os.system('id')\"",
            "node -e \"console.log(process.env)\"",
            "git push origin main --force",
            "C:\\Python312\\python.exe script.py",
            "python \"unclosed quote",
        ] {
            assert!(
                validate_command_string(blocked, root, None).is_err(),
                "expected command_guard to reject {blocked:?}"
            );
        }
    }

    #[test]
    fn command_guard_allows_confined_safe_invocations_and_scrubs_secrets() {
        let dir = tempdir().expect("create tempdir");
        let root = dir.path();
        std::fs::write(root.join("app.py"), "print('ok')").unwrap();

        let validated = validate_command_string("python \"app.py\" --version", root, None)
            .expect("safe confined invocation allowed");
        assert_eq!(validated.program, "python");
        assert_eq!(validated.args, vec!["app.py", "--version"]);

        std::env::set_var("JARVIS_TEST_SECRET_TOKEN", "top-secret-123");
        let sanitized = build_sanitized_env();
        assert!(!sanitized.contains_key("JARVIS_TEST_SECRET_TOKEN"));
        std::env::remove_var("JARVIS_TEST_SECRET_TOKEN");
    }

    #[tokio::test]
    async fn execute_guarded_command_runs_python_without_leaking_secrets() {
        let dir = tempdir().expect("create tempdir");
        let root = dir.path();
        let script = root.join("check_env.py");
        std::fs::write(
            &script,
            "import os, sys; print(os.environ.get('JARVIS_SECRET_LEAK_TEST', 'NONE'))",
        )
        .unwrap();

        std::env::set_var("JARVIS_SECRET_LEAK_TEST", "SHOULD_NOT_LEAK");
        let validated = validate_command_string("python check_env.py", root, None)
            .expect("validate safe python script");
        let output = execute_guarded_command(&validated, Duration::from_secs(5))
            .await
            .expect("execute python cleanly");
        std::env::remove_var("JARVIS_SECRET_LEAK_TEST");

        assert_eq!(output.exit_code, Some(0));
        assert!(!output.timed_out);
        assert_eq!(output.stdout.trim(), "NONE");
    }
}

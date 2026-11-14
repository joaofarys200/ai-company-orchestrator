//! Supervised pool of specialized Python sidecar workers.
//!
//! Each worker role runs inside an isolated OS process assigned to a Windows Job Object,
//! boots `workers/worker_boot.py --worker <role>`, completes the `worker.ready` ->
//! `worker.init` handshake, maintains 5s/15s heartbeats, and auto-restarts with bounded
//! exponential backoff when crashed or unresponsive.

use std::collections::{BTreeMap, HashMap, HashSet, VecDeque};
use std::future::Future;
use std::path::{Path, PathBuf};
use std::pin::Pin;
use std::process::Stdio;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, BufReader};
use tokio::process::{Child, Command};
use tokio::sync::{mpsc, Mutex, RwLock};
use tokio::task::JoinHandle;

use crate::process::job_object::{JobObject, WORKER_CREATION_FLAGS};
use crate::workers::rpc_client::{
    ReverseRpcHandler, RpcCallError, WorkerHealth, WorkerRpcClient, WorkerStreamEvent,
};

const MAX_STDERR_LINES: usize = 64;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum WorkerPoolRole {
    Echo,
    Ai,
    Study,
    Knowledge,
    Mission,
    Voice,
}

impl WorkerPoolRole {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Echo => "echo",
            Self::Ai => "ai",
            Self::Study => "study",
            Self::Knowledge => "knowledge",
            Self::Mission => "mission",
            Self::Voice => "voice",
        }
    }

    pub fn production_roles() -> &'static [WorkerPoolRole] {
        &[Self::Ai, Self::Study, Self::Mission, Self::Voice]
    }

    pub fn all_roles() -> &'static [WorkerPoolRole] {
        &[
            Self::Echo,
            Self::Ai,
            Self::Study,
            Self::Knowledge,
            Self::Mission,
            Self::Voice,
        ]
    }
}

#[derive(Debug, Clone)]
pub struct WorkerSupervisorConfig {
    pub workspace_root: PathBuf,
    pub resource_root: Option<PathBuf>,
    pub canonical_db_path: Option<PathBuf>,
    pub python_executable: Option<PathBuf>,
    pub heartbeat_interval: Duration,
    pub heartbeat_timeout: Duration,
    pub ready_timeout: Duration,
    pub shutdown_timeout: Duration,
    pub max_memory_bytes: Option<usize>,
    pub max_restart_attempts: u32,
    pub base_backoff: Duration,
    pub init_params: Value,
}

impl WorkerSupervisorConfig {
    pub fn for_workspace(workspace_root: PathBuf) -> Self {
        Self {
            workspace_root,
            resource_root: None,
            canonical_db_path: None,
            python_executable: None,
            heartbeat_interval: Duration::from_secs(5),
            heartbeat_timeout: Duration::from_secs(15),
            ready_timeout: Duration::from_secs(45),
            shutdown_timeout: Duration::from_secs(2),
            max_memory_bytes: Some(JobObject::DEFAULT_WORKER_MEMORY_LIMIT_BYTES),
            max_restart_attempts: 5,
            base_backoff: Duration::from_secs(1),
            init_params: json!({}),
        }
    }

    pub fn with_resource_root(mut self, resource_root: PathBuf) -> Self {
        self.resource_root = Some(resource_root);
        self
    }

    pub fn with_canonical_db_path(mut self, db_path: PathBuf) -> Self {
        self.canonical_db_path = Some(db_path);
        self
    }
}

const CORE_WORKER_SAFE_ENV_KEYS: &[&str] = &[
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "SYSTEMDRIVE",
    "COMSPEC",
    "OS",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "APPDATA",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "CURL_CA_BUNDLE",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "CUDA_VISIBLE_DEVICES",
    "NVIDIA_VISIBLE_DEVICES",
    "PYTEST_CURRENT_TEST",
];

const RUNTIME_WORKER_SAFE_ENV_KEYS: &[&str] = &[
    "ALLOW_EXTERNAL_FALLBACK",
    "CHAT_MAX_TOKENS",
    "CHAT_TIMEOUT_SECONDS",
    "CLOUD_FOR_COMPLEX",
    "CREWAI_TEMPERATURE",
    "FFMPEG_PATH",
    "FFPROBE_PATH",
    "GEMINI_CREW_MODEL",
    "GEMINI_FOR_COMPLEX",
    "GEMINI_LIVE_VOICE",
    "GEMINI_MODEL",
    "GEMINI_OPENAI_BASE_URL",
    "HF_HOME",
    "HUGGINGFACE_HUB_CACHE",
    "JARVIS_MISSION_STALE_LOCK_SECONDS",
    "JARVIS_STATE_DIR",
    "JARVIS_STORAGE_BACKEND",
    "MAX_BUDGET_USD",
    "MAX_DAILY_SPEND",
    "MAX_SINGLE_TRANSACTION",
    "OBSIDIAN_VAULT_PATH",
    "ORCHESTRATOR_MODE",
];

const AI_WORKER_API_ENV_KEYS: &[&str] = &[
    "ANTHROPIC_API_KEY",
    "APIFY_API_TOKEN",
    "BROWSERBASE_API_KEY",
    "COMPOSIO_API_KEY",
    "FIRECRAWL_API_KEY",
    "GEMINI_API_KEY",
];

fn is_allowed_worker_env_key(role: WorkerPoolRole, upper_key: &str) -> bool {
    if CORE_WORKER_SAFE_ENV_KEYS.contains(&upper_key) {
        return true;
    }
    if role == WorkerPoolRole::Echo {
        return false;
    }
    if RUNTIME_WORKER_SAFE_ENV_KEYS.contains(&upper_key)
        || upper_key.starts_with("OLLAMA_")
        || upper_key.starts_with("VOICE_")
        || upper_key.starts_with("WHISPER_")
        || upper_key.starts_with("STUDY_")
        || upper_key.starts_with("AIRLLM_")
    {
        return true;
    }
    if matches!(
        role,
        WorkerPoolRole::Ai
            | WorkerPoolRole::Study
            | WorkerPoolRole::Voice
            | WorkerPoolRole::Mission
    ) && (AI_WORKER_API_ENV_KEYS.contains(&upper_key)
        || upper_key.starts_with("GEMINI_API_KEY_"))
    {
        return true;
    }
    false
}

/// Builds an explicitly allowlisted, role-scoped child environment (used with `cmd.env_clear()`).
pub fn build_worker_environment_from_iter<I, K, V>(
    role: WorkerPoolRole,
    workspace_root: &Path,
    canonical_db: &Path,
    parent_env: I,
) -> BTreeMap<String, String>
where
    I: IntoIterator<Item = (K, V)>,
    K: AsRef<str>,
    V: AsRef<str>,
{
    let mut env = BTreeMap::new();
    for (k, v) in parent_env {
        let key_str = k.as_ref();
        let upper = key_str.to_ascii_uppercase();
        if is_allowed_worker_env_key(role, &upper) {
            env.insert(key_str.to_string(), v.as_ref().to_string());
        }
    }

    env.insert("PYTHONUNBUFFERED".to_string(), "1".to_string());
    env.insert("PYTHONIOENCODING".to_string(), "utf-8".to_string());
    env.insert("PYTHONDONTWRITEBYTECODE".to_string(), "1".to_string());
    env.insert("JARVIS_DB_WRITE_OWNER".to_string(), "rust".to_string());
    env.insert(
        "JARVIS_CANONICAL_DB_PATH".to_string(),
        canonical_db.to_string_lossy().into_owned(),
    );
    env.insert(
        "JARVIS_PROJECT_ROOT".to_string(),
        workspace_root.to_string_lossy().into_owned(),
    );
    env
}

pub fn build_worker_environment(
    role: WorkerPoolRole,
    workspace_root: &Path,
    canonical_db: &Path,
) -> BTreeMap<String, String> {
    build_worker_environment_from_iter(role, workspace_root, canonical_db, std::env::vars())
}

/// Resolves the JARVIS OS workspace root containing `workers/worker_boot.py`.
pub fn resolve_workspace_root() -> PathBuf {
    if let Some(env_root) = std::env::var_os("JARVIS_WORKSPACE_ROOT") {
        let candidate = PathBuf::from(env_root);
        if candidate.join("workers").join("worker_boot.py").exists() {
            return dunce::canonicalize(&candidate).unwrap_or(candidate);
        }
    }

    let mut search_bases = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        search_bases.push(cwd);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            search_bases.push(parent.to_path_buf());
        }
    }

    for base in search_bases {
        let mut cursor = Some(base.as_path());
        for _ in 0..6 {
            let Some(dir) = cursor else {
                break;
            };
            if dir.join("workers").join("worker_boot.py").exists() {
                return dunce::canonicalize(dir).unwrap_or_else(|_| dir.to_path_buf());
            }
            cursor = dir.parent();
        }
    }

    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

/// Resolves the Python interpreter binary to use for sidecar workers.
pub fn resolve_python_executable(workspace_root: &Path, override_path: Option<&Path>) -> PathBuf {
    if let Some(explicit) = override_path {
        return explicit.to_path_buf();
    }
    if let Some(env_bin) = std::env::var_os("JARVIS_PYTHON_BIN") {
        if !env_bin.is_empty() {
            return PathBuf::from(env_bin);
        }
    }

    let venv_candidates = if cfg!(windows) {
        vec![
            workspace_root
                .join("venv")
                .join("Scripts")
                .join("python.exe"),
            workspace_root
                .join(".venv")
                .join("Scripts")
                .join("python.exe"),
        ]
    } else {
        vec![
            workspace_root.join("venv").join("bin").join("python"),
            workspace_root.join(".venv").join("bin").join("python"),
        ]
    };

    for candidate in venv_candidates {
        if candidate.is_file() {
            return candidate;
        }
    }

    PathBuf::from("python")
}

#[derive(Debug, Clone, Serialize)]
pub struct WorkerStatusSnapshot {
    pub role: WorkerPoolRole,
    pub running: bool,
    pub pid: Option<u32>,
    pub capabilities: Vec<String>,
    pub rss_memory_mb: f64,
    pub active_tasks: usize,
    pub health: String,
    pub restart_count: u32,
}

/// Active running worker instance bound to a Job Object and RPC client.
pub struct ManagedWorker {
    pub role: WorkerPoolRole,
    pub pid: u32,
    pub capabilities: Vec<String>,
    _job: JobObject,
    rpc: WorkerRpcClient,
    child: Mutex<Child>,
    stderr_lines: Arc<Mutex<VecDeque<String>>>,
    stderr_task: Mutex<Option<JoinHandle<()>>>,
}

/// Ensures that if a packaged `py-runtime/runtime-bundle.zip` (or pre-extracted
/// `py-runtime/python/python.exe`) exists under `resource_root`, it is extracted once
/// (verified by SHA-256 stamp) into `workspace_root/runtime/python-bundle` and returns
/// `(python_exe_path, app_code_root)`.
pub fn ensure_bundled_python_runtime(
    resource_root: &Path,
    workspace_root: &Path,
) -> Option<(PathBuf, PathBuf)> {
    let direct_candidates = [
        resource_root.join("py-runtime"),
        resource_root.join("_up_").join("py-runtime"),
        resource_root.to_path_buf(),
    ];

    for dir in &direct_candidates {
        let direct_py = dir.join("python").join("python.exe");
        let direct_app = dir.join("app");
        if direct_py.is_file() && direct_app.join("workers").join("worker_boot.py").is_file() {
            return Some((direct_py, direct_app));
        }
    }

    let bundle_zip = direct_candidates
        .iter()
        .map(|d| d.join("runtime-bundle.zip"))
        .find(|p| p.is_file())?;

    static EXTRACT_LOCK: std::sync::OnceLock<std::sync::Mutex<()>> = std::sync::OnceLock::new();
    let _extract_guard = EXTRACT_LOCK
        .get_or_init(|| std::sync::Mutex::new(()))
        .lock()
        .ok()?;

    let manifest_path = bundle_zip.parent()?.join("manifest.json");
    let expected_stamp = std::fs::read_to_string(&manifest_path)
        .ok()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| {
            v.get("bundle_sha256")
                .and_then(|x| x.as_str())
                .map(|x| x.to_string())
        })
        .unwrap_or_else(|| {
            let len = std::fs::metadata(&bundle_zip).map(|m| m.len()).unwrap_or(0);
            format!("size:{len}")
        });

    let target_dir = workspace_root.join("runtime").join("python-bundle");
    let stamp_file = target_dir.join(".extracted_sha256");
    let extracted_py = target_dir.join("python").join("python.exe");
    let extracted_app = target_dir.join("app");
    let extracted_boot = extracted_app.join("workers").join("worker_boot.py");

    let already_valid = extracted_py.is_file()
        && extracted_boot.is_file()
        && std::fs::read_to_string(&stamp_file)
            .map(|s| s.trim() == expected_stamp)
            .unwrap_or(false);

    if !already_valid {
        let _ = std::fs::create_dir_all(&target_dir);
        let tar_bin = if cfg!(windows) {
            PathBuf::from(r"C:\Windows\System32\tar.exe")
        } else {
            PathBuf::from("tar")
        };
        let tar_cmd = if tar_bin.is_file() {
            tar_bin
        } else {
            PathBuf::from("tar")
        };
        let mut extract_cmd = std::process::Command::new(tar_cmd);
        extract_cmd
            .arg("-xf")
            .arg(&bundle_zip)
            .arg("-C")
            .arg(&target_dir);
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            extract_cmd.creation_flags(WORKER_CREATION_FLAGS);
        }
        let status = extract_cmd.status().ok()?;
        if !status.success() {
            return None;
        }
        let _ = std::fs::write(&stamp_file, &expected_stamp);
    }

    if extracted_py.is_file() && extracted_boot.is_file() {
        Some((extracted_py, extracted_app))
    } else {
        None
    }
}

impl ManagedWorker {
    async fn spawn(
        role: WorkerPoolRole,
        config: &WorkerSupervisorConfig,
        reverse_handler: Arc<RwLock<Option<ReverseRpcHandler>>>,
    ) -> Result<Arc<Self>, RpcCallError> {
        let base_code_root = config
            .resource_root
            .as_deref()
            .unwrap_or(&config.workspace_root);

        let bundled_runtime = if config.python_executable.is_none()
            && std::env::var_os("JARVIS_PYTHON_BIN").is_none()
        {
            ensure_bundled_python_runtime(base_code_root, &config.workspace_root)
        } else {
            None
        };

        let code_root: PathBuf = bundled_runtime
            .as_ref()
            .map(|(_, app_dir)| app_dir.clone())
            .unwrap_or_else(|| base_code_root.to_path_buf());

        let script_candidates = [
            code_root.join("workers").join("worker_boot.py"),
            code_root
                .join("_up_")
                .join("workers")
                .join("worker_boot.py"),
            base_code_root.join("workers").join("worker_boot.py"),
            base_code_root
                .join("_up_")
                .join("workers")
                .join("worker_boot.py"),
            config.workspace_root.join("workers").join("worker_boot.py"),
        ];
        let script_path = script_candidates
            .iter()
            .find(|p| p.is_file())
            .cloned()
            .unwrap_or_else(|| script_candidates[0].clone());
        if !script_path.is_file() {
            return Err(RpcCallError::Protocol(format!(
                "Worker bootstrapper not found: {}",
                script_path.display()
            )));
        }

        let python_bin = if let Some((bundled_py, _)) = &bundled_runtime {
            bundled_py.clone()
        } else {
            let from_code =
                resolve_python_executable(&code_root, config.python_executable.as_deref());
            if from_code != Path::new("python") {
                from_code
            } else {
                resolve_python_executable(
                    &config.workspace_root,
                    config.python_executable.as_deref(),
                )
            }
        };
        let raw_canonical_db = config
            .canonical_db_path
            .clone()
            .unwrap_or_else(|| config.workspace_root.join("database.db"));
        let resolved_canonical_db = if raw_canonical_db.exists() {
            dunce::canonicalize(&raw_canonical_db).unwrap_or(raw_canonical_db)
        } else if let (Some(parent), Some(name)) =
            (raw_canonical_db.parent(), raw_canonical_db.file_name())
        {
            let canon_parent = dunce::canonicalize(parent).unwrap_or_else(|_| parent.to_path_buf());
            canon_parent.join(name)
        } else {
            raw_canonical_db
        };
        let job = JobObject::with_default_memory_limit(config.max_memory_bytes)
            .map_err(RpcCallError::TransportClosed)?;
        let mut worker_env =
            build_worker_environment(role, &config.workspace_root, resolved_canonical_db.as_ref());
        worker_env.insert(
            "JARVIS_RESOURCE_ROOT".to_string(),
            code_root.to_string_lossy().into_owned(),
        );

        let path_sep = if cfg!(windows) { ";" } else { ":" };
        let mut python_path_entries = vec![code_root.to_string_lossy().into_owned()];
        if let Some(py_dir) = python_bin.parent() {
            let stdlib_dir = py_dir.join("Lib");
            let site_packages_dir = stdlib_dir.join("site-packages");
            let dlls_dir = py_dir.join("DLLs");
            if stdlib_dir.is_dir() {
                python_path_entries.push(stdlib_dir.to_string_lossy().into_owned());
            }
            if site_packages_dir.is_dir() {
                python_path_entries.push(site_packages_dir.to_string_lossy().into_owned());
            }
            if dlls_dir.is_dir() {
                python_path_entries.push(dlls_dir.to_string_lossy().into_owned());
            }
            if stdlib_dir.join("os.py").is_file() && !py_dir.join("pyvenv.cfg").is_file() {
                worker_env.insert(
                    "PYTHONHOME".to_string(),
                    py_dir.to_string_lossy().into_owned(),
                );
                worker_env.insert("PYTHONNOUSERSITE".to_string(), "1".to_string());
            }
        }
        worker_env.insert("PYTHONPATH".to_string(), python_path_entries.join(path_sep));

        let mut cmd = Command::new(&python_bin);
        cmd.env_clear()
            .arg("-u")
            .arg(&script_path)
            .arg("--worker")
            .arg(role.as_str())
            .current_dir(&config.workspace_root)
            .envs(&worker_env)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);

        #[cfg(windows)]
        {
            cmd.creation_flags(WORKER_CREATION_FLAGS);
        }

        let mut child = cmd.spawn().map_err(|err| {
            RpcCallError::TransportClosed(format!(
                "Failed to spawn {} worker via {}: {err}",
                role.as_str(),
                python_bin.display()
            ))
        })?;

        let pid = child.id().unwrap_or(0);

        #[cfg(windows)]
        {
            if let Some(raw_handle) = child.raw_handle() {
                job.assign_raw_handle(raw_handle)
                    .map_err(RpcCallError::TransportClosed)?;
            } else if pid > 0 {
                job.assign_pid(pid).map_err(RpcCallError::TransportClosed)?;
            }
        }

        let stdin = child.stdin.take().ok_or_else(|| {
            RpcCallError::TransportClosed("worker child missing piped stdin".into())
        })?;
        let stdout = child.stdout.take().ok_or_else(|| {
            RpcCallError::TransportClosed("worker child missing piped stdout".into())
        })?;
        let stderr = child.stderr.take().ok_or_else(|| {
            RpcCallError::TransportClosed("worker child missing piped stderr".into())
        })?;

        let stderr_lines = Arc::new(Mutex::new(VecDeque::with_capacity(MAX_STDERR_LINES)));
        let stderr_buf = Arc::clone(&stderr_lines);
        let role_name = role.as_str();
        let stderr_task = tokio::spawn(async move {
            let mut reader = BufReader::new(stderr).lines();
            while let Ok(Some(line)) = reader.next_line().await {
                eprintln!("[worker:{role_name}] {line}");
                let mut ring = stderr_buf.lock().await;
                if ring.len() >= MAX_STDERR_LINES {
                    ring.pop_front();
                }
                ring.push_back(line);
            }
        });

        let rpc = WorkerRpcClient::start(
            stdin,
            stdout,
            config.heartbeat_interval,
            config.heartbeat_timeout,
            reverse_handler,
        );

        let ready = match rpc.wait_ready(config.ready_timeout).await {
            Ok(info) => info,
            Err(err) => {
                stderr_task.abort();
                let _ = child.start_kill();
                return Err(err);
            }
        };

        let mut init_payload = match &config.init_params {
            Value::Object(map) => map.clone(),
            _ => serde_json::Map::new(),
        };
        init_payload.insert("role".into(), Value::String(role.as_str().into()));
        init_payload.insert(
            "workspace_root".into(),
            Value::String(config.workspace_root.to_string_lossy().into_owned()),
        );

        if let Err(err) = rpc
            .call(
                "worker.init",
                Value::Object(init_payload),
                config.ready_timeout,
            )
            .await
        {
            stderr_task.abort();
            let _ = child.start_kill();
            return Err(err);
        }

        Ok(Arc::new(Self {
            role,
            pid: if ready.pid > 0 { ready.pid } else { pid },
            capabilities: ready.capabilities,
            _job: job,
            rpc,
            child: Mutex::new(child),
            stderr_lines,
            stderr_task: Mutex::new(Some(stderr_task)),
        }))
    }

    pub fn rpc(&self) -> &WorkerRpcClient {
        &self.rpc
    }

    pub async fn is_alive(&self) -> bool {
        if self.rpc.health() != WorkerHealth::Healthy {
            return false;
        }
        let mut child = self.child.lock().await;
        matches!(child.try_wait(), Ok(None))
    }

    pub async fn recent_stderr(&self) -> Vec<String> {
        self.stderr_lines.lock().await.iter().cloned().collect()
    }

    pub async fn shutdown(&self, timeout: Duration) {
        let _ = self.rpc.graceful_shutdown(timeout).await;
        if let Some(handle) = self.stderr_task.lock().await.take() {
            handle.abort();
        }
        let mut child = self.child.lock().await;
        let _ = child.start_kill();
        let _ = tokio::time::timeout(Duration::from_millis(500), child.wait()).await;
    }
}

struct RoleSlot {
    worker: Mutex<Option<Arc<ManagedWorker>>>,
    restarts: AtomicU32,
    last_failure_at: Mutex<Option<Instant>>,
}

impl RoleSlot {
    fn new() -> Self {
        Self {
            worker: Mutex::new(None),
            restarts: AtomicU32::new(0),
            last_failure_at: Mutex::new(None),
        }
    }
}

/// Thread-safe supervisor coordinating the JARVIS OS specialized Python worker pool.
pub struct WorkerSupervisor {
    config: WorkerSupervisorConfig,
    slots: HashMap<WorkerPoolRole, Arc<RoleSlot>>,
    reverse_handler: Arc<RwLock<Option<ReverseRpcHandler>>>,
    active_pids: Arc<std::sync::RwLock<HashSet<u32>>>,
}

impl WorkerSupervisor {
    pub fn new(config: WorkerSupervisorConfig) -> Self {
        let mut slots = HashMap::new();
        for &role in WorkerPoolRole::all_roles() {
            slots.insert(role, Arc::new(RoleSlot::new()));
        }
        Self {
            config,
            slots,
            reverse_handler: Arc::new(RwLock::new(None)),
            active_pids: Arc::new(std::sync::RwLock::new(HashSet::new())),
        }
    }

    /// Returns currently tracked live Python worker PIDs without waiting on async slot locks.
    pub fn live_pids(&self) -> Vec<u32> {
        self.active_pids
            .read()
            .map(|guard| guard.iter().copied().collect())
            .unwrap_or_default()
    }

    pub fn config(&self) -> &WorkerSupervisorConfig {
        &self.config
    }

    /// Registers an asynchronous Reverse RPC handler (for example, HITL permission prompts).
    pub async fn set_reverse_handler(&self, handler: ReverseRpcHandler) {
        let mut guard = self.reverse_handler.write().await;
        *guard = Some(handler);
    }

    /// Clears the registered Reverse RPC handler (restoring fail-closed defaults).
    pub async fn clear_reverse_handler(&self) {
        let mut guard = self.reverse_handler.write().await;
        *guard = None;
    }

    /// Ensures a healthy worker process exists for `role`, respawning with exponential backoff
    /// if a previous instance exited or missed heartbeats.
    pub async fn ensure_worker(
        &self,
        role: WorkerPoolRole,
    ) -> Result<Arc<ManagedWorker>, RpcCallError> {
        let slot = self
            .slots
            .get(&role)
            .ok_or_else(|| RpcCallError::Protocol(format!("Unknown role {:?}", role)))?;

        let mut guard = slot.worker.lock().await;
        if let Some(existing) = guard.as_ref() {
            if existing.is_alive().await {
                return Ok(Arc::clone(existing));
            }
            existing.shutdown(self.config.shutdown_timeout).await;
            if let Ok(mut pids) = self.active_pids.write() {
                pids.remove(&existing.pid);
            }
            *guard = None;
            let failures = slot.restarts.fetch_add(1, Ordering::SeqCst) + 1;
            *slot.last_failure_at.lock().await = Some(Instant::now());
            if failures > self.config.max_restart_attempts {
                return Err(RpcCallError::TransportClosed(format!(
                    "worker `{}` exceeded max restart limit ({})",
                    role.as_str(),
                    self.config.max_restart_attempts
                )));
            }
        }

        let failures = slot.restarts.load(Ordering::SeqCst);
        if failures > 0 {
            if let Some(last_fail) = *slot.last_failure_at.lock().await {
                let exponent = (failures - 1).min(4);
                let backoff = self.config.base_backoff.saturating_mul(1u32 << exponent);
                let elapsed = last_fail.elapsed();
                if elapsed < backoff {
                    tokio::time::sleep(backoff - elapsed).await;
                }
            }
        }

        let worker =
            ManagedWorker::spawn(role, &self.config, Arc::clone(&self.reverse_handler)).await?;
        if worker.pid > 0 {
            if let Ok(mut pids) = self.active_pids.write() {
                pids.insert(worker.pid);
            }
        }
        *guard = Some(Arc::clone(&worker));
        Ok(worker)
    }

    /// Dispatches a unary RPC call to `role`, starting the worker lazily if needed.
    pub async fn call(
        &self,
        role: WorkerPoolRole,
        method: &str,
        params: Value,
        timeout: Duration,
    ) -> Result<Value, RpcCallError> {
        let worker = self.ensure_worker(role).await?;
        worker.rpc().call(method, params, timeout).await
    }

    /// Dispatches a streaming RPC call to `role` forwarding `stream.chunk` and `task.progress`.
    pub async fn call_streaming(
        &self,
        role: WorkerPoolRole,
        method: &str,
        params: Value,
        stream_tx: mpsc::Sender<WorkerStreamEvent>,
        timeout: Duration,
    ) -> Result<Value, RpcCallError> {
        let worker = self.ensure_worker(role).await?;
        worker
            .rpc()
            .call_streaming(method, params, stream_tx, timeout)
            .await
    }

    /// Starts a streaming RPC call returning `(request_id, stream_rx, response_future)`.
    pub async fn start_streaming(
        &self,
        role: WorkerPoolRole,
        method: &str,
        params: Value,
        timeout: Duration,
    ) -> Result<
        (
            String,
            mpsc::Receiver<WorkerStreamEvent>,
            Pin<Box<dyn Future<Output = Result<Value, RpcCallError>> + Send>>,
        ),
        RpcCallError,
    > {
        let worker = self.ensure_worker(role).await?;
        worker.rpc().start_streaming(method, params, timeout).await
    }

    /// Sends cooperative `task.cancel` to an active worker role.
    pub async fn cancel_task(
        &self,
        role: WorkerPoolRole,
        request_id: &str,
        reason: &str,
    ) -> Result<(), RpcCallError> {
        let Some(slot) = self.slots.get(&role) else {
            return Ok(());
        };
        let guard = slot.worker.lock().await;
        if let Some(worker) = guard.as_ref() {
            worker.rpc().cancel_task(request_id, reason).await?;
        }
        Ok(())
    }

    /// Returns a health snapshot across all managed worker slots.
    pub async fn status_snapshot(&self) -> Vec<WorkerStatusSnapshot> {
        let mut out = Vec::new();
        for &role in WorkerPoolRole::all_roles() {
            let Some(slot) = self.slots.get(&role) else {
                continue;
            };
            let restart_count = slot.restarts.load(Ordering::SeqCst);
            let worker_opt = slot.worker.lock().await.clone();
            if let Some(worker) = worker_opt {
                let alive = worker.is_alive().await;
                let hb = worker.rpc().heartbeat_snapshot().await;
                let health_str = match worker.rpc().health() {
                    WorkerHealth::Healthy => "healthy".to_string(),
                    WorkerHealth::Unhealthy(reason) => format!("unhealthy: {reason}"),
                };
                out.push(WorkerStatusSnapshot {
                    role,
                    running: alive,
                    pid: Some(worker.pid),
                    capabilities: worker.capabilities.clone(),
                    rss_memory_mb: hb.rss_memory_mb,
                    active_tasks: hb.active_tasks,
                    health: health_str,
                    restart_count,
                });
            } else {
                out.push(WorkerStatusSnapshot {
                    role,
                    running: false,
                    pid: None,
                    capabilities: Vec::new(),
                    rss_memory_mb: 0.0,
                    active_tasks: 0,
                    health: "stopped".to_string(),
                    restart_count,
                });
            }
        }
        out
    }

    /// Gracefully shuts down one worker slot and terminates its Job Object.
    pub async fn shutdown_role(&self, role: WorkerPoolRole) {
        let Some(slot) = self.slots.get(&role) else {
            return;
        };
        let worker_opt = slot.worker.lock().await.take();
        if let Some(worker) = worker_opt {
            if let Ok(mut pids) = self.active_pids.write() {
                pids.remove(&worker.pid);
            }
            worker.shutdown(self.config.shutdown_timeout).await;
        }
    }

    /// Gracefully shuts down all active workers and terminates their Job Objects.
    pub async fn shutdown_all(&self) {
        for &role in WorkerPoolRole::all_roles() {
            self.shutdown_role(role).await;
        }
    }

    /// Boots all four production worker roles (`ai`, `study`, `mission`, `voice`),
    /// verifies each role is responsive over JSON-RPC, and returns a JSON report
    /// with each role's PID and capabilities.
    pub async fn verify_and_boot_production_workers(&self) -> Result<Value, RpcCallError> {
        let mut roles_report = serde_json::Map::new();
        let mut spawned_pids = Vec::new();
        for &role in WorkerPoolRole::production_roles() {
            let worker = self.ensure_worker(role).await?;
            let hb = worker.rpc().heartbeat_snapshot().await;
            spawned_pids.push(worker.pid);
            roles_report.insert(
                role.as_str().to_string(),
                json!({
                    "pid": worker.pid,
                    "running": worker.is_alive().await,
                    "capabilities": worker.capabilities,
                    "capabilities_count": worker.capabilities.len(),
                    "rss_memory_mb": hb.rss_memory_mb,
                }),
            );
        }
        Ok(json!({
            "status": "verified",
            "workspace_root": self.config.workspace_root.to_string_lossy(),
            "resource_root": self
                .config
                .resource_root
                .as_ref()
                .map(|p| p.to_string_lossy().into_owned()),
            "spawned_pids": spawned_pids,
            "roles": roles_report,
        }))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_workspace_root() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .parent()
            .expect("src-tauri has repository root parent")
            .to_path_buf()
    }

    #[tokio::test]
    async fn supervisor_handles_echo_streaming_stdout_isolation_and_heartbeat() {
        let mut cfg = WorkerSupervisorConfig::for_workspace(test_workspace_root());
        cfg.heartbeat_interval = Duration::from_millis(80);
        cfg.heartbeat_timeout = Duration::from_secs(2);
        let supervisor = WorkerSupervisor::new(cfg);

        // 1. Unary echo + stray print() stdout isolation
        let res = supervisor
            .call(
                WorkerPoolRole::Echo,
                "worker.echo",
                json!({ "message": "ping-from-rust" }),
                Duration::from_secs(5),
            )
            .await
            .expect("unary worker.echo");
        assert_eq!(res["status"], "ok");
        assert_eq!(res["echo"], "ping-from-rust");

        // 2. Streaming echo chunks
        let (tx, mut rx) = mpsc::channel(32);
        let stream_res = supervisor
            .call_streaming(
                WorkerPoolRole::Echo,
                "worker.echo",
                json!({ "stream": true, "tokens": ["alpha ", "beta ", "gamma"] }),
                tx,
                Duration::from_secs(5),
            )
            .await
            .expect("streaming worker.echo");
        assert_eq!(stream_res["status"], "ok");

        let mut assembled = String::new();
        let mut saw_last = false;
        while let Ok(evt) = rx.try_recv() {
            if let WorkerStreamEvent::Chunk { delta, is_last, .. } = evt {
                assembled.push_str(&delta);
                if is_last {
                    saw_last = true;
                }
            }
        }
        assert_eq!(assembled, "alpha beta gamma");
        assert!(saw_last, "expected final chunk with is_last=true");

        // 3. Verify stray print() landed in stderr and heartbeat pong arrived cleanly
        tokio::time::sleep(Duration::from_millis(180)).await;
        let worker = supervisor
            .ensure_worker(WorkerPoolRole::Echo)
            .await
            .expect("worker healthy after heartbeat");
        let stderr = worker.recent_stderr().await;
        assert!(
            stderr.iter().any(|l| l.contains("[worker-echo-noise]")),
            "expected print() output redirected to stderr, got {stderr:?}"
        );
        assert_eq!(worker.rpc().health(), WorkerHealth::Healthy);

        supervisor.shutdown_all().await;
    }

    #[tokio::test]
    async fn supervisor_handles_reverse_rpc_non_blocking() {
        let mut cfg = WorkerSupervisorConfig::for_workspace(test_workspace_root());
        cfg.heartbeat_interval = Duration::from_millis(40);
        cfg.heartbeat_timeout = Duration::from_secs(2);
        let supervisor = WorkerSupervisor::new(cfg);

        supervisor
            .set_reverse_handler(Arc::new(|req| {
                Box::pin(async move {
                    assert_eq!(req.method, "permission.request_approval");
                    assert_eq!(req.params["action"], "fs.write");
                    // Delay longer than 2x heartbeat_interval to prove reader never blocks.
                    tokio::time::sleep(Duration::from_millis(120)).await;
                    Ok(json!({
                        "decision": "approved",
                        "grant_type": "allow_once",
                        "request_id": req.id,
                    }))
                })
            }))
            .await;

        let res = supervisor
            .call(
                WorkerPoolRole::Echo,
                "worker.echo",
                json!({
                    "require_approval": true,
                    "action": "fs.write",
                    "resource": "workspace/test.py",
                    "timeout_ms": 5000
                }),
                Duration::from_secs(5),
            )
            .await
            .expect("worker.echo with Reverse RPC approval");

        assert_eq!(res["status"], "completed");
        assert_eq!(res["decision"]["decision"], "approved");
        assert_eq!(res["decision"]["grant_type"], "allow_once");

        supervisor.shutdown_all().await;
    }

    #[tokio::test]
    async fn supervisor_cancels_tasks_and_recovers_from_worker_crash() {
        let mut cfg = WorkerSupervisorConfig::for_workspace(test_workspace_root());
        cfg.base_backoff = Duration::from_millis(20);
        cfg.heartbeat_interval = Duration::from_millis(100);
        cfg.heartbeat_timeout = Duration::from_secs(2);
        let supervisor = WorkerSupervisor::new(cfg);

        // 1. Start slow streaming task and cancel cooperatively on first progress event
        let (req_id, mut stream_rx, fut) = supervisor
            .start_streaming(
                WorkerPoolRole::Echo,
                "worker.echo",
                json!({ "sleep_ms": 2000 }),
                Duration::from_secs(5),
            )
            .await
            .expect("start_streaming");

        let evt = tokio::time::timeout(Duration::from_secs(3), stream_rx.recv())
            .await
            .expect("progress event arrive")
            .expect("stream channel open");
        assert!(matches!(evt, WorkerStreamEvent::Progress { .. }));

        supervisor
            .cancel_task(WorkerPoolRole::Echo, &req_id, "user_cancelled")
            .await
            .expect("send task.cancel");

        let cancel_res = fut.await.expect("cancelled task returns partial result");
        assert_eq!(cancel_res["status"], "cancelled");

        // 2. Kill running worker abruptly and confirm supervisor auto-restarts a fresh PID
        let worker_before = supervisor
            .ensure_worker(WorkerPoolRole::Echo)
            .await
            .expect("active worker before crash");
        let old_pid = worker_before.pid;
        {
            let mut child = worker_before.child.lock().await;
            let _ = child.kill().await;
        }
        tokio::time::sleep(Duration::from_millis(120)).await;

        let health_after = supervisor
            .call(
                WorkerPoolRole::Echo,
                "system.health",
                json!({}),
                Duration::from_secs(5),
            )
            .await
            .expect("supervisor respawns worker after crash");
        let new_pid = health_after["pid"].as_u64().expect("pid present") as u32;
        assert_eq!(health_after["status"], "healthy");
        assert_ne!(new_pid, old_pid);

        supervisor.shutdown_all().await;
    }

    #[tokio::test]
    async fn supervisor_routes_real_worker_sqlite_via_reverse_rpc_exclusively() {
        let temp_dir = tempfile::tempdir().expect("tempdir");
        let canon_db = temp_dir.path().join("database.db");
        let db = Arc::new(
            crate::storage::sqlite::SqliteDatabase::open(&canon_db).expect("open sqlite db"),
        );
        db.add_compounding_rule("RUST_OWNED_RULE", "desc", "Always route via Rust")
            .await
            .expect("seed rule");
        let permissions = Arc::new(crate::permissions::gateway::PermissionGateway::new(
            Duration::from_secs(30),
        ));

        let mut cfg = WorkerSupervisorConfig::for_workspace(test_workspace_root())
            .with_canonical_db_path(canon_db.clone());
        cfg.ready_timeout = Duration::from_secs(30);
        let supervisor = WorkerSupervisor::new(cfg);
        supervisor
            .set_reverse_handler(
                crate::workers::reverse_rpc::build_composite_reverse_rpc_handler(
                    Arc::clone(&db),
                    permissions,
                ),
            )
            .await;

        // Real production Knowledge worker triggers synchronous `database.get_compounding_rules()`
        // and `database.delete_compounding_rule()` inside its event loop thread, transparently
        // bridged over stdio Reverse-RPC to Rust's single-writer SqliteDatabase.
        let get_res = supervisor
            .call(
                WorkerPoolRole::Knowledge,
                "domain.dispatch",
                json!({ "message": { "type": "get_rules" } }),
                Duration::from_secs(30),
            )
            .await
            .expect("knowledge worker get_rules via reverse RPC");
        assert_eq!(get_res["status"], "ok");
        let events = get_res["events"].as_array().expect("events array");
        assert_eq!(events[0]["type"], "rules_list");
        assert_eq!(events[0]["rules"].as_array().unwrap().len(), 1);
        assert_eq!(events[0]["rules"][0]["rule_key"], "RUST_OWNED_RULE");

        let del_res = supervisor
            .call(
                WorkerPoolRole::Knowledge,
                "domain.dispatch",
                json!({ "message": { "type": "delete_rule", "key": "RUST_OWNED_RULE" } }),
                Duration::from_secs(15),
            )
            .await
            .expect("knowledge worker delete_rule via reverse RPC");
        assert_eq!(del_res["status"], "ok");
        assert!(db.get_compounding_rules().await.unwrap().is_empty());

        supervisor.shutdown_all().await;
    }

    #[test]
    fn worker_environment_scrubs_unallowlisted_secrets_and_defaults_memory_cap() {
        let workspace = PathBuf::from(r"C:\JarvisWorkspace");
        let db = PathBuf::from(r"C:\Users\demo\AppData\Local\JarvisOS\data\database.db");
        let cfg = WorkerSupervisorConfig::for_workspace(workspace.clone());
        assert_eq!(
            cfg.max_memory_bytes,
            Some(JobObject::DEFAULT_WORKER_MEMORY_LIMIT_BYTES)
        );

        let fake_parent = vec![
            ("PATH", r"C:\Windows\System32"),
            ("SYSTEMROOT", r"C:\Windows"),
            ("TEMP", r"C:\Temp"),
            ("VIRTUAL_ENV", r"C:\JarvisWorkspace\venv"),
            ("OLLAMA_MODEL", "qwen3.5:9b"),
            ("GEMINI_API_KEY", "gem-secret-123"),
            ("ANTHROPIC_API_KEY", "ant-secret-456"),
            ("GITHUB_TOKEN", "ghp_should_be_scrubbed"),
            ("AWS_SECRET_ACCESS_KEY", "aws_should_be_scrubbed"),
            ("JARVIS_HTTP_TOKEN", "loopback_master_token_never_inherited"),
            ("JARVIS_DB_WRITE_OWNER", "python"),
        ];

        // Echo receives only core OS/Python keys and forced Rust write-ownership vars
        let echo_env = build_worker_environment_from_iter(
            WorkerPoolRole::Echo,
            &workspace,
            &db,
            fake_parent.clone(),
        );
        assert_eq!(
            echo_env.get("SYSTEMROOT").map(String::as_str),
            Some(r"C:\Windows")
        );
        assert_eq!(
            echo_env.get("VIRTUAL_ENV").map(String::as_str),
            Some(r"C:\JarvisWorkspace\venv")
        );
        assert_eq!(
            echo_env.get("JARVIS_DB_WRITE_OWNER").map(String::as_str),
            Some("rust")
        );
        assert!(!echo_env.contains_key("GITHUB_TOKEN"));
        assert!(!echo_env.contains_key("AWS_SECRET_ACCESS_KEY"));
        assert!(!echo_env.contains_key("JARVIS_HTTP_TOKEN"));
        assert!(!echo_env.contains_key("GEMINI_API_KEY"));
        assert!(!echo_env.contains_key("OLLAMA_MODEL"));

        // Knowledge receives OLLAMA runtime vars without external LLM/cloud keys
        let know_env = build_worker_environment_from_iter(
            WorkerPoolRole::Knowledge,
            &workspace,
            &db,
            fake_parent.clone(),
        );
        assert_eq!(
            know_env.get("OLLAMA_MODEL").map(String::as_str),
            Some("qwen3.5:9b")
        );
        assert!(!know_env.contains_key("GEMINI_API_KEY"));
        assert!(!know_env.contains_key("GITHUB_TOKEN"));

        // AI receives allowlisted LLM keys while scrubbing GitHub/AWS/loopback secrets
        let ai_env =
            build_worker_environment_from_iter(WorkerPoolRole::Ai, &workspace, &db, fake_parent);
        assert_eq!(
            ai_env.get("GEMINI_API_KEY").map(String::as_str),
            Some("gem-secret-123")
        );
        assert_eq!(
            ai_env.get("ANTHROPIC_API_KEY").map(String::as_str),
            Some("ant-secret-456")
        );
        assert_eq!(
            ai_env.get("JARVIS_DB_WRITE_OWNER").map(String::as_str),
            Some("rust")
        );
        assert!(!ai_env.contains_key("GITHUB_TOKEN"));
        assert!(!ai_env.contains_key("AWS_SECRET_ACCESS_KEY"));
        assert!(!ai_env.contains_key("JARVIS_HTTP_TOKEN"));
    }
}

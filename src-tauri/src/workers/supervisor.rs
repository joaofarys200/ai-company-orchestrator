//! Supervised pool of specialized Python sidecar workers.
//!
//! Each worker role runs inside an isolated OS process assigned to a Windows Job Object,
//! boots `workers/worker_boot.py --worker <role>`, completes the `worker.ready` ->
//! `worker.init` handshake, maintains 5s/15s heartbeats, and auto-restarts with bounded
//! exponential backoff when crashed or unresponsive.

use std::collections::{HashMap, HashSet, VecDeque};
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
        &[
            Self::Ai,
            Self::Study,
            Self::Knowledge,
            Self::Mission,
            Self::Voice,
        ]
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
            python_executable: None,
            heartbeat_interval: Duration::from_secs(5),
            heartbeat_timeout: Duration::from_secs(15),
            ready_timeout: Duration::from_secs(15),
            shutdown_timeout: Duration::from_secs(2),
            max_memory_bytes: None,
            max_restart_attempts: 5,
            base_backoff: Duration::from_secs(1),
            init_params: json!({}),
        }
    }
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
            workspace_root.join("venv").join("Scripts").join("python.exe"),
            workspace_root.join(".venv").join("Scripts").join("python.exe"),
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

impl ManagedWorker {
    async fn spawn(
        role: WorkerPoolRole,
        config: &WorkerSupervisorConfig,
        reverse_handler: Arc<RwLock<Option<ReverseRpcHandler>>>,
    ) -> Result<Arc<Self>, RpcCallError> {
        let script_path = config.workspace_root.join("workers").join("worker_boot.py");
        if !script_path.is_file() {
            return Err(RpcCallError::Protocol(format!(
                "Worker bootstrapper not found: {}",
                script_path.display()
            )));
        }

        let python_bin =
            resolve_python_executable(&config.workspace_root, config.python_executable.as_deref());
        let job = JobObject::new(config.max_memory_bytes).map_err(RpcCallError::TransportClosed)?;

        let mut cmd = Command::new(&python_bin);
        cmd.arg("-u")
            .arg(&script_path)
            .arg("--worker")
            .arg(role.as_str())
            .current_dir(&config.workspace_root)
            .env("PYTHONUNBUFFERED", "1")
            .env("PYTHONIOENCODING", "utf-8")
            .env("PYTHONDONTWRITEBYTECODE", "1")
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
            .call("worker.init", Value::Object(init_payload), config.ready_timeout)
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

        let worker = ManagedWorker::spawn(
            role,
            &self.config,
            Arc::clone(&self.reverse_handler),
        )
        .await?;
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
}


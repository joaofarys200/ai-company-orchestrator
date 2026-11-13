//! Bidirectional NDJSON JSON-RPC 2.0 client over stdio pipes for Python workers.
//!
//! Guarantees:
//! - Strict 16 MiB frame ceiling on both ingress and egress.
//! - Bounded `mpsc(1024)` outbound write queue for explicit backpressure.
//! - Non-blocking stdout reader dispatching `stream.chunk`, `task.progress`, `system.pong`,
//!   and asynchronous `reverse_request` frames (such as `permission.request_approval`) on
//!   separate spawned tasks so heartbeat pongs never stall behind HITL UI approval waits.

use std::collections::HashMap;
use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::time::{Duration, Instant};

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::io::{AsyncBufReadExt, AsyncRead, AsyncWrite, AsyncWriteExt, BufReader};
use tokio::sync::{mpsc, oneshot, watch, Mutex, RwLock};
use tokio::task::JoinHandle;
use uuid::Uuid;

pub const PROTOCOL_VERSION: &str = "1.0.0";
pub const MAX_FRAME_BYTES: usize = 16 * 1024 * 1024;
pub const OUTBOUND_QUEUE_CAPACITY: usize = 1024;
pub const STREAM_QUEUE_CAPACITY: usize = 1024;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct WorkerReadyInfo {
    pub worker_type: String,
    pub pid: u32,
    pub version: String,
    pub capabilities: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct WorkerPongInfo {
    pub sequence: u64,
    pub rss_memory_mb: f64,
    pub active_tasks: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RpcRemoteError {
    pub code: i64,
    pub message: String,
    #[serde(default)]
    pub data: Option<Value>,
}

impl std::fmt::Display for RpcRemoteError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "RPC error {}: {}", self.code, self.message)
    }
}

impl std::error::Error for RpcRemoteError {}

#[derive(Debug, Clone)]
pub enum RpcCallError {
    TransportClosed(String),
    Timeout(String),
    Remote(RpcRemoteError),
    Protocol(String),
    QueueFull,
}

impl std::fmt::Display for RpcCallError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::TransportClosed(msg) => write!(f, "worker transport closed: {msg}"),
            Self::Timeout(msg) => write!(f, "worker RPC timeout: {msg}"),
            Self::Remote(err) => write!(f, "{err}"),
            Self::Protocol(msg) => write!(f, "worker protocol violation: {msg}"),
            Self::QueueFull => write!(f, "worker outbound RPC queue is full"),
        }
    }
}

impl std::error::Error for RpcCallError {}

#[derive(Debug, Clone, Serialize, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum WorkerStreamEvent {
    Chunk {
        request_id: String,
        sequence: u64,
        delta: String,
        is_last: bool,
    },
    Progress {
        request_id: String,
        stage: String,
        progress: f64,
        message: String,
        eta_seconds: Option<f64>,
    },
}

#[derive(Debug, Clone)]
pub struct ReverseRequest {
    pub id: String,
    pub method: String,
    pub params: Value,
}

pub type ReverseRpcFuture =
    Pin<Box<dyn Future<Output = Result<Value, RpcRemoteError>> + Send>>;
pub type ReverseRpcHandler = Arc<dyn Fn(ReverseRequest) -> ReverseRpcFuture + Send + Sync>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WorkerHealth {
    Healthy,
    Unhealthy(String),
}

struct PendingCall {
    resp_tx: oneshot::Sender<Result<Value, RpcRemoteError>>,
    stream_tx: Option<mpsc::Sender<WorkerStreamEvent>>,
}

#[derive(Debug)]
struct HeartbeatState {
    next_seq: u64,
    last_pong_seq: u64,
    last_pong_at: Instant,
    missed_pings: u32,
    rss_memory_mb: f64,
    active_tasks: usize,
}

impl HeartbeatState {
    fn new() -> Self {
        Self {
            next_seq: 1,
            last_pong_seq: 0,
            last_pong_at: Instant::now(),
            missed_pings: 0,
            rss_memory_mb: 0.0,
            active_tasks: 0,
        }
    }
}

#[derive(Debug, Clone)]
pub struct HeartbeatSnapshot {
    pub rss_memory_mb: f64,
    pub active_tasks: usize,
    pub missed_pings: u32,
}

/// Active JSON-RPC 2.0 client bound to one worker process's stdio pipes.
pub struct WorkerRpcClient {
    writer_tx: mpsc::Sender<String>,
    pending: Arc<Mutex<HashMap<String, PendingCall>>>,
    ready_rx: Mutex<Option<oneshot::Receiver<WorkerReadyInfo>>>,
    heartbeat_state: Arc<Mutex<HeartbeatState>>,
    health_tx: watch::Sender<WorkerHealth>,
    health_rx: watch::Receiver<WorkerHealth>,
    tasks: Mutex<Vec<JoinHandle<()>>>,
}

impl WorkerRpcClient {
    /// Connects the RPC client to piped worker `stdin` and `stdout` handles.
    pub fn start<W, R>(
        mut stdin: W,
        stdout: R,
        heartbeat_interval: Duration,
        heartbeat_timeout: Duration,
        reverse_handler: Arc<RwLock<Option<ReverseRpcHandler>>>,
    ) -> Self
    where
        W: AsyncWrite + Unpin + Send + 'static,
        R: AsyncRead + Unpin + Send + 'static,
    {
        let (writer_tx, mut writer_rx) = mpsc::channel::<String>(OUTBOUND_QUEUE_CAPACITY);
        let pending: Arc<Mutex<HashMap<String, PendingCall>>> =
            Arc::new(Mutex::new(HashMap::new()));
        let (ready_tx, ready_rx) = oneshot::channel::<WorkerReadyInfo>();
        let heartbeat_state = Arc::new(Mutex::new(HeartbeatState::new()));
        let (health_tx, health_rx) = watch::channel(WorkerHealth::Healthy);

        // Writer task drains bounded queue to child stdin sequentially.
        let writer_health_tx = health_tx.clone();
        let writer_handle = tokio::spawn(async move {
            while let Some(line) = writer_rx.recv().await {
                if let Err(err) = stdin.write_all(line.as_bytes()).await {
                    let _ = writer_health_tx.send(WorkerHealth::Unhealthy(format!(
                        "worker stdin write failed: {err}"
                    )));
                    break;
                }
                if let Err(err) = stdin.flush().await {
                    let _ = writer_health_tx.send(WorkerHealth::Unhealthy(format!(
                        "worker stdin flush failed: {err}"
                    )));
                    break;
                }
            }
        });

        // Reader task consumes bounded NDJSON lines from child stdout without blocking.
        let reader_pending = Arc::clone(&pending);
        let reader_hb = Arc::clone(&heartbeat_state);
        let reader_health_tx = health_tx.clone();
        let reader_writer_tx = writer_tx.clone();
        let reader_handle = tokio::spawn(async move {
            let mut reader = BufReader::with_capacity(64 * 1024, stdout);
            let mut ready_slot = Some(ready_tx);

            loop {
                match read_bounded_ndjson_line(&mut reader, MAX_FRAME_BYTES).await {
                    Ok(Some(line)) => {
                        let trimmed = line.trim();
                        if trimmed.is_empty() {
                            continue;
                        }
                        let Ok(frame) = serde_json::from_str::<Value>(trimmed) else {
                            continue;
                        };
                        dispatch_inbound_frame(
                            frame,
                            &mut ready_slot,
                            &reader_pending,
                            &reader_hb,
                            &reverse_handler,
                            &reader_writer_tx,
                        )
                        .await;
                    }
                    Ok(None) => {
                        let _ = reader_health_tx
                            .send(WorkerHealth::Unhealthy("worker stdout closed (EOF)".into()));
                        break;
                    }
                    Err(err) => {
                        let _ = reader_health_tx.send(WorkerHealth::Unhealthy(format!(
                            "worker stdout read error: {err}"
                        )));
                        break;
                    }
                }
            }

            // Fail any in-flight callers promptly so they don't hang until full RPC timeout.
            let mut guard = reader_pending.lock().await;
            for (_, call) in guard.drain() {
                let _ = call.resp_tx.send(Err(RpcRemoteError {
                    code: -32002,
                    message: "Worker process exited before completing request".to_string(),
                    data: None,
                }));
            }
        });

        // Heartbeat task sends periodic system.ping frames and detects 3 consecutive misses.
        let hb_writer_tx = writer_tx.clone();
        let hb_state = Arc::clone(&heartbeat_state);
        let hb_health_tx = health_tx.clone();
        let mut hb_health_watch = health_rx.clone();
        let hb_handle = tokio::spawn(async move {
            let interval = heartbeat_interval.max(Duration::from_millis(25));
            let mut ticker = tokio::time::interval(interval);
            ticker.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Delay);
            // Skip immediate first tick at t=0 so startup has one interval before checking misses.
            ticker.tick().await;

            loop {
                tokio::select! {
                    _ = hb_health_watch.changed() => {
                        if !matches!(*hb_health_watch.borrow(), WorkerHealth::Healthy) {
                            break;
                        }
                    }
                    _ = ticker.tick() => {
                        let seq = {
                            let mut st = hb_state.lock().await;
                            // Wait until worker finished initial boot (`ready`) or first pong window starts.
                            if st.next_seq > 1 && st.last_pong_seq + 1 < st.next_seq {
                                st.missed_pings += 1;
                                if st.missed_pings >= 3 && st.last_pong_at.elapsed() >= heartbeat_timeout {
                                    let _ = hb_health_tx.send(WorkerHealth::Unhealthy(format!(
                                        "worker missed {} heartbeats (last pong {:?} ago)",
                                        st.missed_pings,
                                        st.last_pong_at.elapsed()
                                    )));
                                    break;
                                }
                            }
                            let seq = st.next_seq;
                            st.next_seq += 1;
                            seq
                        };

                        let ping = build_envelope(json!({
                            "method": "system.ping",
                            "params": { "sequence": seq },
                        }));
                        if let Ok(line) = encode_ndjson_line(&ping) {
                            if hb_writer_tx.try_send(line).is_err() {
                                let _ = hb_health_tx.send(WorkerHealth::Unhealthy(
                                    "worker outbound queue closed or saturated during heartbeat"
                                        .into(),
                                ));
                                break;
                            }
                        }
                    }
                }
            }
        });

        Self {
            writer_tx,
            pending,
            ready_rx: Mutex::new(Some(ready_rx)),
            heartbeat_state,
            health_tx,
            health_rx,
            tasks: Mutex::new(vec![writer_handle, reader_handle, hb_handle]),
        }
    }

    /// Waits for the initial `worker.ready` frame emitted on startup.
    pub async fn wait_ready(&self, timeout: Duration) -> Result<WorkerReadyInfo, RpcCallError> {
        let rx = self
            .ready_rx
            .lock()
            .await
            .take()
            .ok_or_else(|| RpcCallError::Protocol("wait_ready called more than once".into()))?;

        match tokio::time::timeout(timeout, rx).await {
            Ok(Ok(info)) => {
                // Reset heartbeat baseline now that Python finished booting and stdio is open.
                let mut st = self.heartbeat_state.lock().await;
                st.last_pong_at = Instant::now();
                st.missed_pings = 0;
                Ok(info)
            }
            Ok(Err(_)) => Err(RpcCallError::TransportClosed(
                "worker exited before emitting worker.ready".into(),
            )),
            Err(_) => Err(RpcCallError::Timeout(
                "timed out waiting for worker.ready banner".into(),
            )),
        }
    }

    /// Sends a unary JSON-RPC request and awaits its response within `timeout`.
    pub async fn call(
        &self,
        method: &str,
        params: Value,
        timeout: Duration,
    ) -> Result<Value, RpcCallError> {
        self.call_internal(method, params, None, timeout).await
    }

    /// Sends a streaming JSON-RPC request (`stream.chunk` + `task.progress`) with a caller channel.
    pub async fn call_streaming(
        &self,
        method: &str,
        params: Value,
        stream_tx: mpsc::Sender<WorkerStreamEvent>,
        timeout: Duration,
    ) -> Result<Value, RpcCallError> {
        self.call_internal(method, params, Some(stream_tx), timeout)
            .await
    }

    /// Starts a streaming RPC call and returns `(request_id, stream_rx, response_future)`.
    /// Useful when the caller needs `request_id` immediately for cooperative cancellation.
    pub async fn start_streaming(
        &self,
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
        let request_id = format!("req-{}", Uuid::new_v4());
        let (resp_tx, resp_rx) = oneshot::channel();
        let (stream_tx, stream_rx) = mpsc::channel(STREAM_QUEUE_CAPACITY);

        {
            let mut guard = self.pending.lock().await;
            guard.insert(
                request_id.clone(),
                PendingCall {
                    resp_tx,
                    stream_tx: Some(stream_tx),
                },
            );
        }

        let payload = build_envelope(json!({
            "id": request_id,
            "method": method,
            "params": params,
        }));
        let line = encode_ndjson_line(&payload)?;
        if let Err(err) = self.writer_tx.try_send(line) {
            self.pending.lock().await.remove(&request_id);
            return Err(match err {
                mpsc::error::TrySendError::Full(_) => RpcCallError::QueueFull,
                mpsc::error::TrySendError::Closed(_) => {
                    RpcCallError::TransportClosed("worker outbound writer closed".into())
                }
            });
        }

        let pending = Arc::clone(&self.pending);
        let req_id_for_cleanup = request_id.clone();
        let fut = Box::pin(async move {
            match tokio::time::timeout(timeout, resp_rx).await {
                Ok(Ok(Ok(val))) => Ok(val),
                Ok(Ok(Err(remote))) => Err(RpcCallError::Remote(remote)),
                Ok(Err(_)) => Err(RpcCallError::TransportClosed(
                    "response channel dropped".into(),
                )),
                Err(_) => {
                    pending.lock().await.remove(&req_id_for_cleanup);
                    Err(RpcCallError::Timeout(format!(
                        "request {req_id_for_cleanup} exceeded {:?}",
                        timeout
                    )))
                }
            }
        });

        Ok((request_id, stream_rx, fut))
    }

    async fn call_internal(
        &self,
        method: &str,
        params: Value,
        stream_tx: Option<mpsc::Sender<WorkerStreamEvent>>,
        timeout: Duration,
    ) -> Result<Value, RpcCallError> {
        let request_id = format!("req-{}", Uuid::new_v4());
        let (resp_tx, resp_rx) = oneshot::channel();

        {
            let mut guard = self.pending.lock().await;
            guard.insert(
                request_id.clone(),
                PendingCall { resp_tx, stream_tx },
            );
        }

        let payload = build_envelope(json!({
            "id": request_id,
            "method": method,
            "params": params,
        }));
        let line = encode_ndjson_line(&payload)?;
        if let Err(err) = self.writer_tx.try_send(line) {
            self.pending.lock().await.remove(&request_id);
            return Err(match err {
                mpsc::error::TrySendError::Full(_) => RpcCallError::QueueFull,
                mpsc::error::TrySendError::Closed(_) => {
                    RpcCallError::TransportClosed("worker outbound writer closed".into())
                }
            });
        }

        match tokio::time::timeout(timeout, resp_rx).await {
            Ok(Ok(Ok(val))) => Ok(val),
            Ok(Ok(Err(remote))) => Err(RpcCallError::Remote(remote)),
            Ok(Err(_)) => Err(RpcCallError::TransportClosed(
                "response channel dropped".into(),
            )),
            Err(_) => {
                self.pending.lock().await.remove(&request_id);
                Err(RpcCallError::Timeout(format!(
                    "RPC method `{method}` timed out after {:?}",
                    timeout
                )))
            }
        }
    }

    /// Sends a cooperative cancellation notification (`task.cancel`) for an active request.
    pub async fn cancel_task(&self, request_id: &str, reason: &str) -> Result<(), RpcCallError> {
        let frame = build_envelope(json!({
            "method": "task.cancel",
            "params": {
                "request_id": request_id,
                "reason": reason,
            }
        }));
        let line = encode_ndjson_line(&frame)?;
        self.writer_tx.send(line).await.map_err(|_| {
            RpcCallError::TransportClosed("worker outbound writer closed".into())
        })
    }

    /// Attempts a graceful `worker.shutdown` RPC before process termination.
    pub async fn graceful_shutdown(&self, timeout: Duration) -> Result<(), RpcCallError> {
        let request_id = format!("shutdown-{}", Uuid::new_v4());
        let (resp_tx, resp_rx) = oneshot::channel();
        self.pending.lock().await.insert(
            request_id.clone(),
            PendingCall {
                resp_tx,
                stream_tx: None,
            },
        );
        let frame = build_envelope(json!({
            "id": request_id,
            "method": "worker.shutdown",
            "params": {},
        }));
        if let Ok(line) = encode_ndjson_line(&frame) {
            let _ = self.writer_tx.try_send(line);
        }
        let _ = tokio::time::timeout(timeout, resp_rx).await;
        self.abort_background_tasks().await;
        Ok(())
    }

    pub fn health(&self) -> WorkerHealth {
        self.health_rx.borrow().clone()
    }

    pub fn subscribe_health(&self) -> watch::Receiver<WorkerHealth> {
        self.health_rx.clone()
    }

    pub async fn heartbeat_snapshot(&self) -> HeartbeatSnapshot {
        let st = self.heartbeat_state.lock().await;
        HeartbeatSnapshot {
            rss_memory_mb: st.rss_memory_mb,
            active_tasks: st.active_tasks,
            missed_pings: st.missed_pings,
        }
    }

    pub async fn abort_background_tasks(&self) {
        let mut tasks = self.tasks.lock().await;
        for handle in tasks.drain(..) {
            handle.abort();
        }
    }
}

impl Drop for WorkerRpcClient {
    fn drop(&mut self) {
        if let Ok(mut tasks) = self.tasks.try_lock() {
            for handle in tasks.drain(..) {
                handle.abort();
            }
        }
        let _ = self
            .health_tx
            .send(WorkerHealth::Unhealthy("rpc client dropped".into()));
    }
}

fn build_envelope(mut payload: Value) -> Value {
    if let Some(obj) = payload.as_object_mut() {
        obj.insert("jsonrpc".into(), Value::String("2.0".into()));
        obj.insert("protocol_version".into(), Value::String(PROTOCOL_VERSION.into()));
        obj.insert(
            "timestamp".into(),
            Value::Number(serde_json::Number::from(
                chrono::Utc::now().timestamp_millis(),
            )),
        );
    }
    payload
}

fn encode_ndjson_line(payload: &Value) -> Result<String, RpcCallError> {
    let mut encoded = serde_json::to_string(payload)
        .map_err(|e| RpcCallError::Protocol(format!("JSON encode failed: {e}")))?;
    if encoded.len() + 1 > MAX_FRAME_BYTES {
        return Err(RpcCallError::Protocol(format!(
            "outbound frame size {} exceeds {MAX_FRAME_BYTES} byte limit",
            encoded.len() + 1
        )));
    }
    encoded.push('\n');
    Ok(encoded)
}

async fn read_bounded_ndjson_line<R: AsyncRead + Unpin>(
    reader: &mut BufReader<R>,
    max_bytes: usize,
) -> std::io::Result<Option<String>> {
    let mut buf = Vec::new();
    loop {
        let available = reader.fill_buf().await?;
        if available.is_empty() {
            if buf.is_empty() {
                return Ok(None);
            }
            let text = String::from_utf8_lossy(&buf).into_owned();
            return Ok(Some(text));
        }

        if let Some(nl_pos) = available.iter().position(|&b| b == b'\n') {
            let chunk_len = nl_pos + 1;
            if buf.len() + chunk_len > max_bytes {
                reader.consume(chunk_len);
                return Err(std::io::Error::new(
                    std::io::ErrorKind::InvalidData,
                    "NDJSON line exceeds MAX_FRAME_BYTES",
                ));
            }
            buf.extend_from_slice(&available[..chunk_len]);
            reader.consume(chunk_len);
            let text = String::from_utf8_lossy(&buf).into_owned();
            return Ok(Some(text));
        }

        if buf.len() + available.len() > max_bytes {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "unterminated NDJSON frame exceeds MAX_FRAME_BYTES",
            ));
        }
        buf.extend_from_slice(available);
        let len = available.len();
        reader.consume(len);
    }
}

async fn dispatch_inbound_frame(
    frame: Value,
    ready_slot: &mut Option<oneshot::Sender<WorkerReadyInfo>>,
    pending: &Arc<Mutex<HashMap<String, PendingCall>>>,
    heartbeat_state: &Arc<Mutex<HeartbeatState>>,
    reverse_handler: &Arc<RwLock<Option<ReverseRpcHandler>>>,
    writer_tx: &mpsc::Sender<String>,
) {
    // 1. Reverse RPC requests MUST be spawned asynchronously so the reader keeps draining
    // heartbeats and other responses while waiting on HITL approval or other slow operations.
    if frame.get("type").and_then(Value::as_str) == Some("reverse_request") {
        let Some(rev_id) = frame.get("id").and_then(Value::as_str).map(ToOwned::to_owned) else {
            return;
        };
        let Some(method) = frame
            .get("method")
            .and_then(Value::as_str)
            .map(ToOwned::to_owned)
        else {
            return;
        };
        let params = frame.get("params").cloned().unwrap_or_else(|| json!({}));
        let handler_opt = reverse_handler.read().await.clone();
        let reply_tx = writer_tx.clone();

        tokio::spawn(async move {
            let outcome = match handler_opt {
                Some(handler) => handler(ReverseRequest {
                    id: rev_id.clone(),
                    method,
                    params,
                })
                .await,
                None => Err(RpcRemoteError {
                    code: -32003,
                    message: "Reverse RPC denied: no approval handler registered (fail-closed)"
                        .to_string(),
                    data: None,
                }),
            };

            let reply = match outcome {
                Ok(result) => build_envelope(json!({
                    "id": rev_id,
                    "type": "reverse_response",
                    "result": result,
                })),
                Err(err) => build_envelope(json!({
                    "id": rev_id,
                    "type": "reverse_response",
                    "error": err,
                })),
            };

            if let Ok(line) = encode_ndjson_line(&reply) {
                let _ = reply_tx.send(line).await;
            }
        });
        return;
    }

    // 2. Final unary / streaming RPC responses.
    if let Some(id) = frame.get("id").and_then(Value::as_str) {
        if frame.get("result").is_some() || frame.get("error").is_some() {
            if let Some(call) = pending.lock().await.remove(id) {
                let outcome = if let Some(err_val) = frame.get("error") {
                    let parsed = serde_json::from_value::<RpcRemoteError>(err_val.clone())
                        .unwrap_or_else(|_| RpcRemoteError {
                            code: -32603,
                            message: err_val.to_string(),
                            data: None,
                        });
                    Err(parsed)
                } else {
                    Ok(frame.get("result").cloned().unwrap_or(Value::Null))
                };
                let _ = call.resp_tx.send(outcome);
            }
            return;
        }
    }

    // 3. Notifications (`worker.ready`, `system.pong`, `stream.chunk`, `task.progress`).
    let Some(method) = frame.get("method").and_then(Value::as_str) else {
        return;
    };
    let params = frame.get("params").cloned().unwrap_or_else(|| json!({}));

    match method {
        "worker.ready" => {
            if let Some(tx) = ready_slot.take() {
                if let Ok(info) = serde_json::from_value::<WorkerReadyInfo>(params) {
                    let _ = tx.send(info);
                }
            }
        }
        "system.pong" => {
            if let Ok(pong) = serde_json::from_value::<WorkerPongInfo>(params) {
                let mut st = heartbeat_state.lock().await;
                if pong.sequence >= st.last_pong_seq {
                    st.last_pong_seq = pong.sequence;
                }
                st.last_pong_at = Instant::now();
                st.missed_pings = 0;
                st.rss_memory_mb = pong.rss_memory_mb;
                st.active_tasks = pong.active_tasks;
            }
        }
        "stream.chunk" => {
            let Some(req_id) = params.get("request_id").and_then(Value::as_str) else {
                return;
            };
            let seq = params.get("sequence").and_then(Value::as_u64).unwrap_or(0);
            let delta = params
                .get("delta")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let is_last = params
                .get("is_last")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            let guard = pending.lock().await;
            if let Some(call) = guard.get(req_id) {
                if let Some(tx) = &call.stream_tx {
                    let _ = tx.try_send(WorkerStreamEvent::Chunk {
                        request_id: req_id.to_string(),
                        sequence: seq,
                        delta,
                        is_last,
                    });
                }
            }
        }
        "task.progress" => {
            let Some(req_id) = params.get("request_id").and_then(Value::as_str) else {
                return;
            };
            let stage = params
                .get("stage")
                .and_then(Value::as_str)
                .unwrap_or("running")
                .to_string();
            let progress = params
                .get("progress")
                .and_then(Value::as_f64)
                .unwrap_or(0.0);
            let message = params
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let eta_seconds = params.get("eta_seconds").and_then(Value::as_f64);
            let guard = pending.lock().await;
            if let Some(call) = guard.get(req_id) {
                if let Some(tx) = &call.stream_tx {
                    let _ = tx.try_send(WorkerStreamEvent::Progress {
                        request_id: req_id.to_string(),
                        stage,
                        progress,
                        message,
                        eta_seconds,
                    });
                }
            }
        }
        _ => {}
    }
}


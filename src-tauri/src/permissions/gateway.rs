//! Fail-closed HITL Permission Gateway coordinating 300s TTL approvals and Worker Reverse RPC.

use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use std::time::{Duration, Instant};

use chrono::{SecondsFormat, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use tokio::sync::{oneshot, Mutex};
use uuid::Uuid;

use crate::permissions::policy::{
    evaluate_permission_policy, PermissionRequestStatus,
};
use crate::workers::rpc_client::{ReverseRpcHandler, RpcRemoteError};

pub const DEFAULT_PERMISSION_TTL: Duration = Duration::from_secs(300);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PermissionRequestRecord {
    pub request_id: String,
    pub tool_name: String,
    pub requested_operation: String,
    pub reason: String,
    pub risk_level: String,
    pub affected_resources: Vec<String>,
    pub mission_id: Option<String>,
    pub project_id: Option<String>,
    pub agent_id: Option<String>,
    pub status: PermissionRequestStatus,
    pub policy_reason: String,
    pub decided_by: Option<String>,
    pub created_at: String,
    pub expires_in_ms: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditLogEntry {
    pub timestamp: String,
    pub request_id: String,
    pub event_type: String,
    pub tool_name: String,
    pub risk_level: String,
    pub decision: Option<String>,
    pub details: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct PermissionDecision {
    pub decision: String, // "approved" | "denied"
    pub grant_type: String,
    pub request_id: String,
    pub reason: String,
}

pub type PermissionPromptNotifier = Arc<dyn Fn(&PermissionRequestRecord) + Send + Sync>;

struct ActivePending {
    record: PermissionRequestRecord,
    deadline: Instant,
    waiter: Option<oneshot::Sender<PermissionDecision>>,
}

struct GatewayState {
    requests: HashMap<String, ActivePending>,
    audit_log: VecDeque<AuditLogEntry>,
    notifier: Option<PermissionPromptNotifier>,
}

/// Thread-safe, fail-closed Human-in-the-Loop permission gateway.
#[derive(Clone)]
pub struct PermissionGateway {
    default_ttl: Duration,
    state: Arc<Mutex<GatewayState>>,
}

impl PermissionGateway {
    pub fn new(default_ttl: Duration) -> Self {
        Self {
            default_ttl: default_ttl.max(Duration::from_millis(25)),
            state: Arc::new(Mutex::new(GatewayState {
                requests: HashMap::new(),
                audit_log: VecDeque::with_capacity(512),
                notifier: None,
            })),
        }
    }

    pub async fn set_notifier(&self, notifier: PermissionPromptNotifier) {
        self.state.lock().await.notifier = Some(notifier);
    }

    /// Creates a tracked permission request according to fail-closed policy evaluation.
    pub async fn create_request(
        &self,
        tool_name: impl Into<String>,
        requested_operation: impl Into<String>,
        reason: impl Into<String>,
        risk_level: impl Into<String>,
        affected_resources: Vec<String>,
        mission_id: Option<String>,
        project_id: Option<String>,
        agent_id: Option<String>,
        ttl_override: Option<Duration>,
    ) -> Result<(PermissionRequestRecord, Option<oneshot::Receiver<PermissionDecision>>), String> {
        let tool_name = tool_name.into();
        let requested_operation = requested_operation.into();
        let reason = reason.into();
        let risk_level = risk_level.into();

        let eval = evaluate_permission_policy(&tool_name, &requested_operation, &risk_level);
        let ttl = ttl_override
            .map(|d| d.min(self.default_ttl).max(Duration::from_millis(20)))
            .unwrap_or(self.default_ttl);
        let request_id = format!("perm-{}", Uuid::new_v4().simple());
        let now = Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true);

        let record = PermissionRequestRecord {
            request_id: request_id.clone(),
            tool_name: tool_name.clone(),
            requested_operation: requested_operation.clone(),
            reason,
            risk_level: risk_level.clone(),
            affected_resources,
            mission_id,
            project_id,
            agent_id,
            status: eval.initial_status,
            policy_reason: eval.reason.clone(),
            decided_by: None,
            created_at: now.clone(),
            expires_in_ms: ttl.as_millis() as u64,
        };

        let mut guard = self.state.lock().await;
        push_audit(
            &mut guard.audit_log,
            AuditLogEntry {
                timestamp: now,
                request_id: request_id.clone(),
                event_type: if eval.is_blocked_by_policy {
                    "BLOCKED_BY_POLICY".into()
                } else if eval.is_auto_permitted {
                    "AUTO_PERMITTED".into()
                } else {
                    "REQUEST_CREATED".into()
                },
                tool_name,
                risk_level,
                decision: None,
                details: eval.reason.clone(),
            },
        );

        if eval.is_blocked_by_policy {
            guard.requests.insert(
                request_id,
                ActivePending {
                    record: record.clone(),
                    deadline: Instant::now() + ttl,
                    waiter: None,
                },
            );
            return Err(format!("PERMISSION_BLOCKED_BY_POLICY: {}", eval.reason));
        }

        if eval.is_auto_permitted {
            guard.requests.insert(
                request_id,
                ActivePending {
                    record: record.clone(),
                    deadline: Instant::now() + ttl,
                    waiter: None,
                },
            );
            return Ok((record, None));
        }

        let (tx, rx) = oneshot::channel();
        if let Some(cb) = &guard.notifier {
            cb(&record);
        }
        guard.requests.insert(
            request_id,
            ActivePending {
                record: record.clone(),
                deadline: Instant::now() + ttl,
                waiter: Some(tx),
            },
        );

        Ok((record, Some(rx)))
    }

    /// Resolves an explicit human approval, validating scope isolation and TTL expiry.
    pub async fn approve_request(
        &self,
        request_id: &str,
        decided_by: &str,
        grant_type: &str,
        expected_project_id: Option<&str>,
        expected_mission_id: Option<&str>,
    ) -> Result<PermissionRequestRecord, String> {
        self.resolve_decision(
            request_id,
            true,
            decided_by,
            grant_type,
            "Approved by operator",
            expected_project_id,
            expected_mission_id,
        )
        .await
    }

    /// Denies an active permission request.
    pub async fn deny_request(
        &self,
        request_id: &str,
        decided_by: &str,
        reason: &str,
        expected_project_id: Option<&str>,
        expected_mission_id: Option<&str>,
    ) -> Result<PermissionRequestRecord, String> {
        self.resolve_decision(
            request_id,
            false,
            decided_by,
            "denied",
            reason,
            expected_project_id,
            expected_mission_id,
        )
        .await
    }

    #[allow(clippy::too_many_arguments)]
    async fn resolve_decision(
        &self,
        request_id: &str,
        approved: bool,
        decided_by: &str,
        grant_type: &str,
        reason: &str,
        expected_project_id: Option<&str>,
        expected_mission_id: Option<&str>,
    ) -> Result<PermissionRequestRecord, String> {
        let mut guard = self.state.lock().await;
        let Some(entry) = guard.requests.get_mut(request_id) else {
            return Err(format!("PERMISSION_NOT_FOUND: {request_id}"));
        };

        if let Some(bound_proj) = entry.record.project_id.as_deref() {
            if expected_project_id != Some(bound_proj) {
                return Err(format!(
                    "CROSS_PROJECT_APPROVAL_DENIED: request belongs to project `{bound_proj}`"
                ));
            }
        }
        if let Some(bound_mission) = entry.record.mission_id.as_deref() {
            if expected_mission_id != Some(bound_mission) {
                return Err(format!(
                    "CROSS_MISSION_APPROVAL_DENIED: request belongs to mission `{bound_mission}`"
                ));
            }
        }

        if entry.record.status != PermissionRequestStatus::WaitingForUser {
            return Err(format!(
                "INVALID_APPROVAL_STATE: request `{request_id}` is already {:?}",
                entry.record.status
            ));
        }

        if Instant::now() > entry.deadline {
            entry.record.status = PermissionRequestStatus::Expired;
            let expired_waiter = entry.waiter.take();
            let snapshot = entry.record.clone();
            if let Some(tx) = expired_waiter {
                let _ = tx.send(PermissionDecision {
                    decision: "denied".to_string(),
                    grant_type: "expired".to_string(),
                    request_id: request_id.to_string(),
                    reason: "Permission approval TTL expired (fail-closed)".to_string(),
                });
            }
            push_audit(
                &mut guard.audit_log,
                AuditLogEntry {
                    timestamp: Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true),
                    request_id: request_id.to_string(),
                    event_type: "EXPIRED".to_string(),
                    tool_name: snapshot.tool_name.clone(),
                    risk_level: snapshot.risk_level.clone(),
                    decision: Some("denied".to_string()),
                    details: "TTL elapsed before human decision".to_string(),
                },
            );
            return Err(format!("PERMISSION_EXPIRED: {request_id}"));
        }

        entry.record.status = if approved {
            PermissionRequestStatus::Approved
        } else {
            PermissionRequestStatus::Denied
        };
        entry.record.decided_by = Some(decided_by.to_string());
        let waiter = entry.waiter.take();
        let snapshot = entry.record.clone();

        push_audit(
            &mut guard.audit_log,
            AuditLogEntry {
                timestamp: Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true),
                request_id: request_id.to_string(),
                event_type: if approved { "APPROVED" } else { "DENIED" }.to_string(),
                tool_name: snapshot.tool_name.clone(),
                risk_level: snapshot.risk_level.clone(),
                decision: Some(if approved { "approved" } else { "denied" }.to_string()),
                details: reason.to_string(),
            },
        );

        if let Some(tx) = waiter {
            let _ = tx.send(PermissionDecision {
                decision: if approved { "approved" } else { "denied" }.to_string(),
                grant_type: if approved {
                    grant_type.to_string()
                } else {
                    "denied".to_string()
                },
                request_id: request_id.to_string(),
                reason: reason.to_string(),
            });
        }

        Ok(snapshot)
    }

    /// Expires any stale pending requests fail-closed.
    pub async fn sweep_expired(&self) -> Vec<String> {
        let now = Instant::now();
        let mut expired_ids = Vec::new();
        let mut guard = self.state.lock().await;
        for (req_id, entry) in guard.requests.iter_mut() {
            if entry.record.status == PermissionRequestStatus::WaitingForUser && now > entry.deadline
            {
                entry.record.status = PermissionRequestStatus::Expired;
                if let Some(tx) = entry.waiter.take() {
                    let _ = tx.send(PermissionDecision {
                        decision: "denied".to_string(),
                        grant_type: "expired".to_string(),
                        request_id: req_id.clone(),
                        reason: "Permission approval TTL expired (fail-closed)".to_string(),
                    });
                }
                expired_ids.push(req_id.clone());
            }
        }
        expired_ids
    }

    pub async fn pending_requests(&self) -> Vec<PermissionRequestRecord> {
        let guard = self.state.lock().await;
        guard
            .requests
            .values()
            .filter(|e| e.record.status == PermissionRequestStatus::WaitingForUser)
            .map(|e| e.record.clone())
            .collect()
    }

    pub async fn audit_entries(&self) -> Vec<AuditLogEntry> {
        self.state.lock().await.audit_log.iter().cloned().collect()
    }

    /// Produces a Reverse RPC handler that enforces policy + 300s HITL approval fail-closed
    /// for Python worker requests (`permission.request_approval`).
    pub fn as_reverse_rpc_handler(&self) -> ReverseRpcHandler {
        let gw = self.clone();
        Arc::new(move |req| {
            let gw = gw.clone();
            Box::pin(async move { gw.handle_reverse_request(req).await })
        })
    }

    /// Handles a single Reverse-RPC `permission.*` request directly.
    pub async fn handle_reverse_request(
        &self,
        req: ReverseRequest,
    ) -> Result<Value, RpcRemoteError> {
        if req.method != "permission.request_approval" {
            return Err(RpcRemoteError {
                code: -32601,
                message: format!("Unsupported reverse RPC method: {}", req.method),
                data: None,
            });
        }

        let action = req
            .params
            .get("action")
            .and_then(Value::as_str)
            .unwrap_or("unknown");
        let resource = req
            .params
            .get("resource")
            .and_then(Value::as_str)
            .unwrap_or("");
        let agent_name = req
            .params
            .get("agent_name")
            .and_then(Value::as_str)
            .map(ToOwned::to_owned);
        let security_level = req
            .params
            .get("security_level")
            .and_then(Value::as_str)
            .unwrap_or("LOW_RISK_MUTATION");
        let project_id = req
            .params
            .get("project_id")
            .and_then(Value::as_str)
            .map(ToOwned::to_owned);
        let mission_id = req
            .params
            .get("mission_id")
            .and_then(Value::as_str)
            .map(ToOwned::to_owned);
        let timeout_ms = req
            .params
            .get("timeout_ms")
            .and_then(Value::as_u64)
            .unwrap_or(DEFAULT_PERMISSION_TTL.as_millis() as u64)
            .min(DEFAULT_PERMISSION_TTL.as_millis() as u64);

        let (record, rx_opt) = self
            .create_request(
                action,
                format!("{action} {resource}"),
                "Worker Reverse RPC authorization request",
                security_level,
                if resource.is_empty() {
                    vec![]
                } else {
                    vec![resource.to_string()]
                },
                mission_id,
                project_id,
                agent_name,
                Some(Duration::from_millis(timeout_ms)),
            )
            .await
            .map_err(|msg| RpcRemoteError {
                code: -32003,
                message: msg,
                data: None,
            })?;

        let Some(rx) = rx_opt else {
            return Ok(json!({
                "decision": "approved",
                "grant_type": "read_only_auto",
                "request_id": record.request_id,
            }));
        };

        let wait_dur = Duration::from_millis(timeout_ms);
        match tokio::time::timeout(wait_dur, rx).await {
            Ok(Ok(decision)) => serde_json::to_value(decision).map_err(|e| RpcRemoteError {
                code: -32603,
                message: e.to_string(),
                data: None,
            }),
            _ => {
                let _ = self.sweep_expired().await;
                Ok(json!({
                    "decision": "denied",
                    "grant_type": "timeout_fail_closed",
                    "request_id": record.request_id,
                    "reason": "HITL approval timed out (fail-closed)",
                }))
            }
        }
    }
}

fn push_audit(log: &mut VecDeque<AuditLogEntry>, entry: AuditLogEntry) {
    if log.len() >= 512 {
        log.pop_front();
    }
    log.push_back(entry);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::workers::rpc_client::ReverseRequest;

    #[tokio::test]
    async fn permission_gateway_enforces_fail_closed_policy_scoping_and_ttl() {
        let gw = PermissionGateway::new(Duration::from_millis(80));

        // 1. Critical mutation and uncatalogued high-risk tool must block by policy
        assert!(gw
            .create_request(
                "rm",
                "rm -rf /",
                "cleanup",
                "CRITICAL_MUTATION",
                vec![],
                None,
                None,
                None,
                None,
            )
            .await
            .is_err());

        assert!(gw
            .create_request(
                "uncatalogued-tool",
                "uncatalogued-tool --danger",
                "test",
                "HIGH_RISK_MUTATION",
                vec![],
                None,
                None,
                None,
                None,
            )
            .await
            .is_err());

        // 2. ReadOnly is auto-permitted without human wait
        let (ro, rx) = gw
            .create_request(
                "read_file",
                "read src/main.rs",
                "inspect",
                "READ_ONLY",
                vec![],
                None,
                None,
                None,
                None,
            )
            .await
            .expect("read_only auto-permitted");
        assert!(rx.is_none());
        assert_eq!(ro.status, PermissionRequestStatus::Available);

        // 3. Project/mission scope isolation + explicit approval
        let (req, rx_opt) = gw
            .create_request(
                "ffmpeg",
                "ffmpeg -i video.mp4 frame.png",
                "extract frame",
                "HIGH_RISK_MUTATION",
                vec!["video.mp4".into()],
                Some("mission-A".into()),
                Some("proj-A".into()),
                None,
                Some(Duration::from_secs(2)),
            )
            .await
            .expect("create scoped pending request");

        assert!(gw
            .approve_request(
                &req.request_id,
                "user",
                "allow_once",
                Some("proj-OTHER"),
                Some("mission-A"),
            )
            .await
            .is_err());

        gw.approve_request(
            &req.request_id,
            "user",
            "allow_once",
            Some("proj-A"),
            Some("mission-A"),
        )
        .await
        .expect("matching project+mission approves");

        let decision = rx_opt.unwrap().await.expect("receive decision");
        assert_eq!(decision.decision, "approved");

        // 4. Reverse RPC handler expires fail-closed on timeout
        let handler = gw.as_reverse_rpc_handler();
        let timeout_res = handler(ReverseRequest {
            id: "rev-timeout".into(),
            method: "permission.request_approval".into(),
            params: json!({
                "action": "fs.write",
                "resource": "workspace/out.txt",
                "security_level": "LOW_RISK_MUTATION",
                "timeout_ms": 40
            }),
        })
        .await
        .expect("reverse handler resolves fail-closed decision");
        assert_eq!(timeout_res["decision"], "denied");
    }
}

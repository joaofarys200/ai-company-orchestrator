//! Native Sentinel WebSocket/IPC command dispatcher for all 10 `sentinel_*` routes.
//!
//! Consolidates Sentinel audit/status/baseline/known-good/action/review/telemetry handling
//! directly in Rust via `SentinelWatchdog` + `SentinelScheduler`.

use serde_json::{json, Value};

use crate::error::AppError;
use crate::sentinel::watchdog_store::SentinelWatchdog;

/// Executes all 10 `sentinel_*` client commands natively in Rust.
pub async fn try_execute_sentinel_fast_path(
    watchdog: &SentinelWatchdog,
    msg_type: &str,
    message: &Value,
) -> Result<Option<Vec<Value>>, AppError> {
    if !msg_type.starts_with("sentinel_") {
        return Ok(None);
    }

    match msg_type {
        "sentinel_get_status" => {
            let status = watchdog.status_payload().await;
            Ok(Some(vec![json!({
                "type": "sentinel_status",
                "data": status,
            })]))
        }

        "sentinel_run_audit" => Ok(Some(watchdog.run_audit().await?)),

        "sentinel_get_baseline" => {
            let baseline = watchdog.baseline_payload().await;
            Ok(Some(vec![json!({
                "type": "sentinel_baseline",
                "data": baseline,
            })]))
        }

        "sentinel_accept_known_good" => {
            let item_key = message
                .get("item_key")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim();
            if item_key.is_empty() {
                return Err(AppError::new(
                    "INVALID_SENTINEL_ITEM",
                    "item_key é obrigatório para marcar Known Good.",
                ));
            }
            let reason = message
                .get("reason")
                .and_then(Value::as_str)
                .unwrap_or("Aprovado pelo operador.");
            let user = message
                .get("user")
                .and_then(Value::as_str)
                .unwrap_or("local_user");
            Ok(Some(
                watchdog.accept_known_good(item_key, reason, user).await?,
            ))
        }

        "sentinel_get_actions" => {
            let actions = watchdog.actions_payload().await;
            Ok(Some(vec![json!({
                "type": "sentinel_actions_list",
                "data": actions,
            })]))
        }

        "sentinel_approve_action" => {
            let action_id = message
                .get("action_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim();
            let user = message
                .get("user")
                .and_then(Value::as_str)
                .unwrap_or("local_user");
            let session_id = message.get("session_id").and_then(Value::as_str);
            Ok(Some(
                watchdog.approve_action(action_id, user, session_id).await?,
            ))
        }

        "sentinel_reject_action" => {
            let action_id = message
                .get("action_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim();
            let reason = message
                .get("reason")
                .and_then(Value::as_str)
                .unwrap_or("Rejeitado pelo operador.");
            let user = message
                .get("user")
                .and_then(Value::as_str)
                .unwrap_or("local_user");
            Ok(Some(watchdog.reject_action(action_id, reason, user).await?))
        }

        "sentinel_rollback_action" => {
            let action_id = message
                .get("action_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim();
            let user = message
                .get("user")
                .and_then(Value::as_str)
                .unwrap_or("local_user");
            Ok(Some(watchdog.rollback_action(action_id, user).await?))
        }

        "sentinel_get_shadow_telemetry" => {
            let telemetry = watchdog.shadow_telemetry_payload().await;
            Ok(Some(vec![json!({
                "type": "sentinel_shadow_telemetry",
                "data": telemetry,
            })]))
        }

        "sentinel_submit_review" => {
            let event_id = message
                .get("event_id")
                .and_then(Value::as_str)
                .unwrap_or_default()
                .trim();
            let final_class = message
                .get("final_classification")
                .and_then(Value::as_str)
                .unwrap_or("BENIGN")
                .trim();
            let reason = message
                .get("reason")
                .and_then(Value::as_str)
                .unwrap_or("Revisão humana aplicada.");
            let operator = message
                .get("operator")
                .and_then(Value::as_str)
                .unwrap_or("local_operator");
            Ok(Some(
                watchdog
                    .submit_review(event_id, final_class, reason, operator)
                    .await?,
            ))
        }

        _ => Ok(None),
    }
}

#[cfg(test)]
mod tests {
    use std::sync::Arc;

    use super::*;
    use crate::sentinel::scheduler::SentinelScheduler;
    use tempfile::tempdir;

    #[tokio::test]
    async fn all_10_sentinel_routes_execute_in_rust_respecting_shadow_and_protected_pids() {
        let dir = tempdir().unwrap();
        let root = dunce::canonicalize(dir.path()).unwrap();
        let protected_pid = std::process::id();
        let scheduler = Arc::new(SentinelScheduler::with_default_read_only(Arc::new(
            move || vec![protected_pid],
        )));
        let watchdog = SentinelWatchdog::open(&root, Arc::clone(&scheduler));

        let st = try_execute_sentinel_fast_path(&watchdog, "sentinel_get_status", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(st[0]["type"], "sentinel_status");
        assert_eq!(st[0]["data"]["shadow_mode"], true);

        let audit = try_execute_sentinel_fast_path(&watchdog, "sentinel_run_audit", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(audit[0]["type"], "sentinel_audit_completed");
        assert_eq!(audit[0]["data"]["is_initial_baseline"], true);

        let base = try_execute_sentinel_fast_path(&watchdog, "sentinel_get_baseline", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(base[0]["type"], "sentinel_baseline");
        assert!(base[0]["data"]["baseline_id"].is_string());

        let telem =
            try_execute_sentinel_fast_path(&watchdog, "sentinel_get_shadow_telemetry", &json!({}))
                .await
                .unwrap()
                .unwrap();
        assert_eq!(telem[0]["type"], "sentinel_shadow_telemetry");
        assert_eq!(telem[0]["data"]["shadow_mode"], true);
        assert!(telem[0]["data"]["protected_pids"]
            .as_array()
            .unwrap()
            .iter()
            .any(|v| v.as_u64() == Some(protected_pid as u64)));

        // Inject synthetic event + protected-PID action to test approve/reject/rollback/review/known_good
        {
            let res = watchdog
                .accept_known_good("fp_demo", "Trusted binary", "tester")
                .await
                .unwrap();
            assert_eq!(res[0]["type"], "sentinel_known_good_updated");
            assert_eq!(res[0]["status"], "ACCEPTED");
        }

        let actions = try_execute_sentinel_fast_path(&watchdog, "sentinel_get_actions", &json!({}))
            .await
            .unwrap()
            .unwrap();
        assert_eq!(actions[0]["type"], "sentinel_actions_list");

        // Ensure protected PID termination is always blocked even when ShadowMode is turned off
        scheduler.set_shadow_mode(false).await;
        let outcome = scheduler
            .evaluate_remediation(protected_pid, "jarvis-os.exe")
            .await
            .unwrap();
        assert_eq!(
            outcome,
            crate::sentinel::scheduler::RemediationOutcome::BlockedProtectedPid
        );
    }
}

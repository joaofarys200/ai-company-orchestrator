//! Fail-closed permission policy engine matching JARVIS OS risk classification rules.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PermissionRiskLevel {
    ReadOnly,
    LowRiskMutation,
    HighRiskMutation,
    CriticalMutation,
}

impl PermissionRiskLevel {
    pub fn parse_lossy(raw: &str) -> Option<Self> {
        match raw.trim().to_ascii_uppercase().as_str() {
            "READ_ONLY" | "LOW" => Some(Self::ReadOnly),
            "LOW_RISK_MUTATION" | "MEDIUM" => Some(Self::LowRiskMutation),
            "HIGH_RISK_MUTATION" | "HIGH" => Some(Self::HighRiskMutation),
            "CRITICAL_MUTATION" | "CRITICAL" => Some(Self::CriticalMutation),
            _ => None,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::ReadOnly => "READ_ONLY",
            Self::LowRiskMutation => "LOW_RISK_MUTATION",
            Self::HighRiskMutation => "HIGH_RISK_MUTATION",
            Self::CriticalMutation => "CRITICAL_MUTATION",
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PermissionRequestStatus {
    WaitingForUser,
    Available,
    Approved,
    Denied,
    BlockedByPolicy,
    Expired,
    Executed,
    Failed,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PolicyEvaluation {
    pub is_eligible_for_human_approval: bool,
    pub is_auto_permitted: bool,
    pub is_blocked_by_policy: bool,
    pub reason: String,
    pub initial_status: PermissionRequestStatus,
}

pub const AUTHORIZED_HIGH_RISK_TOOLS: &[&str] = &[
    "nmap",
    "npcap",
    "arp-scan",
    "ffmpeg",
    "ocr",
    "tesseract",
    "node-gyp",
    "build-tools",
    "fs.write",
    "fs.delete",
    "process.exec",
];

const DESTRUCTIVE_PATTERNS: &[(&str, &str)] = &[
    ("rm -rf /", "recursive root deletion"),
    ("rm -rf ~", "recursive home deletion"),
    ("del /s /q c:\\", "recursive system drive deletion"),
    ("format ", "disk format operation"),
    ("mkfs", "filesystem format"),
    ("/dev/tcp/", "raw reverse shell socket"),
    ("taskkill /f /im explorer", "system shell termination"),
    ("taskkill /f /im lsass", "security subsystem termination"),
    ("cipher /w", "disk wipe utility"),
    ("reg delete hklm", "registry hive destruction"),
];

pub fn is_destructive_operation(operation: &str) -> Option<&'static str> {
    let lower = operation.trim().to_ascii_lowercase();
    for &(needle, reason) in DESTRUCTIVE_PATTERNS {
        if lower.contains(needle) {
            return Some(reason);
        }
    }
    if (lower.contains("| sh") || lower.contains("| bash") || lower.contains("| powershell"))
        && (lower.contains("curl") || lower.contains("wget") || lower.contains("invoke-"))
    {
        return Some("remote pipe-to-shell execution");
    }
    None
}

/// Evaluates risk classification + tool allowlists fail-closed.
pub fn evaluate_permission_policy(
    tool_name: &str,
    requested_operation: &str,
    risk_raw: &str,
) -> PolicyEvaluation {
    if let Some(reason) = is_destructive_operation(requested_operation) {
        return PolicyEvaluation {
            is_eligible_for_human_approval: false,
            is_auto_permitted: false,
            is_blocked_by_policy: true,
            reason: format!("Blocked by Sentinel security policy: {reason}."),
            initial_status: PermissionRequestStatus::BlockedByPolicy,
        };
    }

    let Some(risk) = PermissionRiskLevel::parse_lossy(risk_raw) else {
        return PolicyEvaluation {
            is_eligible_for_human_approval: false,
            is_auto_permitted: false,
            is_blocked_by_policy: true,
            reason: format!("Fail-closed: unrecognized risk level `{risk_raw}`."),
            initial_status: PermissionRequestStatus::BlockedByPolicy,
        };
    };

    match risk {
        PermissionRiskLevel::CriticalMutation => PolicyEvaluation {
            is_eligible_for_human_approval: false,
            is_auto_permitted: false,
            is_blocked_by_policy: true,
            reason: "Critical destructive mutations are unconditionally blocked by policy."
                .to_string(),
            initial_status: PermissionRequestStatus::BlockedByPolicy,
        },
        PermissionRiskLevel::ReadOnly => PolicyEvaluation {
            is_eligible_for_human_approval: false,
            is_auto_permitted: true,
            is_blocked_by_policy: false,
            reason: "Read-only inspection permitted automatically.".to_string(),
            initial_status: PermissionRequestStatus::Available,
        },
        PermissionRiskLevel::LowRiskMutation => PolicyEvaluation {
            is_eligible_for_human_approval: true,
            is_auto_permitted: false,
            is_blocked_by_policy: false,
            reason: "Low-risk mutation eligible for JIT human approval.".to_string(),
            initial_status: PermissionRequestStatus::WaitingForUser,
        },
        PermissionRiskLevel::HighRiskMutation => {
            let normalized = tool_name.trim().to_ascii_lowercase();
            if AUTHORIZED_HIGH_RISK_TOOLS.contains(&normalized.as_str()) {
                PolicyEvaluation {
                    is_eligible_for_human_approval: true,
                    is_auto_permitted: false,
                    is_blocked_by_policy: false,
                    reason: "Controlled high-risk tool requires explicit human authorization."
                        .to_string(),
                    initial_status: PermissionRequestStatus::WaitingForUser,
                }
            } else {
                PolicyEvaluation {
                    is_eligible_for_human_approval: false,
                    is_auto_permitted: false,
                    is_blocked_by_policy: true,
                    reason: format!(
                        "High-risk tool `{tool_name}` is not cataloged for elevation."
                    ),
                    initial_status: PermissionRequestStatus::BlockedByPolicy,
                }
            }
        }
    }
}

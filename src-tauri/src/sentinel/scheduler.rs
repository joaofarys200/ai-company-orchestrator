//! Sentinel observability scheduler with `ShadowMode=true` default and protected-PID immunity.
//!
//! Guarantees:
//! - Default mode is strictly read-only (`shadow_mode: true`): anomalies and candidate remediations
//!   are logged/emitted as observations without killing processes or mutating host state.
//! - Protected PIDs (Windows kernel/system PIDs `0`/`4`, the Tauri shell PID, critical OS daemons,
//!   and all live Python worker PIDs reported dynamically by `WorkerSupervisor`) are unconditionally
//!   immune even if active remediation mode is explicitly enabled.

use std::collections::{HashSet, VecDeque};
use std::sync::Arc;
use std::time::Duration;

use chrono::{SecondsFormat, Utc};
use serde::{Deserialize, Serialize};
use tokio::sync::RwLock;

use crate::sentinel::collectors_win::{
    collect_system_telemetry, MemoryTelemetry, SystemTelemetrySnapshot,
};

pub const DEFAULT_SHADOW_MODE: bool = true;
pub const DEFAULT_SENTINEL_INTERVAL: Duration = Duration::from_secs(15);
pub const DEFAULT_CRITICAL_MEMORY_LOAD_PCT: u32 = 92;

const PROTECTED_SYSTEM_EXECUTABLES: &[&str] = &[
    "system",
    "idle",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "svchost.exe",
    "explorer.exe",
    "dwm.exe",
    "jarvis-os.exe",
    "msedgewebview2.exe",
    "ollama.exe",
];

pub type ProtectedPidProvider = Arc<dyn Fn() -> Vec<u32> + Send + Sync>;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SentinelConfig {
    pub shadow_mode: bool,
    pub poll_interval_ms: u64,
    pub critical_memory_load_pct: u32,
}

impl Default for SentinelConfig {
    fn default() -> Self {
        Self {
            shadow_mode: DEFAULT_SHADOW_MODE,
            poll_interval_ms: DEFAULT_SENTINEL_INTERVAL.as_millis() as u64,
            critical_memory_load_pct: DEFAULT_CRITICAL_MEMORY_LOAD_PCT,
        }
    }
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum RemediationOutcome {
    BlockedShadowMode,
    BlockedProtectedPid,
    AllowedNonProtected,
}

#[derive(Debug, Clone, Serialize)]
pub struct SentinelObservation {
    pub timestamp: String,
    pub shadow_mode: bool,
    pub memory: MemoryTelemetry,
    pub process_count: usize,
    pub high_memory_pressure: bool,
    pub protected_pid_count: usize,
    pub alerts: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SentinelStatusSnapshot {
    pub shadow_mode: bool,
    pub critical_memory_load_pct: u32,
    pub last_observation: Option<SentinelObservation>,
    pub recent_observations_count: usize,
    pub protected_pids: Vec<u32>,
}

struct SchedulerInner {
    config: SentinelConfig,
    observations: VecDeque<SentinelObservation>,
}

/// Coordinates non-blocking telemetry polling and enforces ShadowMode + Protected PID immunity.
pub struct SentinelScheduler {
    inner: RwLock<SchedulerInner>,
    protected_pid_provider: ProtectedPidProvider,
}

impl SentinelScheduler {
    pub fn new(config: SentinelConfig, protected_pid_provider: ProtectedPidProvider) -> Self {
        Self {
            inner: RwLock::new(SchedulerInner {
                config,
                observations: VecDeque::with_capacity(64),
            }),
            protected_pid_provider,
        }
    }

    pub fn with_default_read_only(protected_pid_provider: ProtectedPidProvider) -> Self {
        Self::new(SentinelConfig::default(), protected_pid_provider)
    }

    pub async fn is_shadow_mode(&self) -> bool {
        self.inner.read().await.config.shadow_mode
    }

    pub async fn set_shadow_mode(&self, enabled: bool) {
        self.inner.write().await.config.shadow_mode = enabled;
    }

    /// Computes the live set of protected PIDs (system PIDs + Tauri shell PID + dynamic workers).
    pub fn current_protected_pids(&self) -> Vec<u32> {
        let mut set: HashSet<u32> = HashSet::new();
        set.insert(0);
        set.insert(4);
        set.insert(std::process::id());
        for pid in (self.protected_pid_provider)() {
            if pid > 0 {
                set.insert(pid);
            }
        }
        let mut sorted: Vec<u32> = set.into_iter().collect();
        sorted.sort_unstable();
        sorted
    }

    /// Evaluates whether a remediation action targeting `(pid, exe_name)` is permitted.
    /// Guarantees ShadowMode read-only enforcement and strict protected-PID immunity.
    pub async fn evaluate_remediation(
        &self,
        pid: u32,
        exe_name: &str,
    ) -> Result<RemediationOutcome, String> {
        let shadow_mode = self.inner.read().await.config.shadow_mode;
        let normalized_name = exe_name.trim().to_ascii_lowercase();
        let protected_pids = self.current_protected_pids();

        if protected_pids.contains(&pid)
            || PROTECTED_SYSTEM_EXECUTABLES.contains(&normalized_name.as_str())
        {
            return Err(format!(
                "SENTINEL_PROTECTED_TARGET: PID {pid} ({exe_name}) is immune to remediation"
            ));
        }

        if shadow_mode {
            return Ok(RemediationOutcome::BlockedShadowMode);
        }

        Ok(RemediationOutcome::AllowedNonProtected)
    }

    /// Collects one non-blocking telemetry snapshot and records a shadow observation.
    pub async fn tick_once(&self) -> Result<SentinelObservation, String> {
        let snapshot: SystemTelemetrySnapshot = collect_system_telemetry().await?;
        let (shadow_mode, threshold) = {
            let guard = self.inner.read().await;
            (guard.config.shadow_mode, guard.config.critical_memory_load_pct)
        };
        let protected_pids = self.current_protected_pids();
        let high_memory_pressure = snapshot.memory.memory_load_pct >= threshold;

        let mut alerts = Vec::new();
        if high_memory_pressure {
            alerts.push(format!(
                "High physical memory pressure detected: {}% (shadow_mode={})",
                snapshot.memory.memory_load_pct, shadow_mode
            ));
        }

        let obs = SentinelObservation {
            timestamp: Utc::now().to_rfc3339_opts(SecondsFormat::Millis, true),
            shadow_mode,
            memory: snapshot.memory,
            process_count: snapshot.process_count,
            high_memory_pressure,
            protected_pid_count: protected_pids.len(),
            alerts,
        };

        let mut guard = self.inner.write().await;
        if guard.observations.len() >= 64 {
            guard.observations.pop_front();
        }
        guard.observations.push_back(obs.clone());
        Ok(obs)
    }

    pub async fn status_snapshot(&self) -> SentinelStatusSnapshot {
        let guard = self.inner.read().await;
        SentinelStatusSnapshot {
            shadow_mode: guard.config.shadow_mode,
            critical_memory_load_pct: guard.config.critical_memory_load_pct,
            last_observation: guard.observations.back().cloned(),
            recent_observations_count: guard.observations.len(),
            protected_pids: self.current_protected_pids(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn sentinel_defaults_to_shadow_mode_and_protects_host_and_worker_pids() {
        let worker_pid = 42420u32;
        let scheduler = SentinelScheduler::with_default_read_only(Arc::new(move || vec![worker_pid]));

        assert!(scheduler.is_shadow_mode().await);

        // Even non-protected PIDs must NOT remediate while shadow_mode == true
        let shadow_outcome = scheduler
            .evaluate_remediation(99991, "rogue_dummy.exe")
            .await
            .expect("non-protected pid returns BlockedShadowMode");
        assert_eq!(shadow_outcome, RemediationOutcome::BlockedShadowMode);

        // Even when shadow mode is explicitly turned off, protected PIDs stay immune
        scheduler.set_shadow_mode(false).await;
        assert!(scheduler
            .evaluate_remediation(std::process::id(), "test_runner.exe")
            .await
            .is_err());
        assert!(scheduler
            .evaluate_remediation(worker_pid, "python.exe")
            .await
            .is_err());
        assert!(scheduler
            .evaluate_remediation(4, "System")
            .await
            .is_err());
        assert!(scheduler
            .evaluate_remediation(55555, "ollama.exe")
            .await
            .is_err());

        let active_outcome = scheduler
            .evaluate_remediation(99991, "rogue_dummy.exe")
            .await
            .expect("unprotected pid allowed only when shadow_mode=false");
        assert_eq!(active_outcome, RemediationOutcome::AllowedNonProtected);

        // Read-only tick succeeds and leaves shadow telemetry trace
        scheduler.set_shadow_mode(true).await;
        let obs = scheduler.tick_once().await.expect("tick_once succeeds");
        assert!(obs.shadow_mode);
        assert!(obs.protected_pid_count >= 4);
    }
}

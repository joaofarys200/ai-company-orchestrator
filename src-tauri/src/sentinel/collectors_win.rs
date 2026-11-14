//! Non-blocking native Windows telemetry collectors for JARVIS OS Sentinel.
//!
//! Replaces blocking PowerShell / WMI / psutil subprocess calls with direct Win32 APIs
//! (`GlobalMemoryStatusEx` and `CreateToolhelp32Snapshot`) intended to run inside
//! `tokio::task::spawn_blocking`.

use serde::Serialize;

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct MemoryTelemetry {
    pub memory_load_pct: u32,
    pub total_phys_bytes: u64,
    pub avail_phys_bytes: u64,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct ProcessSnapshot {
    pub pid: u32,
    pub parent_pid: u32,
    pub exe_name: String,
    pub threads: u32,
}

#[derive(Debug, Clone, Serialize, PartialEq, Eq)]
pub struct SystemTelemetrySnapshot {
    pub memory: MemoryTelemetry,
    pub process_count: usize,
    pub processes: Vec<ProcessSnapshot>,
}

/// Captures system physical memory usage without allocating subprocesses.
pub fn read_memory_telemetry() -> Result<MemoryTelemetry, String> {
    #[cfg(windows)]
    {
        use std::mem::size_of;
        use windows_sys::Win32::System::SystemInformation::{
            GlobalMemoryStatusEx, MEMORYSTATUSEX,
        };

        let mut mem: MEMORYSTATUSEX = unsafe { std::mem::zeroed() };
        mem.dwLength = size_of::<MEMORYSTATUSEX>() as u32;
        let ok = unsafe { GlobalMemoryStatusEx(&mut mem) };
        if ok == 0 {
            return Err(format!(
                "GlobalMemoryStatusEx failed: {}",
                std::io::Error::last_os_error()
            ));
        }

        Ok(MemoryTelemetry {
            memory_load_pct: mem.dwMemoryLoad,
            total_phys_bytes: mem.ullTotalPhys,
            avail_phys_bytes: mem.ullAvailPhys,
        })
    }

    #[cfg(not(windows))]
    {
        Ok(MemoryTelemetry {
            memory_load_pct: 0,
            total_phys_bytes: 0,
            avail_phys_bytes: 0,
        })
    }
}

/// Captures active OS processes via Win32 Toolhelp32 snapshot without shell calls.
pub fn snapshot_processes() -> Result<Vec<ProcessSnapshot>, String> {
    #[cfg(windows)]
    {
        use std::mem::size_of;
        use windows_sys::Win32::Foundation::{CloseHandle, HANDLE, INVALID_HANDLE_VALUE};
        use windows_sys::Win32::System::Diagnostics::ToolHelp::{
            CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W,
            TH32CS_SNAPPROCESS,
        };

        struct SnapshotGuard(HANDLE);
        impl Drop for SnapshotGuard {
            fn drop(&mut self) {
                if !self.0.is_null() && self.0 != INVALID_HANDLE_VALUE {
                    unsafe {
                        CloseHandle(self.0);
                    }
                }
            }
        }

        let handle = unsafe { CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0) };
        if handle.is_null() || handle == INVALID_HANDLE_VALUE {
            return Err(format!(
                "CreateToolhelp32Snapshot failed: {}",
                std::io::Error::last_os_error()
            ));
        }
        let _guard = SnapshotGuard(handle);

        let mut entry: PROCESSENTRY32W = unsafe { std::mem::zeroed() };
        entry.dwSize = size_of::<PROCESSENTRY32W>() as u32;

        if unsafe { Process32FirstW(handle, &mut entry) } == 0 {
            return Ok(Vec::new());
        }

        let mut out = Vec::with_capacity(128);
        loop {
            let nul_pos = entry
                .szExeFile
                .iter()
                .position(|&c| c == 0)
                .unwrap_or(entry.szExeFile.len());
            let exe_name = String::from_utf16_lossy(&entry.szExeFile[..nul_pos]);

            out.push(ProcessSnapshot {
                pid: entry.th32ProcessID,
                parent_pid: entry.th32ParentProcessID,
                exe_name,
                threads: entry.cntThreads,
            });

            if unsafe { Process32NextW(handle, &mut entry) } == 0 {
                break;
            }
        }

        Ok(out)
    }

    #[cfg(not(windows))]
    {
        Ok(Vec::new())
    }
}

/// Collects full system memory + process snapshot synchronously (call via `spawn_blocking`).
pub fn collect_system_telemetry_blocking() -> Result<SystemTelemetrySnapshot, String> {
    let memory = read_memory_telemetry()?;
    let processes = snapshot_processes()?;
    Ok(SystemTelemetrySnapshot {
        memory,
        process_count: processes.len(),
        processes,
    })
}

/// Async non-blocking wrapper executing Win32 telemetry collectors on Tokio's blocking pool.
pub async fn collect_system_telemetry() -> Result<SystemTelemetrySnapshot, String> {
    tokio::task::spawn_blocking(collect_system_telemetry_blocking)
        .await
        .map_err(|e| format!("Sentinel collector join error: {e}"))?
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn win32_collectors_return_valid_memory_and_current_process() {
        let snapshot = collect_system_telemetry()
            .await
            .expect("collect_system_telemetry succeeds");

        #[cfg(windows)]
        {
            assert!(snapshot.memory.total_phys_bytes > 0);
            assert!(snapshot.process_count > 0);
            let self_pid = std::process::id();
            assert!(
                snapshot.processes.iter().any(|p| p.pid == self_pid),
                "current test pid {self_pid} must appear in Toolhelp snapshot"
            );
        }
    }
}

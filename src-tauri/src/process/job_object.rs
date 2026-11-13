//! Windows Job Object lifecycle management for Python sidecar workers.
//!
//! Ensures every spawned worker and all of its descendant processes (for example,
//! ffmpeg, PyMuPDF helpers, or subprocess tools) are terminated atomically whenever
//! the owning JobObject is dropped or Rust Core exits unexpectedly.

#[cfg(windows)]
use std::ffi::c_void;
#[cfg(windows)]
use std::os::windows::io::RawHandle;

#[cfg(windows)]
use windows_sys::Win32::Foundation::{CloseHandle, HANDLE};
#[cfg(windows)]
use windows_sys::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
    SetInformationJobObject, TerminateJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION, JOB_OBJECT_LIMIT_JOB_MEMORY,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
};
#[cfg(windows)]
use windows_sys::Win32::System::Threading::{
    OpenProcess, CREATE_NO_WINDOW, PROCESS_SET_QUOTA, PROCESS_TERMINATE,
};

/// Win32 process creation flag hiding console windows for headless worker children.
#[cfg(windows)]
pub const WORKER_CREATION_FLAGS: u32 = CREATE_NO_WINDOW;

#[cfg(not(windows))]
pub const WORKER_CREATION_FLAGS: u32 = 0;

/// RAII wrapper around an OS Job Object (`HANDLE` on Windows).
///
/// Configured with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and
/// `JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION` plus an optional job memory cap.
pub struct JobObject {
    #[cfg(windows)]
    handle: isize,
}

#[cfg(windows)]
unsafe impl Send for JobObject {}
#[cfg(windows)]
unsafe impl Sync for JobObject {}

impl std::fmt::Debug for JobObject {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        #[cfg(windows)]
        {
            f.debug_struct("JobObject")
                .field("handle", &self.handle)
                .finish()
        }
        #[cfg(not(windows))]
        {
            f.debug_struct("JobObject").finish()
        }
    }
}

impl JobObject {
    /// Creates a new anonymous Job Object configured to kill all assigned processes
    /// when the job handle is closed.
    pub fn new(max_memory_bytes: Option<usize>) -> Result<Self, String> {
        #[cfg(windows)]
        {
            let handle = unsafe { CreateJobObjectW(std::ptr::null(), std::ptr::null()) };
            if handle.is_null() {
                return Err(format!(
                    "CreateJobObjectW failed: {}",
                    std::io::Error::last_os_error()
                ));
            }

            let mut info: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = Default::default();
            let mut flags =
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION;

            if let Some(limit) = max_memory_bytes {
                if limit > 0 {
                    flags |= JOB_OBJECT_LIMIT_JOB_MEMORY;
                    info.JobMemoryLimit = limit;
                }
            }
            info.BasicLimitInformation.LimitFlags = flags;

            let ok = unsafe {
                SetInformationJobObject(
                    handle,
                    JobObjectExtendedLimitInformation,
                    (&info as *const JOBOBJECT_EXTENDED_LIMIT_INFORMATION).cast::<c_void>(),
                    std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
                )
            };
            if ok == 0 {
                let err = std::io::Error::last_os_error();
                unsafe {
                    CloseHandle(handle);
                }
                return Err(format!("SetInformationJobObject failed: {err}"));
            }

            Ok(Self {
                handle: handle as isize,
            })
        }

        #[cfg(not(windows))]
        {
            let _ = max_memory_bytes;
            Ok(Self {})
        }
    }

    #[cfg(windows)]
    fn as_handle(&self) -> HANDLE {
        self.handle as HANDLE
    }

    /// Assigns an open OS process handle directly to this Job Object.
    #[cfg(windows)]
    pub fn assign_raw_handle(&self, process_handle: RawHandle) -> Result<(), String> {
        if process_handle.is_null() {
            return Err("Cannot assign null process handle to JobObject".to_string());
        }
        let ok = unsafe { AssignProcessToJobObject(self.as_handle(), process_handle as HANDLE) };
        if ok == 0 {
            return Err(format!(
                "AssignProcessToJobObject failed: {}",
                std::io::Error::last_os_error()
            ));
        }
        Ok(())
    }

    /// Opens an existing PID with `PROCESS_SET_QUOTA | PROCESS_TERMINATE` and assigns it.
    pub fn assign_pid(&self, pid: u32) -> Result<(), String> {
        #[cfg(windows)]
        {
            let proc_handle =
                unsafe { OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, 0, pid) };
            if proc_handle.is_null() {
                return Err(format!(
                    "OpenProcess(pid={pid}) failed: {}",
                    std::io::Error::last_os_error()
                ));
            }
            let assign_res = unsafe { AssignProcessToJobObject(self.as_handle(), proc_handle) };
            let assign_err = if assign_res == 0 {
                Some(std::io::Error::last_os_error())
            } else {
                None
            };
            unsafe {
                CloseHandle(proc_handle);
            }
            if let Some(err) = assign_err {
                return Err(format!("AssignProcessToJobObject(pid={pid}) failed: {err}"));
            }
            Ok(())
        }

        #[cfg(not(windows))]
        {
            let _ = pid;
            Ok(())
        }
    }

    /// Explicitly terminates every process inside the Job Object immediately.
    pub fn terminate(&self, exit_code: u32) -> Result<(), String> {
        #[cfg(windows)]
        {
            let ok = unsafe { TerminateJobObject(self.as_handle(), exit_code) };
            if ok == 0 {
                return Err(format!(
                    "TerminateJobObject failed: {}",
                    std::io::Error::last_os_error()
                ));
            }
            Ok(())
        }

        #[cfg(not(windows))]
        {
            let _ = exit_code;
            Ok(())
        }
    }
}

impl Drop for JobObject {
    fn drop(&mut self) {
        #[cfg(windows)]
        {
            if self.handle != 0 {
                unsafe {
                    let _ = TerminateJobObject(self.as_handle(), 1);
                    let _ = CloseHandle(self.as_handle());
                }
                self.handle = 0;
            }
        }
    }
}

#[cfg(all(test, windows))]
mod tests {
    use super::*;
    use std::os::windows::process::CommandExt;
    use std::process::Command;
    use std::time::{Duration, Instant};

    #[test]
    fn dropping_job_object_terminates_assigned_child_process() {
        let job = JobObject::new(Some(512 * 1024 * 1024)).expect("create JobObject");
        let mut child = Command::new("powershell.exe")
            .args(["-NoProfile", "-Command", "Start-Sleep -Seconds 30"])
            .creation_flags(WORKER_CREATION_FLAGS)
            .spawn()
            .expect("spawn child powershell process");

        job.assign_pid(child.id()).expect("assign child pid to JobObject");
        drop(job);

        let deadline = Instant::now() + Duration::from_secs(5);
        loop {
            match child.try_wait().expect("poll child status") {
                Some(_) => break,
                None if Instant::now() < deadline => {
                    std::thread::sleep(Duration::from_millis(50));
                }
                None => {
                    let _ = child.kill();
                    panic!("child process survived JobObject drop");
                }
            }
        }
    }
}

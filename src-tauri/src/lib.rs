pub mod commands;
pub mod error;
pub mod permissions;
pub mod process;
pub mod protocol;
pub mod storage;
pub mod workers;

use std::sync::Arc;
use tauri::Manager;

pub const SHELL_NAME: &str = "tauri";
pub const APP_DISPLAY_NAME: &str = "JARVIS OS";

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            let project_root = permissions::path_jail::resolve_project_root();
            let workspace_dir = project_root.join("workspace");
            let initial_preview_root = if workspace_dir.is_dir() {
                Some(workspace_dir)
            } else {
                None
            };

            let worker_config =
                workers::supervisor::WorkerSupervisorConfig::for_workspace(project_root.clone());
            let worker_supervisor = Arc::new(workers::supervisor::WorkerSupervisor::new(worker_config));

            let (loopback, preview) = tauri::async_runtime::block_on(async move {
                let loopback = protocol::loopback::LoopbackHandle::start(project_root)
                    .await
                    .map_err(|err| Box::new(err) as Box<dyn std::error::Error>)?;
                let preview = process::preview_server::PreviewServerHandle::start(
                    initial_preview_root,
                )
                .await
                .map_err(|err| Box::new(err) as Box<dyn std::error::Error>)?;
                Ok::<_, Box<dyn std::error::Error>>((loopback, preview))
            })?;

            app.manage(commands::media::RuntimeServices {
                loopback,
                preview,
                workers: worker_supervisor,
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::system::system_ping,
            commands::system::system_info,
            commands::system::system_open_path,
            commands::media::get_loopback_config,
            commands::media::get_media_ticket,
            commands::workers::get_worker_health,
            commands::workers::restart_worker_role,
            commands::workers::worker_system_health,
        ])
        .build(tauri::generate_context!())
        .expect("error while building JARVIS OS Tauri shell");

    app.run(|app_handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(services) = app_handle.try_state::<commands::media::RuntimeServices>() {
                tauri::async_runtime::block_on(services.workers.shutdown_all());
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::permissions::path_jail::{
        resolve_confined_path, validate_open_target, ValidatedOpenTarget,
    };
    use std::fs;
    use std::path::PathBuf;

    fn make_temp_test_root(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "jarvis_path_jail_test_{name}_{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(dir.join("data").join("study")).unwrap();
        fs::write(dir.join("data").join("study").join("notes.txt"), b"ok").unwrap();
        dir
    }

    #[test]
    fn shell_constants_match_stage2_identity() {
        assert_eq!(SHELL_NAME, "tauri");
        assert_eq!(APP_DISPLAY_NAME, "JARVIS OS");
    }

    #[test]
    fn build_ping_and_info_return_tauri_identity() {
        let ping = commands::system::build_ping_response("0.1.0");
        assert_eq!(ping.status, "ok");
        assert_eq!(ping.shell, "tauri");
        assert_eq!(ping.app_version, "0.1.0");
        assert!(ping.timestamp_ms > 0);

        let info = commands::system::build_system_info("0.1.0");
        assert_eq!(info.shell, "tauri");
        assert_eq!(info.app_name, "JARVIS OS");
        assert!(info.dialog_supported);
        assert!(info.native_open_supported);
    }

    #[test]
    fn path_jail_allows_http_and_confined_files_only() {
        let root = make_temp_test_root("allowed");
        let roots = vec![root.clone()];

        let https = validate_open_target(&roots, "https://example.com/docs").unwrap();
        assert_eq!(
            https,
            ValidatedOpenTarget::Url("https://example.com/docs".to_string())
        );

        let file_path = root.join("data").join("study").join("notes.txt");
        let validated = validate_open_target(&roots, &file_path.to_string_lossy()).unwrap();
        match validated {
            ValidatedOpenTarget::LocalPath(p) => assert!(p.ends_with("notes.txt")),
            other => panic!("expected LocalPath, got {other:?}"),
        }

        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn path_jail_blocks_disallowed_schemes_traversal_and_reserved_names() {
        let root = make_temp_test_root("blocked");
        let roots = vec![root.clone()];

        for bad in [
            "",
            "ms-msdt:id PCWDiagnostic",
            "file:///C:/Windows/System32/cmd.exe",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "https://evil.com\\backslash",
            "..\\..\\Windows\\win.ini",
            "CON",
            "nul.txt",
            "COM1.log",
            "data/study/../../outside.txt",
        ] {
            assert!(
                validate_open_target(&roots, bad).is_err(),
                "expected validate_open_target to reject {bad:?}"
            );
        }

        let non_existent_child = PathBuf::from("data/study/new_output.json");
        assert!(resolve_confined_path(&root, &non_existent_child).is_ok());

        let reserved_child = PathBuf::from("data/study/LPT1.json");
        assert!(resolve_confined_path(&root, &reserved_child).is_err());

        let _ = fs::remove_dir_all(&root);
    }
}

pub const SHELL_NAME: &str = "tauri";
pub const APP_DISPLAY_NAME: &str = "JARVIS OS";

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running JARVIS OS Tauri shell");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shell_constants_match_stage2_identity() {
        assert_eq!(SHELL_NAME, "tauri");
        assert_eq!(APP_DISPLAY_NAME, "JARVIS OS");
    }
}


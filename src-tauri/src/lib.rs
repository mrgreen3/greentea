// Core app wiring: PTY lifecycle and the IPC commands the frontend calls.
//
// TODO next:
//   - spawn_pty: open a portable_pty::PtySystem, exec $SHELL, wire
//     reader -> "pty://output" events, writer <- write_pty command
//   - resize_pty: forward xterm.js resize to the pty
//   - context bus: expose recent scrollback + cwd + last exit code
//     to the AI layer via a dedicated command, not by scraping stdout

#[tauri::command]
fn greeting() -> &'static str {
    "greentea scaffold alive"
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![greeting])
        .run(tauri::generate_context!())
        .expect("error while running greentea");
}

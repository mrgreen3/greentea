// greentea entry point.
// PTY spawning and IPC commands live in lib.rs; kept separate so the
// core logic is testable without the Tauri runtime attached.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    greentea_lib::run();
}

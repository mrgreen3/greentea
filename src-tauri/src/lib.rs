// Core app wiring: PTY lifecycle and the IPC commands the frontend calls.
//
// TODO next:
//   - context bus: expose recent scrollback + cwd + last exit code
//     to the AI layer via a dedicated command, not by scraping stdout

use std::io::{Read, Write};
use std::sync::Mutex;

use portable_pty::{Child, CommandBuilder, MasterPty, PtySize};
use tauri::{AppHandle, Emitter, Manager, State};

struct PtySession {
    master: Box<dyn MasterPty + Send>,
    writer: Box<dyn Write + Send>,
    child: Box<dyn Child + Send + Sync>,
}

#[derive(Default)]
struct PtyState(Mutex<Option<PtySession>>);

/// Number of trailing bytes that form the start of a UTF-8 sequence the
/// reader hasn't finished receiving yet. Held back so multibyte characters
/// split across read chunks aren't mangled by lossy decoding.
fn incomplete_tail_len(buf: &[u8]) -> usize {
    for back in 1..=buf.len().min(3) {
        let b = buf[buf.len() - back];
        if b & 0b1100_0000 == 0b1100_0000 {
            // Lead byte `back` bytes from the end; how long should it be?
            let need = if b >= 0xF0 {
                4
            } else if b >= 0xE0 {
                3
            } else {
                2
            };
            return if need > back { back } else { 0 };
        }
        if b & 0b1000_0000 == 0 {
            return 0; // ASCII, nothing pending
        }
        // Continuation byte: keep scanning backwards for the lead byte.
    }
    0
}

#[tauri::command]
fn spawn_pty(
    app: AppHandle,
    state: State<'_, PtyState>,
    cols: u16,
    rows: u16,
) -> Result<(), String> {
    let mut guard = state.0.lock().unwrap();

    // Dev-mode hot reload re-runs frontend init: replace any existing
    // session instead of leaking a second shell.
    if let Some(mut old) = guard.take() {
        let _ = old.child.kill();
    }

    let pty = portable_pty::native_pty_system()
        .openpty(PtySize {
            rows,
            cols,
            pixel_width: 0,
            pixel_height: 0,
        })
        .map_err(|e| e.to_string())?;

    let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/sh".into());
    let mut cmd = CommandBuilder::new(shell);
    cmd.env("TERM", "xterm-256color");
    if let Ok(home) = std::env::var("HOME") {
        cmd.cwd(home);
    }

    let child = pty.slave.spawn_command(cmd).map_err(|e| e.to_string())?;
    // Drop our copy of the slave end so reads hit EOF when the shell exits.
    drop(pty.slave);

    let mut reader = pty.master.try_clone_reader().map_err(|e| e.to_string())?;
    let writer = pty.master.take_writer().map_err(|e| e.to_string())?;

    std::thread::spawn(move || {
        let mut buf = [0u8; 8192];
        let mut pending: Vec<u8> = Vec::new();
        loop {
            match reader.read(&mut buf) {
                Ok(0) | Err(_) => break,
                Ok(n) => {
                    pending.extend_from_slice(&buf[..n]);
                    let cut = pending.len() - incomplete_tail_len(&pending);
                    if cut == 0 {
                        continue;
                    }
                    let chunk = String::from_utf8_lossy(&pending[..cut]).into_owned();
                    pending.drain(..cut);
                    if app.emit("pty://output", chunk).is_err() {
                        break;
                    }
                }
            }
        }
    });

    *guard = Some(PtySession {
        master: pty.master,
        writer,
        child,
    });
    Ok(())
}

#[tauri::command]
fn write_pty(state: State<'_, PtyState>, data: String) -> Result<(), String> {
    if let Some(session) = state.0.lock().unwrap().as_mut() {
        session
            .writer
            .write_all(data.as_bytes())
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn resize_pty(state: State<'_, PtyState>, cols: u16, rows: u16) -> Result<(), String> {
    if let Some(session) = state.0.lock().unwrap().as_ref() {
        session
            .master
            .resize(PtySize {
                rows,
                cols,
                pixel_width: 0,
                pixel_height: 0,
            })
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(PtyState::default())
        .invoke_handler(tauri::generate_handler![spawn_pty, write_pty, resize_pty])
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // Don't leave an orphaned shell behind the closed window.
                if let Some(mut session) = window.state::<PtyState>().0.lock().unwrap().take() {
                    let _ = session.child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running greentea");
}

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command as StdCommand, Child};
use std::sync::Mutex;
use tauri::api::process::{Command as TauriCommand, CommandEvent};
use tauri::{Manager, WindowEvent};

struct AppState {
    sidecar_process: Mutex<Option<Child>>,
}

fn main() {
    let context = tauri::generate_context!();

    tauri::Builder::default()
        .manage(AppState {
            sidecar_process: Mutex::new(None),
        })
        .setup(|app| {
            // 方式1：尝试用 Tauri sidecar API 启动
            match TauriCommand::new_sidecar("localswitch-backend") {
                Ok(sidecar) => {
                    match sidecar.spawn() {
                        Ok((mut rx, _child)) => {
                            println!("[Rust] Sidecar started via Tauri API");

                            // 监听 sidecar 输出
                            tauri::async_runtime::spawn(async move {
                                while let Some(event) = rx.recv().await {
                                    match event {
                                        CommandEvent::Stdout(line) => {
                                            println!("[Sidecar] {}", line);
                                        }
                                        CommandEvent::Stderr(line) => {
                                            eprintln!("[Sidecar Err] {}", line);
                                        }
                                        CommandEvent::Error(err) => {
                                            eprintln!("[Sidecar Error] {}", err);
                                        }
                                        CommandEvent::Terminated(payload) => {
                                            println!("[Sidecar] Terminated: code={:?}, signal={:?}", payload.code, payload.signal);
                                            break;
                                        }
                                        _ => {}
                                    }
                                }
                            });
                        }
                        Err(e) => {
                            eprintln!("[Rust] Failed to spawn sidecar via Tauri API: {}", e);
                            // 回退到直接启动
                            spawn_sidecar_direct(app);
                        }
                    }
                }
                Err(e) => {
                    eprintln!("[Rust] Failed to create sidecar command: {}", e);
                    // 回退到直接启动
                    spawn_sidecar_direct(app);
                }
            }

            Ok(())
        })
        .on_window_event(|event| {
            if let WindowEvent::CloseRequested { .. } = event.event() {
                // 关闭窗口时终止 sidecar
                if let Ok(mut guard) = event.window().state::<AppState>().sidecar_process.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.kill();
                        println!("[Rust] Sidecar stopped.");
                    }
                }
            }
        })
        .run(context)
        .expect("error while running tauri application");
}

fn spawn_sidecar_direct(app: &tauri::App) {
    // 回退：直接用 std::process::Command 启动 sidecar
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|p| p.to_path_buf()))
        .unwrap_or_default();

    let sidecar_name = if cfg!(target_os = "windows") {
        "localswitch-backend.exe"
    } else {
        "localswitch-backend"
    };

    let sidecar_path = exe_dir.join(sidecar_name);

    if !sidecar_path.exists() {
        eprintln!("[Rust] Sidecar not found at: {:?}", sidecar_path);
        return;
    }

    match StdCommand::new(&sidecar_path).spawn() {
        Ok(child) => {
            println!("[Rust] Sidecar started directly: {:?}", sidecar_path);
            if let Ok(mut guard) = app.state::<AppState>().sidecar_process.lock() {
                guard.replace(child);
            }
        }
        Err(e) => {
            eprintln!("[Rust] Failed to start sidecar directly: {}", e);
        }
    }
}

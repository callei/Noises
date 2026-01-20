#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use std::process::{Child, Stdio};
use std::sync::{Arc, Mutex};
use tauri::{Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

// Structure to hold the child process handle.
// We need to support both std::process::Child (for dev) and CommandChild (for prod/sidecar)
// this should give us tools to kill the process on exit.
struct BackendState {
    dev_process: Option<Child>,
    prod_process: Option<CommandChild>,
}

// Wrap in Arc<Mutex> so it can be shared across the app
type SharedBackendState = Arc<Mutex<BackendState>>;

#[tauri::command]
fn show_in_folder(path: String) {
  #[cfg(target_os = "windows")]
  {
    std::process::Command::new("explorer")
      .args(["/select,", &path])
      .spawn()
      .unwrap();
  }
  #[cfg(target_os = "macos")]
  {
    std::process::Command::new("open")
      .args(["-R", &path])
      .spawn()
      .unwrap();
  }
  #[cfg(target_os = "linux")]
  {
    std::process::Command::new("xdg-open")
      .arg(&path)
      .spawn()
      .unwrap();
  }
}

fn main() {
    let backend_state = Arc::new(Mutex::new(BackendState {
        dev_process: None,
        prod_process: None,
    }));

    let state_clone = backend_state.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_drag::init())
        .invoke_handler(tauri::generate_handler![show_in_folder])
        .setup(move |app| {
            let pid = std::process::id();

            #[cfg(debug_assertions)]
            {
                let mut cmd = std::process::Command::new("python");
                cmd.arg("../backend/main.py");
                cmd.arg("--parent-pid");
                cmd.arg(pid.to_string());
                cmd.stdin(Stdio::piped());
                
                match cmd.spawn() {
                    Ok(child) => {
                        println!("[Tauri] Backend (DEV) started with PID: {}", child.id());
                        let mut state = state_clone.lock().unwrap();
                        state.dev_process = Some(child);
                    }
                    Err(e) => eprintln!("[Tauri] Failed to spawn dev backend: {}", e),
                }
            }

            #[cfg(not(debug_assertions))]
            {
                let sidecar_command = app.shell().sidecar("backend").unwrap()
                    .args(["--parent-pid", &pid.to_string()]);
                
                match sidecar_command.spawn() {
                    Ok((_rx, child)) => {
                        println!("[Tauri] Backend (PROD) started with PID: {}", child.pid());
                        let mut state = state_clone.lock().unwrap();
                        state.prod_process = Some(child);
                        
                        // Optional: listen to backend logs via _rx here if needed
                    }
                    Err(e) => eprintln!("[Tauri] Failed to spawn sidecar: {}", e),
                };
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(move |_app_handle, event| match event {
            // This event fires when the app is completely shutting down
            RunEvent::Exit => {
                println!("[Tauri] App exiting, killing backend...");
                let mut state = backend_state.lock().unwrap();

                // Kill DEV process (std::process::Child)
                if let Some(mut child) = state.dev_process.take() {
                    let _ = child.kill(); // Sends SIGKILL / TerminateProcess
                    println!("[Tauri] Killed dev backend");
                }

                // Kill PROD process (CommandChild)
                if let Some(child) = state.prod_process.take() {
                    let _ = child.kill(); 
                    println!("[Tauri] Killed prod backend");
                }
            }
            _ => {}
        });
}
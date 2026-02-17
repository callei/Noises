#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

use std::process::{Child, Stdio};
use std::sync::{Arc, Mutex};
use tauri::RunEvent;

#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

use tauri_plugin_shell::process::CommandChild;

const BACKEND_URL: &str = "http://127.0.0.1:8000";

// Structure to hold the child process handle.
// We need to support both std::process::Child (for dev) and CommandChild (for prod/sidecar)
// this should give us tools to kill the process on exit.
struct BackendState {
    dev_process: Option<Child>,
    prod_process: Option<CommandChild>,
}

#[tauri::command]
async fn check_backend_health() -> Result<bool, String> {
    match reqwest::get(format!("{}/health", BACKEND_URL)).await {
        Ok(res) => Ok(res.status().is_success()),
        Err(_) => Ok(false),
    }
}

#[tauri::command]
async fn generate_audio(config: serde_json::Value) -> Result<serde_json::Value, String> {
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(600)) // 10 min for GPU inference
        .build()
        .map_err(|e| format!("Failed to create HTTP client: {}", e))?;

    let res = client
        .post(format!("{}/generate", BACKEND_URL))
        .json(&config)
        .send()
        .await
        .map_err(|e| format!("Backend request failed: {}", e))?;

    if !res.status().is_success() {
        let status = res.status();
        let body = res.text().await.unwrap_or_default();
        // Try to extract FastAPI's "detail" field
        if let Ok(err_json) = serde_json::from_str::<serde_json::Value>(&body) {
            if let Some(detail) = err_json.get("detail").and_then(|d| d.as_str()) {
                return Err(detail.to_string());
            }
        }
        return Err(format!("Backend error ({}): {}", status, body));
    }

    res.json::<serde_json::Value>()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))
}

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

#[tauri::command]
fn delete_file(path: String) -> Result<(), String> {
  std::fs::remove_file(&path)
    .map_err(|e| format!("Failed to delete file: {}", e))?;
  Ok(())
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
        .invoke_handler(tauri::generate_handler![show_in_folder, delete_file, check_backend_health, generate_audio])
        .setup(move |app| {
            #[cfg(debug_assertions)]
            let _ = app; // Suppress unused warning in debug mode
            
            let pid = std::process::id();

            #[cfg(debug_assertions)]
            {
                // Use the venv Python for dev mode
                let venv_python = std::path::Path::new("../.venv312/Scripts/python.exe");
                let python_cmd = if venv_python.exists() {
                    venv_python.to_str().unwrap().to_string()
                } else {
                    "python".to_string()
                };
                
                let mut cmd = std::process::Command::new(&python_cmd);
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
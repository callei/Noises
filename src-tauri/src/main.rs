#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use std::process::{Command, Child};
use std::sync::{Arc, Mutex};
use tauri_plugin_shell::process::CommandChild;
use tauri_plugin_shell::ShellExt;
use tauri::Manager;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

struct BackendProcess {
    dev_child: Option<Child>,
    prod_child: Option<CommandChild>,
}

#[tauri::command]
fn show_in_folder(path: String) {
  #[cfg(target_os = "windows")]
  {
    Command::new("explorer")
      .args(["/select,", &path]) // The comma after select is important
      .spawn()
      .unwrap();
  }
  #[cfg(target_os = "macos")]
  {
    Command::new("open")
      .args(["-R", &path])
      .spawn()
      .unwrap();
  }
  #[cfg(target_os = "linux")]
  {
    Command::new("xdg-open")
      .arg(&path)
      .spawn()
      .unwrap();
  }
}

fn main() {
    let backend_process = Arc::new(Mutex::new(BackendProcess { dev_child: None, prod_child: None }));
    let bg_process = backend_process.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_drag::init())
        .invoke_handler(tauri::generate_handler![show_in_folder])
        .setup(move |app| {
            #[cfg(debug_assertions)]
            {
                // DEV MODE: Running raw Python files because compiling takes too long.
                let resource_path = app.path().resource_dir().unwrap_or(std::path::PathBuf::from("."));
                let mut script_path = std::path::PathBuf::from("../backend/main.py");
                if !script_path.exists() {
                     script_path = resource_path.join("backend/main.py");
                }
                
                println!("Starting backend (DEV) from {:?}", script_path.canonicalize());

                let child = Command::new("python")
                    .arg(script_path)
                    .spawn();

                match child {
                    Ok(c) => {
                        println!("Backend started with PID {}", c.id());
                        let mut proc = bg_process.lock().unwrap();
                        proc.dev_child = Some(c);
                    }
                    Err(e) => {
                        eprintln!("Failed to start backend: {}", e);
                    }
                }
            }

            #[cfg(not(debug_assertions))]
            {
                // PROD MODE: Running the frozen executable (the "Sidecar").
                println!("Starting backend (PROD - Sidecar)...");
                let sidecar = app.shell().sidecar("backend");
                
                match sidecar {
                    Ok(cmd) => {
                        let (mut _rx, child) = cmd.spawn().expect("Failed to spawn sidecar");
                        println!("Backend sidecar started.");
                         let mut proc = bg_process.lock().unwrap();
                        proc.prod_child = Some(child);
                    }
                    Err(e) => {
                         eprintln!("Failed to create sidecar command: {}", e);
                    }
                }
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(move |_app_handle, event| match event {
            tauri::RunEvent::Exit => {
                let mut proc = backend_process.lock().unwrap();
                
                // Kill the backend so it doesn't haunt the system processes.
                if let Some(mut child) = proc.dev_child.take() {
                    println!("Killing backend process (DEV)");
                    let pid = child.id();
                    // First try graceful kill
                    let _ = child.kill();
                    // Then nuke the entire process tree on Windows
                    #[cfg(target_os = "windows")]
                    {
                        let _ = Command::new("taskkill")
                            .args(["/F", "/T", "/PID", &pid.to_string()])
                            .creation_flags(0x08000000) // CREATE_NO_WINDOW
                            .spawn();
                    }
                }

                // Kill Prod Process (Sidecar)
                if let Some(child) = proc.prod_child.take() {
                    println!("Killing backend process (PROD)");
                    let pid = child.pid();
                    // First try the Tauri kill method
                    let _ = child.kill();
                    // Then nuke the entire process tree on Windows
                    #[cfg(target_os = "windows")]
                    {
                        let _ = Command::new("taskkill")
                            .args(["/F", "/T", "/PID", &pid.to_string()])
                            .creation_flags(0x08000000) // CREATE_NO_WINDOW
                            .spawn();
                    }
                }
            }
            _ => {}
        });
}


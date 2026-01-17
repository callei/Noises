#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

use std::process::{Command, Child};
use std::sync::{Arc, Mutex};
use tauri::Manager;
use tauri_plugin_shell::process::CommandChild;
use std::path::PathBuf;

struct BackendProcess {
    dev_child: Option<Child>,
    prod_child: Option<CommandChild>,
}

fn main() {
    let backend_process = Arc::new(Mutex::new(BackendProcess { dev_child: None, prod_child: None }));
    let bg_process = backend_process.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_drag::init())
        .setup(move |app| {
            #[cfg(debug_assertions)]
            {
                // DEV MODE: Run Python script directly
                let resource_path = app.path().resource_dir().unwrap_or(PathBuf::from("."));
                let mut script_path = PathBuf::from("../backend/main.py");
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
                // PROD MODE: Run Sidecar Binary
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
                
                // Kill Dev Process
                if let Some(mut child) = proc.dev_child.take() {
                   println!("Killing backend process (DEV)");
                   let _ = child.kill();
                }

                // Kill Prod Process
                if let Some(child) = proc.prod_child.take() {
                    println!("Killing backend process (PROD)");
                    // CommandChild in Tauri v2 needs to be killed properly
                    let _ = child.kill(); 
                }
            }
            _ => {}
        });
}


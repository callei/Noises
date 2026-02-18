; Noises NSIS Installer Hooks
; Called by Tauri's NSIS bundler during install/uninstall.

!macro NSIS_HOOK_POSTINSTALL
  ; Run the backend sidecar with --setup-torch to download the correct
  ; PyTorch CUDA build for this machine's GPU.
  ; This happens once at install time, not on every app launch.
  ;
  ; NOTE: We use ExecWait (not nsExec::ExecToLog) because the backend exe
  ; is built with console=False (windowed mode). nsExec only works with
  ; console applications and returns "error" for windowed apps.
  
  DetailPrint "Detecting GPU and installing PyTorch (this may take a few minutes)..."
  
  ; Try the sidecar binary path
  StrCpy $1 "$INSTDIR\backend-x86_64-pc-windows-msvc.exe"
  IfFileExists $1 0 +3
    ExecWait '"$1" --setup-torch' $0
    Goto check_result
  
  ; Fallback: Tauri may place it in a binaries subdir
  StrCpy $1 "$INSTDIR\binaries\backend-x86_64-pc-windows-msvc.exe"
  IfFileExists $1 0 +3
    ExecWait '"$1" --setup-torch' $0
    Goto check_result
  
  ; Binary not found — not fatal, load_torch() will handle it on first launch
  DetailPrint "Note: Backend binary not found for pre-install setup."
  DetailPrint "PyTorch will be downloaded automatically on first launch."
  Goto done
  
  check_result:
  ${If} $0 != "0"
    DetailPrint "PyTorch setup exited with code $0."
    DetailPrint "PyTorch will be downloaded automatically on first launch."
    ; Check if a log file was created for debugging
    IfFileExists "$LOCALAPPDATA\Noises\setup.log" 0 +2
      DetailPrint "See log: $LOCALAPPDATA\Noises\setup.log"
  ${Else}
    DetailPrint "PyTorch installed successfully."
  ${EndIf}
  
  done:
!macroend

!macro NSIS_HOOK_POSTUNINSTALL
  ; Clean up the PyTorch runtime cache (stored in ProgramData to avoid
  ; MS Store Python filesystem virtualization)
  RMDir /r "$COMMONAPPDATA\Noises\torch_runtime"
  RMDir "$COMMONAPPDATA\Noises"
  ; Clean up log file (stored in LOCALAPPDATA)
  Delete "$LOCALAPPDATA\Noises\setup.log"
  ; Remove parent dir if empty
  RMDir "$LOCALAPPDATA\Noises"
!macroend

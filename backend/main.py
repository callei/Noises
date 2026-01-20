import sys
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

import os
import tempfile
import atexit
import threading
import argparse
import signal
import psutil
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import torch
from models.musicgen import MusicGenModel
from models.stable_audio import StableAudioOpenModel
from audio.postprocess import normalize_audio, fade_audio
from audio.utils import save_wav, get_next_filename
from config import LOOPS_DIR, ONESHOTS_DIR

def _get_lock_file_path():
    return os.path.join(tempfile.gettempdir(), "noises_backend.lock")

def _cleanup_lock():
    try:
        lock_path = _get_lock_file_path()
        if os.path.exists(lock_path):
            with open(lock_path, 'r') as f:
                pid = int(f.read().strip())
            if pid == os.getpid():
                os.remove(lock_path)
    except (ValueError, OSError):
        pass

def _ensure_single_instance():
    """Ensure only one instance runs, terminating duplicates."""
    lock_path = _get_lock_file_path()
    if os.path.exists(lock_path):
        try:
            with open(lock_path, 'r') as f:
                old_pid = int(f.read().strip())
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # 0x1000 = SYNCHRONIZE (enough to check existence)
            handle = kernel32.OpenProcess(0x1000, False, old_pid)
            if handle:
                kernel32.CloseHandle(handle)
                print(f"Backend already running (PID {old_pid}). Exiting.")
                sys.exit(0)
        except (ValueError, OSError, AttributeError):
            pass # stale lock
    
    # Write our PID
    try:
        with open(lock_path, 'w') as f:
            f.write(str(os.getpid()))
        atexit.register(_cleanup_lock)
    except OSError:
        pass

# Initialize Models (Lazy loaded in lifespan)
musicgen = MusicGenModel()
stable_audio = StableAudioOpenModel()

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        musicgen.load()
        stable_audio.load()
    except Exception as e:
        print(f"Error loading models: {e}")
    yield
    # Cleanup
    if musicgen.pipe: del musicgen.pipe
    if stable_audio.pipe: del stable_audio.pipe
    torch.cuda.empty_cache()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/shutdown")
def shutdown():
    print("Received shutdown request")
    
    def kill_server():
        import time
        time.sleep(1)
        os._exit(0)
    
    threading.Thread(target=kill_server).start()
    return {"status": "shutting_down"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

class GenerateRequest(BaseModel):
    type: str
    prompt: str
    bpm: int | None = None
    key: str | None = None
    length: float | None = None
    variations: int = 1
    negative_prompt: str | None = None
    steps: int = 20
    guidance: float = 3.5
    seed: int | None = None
    temperature: float = 1.0
    top_k: int = 250

@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        req_type = req.type.lower().replace("-", "")
        generated_files = []

        if "loop" in req_type:
            # --- MUSICGEN ---
            bpm = req.bpm if req.bpm else 120
            bars = req.length if req.length else 2
            duration_sec = (60 / bpm) * (bars * 4)
            full_prompt = f"{req.prompt}, {bpm} bpm"
            if req.key: full_prompt += f", {req.key}"

            print(f"Generating Loop: {full_prompt}, {duration_sec}s")
            raw_results = musicgen.generate(
                prompt=full_prompt, 
                duration_seconds=duration_sec, 
                variations=req.variations,
                guidance_scale=req.guidance,
                temperature=req.temperature,
                top_k=req.top_k,
                seed=req.seed
            )
            for i, (audio, sr) in enumerate(raw_results):
                audio = normalize_audio(audio, target_db=-10.0)
                audio = fade_audio(audio, sr, fade_out_ms=2.0)
                safe_key = (req.key or 'Key').replace(" ", "_")
                filename = get_next_filename(LOOPS_DIR, f"loop_{int(bpm)}bpm_{safe_key}")
                path = LOOPS_DIR / filename
                save_wav(audio, sr, path)
                generated_files.append({"file": filename, "path": str(path)})

        else:
            # --- STABLE AUDIO ---
            duration = req.length if req.length else 2.5
            full_prompt = req.prompt
            if req.key: full_prompt += f", {req.key}"

            print(f"Generating One-shot: {full_prompt}")
            raw_results = stable_audio.generate(
                prompt=full_prompt, 
                duration_seconds=duration, 
                variations=req.variations,
                num_inference_steps=req.steps, 
                guidance_scale=req.guidance,
                seed=req.seed
            )
            for i, (audio, sr) in enumerate(raw_results):
                audio = normalize_audio(audio, target_db=-10.0)
                audio = fade_audio(audio, sr, fade_out_ms=300.0)
                safe_key = (req.key or 'Key').replace(" ", "_")
                filename = get_next_filename(ONESHOTS_DIR, f"oneshot_{safe_key}")
                path = ONESHOTS_DIR / filename
                save_wav(audio, sr, path)
                generated_files.append({"file": filename, "path": str(path)})

        if not generated_files:
            raise HTTPException(500, "Generation failed")

        return {
            "status": "success",
            "files": generated_files,
            "path": generated_files[0]["path"]
        }

    except Exception as e:
        print(f"Error during generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    _ensure_single_instance()

    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pid", type=int, help="PID of the parent process to monitor")
    args, _ = parser.parse_known_args()

    def _monitor_parent(pid):
        print(f"Monitoring parent process {pid}")
        try:
            parent = psutil.Process(pid)
            while True:
                if not parent.is_running():
                    print(f"Parent {pid} is gone. Exiting.")
                    os._exit(0)
                import time
                time.sleep(1)
        except Exception:
            print(f"Parent {pid} lost. Exiting.")
            os._exit(0)

    if args.parent_pid:
        threading.Thread(target=_monitor_parent, args=(args.parent_pid,), daemon=True).start()

    def watch_stdin():
        try:
            if sys.stdin:
                sys.stdin.read()
        except Exception:
            pass
        print("Parent connection lost. Shutting down.")
        sys.exit(0)

    threading.Thread(target=watch_stdin, daemon=True).start()

    print("Backend starting on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)

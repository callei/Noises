import sys
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

import os
import time
import tempfile
import atexit
import threading
import argparse
import psutil
import shutil
from contextlib import asynccontextmanager

def _clean_old_mei_dirs():
    """
    Cleanup old/orphaned _MEI temp directories from previous runs.
    We identify them by the 'noises_cleanup_marker.txt' file.
    """
    try:
        if not hasattr(sys, '_MEIPASS'):
            return 

        current_mei = getattr(sys, '_MEIPASS')
        temp_dir = os.path.dirname(current_mei)
        
        for name in os.listdir(temp_dir):
            if not name.startswith('_MEI'):
                continue
            
            full_path = os.path.join(temp_dir, name)
            if full_path == current_mei:
                continue

            marker = os.path.join(full_path, 'noises_cleanup_marker.txt')
            if os.path.exists(marker):
                try:
                    shutil.rmtree(full_path)
                    print(f"Cleaned up orphaned runtime: {name}")
                except Exception:
                    pass 
    except Exception as e:
        print(f"Cleanup warning: {e}")

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import torch
import torchaudio
import soundfile as sf

# --- Monkey-patch torchaudio.save to use soundfile directly ---
# torchaudio 2.10+ requires torchcodec for its default save backend.
# Since we don't need torchcodec, we bypass it by using soundfile (already installed).
_original_torchaudio_save = torchaudio.save
def _soundfile_save(filepath, src, sample_rate, **kwargs):
    """Save audio using soundfile instead of torchaudio's backend."""
    audio_np = src.cpu().float().numpy()
    # torchaudio format: (channels, samples) -> soundfile format: (samples, channels)
    if audio_np.ndim == 2:
        audio_np = audio_np.T
    sf.write(str(filepath), audio_np, sample_rate)
torchaudio.save = _soundfile_save
# --- End monkey-patch ---

from models.acestep import ACEStepModel
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
acestep = ACEStepModel()
stable_audio = StableAudioOpenModel()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Models are lazy-loaded on first generation request.
    # ACE-Step uses cpu_offload=True so it only puts one sub-model on GPU at a time (~8GB peak).
    # Stable Audio uses ~3GB VRAM.
    # With 12GB VRAM (RTX 5070), we load each on demand and rely on cpu_offload for ACE-Step.
    print("Backend ready. Models will be loaded on first request.")
    yield
    # Cleanup
    if acestep.pipe: del acestep.pipe
    if stable_audio.pipe: del stable_audio.pipe
    if torch.cuda.is_available():
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
    negative_prompt: str | None = None
    lyrics: str | None = None
    bpm: int | None = None
    key: str | None = None
    length: float | None = None
    variations: int = 1
    steps: int = 200
    guidance: float = 7.0
    seed: int | None = None
    scheduler_type: str = "euler"
    cfg_type: str = "apg"

@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        req_type = req.type.lower().replace("-", "")
        generated_files = []

        if "loop" in req_type:
            # --- STABLE AUDIO (Better for short loops & samples) ---
            duration = req.length if req.length else 2.5
            full_prompt = req.prompt
            if req.bpm: full_prompt += f", {req.bpm} bpm"
            if req.key: full_prompt += f", {req.key}"

            print(f"Generating Loop: {full_prompt}, {duration}s")
            # Free ACE-Step VRAM before loading Stable Audio
            if acestep.is_loaded:
                acestep.unload()
            raw_results = stable_audio.generate(
                prompt=full_prompt,
                negative_prompt=req.negative_prompt or "",
                duration_seconds=duration,
                num_inference_steps=req.steps,
                guidance_scale=req.guidance,
                seed=req.seed,
            )
            for i, (audio, sr) in enumerate(raw_results):
                audio = normalize_audio(audio, target_db=-10.0)
                audio = fade_audio(audio, sr, fade_out_ms=100)
                bpm_part = f"_{req.bpm}bpm" if req.bpm else ""
                safe_key = (req.key or 'Key').replace(" ", "_")
                filename = get_next_filename(LOOPS_DIR, f"loop{bpm_part}_{safe_key}")
                path = LOOPS_DIR / filename
                save_wav(audio, sr, path)
                generated_files.append({"file": filename, "path": str(path)})
            
            # Unload Stable Audio immediately after generation to free GPU memory
            stable_audio.unload()

        else:
            # --- ACE-STEP (Better for full songs with vocals) ---
            duration = req.length if req.length else 30.0
            full_prompt = req.prompt
            if req.key: full_prompt += f", {req.key}"

            print(f"Generating Full Song: {full_prompt}, {duration}s")
            # Free Stable Audio VRAM before loading ACE-Step
            if stable_audio.is_loaded:
                stable_audio.unload()
            raw_results = acestep.generate(
                prompt=full_prompt,
                lyrics=req.lyrics or "",
                duration_seconds=duration,
                steps=req.steps,
                guidance_scale=req.guidance,
                seed=req.seed,
                scheduler_type=req.scheduler_type,
                cfg_type=req.cfg_type,
            )
            for i, (audio, sr) in enumerate(raw_results):
                audio = normalize_audio(audio, target_db=-10.0)
                audio = fade_audio(audio, sr, fade_out_ms=2000)
                filename = get_next_filename(ONESHOTS_DIR, "song")
                path = ONESHOTS_DIR / filename
                save_wav(audio, sr, path)
                generated_files.append({"file": filename, "path": str(path)})
            
            # Unload ACE-Step immediately after generation to free GPU memory
            acestep.unload()

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
    _clean_old_mei_dirs()

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

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import torch
from contextlib import asynccontextmanager

from models.musicgen import MusicGenModel
from models.stable_audio import StableAudioOpenModel
from audio.postprocess import normalize_audio, fade_audio
from audio.utils import save_wav, get_next_filename
from config import LOOPS_DIR, ONESHOTS_DIR

# Our heavy lifting AI models live here
musicgen = MusicGenModel()
stable_audio = StableAudioOpenModel()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fire up the engines! Load models to GPU immediately.
    try:
        musicgen.load()
        stable_audio.load()
        # acestep.load() # Start lazily for now to save VRAM
    except Exception as e:
        print(f"Error loading models: {e}")
    yield
    # Clean up after ourselves so your PC doesn't explode.
    if musicgen.pipe:
        del musicgen.pipe
    if stable_audio.pipe:
        del stable_audio.pipe
    # if acestep.pipe:
    #      del acestep.pipe
    torch.cuda.empty_cache()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    # advanced params
    negative_prompt: str | None = None
    steps: int = 20
    guidance: float = 3.5
    seed: int | None = None
    temperature: float = 1.0
    top_k: int = 250


@app.post("/generate")
async def generate(req: GenerateRequest):
    try:
        req_type = req.type.lower().replace("-", "") # normalize "one-shot" -> "oneshot" (because I always forget the dash)
        generated_files = []

        if "loop" in req_type:
            # --- ACE-STEP (FAST LOOPS) ---
            # FUTURE TODO: Implement ACE-Step when Python 3.13 support arrives
            # if "ace" in req_type:
                # ... implementation commented out ...
             
            # --- MUSICGEN (DEFAULT LOOPS) ---
            # else:
            if True: # Always use MusicGen for now
                if "ace" in req_type: 
                     pass
                
                bpm = req.bpm if req.bpm else 120
                
                # If the length is tiny, we probably mean bars, not seconds.
                bars = req.length if req.length else 2
                duration_sec = (60 / bpm) * (bars * 4)
                
                full_prompt = f"{req.prompt}, {bpm} bpm"
                if req.key:
                    full_prompt += f", {req.key}"

                print(f"Generating Loop: {full_prompt}, duration: {duration_sec}s")
                
                raw_results = musicgen.generate(
                    prompt=full_prompt, 
                    duration_seconds=duration_sec, 
                    variations=req.variations,
                    guidance_scale=req.guidance,
                    temperature=req.temperature,
                    top_k=req.top_k,
                    seed=req.seed
                )

            for _, (audio, sr) in enumerate(raw_results):
                # 1. Normalize (keep it chill at -10dB for dynamics)
                audio = normalize_audio(audio, target_db=-10.0)
                # 2. Tiny little fade to stop those annoying clicks at the loop point
                audio = fade_audio(audio, sr, fade_out_ms=2.0)
                
                safe_key = (req.key or 'Key').replace(" ", "_")
                filename = get_next_filename(LOOPS_DIR, f"loop_{int(bpm)}bpm_{safe_key}")
                path = LOOPS_DIR / filename
                rel_path = save_wav(audio, sr, path)
                generated_files.append({"file": filename, "path": str(path)})

        else:
            # --- STABLE AUDIO (ONESHOTS) ---
            duration = req.length if req.length else 2.5
            
            full_prompt = req.prompt
            if req.key:
                full_prompt += f", {req.key}"

            print(f"Generating One-shot: {full_prompt}")
            
            raw_results = stable_audio.generate(
                prompt=full_prompt, 
                duration_seconds=duration, 
                variations=req.variations,
                num_inference_steps=req.steps, 
                guidance_scale=req.guidance,
                seed=req.seed
            )

            for _, (audio, sr) in enumerate(raw_results):
                # Normalize (keep it chill at -10dB) and slight fade out to prevent clicks
                audio = normalize_audio(audio, target_db=-10.0)
                audio = fade_audio(audio, sr, fade_out_ms=300.0)

                safe_key = (req.key or 'Key').replace(" ", "_")
                filename = get_next_filename(ONESHOTS_DIR, f"oneshot_{safe_key}")
                path = ONESHOTS_DIR / filename
                rel_path = save_wav(audio, sr, path)
                generated_files.append({"file": filename, "path": str(path)})

        if not generated_files:
            raise HTTPException(500, "Generation failed")

        return {
            "status": "success",
            "files": generated_files,
            "path": generated_files[0]["path"] # Return first path for simplicity to match spec
        }

    except Exception as e:
        print(f"Error during generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    import sys
    import os
    import signal
    import atexit
    import threading

    def force_shutdown():
        """Nuclear option: Kill entire process tree on Windows."""
        print("Force shutdown initiated...")
        try:
            import subprocess
            pid = os.getpid()
            # taskkill /T kills the process tree (all children)
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
        except Exception as e:
            print(f"Force shutdown error: {e}")
        finally:
            os._exit(0)

    def signal_handler(signum, frame):
        """Handle termination signals gracefully."""
        print(f"Received signal {signum}. Shutting down...")
        force_shutdown()

    # Register signal handlers (Windows supports SIGTERM, SIGINT, SIGBREAK)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    if sys.platform == "win32":
        signal.signal(signal.SIGBREAK, signal_handler)

    # Robust Parent Death Detection via stdin monitoring
    def watch_stdin():
        """Watch for parent death by monitoring stdin closure."""
        try:
            if sys.stdin:
                while True:
                    line = sys.stdin.readline()
                    if not line:  # EOF means parent closed the pipe
                        break
        except Exception:
            pass
        print("Parent process closed stdin. Shutting down backend.")
        force_shutdown()

    # Start stdin watcher in background
    watcher = threading.Thread(target=watch_stdin, daemon=True)
    watcher.start()

    # Register cleanup on normal exit too
    atexit.register(lambda: print("Backend exiting normally."))

    uvicorn.run(app, host="127.0.0.1", port=8000)

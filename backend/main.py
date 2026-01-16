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

# Global model instances
musicgen = MusicGenModel()
stable_audio = StableAudioOpenModel()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # load everything to GPU at startup
    try:
        musicgen.load()
        stable_audio.load()
        # acestep.load() # Start lazily for now to save VRAM
    except Exception as e:
        print(f"Error loading models: {e}")
    yield
    # clear vram
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
        req_type = req.type.lower().replace("-", "") # normalize "one-shot" -> "oneshot" hehe
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
                
                # assume bars if length is small (e.g. < 32)
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
                # 1. normalize (softer -10dB to allow dynamic range)
                audio = normalize_audio(audio, target_db=-10.0)
                # 2. tiny fade to avoid clicks
                audio = fade_audio(audio, sr, fade_out_ms=2.0)
                
                filename = get_next_filename(LOOPS_DIR, f"loop_{int(bpm)}bpm_{req.key or 'Key'}")
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
                # Normalize (lower volume) and slight fade out to prevent clicks
                audio = normalize_audio(audio, target_db=-10.0)
                audio = fade_audio(audio, sr, fade_out_ms=300.0)

                filename = get_next_filename(ONESHOTS_DIR, f"oneshot_{req.key or 'Key'}")
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
    uvicorn.run(app, host="127.0.0.1", port=8000)

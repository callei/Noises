import os
import tempfile
import torch
import soundfile as sf
import numpy as np
from typing import List, Tuple, Optional
from config import DEVICE


class ACEStepModel:
    def __init__(self):
        self.pipe = None
        self.device = DEVICE
        self.sample_rate = 48000  # ACE-Step native output sample rate
        self.is_loaded = False
        self.dtype = "bfloat16" if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else "float32"

    def load(self):
        if self.is_loaded and self.pipe is not None:
            return

        try:
            print(f"Loading ACE-Step ({self.dtype})...")
            from acestep.pipeline_ace_step import ACEStepPipeline

            # cpu_offload=True: moves model parts to CPU when not in use (~8GB peak VRAM)
            # overlapped_decode=True: more memory-efficient decoding for longer audio
            self.pipe = ACEStepPipeline(
                dtype=self.dtype,
                torch_compile=False,  # Enable on Linux/WSL for speed
                cpu_offload=True,
                overlapped_decode=True,
            )
            # The pipeline auto-downloads models from HuggingFace
            # (ACE-Step/ACE-Step-v1-3.5B) to ~/.cache/ace-step/checkpoints
            # if not already present. Loading checkpoint is deferred to first __call__.

            self.is_loaded = True
            print(f"ACE-Step loaded on {self.device} (cpu_offload=True).")

        except ImportError:
            print("ACE-Step not found. Install with: pip install git+https://github.com/ace-step/ACE-Step.git")
            self.is_loaded = False
            raise
        except Exception as e:
            print(f"Error loading ACE-Step: {e}")
            self.is_loaded = False
            raise

    def unload(self):
        """Free GPU/CPU memory when switching to another model."""
        if self.pipe is not None:
            # Clean up internal model references
            if hasattr(self.pipe, 'cleanup_memory'):
                self.pipe.cleanup_memory()
            del self.pipe
            self.pipe = None
        self.is_loaded = False
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("ACE-Step memory released.")

    def generate(
        self,
        prompt: str,
        lyrics: str = "",
        duration_seconds: float = 30.0,
        steps: int = 60,
        guidance_scale: float = 15.0,
        seed: Optional[int] = None,
        scheduler_type: str = "euler",
        cfg_type: str = "apg",
    ) -> List[Tuple[np.ndarray, int]]:
        """
        Generate music with ACE-Step.
        
        Parameters:
        - prompt: Main description (tags, genres, scene descriptions)
        - lyrics: Use structure tags like [verse], [chorus], [bridge]
        - steps: 60 default, 27-40 for faster generation
        - guidance_scale: 15.0 default (higher = more prompt adherence)
        - scheduler_type: "euler" recommended
        - cfg_type: "apg" (Adaptive Prompt Guidance) recommended

        Returns a list of (audio_ndarray, sample_rate) tuples.
        Audio is (samples, channels) float32 numpy array at 48kHz stereo.
        """
        if not self.is_loaded or self.pipe is None:
            self.load()

        try:
            print(f"Generating '{prompt}' ({duration_seconds}s) with ACE-Step...")

            # ACE-Step pipeline saves files and returns paths.
            # We save to a temp dir, then read back the audio for our own post-processing.
            with tempfile.TemporaryDirectory(prefix="noises_ace_") as tmp_dir:
                output = self.pipe(
                    prompt=prompt,
                    lyrics=lyrics or "",
                    audio_duration=duration_seconds,
                    infer_step=steps,
                    guidance_scale=guidance_scale,
                    manual_seeds=[seed] if seed is not None else None,
                    scheduler_type=scheduler_type,
                    cfg_type=cfg_type,
                    save_path=tmp_dir,
                    batch_size=1,
                )

                # output = ["/path/to/output_0.wav", ..., {params_json_dict}]
                # Last element is always the params dict
                audio_paths = [p for p in output if isinstance(p, str) and os.path.isfile(p)]

                results = []
                for audio_path in audio_paths:
                    # Use soundfile directly to avoid torchaudio/torchcodec backend issues
                    audio_np, sr = sf.read(audio_path)  # Returns (samples, channels) float64
                    audio_np = audio_np.astype(np.float32)
                    results.append((audio_np, sr))

                if not results:
                    raise RuntimeError("ACE-Step produced no audio output")

                print(f"Generated {len(results)} sample(s) with ACE-Step at {self.sample_rate}Hz.")
                return results

        except Exception as e:
            print(f"Error generating with ACE-Step: {e}")
            raise

import torch
import numpy as np
from typing import List, Tuple, Optional, Callable
from diffusers.pipelines.stable_audio.pipeline_stable_audio import StableAudioPipeline
from config import DEVICE


class StableAudioOpenModel:
    def __init__(self):
        self.pipe = None
        self.device = DEVICE
        self.sample_rate = 44100
        self.is_loaded = False

    def load(self):
        if self.is_loaded and self.pipe is not None:
            return

        try:
            print("Loading Stable Audio Open...")
            self.pipe = StableAudioPipeline.from_pretrained(
                "stabilityai/stable-audio-open-1.0",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            )
            self.pipe = self.pipe.to(self.device)

            if self.device == "cuda":
                self.pipe.enable_attention_slicing()

            self.is_loaded = True
            print(f"Stable Audio loaded on {self.device}.")

        except Exception as e:
            print(f"Error loading Stable Audio: {e}")
            self.is_loaded = False
            raise

    def generate(
        self,
        prompt: str,
        duration_seconds: float = 2.0,
        variations: int = 1,
        num_inference_steps: int = 150,
        guidance_scale: float = 7.0,
        seed: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Tuple[np.ndarray, int]]:

        if not self.is_loaded or self.pipe is None:
            self.load()

        try:
            generator = None
            if seed is not None:
                generator = torch.Generator(device=self.device).manual_seed(seed)

            callback_fn = None
            if progress_callback is not None:
                def _callback(step, timestep, latents):
                    progress_callback(step, num_inference_steps)
                callback_fn = _callback

            print(f"Generating '{prompt}' ({duration_seconds}s)...")

            output = self.pipe(
                prompt,
                audio_end_in_s=duration_seconds,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                num_waveforms_per_prompt=variations,
                generator=generator,
                callback=callback_fn,
                callback_steps=5,
            )

            audios = output.audios
            results = []
            for audio in audios:
                # Transpose if (channels, time) -> (time, channels)
                if audio.ndim == 2 and audio.shape[0] < audio.shape[1]:
                     audio = audio.T
                results.append((audio, self.sample_rate))

            print(f"Generated {len(results)} samples.")
            return results

        except Exception as e:
            print(f"Error generating: {e}")
            raise

    def unload(self):
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
            self.is_loaded = False

            if self.device == "cuda":
                torch.cuda.empty_cache()

            print("Stable Audio unloaded.")

    def get_info(self) -> dict:
        return {
            "model_name": "Stable Audio Open",
            "model_id": "stabilityai/stable-audio-open-1.0",
            "device": self.device,
            "is_loaded": self.is_loaded,
            "sample_rate": self.sample_rate,
            "dtype": "float16" if self.device == "cuda" else "float32",
        }

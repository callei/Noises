import torch
import numpy as np
from typing import List, Tuple, Optional, Callable
from transformers import MusicgenProcessor, MusicgenForConditionalGeneration
from config import DEVICE

class MusicGenModel:
    def __init__(self, model_size: str = "small"):
        self.pipe = None
        self.processor = None
        self.device = DEVICE
        self.model_size = model_size
        self.sample_rate = 32000
        self.is_loaded = False
        self.model_id = f"facebook/musicgen-{model_size}"

    def load(self):
        if self.is_loaded and self.pipe is not None:
            return

        try:
            print(f"Loading MusicGen {self.model_size}...")
            
            try:
                self.processor = MusicgenProcessor.from_pretrained(self.model_id, local_files_only=True)
            except OSError:
                # Fallback: if not downloaded, download it
                print("Processor not found locally, downloading...")
                self.processor = MusicgenProcessor.from_pretrained(self.model_id)
            
            try:
                self.pipe = MusicgenForConditionalGeneration.from_pretrained(
                    self.model_id,
                    dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    local_files_only=True
                )
            except OSError:
                print("Model weights not found locally, downloading...")
                self.pipe = MusicgenForConditionalGeneration.from_pretrained(
                    self.model_id,
                    dtype=torch.float16 if self.device == "cuda" else torch.float32
                )
            
            # This must happen regardless of how it was loaded
            self.pipe.to(self.device)
                
            if self.device == "cuda":
                # optimization
                self.pipe.generation_config.cache_implementation = "static"
                
            self.is_loaded = True
            print(f"MusicGen loaded on {self.device}.")
            
        except Exception as e:
            print(f"Error loading MusicGen: {e}")
            self.is_loaded = False
            raise

    def generate(
        self, 
        prompt: str, 
        duration_seconds: float = 5.0,
        variations: int = 1,
        guidance_scale: float = 3.0,
        temperature: float = 1.0,
        top_k: int = 250,
        top_p: float = 0.0,
        seed: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Tuple[np.ndarray, int]]:
        
        if not self.is_loaded or self.pipe is None:
            self.load()

        try:
            if seed is not None:
                torch.manual_seed(seed)
                if self.device == "cuda":
                    torch.cuda.manual_seed(seed)
            
            inputs = self.processor(
                text=[prompt] * variations,
                padding=True,
                return_tensors="pt"
            )
            # Explicitly move all input tensors to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # 50 tokens = 1 second. Add a small buffer (+10 tokens / 0.2s) to ensure we don't cut short.
            max_new_tokens = int(duration_seconds * 50) + 10
            print(f"Generating {variations} var(s) of '{prompt}' ({duration_seconds}s)...")
            
            total_steps = max_new_tokens
            current_step = [0]
            
            def _progress_callback(input_ids, scores):
                current_step[0] += 1
                if progress_callback and current_step[0] % 10 == 0:
                    progress_callback(current_step[0], total_steps)
                return False

            audio_values = self.pipe.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                guidance_scale=guidance_scale,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p if top_p > 0 else None,
                stopping_criteria=None,
            )
            
            audio_values = audio_values.cpu().numpy()
            
            # Removed internal normalization to avoid double-compression/distortion.
            # Post-processing is handled in main.py
            
            results = []
            for i in range(len(audio_values)):
                audio = audio_values[i]
                if audio.ndim > 1:
                    audio = audio.squeeze()
                results.append((audio, self.sample_rate))
            
            if progress_callback:
                progress_callback(total_steps, total_steps)
            
            print(f"Generated {len(results)} samples.")
            return results
            
        except Exception as e:
            print(f"Error generating: {e}")
            raise

    # maybe implement generate_with_melody here later if needed?? requires musicgen-melody model tho

    # Unused batch/unload/info methods could also be added here


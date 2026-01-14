import torch
import numpy as np
from typing import List, Tuple, Optional, Callable
from transformers import AutoProcessor, MusicgenForConditionalGeneration
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
            
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            self.pipe = MusicgenForConditionalGeneration.from_pretrained(
                self.model_id,
                dtype=torch.float16 if self.device == "cuda" else torch.float32
            )
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
            ).to(self.device)
            
            # 50 tokens = 1 second
            max_new_tokens = int(duration_seconds * 50)
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
            
            # normalize -1 to 1
            max_val = np.max(np.abs(audio_values))
            if max_val > 0:
                audio_values = audio_values / max_val
            
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

    def generate_with_melody(
        self,
        prompt: str,
        melody_audio: np.ndarray,
        melody_sample_rate: int,
        duration_seconds: float = 5.0,
        guidance_scale: float = 3.0,
        temperature: float = 1.0,
        seed: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Tuple[np.ndarray, int]]:
        
        if self.model_size != "melody":
            raise ValueError("Melody conditioning requires musicgen-melody model")
        
        if not self.is_loaded or self.pipe is None:
            self.load()

        try:
            if seed is not None:
                torch.manual_seed(seed)
                if self.device == "cuda":
                    torch.cuda.manual_seed(seed)
            
            inputs = self.processor( # this error is annoying
                text=[prompt],
                padding=True,
                return_tensors="pt"
            )
            
            melody_tensor = torch.from_numpy(melody_audio).float().unsqueeze(0)
            
            if melody_sample_rate != self.sample_rate:
                # needs torchaudio for resampling usually, but assuming input is correct or basic handling
                import torchaudio
                resampler = torchaudio.transforms.Resample(melody_sample_rate, self.sample_rate)
                melody_tensor = resampler(melody_tensor)
            
            inputs = inputs.to(self.device)
            melody_tensor = melody_tensor.to(self.device)
            
            max_new_tokens = int(duration_seconds * 50)
            print(f"Generating with melody: '{prompt}'...")
            
            audio_values = self.pipe.generate(
                **inputs,
                audio_values=melody_tensor,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                guidance_scale=guidance_scale,
                temperature=temperature
            )
            
            audio_values = audio_values.cpu().numpy()
            max_val = np.max(np.abs(audio_values))
            if max_val > 0:
                audio_values = audio_values / max_val
            
            results = [(audio_values[0], self.sample_rate)]
            
            if progress_callback:
                progress_callback(max_new_tokens, max_new_tokens)
            
            return results
            
        except Exception as e:
            print(f"Error generating with melody: {e}")
            raise

    def generate_batch(
        self,
        prompts: List[str],
        duration_seconds: float = 5.0,
        guidance_scale: float = 3.0,
        temperature: float = 1.0,
        top_k: int = 250,
        seed: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, int], None]] = None
    ) -> List[List[Tuple[np.ndarray, int]]]:
        if not self.is_loaded or self.pipe is None:
            self.load()
        
        all_results = []
        
        for idx, prompt in enumerate(prompts):
            current_seed = seed + idx if seed is not None else None
            
            prompt_progress = None
            if progress_callback:
                def _prompt_progress(step, total_steps):
                    progress_callback(idx, len(prompts), step)
                prompt_progress = _prompt_progress
            
            results = self.generate(
                prompt=prompt,
                duration_seconds=duration_seconds,
                variations=1,
                guidance_scale=guidance_scale,
                temperature=temperature,
                top_k=top_k,
                seed=current_seed,
                progress_callback=prompt_progress
            )
            
            all_results.append(results)
        
        return all_results

    def unload(self):
        if self.pipe is not None:
            del self.pipe
            self.pipe = None
        
        if self.processor is not None:
            del self.processor
            self.processor = None
        
        self.is_loaded = False
        
        if self.device == "cuda":
            torch.cuda.empty_cache()
        
        print("MusicGen unloaded.")

    def get_info(self) -> dict:
        return {
            "model_name": "MusicGen",
            "model_id": self.model_id,
            "model_size": self.model_size,
            "device": self.device,
            "is_loaded": self.is_loaded,
            "sample_rate": self.sample_rate,
            "dtype": "float16" if self.device == "cuda" else "float32",
            "supports_melody": self.model_size == "melody"
        }


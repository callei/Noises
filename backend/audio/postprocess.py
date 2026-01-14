import numpy as np
import librosa
from typing import Optional, Tuple

class AudioPostProcessor:
    @staticmethod
    def normalize_audio(
        audio: np.ndarray, 
        target_db: float = -3.0,
        method: str = "peak"
    ) -> np.ndarray:
        
        if len(audio) == 0:
            return audio
        
        if method == "peak":
            peak = np.max(np.abs(audio))
            if peak == 0:
                return audio
            target_linear = 10 ** (target_db / 20)
            scalar = target_linear / (peak + 1e-9)
        
        elif method == "rms":
            rms = np.sqrt(np.mean(audio**2))
            if rms == 0:
                return audio
            target_linear = 10 ** (target_db / 20)
            scalar = target_linear / (rms + 1e-9)
        
        else:
            raise ValueError(f"Unknown normalization method: {method}")
        
        normalized = audio * scalar
        
        # clip to prevent distortion
        normalized = np.clip(normalized, -1.0, 1.0)
        
        return normalized
    
    @staticmethod
    def fade_audio(
        audio: np.ndarray, 
        sr: int, 
        fade_in_ms: float = 5.0,
        fade_out_ms: Optional[float] = None,
        fade_type: str = "linear"
    ) -> np.ndarray:
        
        if len(audio) == 0:
            return audio
        
        if fade_out_ms is None:
            fade_out_ms = fade_in_ms
        
        fade_in_samples = int(sr * fade_in_ms / 1000)
        fade_out_samples = int(sr * fade_out_ms / 1000)
        
        max_fade = len(audio) // 2
        fade_in_samples = min(fade_in_samples, max_fade)
        fade_out_samples = min(fade_out_samples, max_fade)
        
        faded = audio.copy()
        
        if fade_type == "linear":
            fade_in_curve = np.linspace(0, 1, fade_in_samples)
            fade_out_curve = np.linspace(1, 0, fade_out_samples)
        
        elif fade_type == "exponential":
            fade_in_curve = np.exp(np.linspace(-5, 0, fade_in_samples))
            fade_in_curve = (fade_in_curve - fade_in_curve[0]) / (fade_in_curve[-1] - fade_in_curve[0])
            fade_out_curve = np.exp(np.linspace(0, -5, fade_out_samples))
            fade_out_curve = (fade_out_curve - fade_out_curve[-1]) / (fade_out_curve[0] - fade_out_curve[-1])
        
        elif fade_type == "logarithmic":
            fade_in_curve = np.log10(np.linspace(1, 10, fade_in_samples)) / np.log10(10)
            fade_out_curve = np.log10(np.linspace(10, 1, fade_out_samples)) / np.log10(10)
        
        else:
            raise ValueError(f"Unknown fade type: {fade_type}")
        
        # handle stereo
        if faded.ndim > 1:
            fade_in_curve = fade_in_curve[:, np.newaxis]
            fade_out_curve = fade_out_curve[:, np.newaxis]

        if fade_in_samples > 0:
            faded[:fade_in_samples] *= fade_in_curve
        if fade_out_samples > 0:
            faded[-fade_out_samples:] *= fade_out_curve
        
        return faded
    
    @staticmethod
    def trim_silence(
        audio: np.ndarray, 
        sr: int,
        top_db: int = 40,
        frame_length: int = 2048,
        hop_length: int = 512,
        margin: int = 0
    ) -> Tuple[np.ndarray, int, int]:
        
        if len(audio) == 0:
            return audio, 0, 0
        
        try:
            analysis_audio = audio
            if audio.ndim == 2:
                analysis_audio = audio.T

            _, indices = librosa.effects.trim(
                analysis_audio,
                top_db=top_db,
                frame_length=frame_length,
                hop_length=hop_length
            )
            
            trim_start = indices[0] if len(indices) > 0 else 0
            trim_end = len(audio) - indices[1] if len(indices) > 1 else 0
            
            if margin > 0:
                margin_samples = margin * hop_length
                trim_start = max(0, trim_start - margin_samples)
                trim_end = max(0, trim_end - margin_samples)
            
            trimmed = audio[trim_start:len(audio)-trim_end]
            
            return trimmed, trim_start, trim_end
        
        except Exception as e:
            print(f"Warning: Silence trimming failed: {e}")
            return audio, 0, 0
    
    @staticmethod
    def exact_loop_cut(
        audio: np.ndarray, 
        sr: int, 
        bpm: float,
        bars: int = 1,
        allow_stretch: bool = False
    ) -> np.ndarray:
        
        if len(audio) == 0:
            return audio
        
        beats = bars * 4
        duration_seconds = (60.0 / bpm) * beats
        samples_needed = int(duration_seconds * sr)
        
        if len(audio) == samples_needed:
            return audio
        
        if allow_stretch:
            stretch_ratio = len(audio) / samples_needed
            stretched = librosa.effects.time_stretch(audio, rate=stretch_ratio)
            
            if len(stretched) > samples_needed:
                return stretched[:samples_needed]
            elif len(stretched) < samples_needed:
                padding = samples_needed - len(stretched)
                return np.pad(stretched, (0, padding), mode='constant')
            return stretched
        
        else:
            if len(audio) > samples_needed:
                return audio[:samples_needed]
            else:
                padding = samples_needed - len(audio)
                
                # short fade before padding
                fade_samples = min(1024, len(audio) // 4)
                audio_faded = audio.copy()
                
                fade_out = np.linspace(1, 0, fade_samples)
                if audio_faded.ndim > 1:
                     fade_out = fade_out[:, np.newaxis]

                audio_faded[-fade_samples:] *= fade_out
                
                if audio_faded.ndim == 1:
                    return np.pad(audio_faded, (0, padding), mode='constant')
                else:
                    return np.pad(audio_faded, ((0, padding), (0, 0)), mode='constant')
    
    @staticmethod
    def remove_dc_offset(audio: np.ndarray) -> np.ndarray:
        if len(audio) == 0:
            return audio
        return audio - np.mean(audio)
    
    @staticmethod
    def apply_highpass_filter(
        audio: np.ndarray,
        sr: int,
        cutoff_hz: float = 20.0
    ) -> np.ndarray:
        
        if len(audio) == 0:
            return audio
        
        try:
            filtered = librosa.effects.preemphasis(audio, coef=0.97)
            return filtered
        except Exception as e:
            print(f"Warning: High-pass filtering failed: {e}")
            return audio
    
    @staticmethod
    def process_pipeline(
        audio: np.ndarray,
        sr: int,
        normalize: bool = True,
        normalize_db: float = -3.0,
        normalize_method: str = "peak",
        trim_silence: bool = True,
        trim_db: int = 40,
        fade: bool = True,
        fade_in_ms: float = 5.0,
        fade_out_ms: Optional[float] = None,
        fade_type: str = "linear",
        remove_dc: bool = True,
        highpass: bool = False,
        highpass_cutoff: float = 20.0,
        loop_cut: Optional[Tuple[float, int]] = None  # (bpm, bars)
    ) -> np.ndarray:
        
        processed = audio.copy()
        
        if remove_dc:
            processed = AudioPostProcessor.remove_dc_offset(processed)
        
        if trim_silence:
            processed, _, _ = AudioPostProcessor.trim_silence(
                processed, sr, top_db=trim_db
            )
        
        if highpass:
            processed = AudioPostProcessor.apply_highpass_filter(
                processed, sr, cutoff_hz=highpass_cutoff
            )
        
        if loop_cut is not None:
            bpm, bars = loop_cut
            processed = AudioPostProcessor.exact_loop_cut(
                processed, sr, bpm=bpm, bars=bars
            )
        
        if normalize:
            processed = AudioPostProcessor.normalize_audio(
                processed, target_db=normalize_db, method=normalize_method
            )
        
        if fade:
            processed = AudioPostProcessor.fade_audio(
                processed, sr, 
                fade_in_ms=fade_in_ms,
                fade_out_ms=fade_out_ms,
                fade_type=fade_type
            )
        
        return processed


# Compatibility wrappers
def normalize_audio(audio: np.ndarray, target_db: float = -3.0) -> np.ndarray:
    return AudioPostProcessor.normalize_audio(audio, target_db, method="peak")

def fade_audio(audio: np.ndarray, sr: int, fade_duration_ms: float = 5.0) -> np.ndarray:
    return AudioPostProcessor.fade_audio(audio, sr, fade_in_ms=fade_duration_ms, fade_out_ms=fade_duration_ms)

def trim_silence(audio: np.ndarray, top_db: int = 60) -> np.ndarray:
    """Trim silence from start and end."""
    trimmed, _, _ = AudioPostProcessor.trim_silence(audio, sr=44100, top_db=top_db)
    return trimmed

def exact_loop_cut(audio: np.ndarray, sr: int, bpm: float, bars: int = 1) -> np.ndarray:
    return AudioPostProcessor.exact_loop_cut(audio, sr, bpm, bars, allow_stretch=False)

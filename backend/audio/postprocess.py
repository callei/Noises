import numpy as np

def normalize_audio(audio: np.ndarray, target_db: float = -7.0) -> np.ndarray:
    """Normalize audio to a specific dB level to avoid clipping."""
    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio
    
    target_linear = 10 ** (target_db / 20)
    scalar = target_linear / (peak + 1e-9)
    normalized = audio * scalar
    return np.clip(normalized, -1.0, 1.0)

def fade_audio(audio: np.ndarray, sr: int, fade_in_ms: float = 0.0, fade_out_ms: float = 0.0) -> np.ndarray:
    """Apply a short fade in/out to prevent clicks."""
    if len(audio) == 0:
        return audio
    
    # Handle fade in
    if fade_in_ms > 0:
        fade_in_len = int(sr * (fade_in_ms / 1000.0))
        if fade_in_len > len(audio):
            fade_in_len = len(audio)
            
        if fade_in_len > 0:
            fade_in_curve = np.linspace(0.0, 1.0, fade_in_len)
            if audio.ndim == 2:
                fade_in_curve = fade_in_curve[:, np.newaxis]
            audio[:fade_in_len] *= fade_in_curve

    # Handle fade out
    if fade_out_ms > 0:
        fade_out_len = int(sr * (fade_out_ms / 1000.0))
        if fade_out_len > len(audio):
             fade_out_len = len(audio)
             
        if fade_out_len > 0:
            fade_out_curve = np.linspace(1.0, 0.0, fade_out_len)
            if audio.ndim == 2:
                fade_out_curve = fade_out_curve[:, np.newaxis]
            audio[-fade_out_len:] *= fade_out_curve
    
    return audio

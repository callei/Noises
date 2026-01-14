import soundfile as sf
import os
import numpy as np
from pathlib import Path

def save_wav(audio_data, sample_rate, path: Path):
    """Save audio data to WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Ensure audio is float32 (soundfile doesn't like float16 output from audioLDM/MusicGen)
    if audio_data.dtype == np.float16:
        audio_data = audio_data.astype(np.float32)
        
    sf.write(str(path), audio_data, sample_rate)
    return str(path)

def get_next_filename(directory: Path, prefix: str, extension: str = ".wav") -> str:
    """Get the next available filename like prefix_001.wav"""
    existing_files = list(directory.glob(f"{prefix}_*{extension}"))
    max_count = 0
    for f in existing_files:
        try:
            # Assuming format prefix_XXX.wav
            parts = f.stem.split('_')
            count = int(parts[-1])
            if count > max_count:
                max_count = count
        except ValueError:
            continue
    
    next_count = max_count + 1
    return f"{prefix}_{next_count:03d}{extension}"

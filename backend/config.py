import os
import sys
from pathlib import Path
import torch

# In production (Sidecar), we can't write to the app directory safely.
# We will use the User's Music directory for samples.
HOME_DIR = Path(os.path.expanduser("~"))

MUSIC_DIR = HOME_DIR / "Music" / "Noises"
BASE_DIR = MUSIC_DIR
SAMPLES_DIR = BASE_DIR / "samples"
LOOPS_DIR = SAMPLES_DIR / "loops"
ONESHOTS_DIR = SAMPLES_DIR / "oneshots"

# Ensure directories exist
LOOPS_DIR.mkdir(parents=True, exist_ok=True)
ONESHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Audio Settings
# Note: Each model uses its own native sample rate internally.
# ACE-Step outputs at 48kHz stereo, Stable Audio at 44.1kHz.
DEFAULT_SAMPLE_RATE = 48000
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

print(f"Device: {DEVICE}")
if DEVICE == "cuda":
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

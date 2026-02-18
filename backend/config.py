import os
import sys
from pathlib import Path
import torch

# ---------------------------------------------------------------------------
# CUDA Diagnostics (cuda_setup.ensure_torch_installed() already ran in main.py)
# ---------------------------------------------------------------------------
print(f"[Config] PyTorch {torch.__version__}  |  CUDA compiled: {torch.version.cuda}  |  CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    gpu = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    print(f"[Config] GPU: {gpu}  |  VRAM: {vram:.1f} GB")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[Config] Device: {DEVICE}")

# ---------------------------------------------------------------------------
# Paths — Use ~/Music/Noises so we never write inside the app bundle
# ---------------------------------------------------------------------------
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
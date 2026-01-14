import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = BASE_DIR / "samples"
LOOPS_DIR = SAMPLES_DIR / "loops"
ONESHOTS_DIR = SAMPLES_DIR / "oneshots"

LOOPS_DIR.mkdir(parents=True, exist_ok=True)
ONESHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Audio Settings
SAMPLE_RATE = 32000  # standard for MusicGen
DEVICE = "cuda" # Assumes GPU as requested

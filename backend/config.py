import os
import sys
from pathlib import Path

# In production (Sidecar), we can't write to the app directory safely.
# We will use the User's Music directory for samples.
HOME_DIR = Path(os.path.expanduser("~"))

if sys.platform == "win32":
    MUSIC_DIR = HOME_DIR / "Music" / "Noises"
else:
    MUSIC_DIR = HOME_DIR / "Music" / "Noises"

BASE_DIR = MUSIC_DIR
SAMPLES_DIR = BASE_DIR / "samples"
LOOPS_DIR = SAMPLES_DIR / "loops"
ONESHOTS_DIR = SAMPLES_DIR / "oneshots"

# Ensure directories exist
LOOPS_DIR.mkdir(parents=True, exist_ok=True)
ONESHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Audio Settings
SAMPLE_RATE = 32000  # standard for MusicGen
DEVICE = "cuda" # Assumes GPU as requested

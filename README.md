# Noises 🎵

A local AI music generator that lives on your desktop. No subscriptions, no cloud wait times, just noise.

<p float="left">
   <img src="screenshots/1.png" width="49%" />
   <img src="screenshots/2.png" width="49%" /> 
</p>


*(Drop a screenshot of your app here!)*

## What is this?

**Noises** is a desktop app I built to make generating AI samples and loops easier. It uses **Tauri** for a lightweight UI and **Python** to run the heavy AI models locally.

It currently supports:
*   **MusicGen (Meta):** For generating consistent, rhythmic loops.
*   **Stable Audio Open (Stability AI):** For generating textures, sound effects, and one-shots.

## Features

- 🎹 **Infinite Loops:** Create seamless loops at any BPM and Key.
- 💥 **One-Shots:** Need a "sci-fi laser impact" or "ambient rain texture"? Easy.
- 🏠 **100% Local:** Everything runs on your own hardware. Your prompts stay private.
- 🎛️ **Full Control:** Tweak Steps, Guidance Scale, Temperature, and more.

## How to Run it (The Easy Way)

1. Go to the [Releases](https://github.com/yourusername/noises/releases) page.
2. Download the installer (`Noises_Setup.exe`).
3. Run it, install it, make noise.

*Note: The first time you generate audio, it will download necessary models (~4GB) from HuggingFace. This connects to the internet once, then never again. If this does not work for you, please reach out so I can fix the issues!*

## Tech Stack (For the nerds)

*   **Frontend:** React, Tailwind CSS, Framer Motion
*   **Backend:** Python (FastAPI), PyTorch, HuggingFace Transformers & Diffusers
*   **Glue:** Rust (Tauri v2)

## Building from Source

If you want to hack on it yourself:

### Prerequisites
*   Node.js 18+
*   Python 3.10+
*   Rust
*   NVIDIA GPU (Recommended)

### Setup
```bash
# 1. Frontend stuff
cd frontend
npm install

# 2. Python stuff
# (Create a venv first!)
pip install -r backend/requirements.txt

# 3. Run it
# (In root folder)
npm run tauri dev
```

## Credits

Big thanks to the open source community for making this possible:
*   [Meta AI](https://github.com/facebookresearch/audiocraft) for MusicGen
*   [Stability AI](https://stability.ai/stable-audio) for Stable Audio Open
*   [Tauri](https://tauri.app) for the framework

## License

MIT License. Do whatever you want with the code, just credit me!
The generated audio is subject to the licenses of the respective models (CC-BY-NC for MusicGen/Stable Audio by default, check their repos for commercial use details).


# Noises - AI Music Generator

A local desktop application for generating AI music loops and sound effects using **MusicGen** and **Stable Audio Open**. Built with **Tauri**, **React**, and **Python**.

## Features for now: 

- **Loops:** Generate seamless music loops using Meta's MusicGen.
- **One-Shots:** Create sound effects and textures using Stability AI's Stable Audio Open.
- **Local Power:** Runs entirely on your machine (CUDA GPU recommended).
- **Control:** Adjust BPM, Key, Steps, Guidance, and more.

## Run it yourself (before I make the exe)

### Prerequisites
- Python 3.10+
- Node.js & npm
- Rust & Cargo
- *Recommended:* NVIDIA GPU with CUDA drivers

### Installation

1. **Install Python Dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Install Frontend Dependencies:**
   ```bash
   cd frontend
   npm install
   ```

3. **Run the App:**
   From the root folder:
   ```bash
   tauri dev
   ```


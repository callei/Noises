# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas = [('noises_cleanup_marker.txt', '.')]
binaries = []
hiddenimports = ['transformers', 'diffusers', 'uvicorn', 'fastapi', 'torchsde', 'psutil', 'acestep']

# ---------------------------------------------------------------------------
# PyTorch is NOT bundled.  It is downloaded at runtime by cuda_setup.py
# to %PROGRAMDATA%/Noises/torch_runtime/ with the correct CUDA variant
# for the user's GPU.  This keeps the installer small (~200 MB vs ~2.5 GB)
# and works across CUDA 11.8 / 12.x / 13.x automatically.
# ---------------------------------------------------------------------------

# Include pip so cuda_setup.py can call it as a library inside the frozen exe
tmp_ret = collect_all('pip')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

tmp_ret = collect_all('transformers')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('diffusers')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('torchsde')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('acestep')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# Collect py3langid data files (language detection model used by ACE-Step)
tmp_ret = collect_all('py3langid')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Exclude torch, torchaudio, and nvidia packages — they are runtime-installed.
# Also exclude heavy unused packages.
_excludes = [
    'torch', 'torchaudio', 'torchvision',
    'nvidia.cublas', 'nvidia.cuda_runtime', 'nvidia.cuda_nvrtc',
    'nvidia.cudnn', 'nvidia.cufft', 'nvidia.cusparse',
    'nvidia.cusolver', 'nvidia.nvjitlink', 'nvidia.nvtx',
    'nvidia.cuda_cupti', 'nvidia.nccl', 'nvidia.curand',
    'matplotlib', 'tkinter', 'IPython',
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_excludes,
    noarchive=False,
    optimize=0,
)

# Strip any nvidia / torch DLLs that sneak in transitively
a.binaries = [b for b in a.binaries
               if not b[0].lower().startswith('nvidia')
               and not b[0].lower().startswith('torch')]
a.datas = [d for d in a.datas
            if not d[0].lower().startswith('nvidia')
            and not d[0].lower().startswith(('torch/', 'torch\\'))]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='backend-x86_64-pc-windows-msvc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

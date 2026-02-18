"""
CUDA Setup & PyTorch Bootstrap
===============================
Two entry points, used at different times:

Install-time  (NSIS post-install → backend.exe --setup-torch):
    install_torch()
        1. Detects NVIDIA GPU via nvidia-smi
        2. Reads the CUDA driver version
        3. Picks the best PyTorch CUDA variant (≤ driver version)
        4. pip installs torch + torchaudio to %PROGRAMDATA%/Noises/torch_runtime/
    This runs ONCE, during app installation.  ~2.5 GB download.

Launch-time  (every normal app start):
    load_torch()
        1. Adds the cached torch directory to sys.path
        2. Registers DLL search directories
    This is instant — no GPU detection, no network, no pip.

If a user upgrades their GPU or CUDA drivers, they simply reinstall the app,
which re-runs install_torch() and picks the new best variant.

CUDA backward compatibility:
    NVIDIA drivers are backward-compatible.  A CUDA 13.0 driver can run
    code built with CUDA 12.1 libraries.  So we always pick the highest
    torch variant whose minimum CUDA version ≤ the driver's version.
"""

import os
import sys
import re
import shutil
import subprocess
from pathlib import Path


# ---------------------------------------------------------------------------
# Fix Windows console encoding issues
# ---------------------------------------------------------------------------

def _configure_console_encoding():
    """
    Reconfigure stdout/stderr to handle UTF-8 on Windows.
    Prevents UnicodeEncodeError when pip outputs Unicode characters.
    """
    if sys.platform == "win32":
        try:
            # Reconfigure stdout and stderr to use UTF-8 with error handling
            import io
            if sys.stdout is not None:
                sys.stdout = io.TextIOWrapper(
                    sys.stdout.buffer if hasattr(sys.stdout, 'buffer') else sys.stdout,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )
            if sys.stderr is not None:
                sys.stderr = io.TextIOWrapper(
                    sys.stderr.buffer if hasattr(sys.stderr, 'buffer') else sys.stderr,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )
        except Exception:
            # If reconfiguration fails, the _log function has fallback handling
            pass

_configure_console_encoding()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_APP_DATA = Path(os.environ.get("LOCALAPPDATA", Path.home()))
_PROGRAM_DATA = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
TORCH_CACHE_DIR = _PROGRAM_DATA / "Noises" / "torch_runtime"
_VARIANT_FILE = TORCH_CACHE_DIR / ".cuda_variant"
_SETUP_COMPLETE = TORCH_CACHE_DIR / ".setup_complete"

# Supported CUDA variants for PyTorch, newest first.
# Each entry: ((major, minor), pip_variant_tag, index_url)
TORCH_CUDA_VARIANTS = [
    ((13, 0), "cu130", "https://download.pytorch.org/whl/cu130"),
    ((12, 8), "cu128", "https://download.pytorch.org/whl/cu128"),
    ((12, 6), "cu126", "https://download.pytorch.org/whl/cu126"),
    ((12, 4), "cu124", "https://download.pytorch.org/whl/cu124"),
    ((12, 1), "cu121", "https://download.pytorch.org/whl/cu121"),
    ((11, 8), "cu118", "https://download.pytorch.org/whl/cu118"),
]


# ---------------------------------------------------------------------------
# Logging  (stdout + file at %LOCALAPPDATA%/Noises/setup.log)
# ---------------------------------------------------------------------------

_LOG_FILE = _APP_DATA / "Noises" / "setup.log"


def _log(msg: str):
    """Print to stdout and append to persistent log file."""
    # Handle console encoding issues on Windows (cp1252 can't encode all Unicode)
    try:
        print(msg)
    except UnicodeEncodeError:
        # Fallback: encode with errors='replace' to substitute problematic chars
        try:
            print(msg.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8'))
        except Exception:
            # Last resort: just write to log file
            pass
    
    # Always write to log file with UTF-8 encoding
    try:
        _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CUDA / GPU detection  (no torch import — only stdlib + nvidia-smi)
# ---------------------------------------------------------------------------

def _find_nvidia_smi() -> str | None:
    """
    Find nvidia-smi executable.  Searches PATH first, then common Windows
    locations (needed because NSIS installer context has a limited PATH).
    """
    # 1. Standard PATH lookup
    found = shutil.which("nvidia-smi")
    if found:
        return found

    # 2. System32 — always present when NVIDIA drivers are installed
    sys32 = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"),
        "System32", "nvidia-smi.exe",
    )
    if os.path.isfile(sys32):
        return sys32

    # 3. NVIDIA Corporation folder (older driver installs)
    nvsmi = os.path.join(
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        "NVIDIA Corporation", "NVSMI", "nvidia-smi.exe",
    )
    if os.path.isfile(nvsmi):
        return nvsmi

    return None


def _parse_version(version_str: str) -> tuple:
    """Parse '13.0' → (13, 0)."""
    parts = version_str.strip().split(".")
    return tuple(int(p) for p in parts[:2])


def detect_nvidia_gpu() -> str | None:
    """Return GPU name if an NVIDIA GPU is present, else None."""
    nvsmi = _find_nvidia_smi()
    if not nvsmi:
        _log("[Setup] nvidia-smi not found in PATH or common locations.")
        return None
    try:
        r = subprocess.run(
            [nvsmi, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        _log(f"[Setup] nvidia-smi execution failed: {e}")
    return None


def detect_cuda_version() -> str | None:
    """
    Detect the maximum CUDA version supported by the installed NVIDIA driver.
    Parses the 'CUDA Version: XX.X' line from nvidia-smi output.
    """
    nvsmi = _find_nvidia_smi()
    if not nvsmi:
        return None
    try:
        r = subprocess.run(
            [nvsmi], capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            m = re.search(r"CUDA Version:\s*([\d.]+)", r.stdout)
            if m:
                return m.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        _log(f"[Setup] nvidia-smi execution failed: {e}")
    return None


def get_best_torch_variant(cuda_version_str: str):
    """
    Given a CUDA driver version string (e.g. '13.0'), return the best
    matching (variant_tag, index_url) for torch.

    Returns (None, None) if the driver is too old.
    """
    cuda_ver = _parse_version(cuda_version_str)
    for min_ver, variant, url in TORCH_CUDA_VARIANTS:
        if cuda_ver >= min_ver:
            return variant, url
    return None, None


# ---------------------------------------------------------------------------
# Torch availability checks  (safe — catch ImportError)
# ---------------------------------------------------------------------------

def _prepare_torch_environment(base: Path):
    """
    Prepare the environment for PyTorch import by setting critical
    environment variables and pre-loading DLL directories.
    This must be called BEFORE any attempt to import torch.
    """
    if sys.platform != "win32":
        # For non-Windows, just add to path
        cache_str = str(base)
        if cache_str not in sys.path:
            sys.path.insert(0, cache_str)
        return
    
    # Set environment variables that torch/CUDA need
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    
    # Ensure the cache is in Python path first
    cache_str = str(base)
    if cache_str not in sys.path:
        sys.path.insert(0, cache_str)
    
    # Also add to PYTHONPATH for good measure
    python_path = os.environ.get("PYTHONPATH", "")
    if cache_str not in python_path:
        os.environ["PYTHONPATH"] = cache_str + os.pathsep + python_path if python_path else cache_str
    
    # Add critical DLL directories to PATH so Windows LoadLibrary can find them
    # This is essential because Python's import system uses LoadLibrary, not LoadLibraryEx
    dll_paths_to_add = [
        base / "torch" / "lib",  # Main torch DLLs
        base / "torch" / "bin",  # Torch binaries
        base,                     # torch_runtime root
    ]
    
    # Also add _MEIPASS if in frozen mode (for python3.dll)
    if hasattr(sys, '_MEIPASS'):
        dll_paths_to_add.insert(0, Path(sys._MEIPASS))
    
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []
    
    # Prepend our paths to ensure they're searched first
    for dll_path in dll_paths_to_add:
        dll_str = str(dll_path)
        if dll_str not in path_parts:
            path_parts.insert(0, dll_str)
    
    os.environ["PATH"] = os.pathsep.join(path_parts)
    _log(f"[Setup] Updated PATH with {len(dll_paths_to_add)} critical directories")
    
    # Register DLL directories
    _register_dll_directories(base)
    
    # Pre-load critical DLLs in the correct order using ctypes
    # This ensures dependencies are loaded before torch_python.dll tries to load them
    _preload_torch_dlls(base)


def _preload_torch_dlls(base: Path):
    """
    Explicitly pre-load PyTorch DLLs in dependency order.
    This solves WinError 126 issues where Windows can't find DLL dependencies.
    """
    if sys.platform != "win32":
        return
    
    import ctypes
    torch_lib = base / "torch" / "lib"
    if not torch_lib.exists():
        return
    
    # First, ensure Python DLL is accessible (critical for torch_python.dll)
    _ensure_python_dll_accessible()
    
    # Pre-load MSVC runtime DLLs (often needed by torch_python.dll)
    _preload_msvc_runtime_dlls()
    
    # Load ALL DLLs in torch/lib in dependency order.
    # Priority DLLs loaded first, torch_python.dll loaded LAST.
    priority_prefixes = [
        "cudart64", "cublas64", "cublasLt64", "cudnn64", "cudnn_",
        "cufft64", "cufftw64", "curand64", "cusolver64", "cusolverMg64",
        "cusparse64", "nvrtc", "nvJitLink", "nvToolsExt", "nvperf",
        "cupti64", "zlibwapi", "libiomp5md", "libiompstubs5md",
        "caffe2", "shm",
        "c10.dll", "torch_global_deps", "torch_cpu", "torch.dll",
        "c10_cuda", "torch_cuda", "uv.dll",
    ]

    all_dlls = sorted(torch_lib.glob("*.dll"), key=lambda p: p.name.lower())
    _log(f"[Setup] Found {len(all_dlls)} DLLs in torch/lib")

    # Partition into priority and remaining (torch_python.dll goes last)
    priority = []
    remaining = []
    torch_python = None
    for dll in all_dlls:
        name_lower = dll.name.lower()
        if name_lower == "torch_python.dll":
            torch_python = dll
        elif any(name_lower.startswith(p.lower()) for p in priority_prefixes):
            priority.append(dll)
        else:
            remaining.append(dll)

    load_order = priority + remaining
    if torch_python:
        load_order.append(torch_python)

    loaded_count = 0
    failed_count = 0
    _log("[Setup] Pre-loading PyTorch DLLs...")

    for dll_path in load_order:
        try:
            ctypes.CDLL(str(dll_path))
            loaded_count += 1
            _log(f"[Setup]   ✓ Pre-loaded {dll_path.name}")
        except Exception as e:
            failed_count += 1
            _log(f"[Setup]   ✗ Failed to pre-load {dll_path.name}: {e}")

    _log(f"[Setup] Pre-loaded {loaded_count}/{loaded_count + failed_count} DLLs")


def _ensure_python_dll_accessible():
    """
    Ensure Python runtime DLL is accessible for torch_python.dll.
    torch_python.dll depends on the Python DLL (python3xx.dll).
    """
    import ctypes
    import sys
    
    _log("[Setup] Checking Python DLL availability...")
    
    # When running frozen, we need to find and load the Python DLL
    is_frozen = getattr(sys, 'frozen', False)
    
    if is_frozen:
        # Check _MEIPASS (PyInstaller temp extraction directory) first
        if hasattr(sys, '_MEIPASS'):
            meipass = Path(sys._MEIPASS)
            _log(f"[Setup]   Checking PyInstaller temp dir: {meipass}")
            python_dlls = list(meipass.glob("python*.dll"))
            loaded_any = False
            for python_dll in python_dlls:
                try:
                    handle = ctypes.WinDLL(str(python_dll))
                    _log(f"[Setup]   ✓ Loaded Python DLL from _MEIPASS: {python_dll.name}")
                    loaded_any = True
                except Exception as e:
                    _log(f"[Setup]   ✗ Could not load {python_dll.name}: {e}")
            # Add _MEIPASS to PATH so torch_python.dll can find Python DLLs
            meipass_str = str(meipass)
            if meipass_str not in os.environ.get("PATH", ""):
                os.environ["PATH"] = meipass_str + os.pathsep + os.environ.get("PATH", "")
            if loaded_any:
                return
        
        # Check exe directory
        exe_dir = Path(sys.executable).parent
        _log(f"[Setup]   Checking exe directory: {exe_dir}")
        python_dlls = list(exe_dir.glob("python*.dll"))
        for python_dll in python_dlls:
            try:
                ctypes.WinDLL(str(python_dll))
                _log(f"[Setup]   ✓ Loaded Python DLL from exe dir: {python_dll.name}")
                return
            except Exception as e:
                _log(f"[Setup]   ✗ Could not load {python_dll.name}: {e}")
    else:
        # In dev mode, Python DLL should already be loaded
        _log(f"[Setup]   ✓ Running in dev mode, Python DLL should be available")
        # But let's still try to explicitly load it
        import platform
        python_version = platform.python_version_tuple()
        python_dll_name = f"python{python_version[0]}{python_version[1]}.dll"
        
        # Try to find it in sys.base_prefix or sys.prefix
        for prefix in [sys.base_prefix, sys.prefix]:
            python_dll_path = Path(prefix) / python_dll_name
            if python_dll_path.exists():
                try:
                    ctypes.WinDLL(str(python_dll_path))
                    _log(f"[Setup]   ✓ Explicitly loaded {python_dll_name} from {prefix}")
                    return
                except Exception as e:
                    _log(f"[Setup]   ✗ Could not load {python_dll_path}: {e}")
        return
    
    # If we couldn't find Python DLL in frozen mode, check System32
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    _log(f"[Setup]   Checking System32: {system32}")
    python_dlls = list(system32.glob("python*.dll"))
    for python_dll in python_dlls:
        try:
            ctypes.WinDLL(str(python_dll))
            _log(f"[Setup]   ✓ Loaded Python DLL from System32: {python_dll.name}")
            return
        except Exception as e:
            _log(f"[Setup]   ✗ Could not load {python_dll.name}: {e}")
    
    _log(f"[Setup]   ⚠ Warning: Could not find Python DLL. This may cause import failures.")


def _preload_msvc_runtime_dlls():
    """
    Pre-load Microsoft Visual C++ runtime DLLs that torch_python.dll depends on.
    These are typically in System32 or bundled with the app.
    """
    import ctypes
    
    _log("[Setup] Checking for MSVC runtime DLLs...")
    
    # Common MSVC runtime DLLs needed by PyTorch
    msvc_dlls = [
        "vcruntime140.dll",
        "vcruntime140_1.dll", 
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "concrt140.dll",
    ]
    
    # Search locations
    search_paths = []
    
    # PyInstaller temp directory (if frozen)
    if hasattr(sys, '_MEIPASS'):
        search_paths.append(Path(sys._MEIPASS))
    
    # System32
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    search_paths.append(system32)
    
    # SysWOW64 for 32-bit DLLs on 64-bit system (unlikely but possible)
    syswow64 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "SysWOW64"
    if syswow64.exists():
        search_paths.append(syswow64)
    
    loaded_count = 0
    for dll_name in msvc_dlls:
        for search_path in search_paths:
            dll_path = search_path / dll_name
            if dll_path.exists():
                try:
                    ctypes.WinDLL(str(dll_path))
                    loaded_count += 1
                    _log(f"[Setup]   ✓ Pre-loaded {dll_name}")
                    break  # Found and loaded, move to next DLL
                except Exception as e:
                    _log(f"[Setup]   ⚠ Found but could not load {dll_name}: {e}")
                    # Continue searching in other paths
    
    if loaded_count > 0:
        _log(f"[Setup] Pre-loaded {loaded_count} MSVC runtime DLLs")


def _is_torch_importable() -> bool:
    try:
        import torch  # noqa: F811
        _log(f"[Setup] \u2713 Torch imported successfully from {torch.__file__}")
        return True
    except Exception as e:
        _log(f"[Setup] Torch import failed: {type(e).__name__}: {e}")
        import traceback
        _log(f"[Setup] Full traceback:")
        for line in traceback.format_exc().splitlines():
            _log(f"[Setup]   {line}")
        return False


def _torch_has_cuda() -> bool:
    """Return True if the importable torch was compiled with CUDA support."""
    try:
        import torch
        return torch.version.cuda is not None
    except (ImportError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# DLL registration (Windows)
# ---------------------------------------------------------------------------

def _find_system_cuda_paths() -> list[Path]:
    """
    Find system CUDA installations by checking:
    1. CUDA_PATH environment variable
    2. Common install locations
    3. Windows registry (if available)
    """
    cuda_paths = []
    
    # Check CUDA_PATH environment variable
    cuda_path_env = os.environ.get("CUDA_PATH")
    if cuda_path_env and os.path.isdir(cuda_path_env):
        cuda_paths.append(Path(cuda_path_env))
        _log(f"[Setup] Found CUDA via CUDA_PATH: {cuda_path_env}")
    
    # Check common CUDA installation paths
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    cuda_base = Path(program_files) / "NVIDIA GPU Computing Toolkit" / "CUDA"
    if cuda_base.exists():
        # Find all CUDA versions, prefer higher versions
        for version_dir in sorted(cuda_base.glob("v*"), reverse=True):
            if version_dir.is_dir():
                cuda_paths.append(version_dir)
                _log(f"[Setup] Found CUDA installation: {version_dir}")
    
    # Check for CUDA in NVIDIA Corporation path
    nvidia_corp = Path(program_files) / "NVIDIA Corporation"
    if nvidia_corp.exists():
        for cuda_dir in nvidia_corp.glob("*CUDA*"):
            if cuda_dir.is_dir():
                cuda_paths.append(cuda_dir)
                _log(f"[Setup] Found CUDA in NVIDIA Corporation: {cuda_dir}")
    
    return cuda_paths


def _find_nvidia_driver_paths() -> list[Path]:
    """
    Find NVIDIA driver DLL directories.
    """
    driver_paths = []
    
    # System32 contains some NVIDIA DLLs
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    if system32.exists():
        driver_paths.append(system32)
    
    # Check Program Files for NVIDIA driver components
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    nvidia_dirs = [
        Path(program_files) / "NVIDIA Corporation",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "NVIDIA Corporation",
    ]
    
    for nvidia_dir in nvidia_dirs:
        if nvidia_dir.exists():
            # Look for DLLs in NVIDIA subdirectories
            for subdir in nvidia_dir.rglob("*"):
                if subdir.is_dir() and any(subdir.glob("*.dll")):
                    driver_paths.append(subdir)
    
    return driver_paths


def _register_dll_directories(base: Path):
    """
    Register DLL search directories for torch and nvidia-* packages
    that live inside `base`.  This is the equivalent of the old
    rthook_cuda.py but for the runtime-installed cache.
    """
    if sys.platform != "win32":
        return

    dirs: list[str] = []
    seen = set()

    def add_dir(path: Path):
        """Add directory if it exists and hasn't been added yet."""
        if path.is_dir():
            path_str = str(path)
            if path_str not in seen:
                seen.add(path_str)
                dirs.append(path_str)

    # torch/lib  (torch_cuda.dll, c10_cuda.dll, …)
    add_dir(base / "torch" / "lib")
    
    # torch/bin (some versions put DLLs here)
    add_dir(base / "torch" / "bin")

    # PyInstaller _MEIPASS directory (contains python3.dll, python313.dll, etc.)
    # This is CRITICAL: torch_python.dll depends on the versioned Python DLL
    # (e.g. python313.dll) and PyTorch's LoadLibraryExW with 0x00001100 flags
    # only searches AddDllDirectory paths, NOT the PATH env var.
    if hasattr(sys, '_MEIPASS'):
        add_dir(Path(sys._MEIPASS))
    
    # Also add the directory containing the current Python executable
    # (in case we're not frozen, this ensures the Python DLL is findable)
    exe_dir = Path(sys.executable).parent
    add_dir(exe_dir)

    # Recursively find all directories containing DLLs in torch tree
    torch_dir = base / "torch"
    if torch_dir.is_dir():
        for subdir in torch_dir.rglob("*"):
            if subdir.is_dir() and any(subdir.glob("*.dll")):
                add_dir(subdir)

    # nvidia/<pkg>/lib/  and  nvidia/<pkg>/bin/
    nvidia_root = base / "nvidia"
    if nvidia_root.is_dir():
        for pkg_dir in nvidia_root.iterdir():
            if not pkg_dir.is_dir():
                continue
            add_dir(pkg_dir)  # Root of nvidia package
            add_dir(pkg_dir / "lib")
            add_dir(pkg_dir / "bin")
            # Recursively find all DLL directories in nvidia packages
            for subdir in pkg_dir.rglob("*"):
                if subdir.is_dir() and any(subdir.glob("*.dll")):
                    add_dir(subdir)

    # System CUDA installations (critical for CUDA DLLs)
    _log("[Setup] Searching for system CUDA...")
    for cuda_path in _find_system_cuda_paths():
        add_dir(cuda_path / "bin")
        add_dir(cuda_path / "lib" / "x64")
        add_dir(cuda_path / "libnvvp")
        # Also check for DLLs in cuda root and subdirectories
        for subdir in cuda_path.rglob("*"):
            if subdir.is_dir() and any(subdir.glob("*.dll")):
                add_dir(subdir)
    
    # NVIDIA driver paths (for cudart, etc.)
    _log("[Setup] Searching for NVIDIA driver DLLs...")
    for driver_path in _find_nvidia_driver_paths():
        add_dir(driver_path)

    _log(f"[Setup] Registering {len(dirs)} DLL directories...")
    success_count = 0
    for d in dirs:
        try:
            os.add_dll_directory(d)
            success_count += 1
            # Only log first 10 to avoid spam, but log CUDA/nvidia paths
            if success_count <= 10 or "cuda" in d.lower() or "nvidia" in d.lower():
                _log(f"[Setup]   ✓ {d}")
        except (OSError, AttributeError) as e:
            _log(f"[Setup]   ✗ {d}: {e}")
        # Always add to PATH as fallback
        if d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    
    if success_count > 10:
        _log(f"[Setup]   ... and {success_count - 10} more directories")
    
    # Diagnostic: Check for critical CUDA DLLs
    _log("[Setup] Checking for critical CUDA DLLs...")
    critical_dlls = ["cudart64_13.dll", "cudart64_12.dll", "cublas64_13.dll", "cublas64_12.dll"]
    for dll_name in critical_dlls:
        found = False
        for d in dirs:
            dll_path = Path(d) / dll_name
            if dll_path.exists():
                _log(f"[Setup]   ✓ Found {dll_name} in {d}")
                found = True
                break
        if not found:
            _log(f"[Setup]   ✗ {dll_name} not found in any registered directory")


def _find_matching_system_python() -> str | None:
    """
    Find a system Python whose major.minor version matches the frozen
    executable.  torch_python.dll is ABI-specific (e.g. links against
    python312.dll), so the pip install MUST use the same Python version
    that PyInstaller used to build the backend.
    """
    major = sys.version_info.major
    minor = sys.version_info.minor
    need = f"{major}.{minor}"
    _log(f"[Setup] Frozen Python version: {need}")

    # Candidate Python commands in preference order
    candidates: list[str] = []

    # Exact versioned commands first (most reliable)
    candidates.append(f"python{major}.{minor}")
    candidates.append(f"python{major}")
    candidates.append("python")
    candidates.append("python3")

    # Windows `py` launcher can target a version: py -3.12
    py_launcher = shutil.which("py")
    if py_launcher:
        candidates.insert(0, f"__py_launcher__{major}.{minor}")

    for cand in candidates:
        # Special handling for `py -X.Y`
        if cand.startswith("__py_launcher__"):
            ver_arg = f"-{cand.removeprefix('__py_launcher__')}"
            exe = py_launcher
            version_cmd = [exe, ver_arg, "-c",
                           "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"]
            pip_exe_prefix = [exe, ver_arg]
        else:
            exe = shutil.which(cand)
            if not exe:
                continue
            version_cmd = [exe, "-c",
                           "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"]
            pip_exe_prefix = [exe]

        try:
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            r = subprocess.run(
                version_cmd,
                capture_output=True, text=True, timeout=10,
                creationflags=creationflags,
            )
            found = r.stdout.strip()
            _log(f"[Setup] Candidate '{cand}' -> Python {found} ({exe})")
            if found == need:
                # Verify pip is available
                pip_check = pip_exe_prefix + ["-m", "pip", "--version"]
                rp = subprocess.run(
                    pip_check,
                    capture_output=True, text=True, timeout=10,
                    creationflags=creationflags,
                )
                if rp.returncode == 0:
                    _log(f"[Setup] \u2713 Using matching Python {found}: {' '.join(pip_exe_prefix)}")
                    return exe
                else:
                    _log(f"[Setup]   pip not available for {cand}")
            else:
                _log(f"[Setup]   Version mismatch: need {need}, got {found}")
        except Exception as e:
            _log(f"[Setup]   Could not query {cand}: {e}")

    _log(f"[Setup] \u2717 No matching Python {need} found on system")
    return None


# ---------------------------------------------------------------------------
# pip-based torch installer
# ---------------------------------------------------------------------------

def _install_torch(variant: str, index_url: str):
    """
    Download and install torch + torchaudio into TORCH_CACHE_DIR using pip.

    Works in both dev (pip as subprocess) and production (pip as library
    bundled in the PyInstaller exe).
    """
    # Clean any previous failed install
    if TORCH_CACHE_DIR.is_dir() and not _SETUP_COMPLETE.exists():
        _log("[Setup] Cleaning incomplete previous install …")
        shutil.rmtree(TORCH_CACHE_DIR, ignore_errors=True)

    TORCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    _log(f"[Setup] ┌──────────────────────────────────────────────────")
    _log(f"[Setup] │  Installing PyTorch ({variant})")
    _log(f"[Setup] │  Destination: {TORCH_CACHE_DIR}")
    _log(f"[Setup] │  Index: {index_url}")
    _log(f"[Setup] │")
    _log(f"[Setup] │  This is a ONE-TIME download (~2.5 GB).")
    _log(f"[Setup] │  Please wait — this may take several minutes.")
    _log(f"[Setup] └──────────────────────────────────────────────────")

    pip_args = [
        "install",
        "--target", str(TORCH_CACHE_DIR),
        "--index-url", index_url,
        "--upgrade",
        "--no-warn-conflicts",
        "torch", "torchaudio",
    ]

    installed = False
    is_frozen = getattr(sys, 'frozen', False)

    # Strategy 1: pip as a library (ONLY in dev mode, NOT in frozen executables)
    # PyInstaller can't properly bundle pip's internal dependencies
    if not is_frozen:
        try:
            from pip._internal.cli.main import main as pip_main
            exit_code = pip_main(pip_args)
            if exit_code != 0:
                raise RuntimeError(f"pip exited with code {exit_code}")
            installed = True
            _log("[Setup] ✓ Installed using pip library")
        except ImportError:
            pass
        except SystemExit as e:
            # pip sometimes calls sys.exit(); treat exit code 0 as success
            if e.code == 0:
                installed = True
                _log("[Setup] ✓ Installed using pip library")
            else:
                _log(f"[Setup] pip library call failed (exit {e.code})")

    # Strategy 2: pip via system Python (preferred for frozen executables)
    # CRITICAL: Must use a Python matching the frozen exe's version (e.g. 3.12)
    # because torch_python.dll links against the versioned Python DLL.
    if not installed:
        try:
            py = _find_matching_system_python()
            if py:
                cmd = [py, "-m", "pip"] + pip_args
                _log(f"[Setup] Running: {' '.join(cmd)}")
                # CREATE_NO_WINDOW prevents console window from appearing
                creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                r = subprocess.run(
                    cmd, 
                    text=True, 
                    capture_output=True, 
                    encoding='utf-8', 
                    errors='replace',
                    creationflags=creationflags
                )
                if r.returncode == 0:
                    installed = True
                    _log("[Setup] ✓ Installed using system Python")
                else:
                    _log(f"[Setup] System pip stderr: {r.stderr}")
        except Exception as exc:
            _log(f"[Setup] System pip failed: {exc}")

    # Strategy 3: pip as subprocess using sys.executable (works in dev / venv)
    if not installed:
        try:
            cmd = [sys.executable, "-m", "pip"] + pip_args
            _log(f"[Setup] Running: {' '.join(cmd)}")
            # CREATE_NO_WINDOW prevents console window from appearing
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            r = subprocess.run(
                cmd, 
                text=True, 
                capture_output=True, 
                encoding='utf-8', 
                errors='replace',
                creationflags=creationflags
            )
            if r.returncode == 0:
                installed = True
                _log("[Setup] ✓ Installed using pip subprocess")
            else:
                _log(f"[Setup] pip subprocess stderr: {r.stderr}")
        except Exception as exc:
            _log(f"[Setup] pip subprocess failed: {exc}")

    if not installed:
        raise RuntimeError(
            "Could not install PyTorch. Ensure you have an internet connection "
            "and try again.  If the problem persists, manually install:\n"
            f"  pip install torch torchaudio --index-url {index_url}"
        )

    # Write success markers
    _VARIANT_FILE.write_text(variant)
    _SETUP_COMPLETE.write_text("ok")
    _log(f"[Setup] PyTorch ({variant}) installed successfully.\n")
    
    # Diagnostic: List what was installed
    _log("[Setup] Installed packages:")
    for item in TORCH_CACHE_DIR.iterdir():
        if item.is_dir():
            _log(f"[Setup]   - {item.name}/")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install_torch():
    """
    INSTALL-TIME entry point.
    Called once by the NSIS installer (backend.exe --setup-torch).

    Detects GPU → picks variant → downloads torch to TORCH_CACHE_DIR.
    If torch is already cached and valid, this is a no-op.
    """

    # Already installed and valid? Skip.
    if (
        TORCH_CACHE_DIR.is_dir()
        and _SETUP_COMPLETE.exists()
        and (TORCH_CACHE_DIR / "torch").is_dir()
    ):
        cached = _VARIANT_FILE.read_text().strip() if _VARIANT_FILE.exists() else "?"
        _log(f"[Setup] PyTorch ({cached}) is already installed at {TORCH_CACHE_DIR}")
        _log("[Setup] To force reinstall, delete that folder and run again.")
        return

    # ── Detect GPU ──────────────────────────────────────────────────────
    _log("[Setup] Starting PyTorch installation …\n")

    gpu_name = detect_nvidia_gpu()
    if not gpu_name:
        raise RuntimeError(
            "No NVIDIA GPU detected.\n"
            "This application requires an NVIDIA GPU with up-to-date drivers.\n"
            "Download drivers: https://www.nvidia.com/drivers/"
        )
    _log(f"[Setup] GPU detected: {gpu_name}")

    cuda_version = detect_cuda_version()
    if not cuda_version:
        raise RuntimeError(
            "Could not detect CUDA driver version.\n"
            "Ensure your NVIDIA drivers are up to date.\n"
            "Download drivers: https://www.nvidia.com/drivers/"
        )
    _log(f"[Setup] CUDA driver version: {cuda_version}")

    variant, index_url = get_best_torch_variant(cuda_version)
    if not variant or not index_url:
        raise RuntimeError(
            f"Your CUDA driver ({cuda_version}) is too old.\n"
            f"Minimum supported: CUDA 11.8.\n"
            f"Update your drivers: https://www.nvidia.com/drivers/"
        )
    _log(f"[Setup] Best PyTorch variant: {variant}\n")

    # ── Download & install ──────────────────────────────────────────────
    _install_torch(variant, index_url)

    # ── Verify ──────────────────────────────────────────────────────────
    _log("[Setup] Verifying installation...")
    _prepare_torch_environment(TORCH_CACHE_DIR)

    if not _is_torch_importable():
        _log("[Setup] ✗ PyTorch import failed")
        raise RuntimeError(
            "PyTorch was installed but cannot be imported.\n"
            "This may indicate missing dependencies or incompatible CUDA drivers.\n"
            "Try deleting the cache and reinstalling:\n"
            f"  rmdir /s /q \"{TORCH_CACHE_DIR}\""
        )

    import torch
    _log(f"[Setup] ✓ PyTorch {torch.__version__} (CUDA {torch.version.cuda})")
    if torch.cuda.is_available():
        _log(f"[Setup] ✓ GPU: {torch.cuda.get_device_name(0)}")
    else:
        _log("[Setup] ⚠ Warning: CUDA device not available")
    _log("[Setup] Installation complete.\n")


def load_torch():
    """
    LAUNCH-TIME entry point.
    Called on every normal app startup from main.py.

    In dev mode:  torch is in the venv → no-op (already importable).
    In production: adds TORCH_CACHE_DIR to sys.path + registers DLLs.

    This does NO GPU detection, NO network calls, NO pip.  It's instant.
    """

    # ── Dev mode: torch already in venv ─────────────────────────────────
    if _is_torch_importable():
        if _torch_has_cuda():
            print("[Torch] Ready (CUDA).")
            return
        else:
            is_frozen = getattr(sys, "frozen", False)
            if not is_frozen:
                print("[Torch] WARNING: CPU-only torch in dev venv.")
                print("[Torch] Fix: pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126")
                return
            # Production but somehow CPU-only → fall through to cache

    # ── Production: load from cache ─────────────────────────────────────
    cache_valid = (
        TORCH_CACHE_DIR.is_dir()
        and _SETUP_COMPLETE.exists()
        and (TORCH_CACHE_DIR / "torch").is_dir()
    )

    if not cache_valid:
        # Cache missing — the installer hook likely failed.
        # Fall back to installing now (one-time first-launch recovery).
        _log("[Torch] PyTorch cache not found. Running first-time setup …")
        _log("[Torch] This is a one-time download (~2.5 GB). Please wait.")
        try:
            install_torch()
        except Exception as e:
            _log(f"[Torch] First-launch setup failed: {e}")
            raise RuntimeError(
                "PyTorch is not installed and automatic setup failed.\n"
                f"Error: {e}\n\n"
                "Please ensure you have:\n"
                "  1. An NVIDIA GPU with up-to-date drivers\n"
                "  2. An active internet connection\n"
                "Then reinstall Noises.\n"
                f"Log file: {_LOG_FILE}"
            ) from e

    # Add cache to sys.path and register DLL directories
    _prepare_torch_environment(TORCH_CACHE_DIR)

    if not _is_torch_importable():
        _log("[Torch] PyTorch import failed after DLL registration")
        raise RuntimeError(
            "PyTorch cache exists but cannot be loaded.\n"
            "This usually means CUDA dependencies are missing or incompatible.\n\n"
            "Troubleshooting steps:\n"
            f"  1. Check log for DLL paths: {_LOG_FILE}\n"
            f"  2. Delete cache: {TORCH_CACHE_DIR}\n"
            "  3. Reinstall Noises\n"
            f"\nLog file: {_LOG_FILE}"
        )

    cached = _VARIANT_FILE.read_text().strip() if _VARIANT_FILE.exists() else "?"
    print(f"[Torch] Ready ({cached}).")

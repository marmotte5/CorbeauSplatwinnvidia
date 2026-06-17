import platform
import os
import shutil
import subprocess
from pathlib import Path

def resolve_project_root() -> Path:
    """Finds project root relative to this script (app/core/system.py)"""
    return Path(__file__).resolve().parent.parent.parent

def is_apple_silicon():
    """Détecte si on est sur Apple Silicon"""
    return platform.system() == 'Darwin' and platform.machine() == 'arm64'


def get_optimal_threads():
    """Retourne le nombre optimal de threads pour Apple Silicon (P-cores) ou autres plateformes"""
    if is_apple_silicon():
        # Apple Silicon has heterogeneous P-cores (performance) + E-cores (efficiency).
        # For compute-heavy tasks (COLMAP, ffmpeg), we prefer P-cores only.
        # Try multiple sysctl keys in order of preference, as not all keys exist
        # on every macOS version or chip generation.
        for key in (
            "hw.perflevel0.logicalcpu",       # P-core logical count (primary)
            "hw.perflevel0.logicalcpu_max",   # P-core logical max (macOS 14+)
            "hw.perflevel0.physicalcpu",      # P-core physical count
            "hw.physicalcpu",                 # total physical cores (P+E)
        ):
            try:
                result = subprocess.run(
                    ["sysctl", "-n", key],
                    capture_output=True, text=True, timeout=2
                )
                if result.returncode == 0:
                    cores = int(result.stdout.strip())
                    if cores > 0:
                        # hw.physicalcpu includes E-cores; approximate P-only
                        if key == "hw.physicalcpu":
                            cores = max(1, cores // 2)
                        return cores
            except (ValueError, subprocess.SubprocessError, OSError):
                continue
        # Absolute fallback: os.cpu_count() includes both P and E logical cores;
        # divide by 2 as a conservative P-core estimate (M1: 8→4✓, M1Pro: 10→5≈,
        # M1Max: 10→5≈, M2Pro: 12→6≈, M3Max: 16→8≈, M4Max: 16→8≈).
        cpu_count = os.cpu_count() or 8
        return max(1, cpu_count // 2)
    return os.cpu_count() or 4

def resolve_binary(name):
    """
    Résoud le chemin d'un binaire en priorisant le dossier 'engines' local.
    Retourne le chemin absolu ou le nom si trouvé dans le PATH, sinon None.
    """
    # 1. Chercher dans le dossier engines à la racine du projet
    engines_dir = resolve_project_root() / "engines"
    
    local_path = engines_dir / name
    
    # Cas binaire direct
    if local_path.exists() and os.access(local_path, os.X_OK):
        return str(local_path)
        
    # Cas macOS .app bundle pour COLMAP
    if name == "colmap":
        colmap_app = engines_dir / "COLMAP.app" / "Contents" / "MacOS" / "colmap"
        if colmap_app.exists() and os.access(colmap_app, os.X_OK):
            return str(colmap_app)
            
    # 2. Chercher dans le PATH système
    return shutil.which(name)

def get_device() -> str:
    """Centralized device selection: mps, cuda, or cpu."""
    if is_apple_silicon():
        return "mps"
    if shutil.which("nvidia-smi") is not None:
        return "cuda"
    return "cpu"

def get_memory_info() -> dict:
    """Returns memory info for UMA/caching strategies via sysctl + vm_stat.

    On Apple Silicon (UMA), memory_pressure is the most reliable indicator
    since GPU and CPU share the same pool.
    """
    total = 0
    available = 0
    percent = 0.0

    # Total physical memory
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=2
        )
        total = int(result.stdout.strip()) if result.returncode == 0 else 0
    except (ValueError, subprocess.SubprocessError, OSError):
        pass

    # Available memory: use vm_stat to get free + inactive + speculative pages.
    # On Apple Silicon UMA, compressed/inactive pages are effectively "available"
    # since the memory compressor frees them on demand.
    if total > 0:
        try:
            result = subprocess.run(
                ["vm_stat"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                page_size = 16384  # Apple Silicon default page size
                pages = {}
                for line in result.stdout.splitlines():
                    if ":" in line:
                        key, val = line.split(":", 1)
                        key = key.strip().strip('"')
                        try:
                            pages[key] = int(val.strip().rstrip("."))
                        except ValueError:
                            pass
                # Page size detection
                if "page size of" in result.stdout:
                    for token in result.stdout.split():
                        try:
                            page_size = int(token)
                            break
                        except ValueError:
                            pass
                free_pages = pages.get("Pages free", 0)
                inactive_pages = pages.get("Pages inactive", 0)
                speculative_pages = pages.get("Pages speculative", 0)
                available_pages = free_pages + inactive_pages + speculative_pages
                available_bytes = available_pages * page_size
                # Clamp to total (vm_stat can report more than hw.memsize
                # if compression reclaims pages from other categories)
                available = min(available_bytes, total)
                percent = round(100.0 * (total - available) / total, 1)
        except (ValueError, subprocess.SubprocessError, OSError):
            pass

    return {"total": total, "available": available, "percent": percent}

def get_brush_build_mode() -> str:
    """Detect Brush build mode from engines/brush.version.

    Returns "release" for tagged versions (e.g. v0.3.0), "source" for
    source builds (e.g. 2a8c4f1-source), defaults to "release".
    """
    version_file = resolve_project_root() / "engines" / "brush.version"
    if version_file.exists():
        version = version_file.read_text().strip()
        if "source" in version:
            return "source"
    return "release"


def is_amx_available() -> bool:
    """Detect whether the Apple Matrix coprocessor (AMX) is available.

    AMX is present on all Apple Silicon chips (M1 and later) and is used
    automatically by Accelerate.framework for BLAS/LAPACK operations.
    No user-space configuration is needed — this is purely informational
    for feature gating and logging.
    """
    if not is_apple_silicon():
        return False
    # All Apple Silicon chips have AMX blocks.  The AMX instruction set
    # is accessed exclusively through Accelerate.framework (not directly
    # by user code), so there is no sysctl key to query.  We return True
    # for any arm64 Darwin system.
    return True


def has_neural_engine() -> bool:
    """Detect whether the Apple Neural Engine (ANE) is available.

    The Neural Engine is present on M1 and later Apple Silicon chips,
    as well as A12 Bionic and later iPhone/iPad SoCs.  It is used
    transparently by CoreML when the model and compute unit selection
    allow it (`.appleNeuralEngine`).

    On macOS, there is no official sysctl key to query ANE presence,
    so we check for Apple Silicon as a proxy (all M-series chips have one).
    """
    if not is_apple_silicon():
        return False
    # M1 and later all include a Neural Engine. The exact core count
    # varies (M1: 16-core, M2: 16-core, M3: 16-core, M4: 16-core,
    # M1 Pro/Max: 16-core, M2 Pro/Max: 16-core, M3 Pro/Max: 16-core,
    # M4 Pro/Max: 16-core). No user-space API exposes the count.
    return True


def check_dependencies():
    """Vérifie si les dépendances nécessaires sont installées"""
    missing = []
    
    # Check ffmpeg
    if resolve_binary('ffmpeg') is None:
        missing.append('ffmpeg')
        
    # Check colmap
    if resolve_binary('colmap') is None:
        missing.append('colmap')

    # Check send2trash
    import importlib.util
    if importlib.util.find_spec("send2trash") is None:
        missing.append('send2trash')

    return missing

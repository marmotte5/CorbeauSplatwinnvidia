"""Utility functions for dependency management — installers, checkers, helpers (Windows)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

from app.scripts.checksum_verifier import load_expected_checksums, verify_download

# ─────────────────────────────────────────────────────────────────────────────
# Config and requirements helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_config():
    """Loads config.json from project root/cwd"""
    p = Path("config.json")
    if p.exists():
        try: return json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load config.json: {e}")
    return {}


def relax_requirements(src, dst):
    """Refactor utils: Relax strict torch deps"""
    with open(src) as f_in, open(dst, 'w') as f_out:
        for line in f_in:
            if line.strip().startswith('torch==') or line.strip().startswith('torchvision=='):
                line = line.replace('==', '>=')
            f_out.write(line)


# ─────────────────────────────────────────────────────────────────────────────
# Version helpers (standalone functions)
# ─────────────────────────────────────────────────────────────────────────────

def get_remote_version(repo_url):
    """Gets the latest commit hash from the remote git repository"""
    try:
        output = subprocess.check_output(["git", "ls-remote", repo_url, "HEAD"], text=True).strip()
        if output:
            return output.split()[0]
    except Exception as e:
        print(f"Attention: Impossible de verifier la version distante pour {repo_url}: {e}")
    return None


def get_local_version(version_file: Path):
    if version_file.exists():
        try:
            return version_file.read_text().strip()
        except OSError:
            pass
    return None


def save_local_version(version_file: Path, version):
    if version:
        try:
            version_file.parent.mkdir(parents=True, exist_ok=True)
            version_file.write_text(version)
        except Exception as e:
            print(f"Attention: Impossible d'enregistrer la version locale: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Checkers
# ─────────────────────────────────────────────────────────────────────────────

def check_cargo():
    return shutil.which("cargo") is not None


def check_winget():
    """Returns True if the Windows Package Manager (winget) is available."""
    return shutil.which("winget") is not None


def check_node():
    return shutil.which("node") is not None and shutil.which("npm") is not None


def check_cmake_ninja():
    return shutil.which("cmake") is not None and shutil.which("ninja") is not None


# ─────────────────────────────────────────────────────────────────────────────
# Installers helpers
# ─────────────────────────────────────────────────────────────────────────────

def _winget_install(package_id: str, friendly_name: str) -> bool:
    """Installs a package via winget. Returns True on success."""
    if not check_winget():
        print(f"⚠️  winget introuvable — installez {friendly_name} manuellement.")
        return False
    print(f"Installing {friendly_name} via winget ({package_id})...")
    try:
        subprocess.check_call([
            "winget", "install", "-e", "--id", package_id,
            "--accept-source-agreements", "--accept-package-agreements",
        ])
        return True
    except (subprocess.CalledProcessError, OSError) as e:
        print(f"Error installing {friendly_name}: {e}")
        return False


def install_node_js():
    return _winget_install("OpenJS.NodeJS", "Node.js")


def install_build_tools():
    ok_cmake = _winget_install("Kitware.CMake", "CMake")
    ok_ninja = _winget_install("Ninja-build.Ninja", "Ninja")
    return ok_cmake and ok_ninja


def install_rust_toolchain():
    print("Installing Rust (cargo) via rustup-init.exe...")
    import tempfile
    import urllib.request
    try:
        rustup_path = Path(tempfile.mkstemp(suffix=".exe")[1])
        req = urllib.request.Request("https://win.rustup.rs/x86_64")
        with urllib.request.urlopen(req, timeout=30) as resp:
            rustup_path.write_bytes(resp.read())

        checksums = load_expected_checksums()
        if not verify_download(rustup_path, checksums.get("windows_rustup", "")):
            print("⚠️ rustup installer SHA256 mismatch (checksum key: windows_rustup). Continuing anyway.")

        subprocess.check_call([str(rustup_path), "-y", "--default-toolchain", "stable"])
        rustup_path.unlink(missing_ok=True)

        # Add to current path for this session
        cargo_bin = Path.home() / ".cargo" / "bin"
        if cargo_bin.exists():
            os.environ["PATH"] = str(cargo_bin) + os.pathsep + os.environ["PATH"]
            print("Rust installed and added to PATH.")
            return True
    except Exception as e:
        print(f"Error installing Rust: {e}")
    return False


def install_system_dependencies(check_only=False):
    """Ensures ffmpeg and a CUDA-enabled COLMAP are available on Windows."""
    from app.core.system import resolve_binary

    print("--- System Dependency Check (Windows) ---")
    missing = []
    if shutil.which("ffmpeg") is None:
        missing.append("ffmpeg")
    # COLMAP may live in a versioned install dir, not just PATH
    if resolve_binary("colmap") is None:
        missing.append("colmap")

    if not missing:
        print("✅ System dependencies present (ffmpeg, COLMAP).")
        return True

    print(f"Missing: {', '.join(missing)}")
    if check_only:
        print("ℹ️ Audit mode: automatic installation skipped.")
        if "colmap" in missing:
            print("    → COLMAP (CUDA): https://github.com/colmap/colmap/releases "
                  "(choose colmap-x64-windows-cuda.zip) and add its folder to PATH.")
        return False

    ok = True
    if "ffmpeg" in missing:
        if not _winget_install("Gyan.FFmpeg", "FFmpeg"):
            ok = False
    if "colmap" in missing:
        # COLMAP CUDA builds are not on winget; guide the user to the release zip.
        print("⚠️  COLMAP must be installed manually for CUDA support:")
        print("    https://github.com/colmap/colmap/releases → colmap-x64-windows-cuda.zip")
        print("    Extract it and add the folder (containing COLMAP.bat) to your PATH.")
        ok = False

    return ok

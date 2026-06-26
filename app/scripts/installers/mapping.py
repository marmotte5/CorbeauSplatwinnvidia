"""COLMAP and Glomap engine dependency installers (Windows/CUDA)."""
import os
import shutil
import subprocess
from pathlib import Path

from app.scripts.installers.base import EngineDependency
from app.scripts.installers.tools import check_cmake_ninja, install_build_tools


GLOMAP_REPO = "https://github.com/colmap/glomap.git"


class ColmapEngineDep(EngineDependency):
    """COLMAP on Windows — detected on PATH or in a known install folder.

    CUDA-enabled COLMAP is distributed as a pre-built zip on GitHub releases
    (colmap-x64-windows-cuda.zip). We don't auto-install it (no winget package),
    but we detect it and guide the user when it is missing.
    """
    ask_before_update = False

    def __init__(self):
        super().__init__("colmap")

    def is_installed(self) -> bool:
        from app.core.system import resolve_binary
        return resolve_binary("colmap") is not None

    def is_enabled_in_config(self, config: dict) -> bool:
        return True  # COLMAP is required by the core pipeline

    def get_local_version(self) -> str:
        from app.core.system import resolve_binary
        colmap = resolve_binary("colmap")
        if not colmap:
            return ""
        try:
            out = subprocess.check_output(
                [colmap, "--version"], text=True, stderr=subprocess.STDOUT, timeout=10
            ).strip()
            return out.splitlines()[0] if out else ""
        except (subprocess.SubprocessError, OSError):
            return ""

    def get_remote_version(self) -> str:
        return ""  # No auto-update for the manually installed CUDA build

    def install(self):
        if self.is_installed():
            return
        print("❌ COLMAP introuvable.")
        print("   Téléchargez la build CUDA : https://github.com/colmap/colmap/releases")
        print("   (colmap-x64-windows-cuda.zip), extrayez-la et ajoutez le dossier")
        print("   contenant COLMAP.bat à votre PATH, puis relancez.")


class GlomapEngineDep(EngineDependency):
    ask_before_update = True

    def __init__(self):
        super().__init__("glomap", GLOMAP_REPO)
        # Source code lives in a separate dir, not replacing the binary
        self.target_dir = self.engines_dir / "glomap-source"

    def is_enabled_in_config(self, config: dict) -> bool:
        return config.get("params", {}).get("use_glomap", False)

    def is_installed(self) -> bool:
        from app.core.system import resolve_binary
        return resolve_binary("glomap") is not None

    def install(self):
        if not check_cmake_ninja():
            if not install_build_tools():
                print("⚠️ CMake/Ninja requis pour compiler Glomap. Installez-les et relancez.")
                return

        self.update_git()
        source_dir = self.target_dir

        build_dir = source_dir / "build"
        if build_dir.exists():
            shutil.rmtree(str(build_dir))
        build_dir.mkdir(exist_ok=True)

        # GLOMAP fetches/builds its own COLMAP. On Windows we let CMake pick the
        # default (MSVC) generator; CUDA is auto-detected by COLMAP's CMake.
        cmake_args = ["cmake", "..", "-DCMAKE_BUILD_TYPE=Release", "-DFETCH_COLMAP=ON"]
        env = os.environ.copy()

        try:
            subprocess.check_call(cmake_args, cwd=str(build_dir), env=env)
            subprocess.check_call(
                ["cmake", "--build", ".", "--config", "Release"],
                cwd=str(build_dir), env=env,
            )
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"⚠️ Glomap build failed: {e}")
            return

        # Locate the built binary (glomap.exe on Windows)
        built_bin = None
        for pattern in ("glomap.exe", "glomap"):
            for found in build_dir.rglob(pattern):
                if found.is_file():
                    built_bin = found
                    break
            if built_bin:
                break

        if built_bin:
            dest = self.engines_dir / ("glomap.exe" if built_bin.suffix == ".exe" else "glomap")
            shutil.copy2(str(built_bin), str(dest))
            self.save_local_version(self.get_remote_version())

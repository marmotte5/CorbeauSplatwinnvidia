"""COLMAP and Glomap engine dependency installers."""
import os
import re
import sys
import json
import shutil
import subprocess
from pathlib import Path

from app.scripts.installers.base import EngineDependency
from app.scripts.installers.tools import check_cmake_ninja, check_xcode_tools, install_build_tools


GLOMAP_REPO = "https://github.com/colmap/glomap.git"


class ColmapBrewDep(EngineDependency):
    """COLMAP géré via Homebrew — vérifie la version et met à jour si nécessaire"""
    ask_before_update = True

    def __init__(self):
        super().__init__("colmap")

    def is_installed(self) -> bool:
        return shutil.which("colmap") is not None

    def is_enabled_in_config(self, config: dict) -> bool:
        return sys.platform == "darwin" and shutil.which("brew") is not None

    def get_local_version(self) -> str:
        try:
            out = subprocess.check_output(
                ["brew", "list", "--versions", "colmap"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            parts = out.split()
            if len(parts) >= 2:
                # Strip Homebrew revision suffix (e.g., 4.0.4_2 → 4.0.4)
                ver = parts[1]
                return re.split(r'_\d+$', ver)[0]
            return ""
        except (subprocess.CalledProcessError, OSError):
            return ""

    def get_remote_version(self) -> str:
        try:
            out = subprocess.check_output(
                ["brew", "info", "--json", "colmap"],
                text=True, stderr=subprocess.DEVNULL, timeout=10
            )
            data = json.loads(out)
            if data and isinstance(data, list):
                return data[0].get("versions", {}).get("stable", "")
        except Exception as e:
            print(f"⚠️ Could not fetch latest COLMAP version: {e}")
        return ""

    def install(self):
        if not shutil.which("brew"):
            print("❌ Homebrew requis pour mettre à jour COLMAP.")
            return
        try:
            if self.is_installed():
                print("Mise à jour de COLMAP via Homebrew...")
                subprocess.check_call(["brew", "upgrade", "colmap"])
            else:
                print("Installation de COLMAP via Homebrew...")
                subprocess.check_call(["brew", "install", "colmap"])
        except subprocess.CalledProcessError:
            print("⚠️ brew upgrade/install colmap a échoué (peut-être déjà à jour).")


class GlomapEngineDep(EngineDependency):
    ask_before_update = True

    def __init__(self):
        super().__init__("glomap", GLOMAP_REPO)
        # Fix: source code is in a separate dir, not replacing the binary
        self.target_dir = self.engines_dir / "glomap-source"

    def is_enabled_in_config(self, config: dict) -> bool:
        return config.get("params", {}).get("use_glomap", False)

    def install(self):
        if sys.platform == "darwin" and not check_xcode_tools():
            print("Xcode Command Line Tools required.")
            return
        
        if not check_cmake_ninja():
            if not install_build_tools(): return
            
        self.update_git()
        # Source dir is now handled by update_git via self.target_dir
        source_dir = self.target_dir

        build_dir = source_dir / "build"
        # Fix CMakeCache error by cleaning build dir if it exists
        if build_dir.exists():
            shutil.rmtree(str(build_dir))
        build_dir.mkdir(exist_ok=True)
        
        cmake_args = ["cmake", "..", "-GNinja", "-DCMAKE_BUILD_TYPE=Release"]
        env = os.environ.copy()

        if sys.platform == "darwin":
            # GLOMAP builds its own COLMAP via FETCH_COLMAP.  The Homebrew COLMAP
            # CMake config does not export the colmap::colmap target, and the
            # SQLite crash that originally motivated -DFETCH_COLMAP=OFF is now
            # handled by _convert_db_journal_mode() in the pipeline.
            cmake_args = ["cmake", "..", "-GNinja", "-DCMAKE_BUILD_TYPE=Release", "-DFETCH_COLMAP=ON"]

            try:
                libomp = subprocess.check_output(["brew", "--prefix", "libomp"], text=True).strip()
                include_p = f"{libomp}/include"
                lib_p = f"{libomp}/lib"
                cmake_args.extend([
                    f"-DOpenMP_ROOT={libomp}",
                    "-DOpenMP_C_FLAGS=-Xpreprocessor -fopenmp",
                    "-DOpenMP_CXX_FLAGS=-Xpreprocessor -fopenmp"
                ])
                env["LDFLAGS"] = f"-L{lib_p} -lomp"
                env["CPPFLAGS"] = f"-I{include_p} -Xpreprocessor -fopenmp"
            except (subprocess.CalledProcessError, OSError) as e:
                print(f"⚠️ Could not detect libomp via brew: {e}")

        subprocess.check_call(cmake_args, cwd=str(build_dir), env=env)
        subprocess.check_call(["ninja"], cwd=str(build_dir), env=env)
        
        # Binary name is glomap
        built_bin = None
        for p in [build_dir / "glomap" / "glomap", build_dir / "glomap"]:
            if p.exists() and not p.is_dir():
                built_bin = p
                break
        
        if built_bin:
            shutil.copy2(str(built_bin), str(self.engines_dir / "glomap"))
            self.save_local_version(self.get_remote_version())

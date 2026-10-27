#!/usr/bin/env python3
from pathlib import Path
import shutil
import sys


NOTICE_FILES = (
    ("LICENSE", "VRCrafter-LICENSE.txt"),
    ("proton/licenses/BepInEx-LICENSE.txt", "BepInEx-LICENSE.txt"),
    ("proton/licenses/HarmonyX-LICENSE.txt", "HarmonyX-LICENSE.txt"),
    ("proton/licenses/MonoMod-LICENSE.txt", "MonoMod-LICENSE.txt"),
    ("proton/licenses/Mono.Cecil-LICENSE.txt", "Mono.Cecil-LICENSE.txt"),
    ("proton/licenses/UPSTREAM-SOURCES.txt", "UPSTREAM-SOURCES.txt"),
    ("third_party/Proton/LICENSE", "Proton-LICENSE.txt"),
    ("third_party/Proton/LICENSE.proton", "Proton-LICENSE.proton.txt"),
    ("third_party/Proton/dist.LICENSE", "Proton-dist.LICENSE.txt"),
    ("third_party/Proton/wine/COPYING.LIB", "Wine-COPYING.LIB.txt"),
)


def package_licenses(root, output):
    root = Path(root).resolve()
    output = Path(output).resolve()
    missing = [source for source, _ in NOTICE_FILES if not (root / source).is_file()]
    if missing:
        raise FileNotFoundError("Required license notices missing: " + ", ".join(missing))

    license_dir = output / "licenses"
    license_dir.mkdir(parents=True, exist_ok=True)
    for source, destination in NOTICE_FILES:
        shutil.copy2(root / source, license_dir / destination)
    return license_dir


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else project_root / "artifacts/proton-dist/vrcrafter-proton"
    if len(sys.argv) > 2:
        raise SystemExit(f"Usage: {sys.argv[0]} [staged-tool-directory]")
    result = package_licenses(project_root, destination)
    print(f"Packaged {len(NOTICE_FILES)} required notices in {result}")

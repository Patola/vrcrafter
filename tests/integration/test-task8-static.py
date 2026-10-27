#!/usr/bin/env python3
import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = ROOT / "artifacts/payload"
CORE_SOURCE = ROOT / "artifacts/deps/bepinex/BepInEx/core"
CORE_STAGED = PAYLOAD / "bepinex/core"
CONTROL_STAGED = PAYLOAD / "bepinex/plugins/Vrcrafter.BepInExControl.dll"


def digest(path):
    return hashlib.sha256(path.read_bytes()).digest()


class PayloadTests(unittest.TestCase):
    def test_pinned_core_and_control_are_staged_exactly(self):
        source_files = sorted(path for path in CORE_SOURCE.rglob("*") if path.is_file())
        self.assertTrue(source_files)
        for source in source_files:
            staged = CORE_STAGED / source.relative_to(CORE_SOURCE)
            self.assertTrue(staged.is_file(), staged)
            self.assertEqual(digest(source), digest(staged), staged)
        staged_files = sorted(path for path in CORE_STAGED.rglob("*") if path.is_file())
        self.assertEqual(source_files, [CORE_SOURCE / path.relative_to(CORE_STAGED)
                                        for path in staged_files])

        control_source = (ROOT / "src/Vrcrafter.BepInExControl/bin/Release/net48"
                          / "Vrcrafter.BepInExControl.dll")
        self.assertEqual(digest(control_source), digest(CONTROL_STAGED))
        self.assertTrue((PAYLOAD / "managed/Vrcrafter.BepInExBridge.dll").is_file())

    def test_payload_excludes_doorstop_game_and_forbidden_plugins(self):
        for path in PAYLOAD.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            self.assertFalse(name.startswith(("assembly-csharp", "unityengine")), path)
            self.assertNotIn(name, ("doorstop.dll", "doorstop_config.ini", ".doorstop_version",
                                    "bepinex.utility.dll", "configurationmanager.dll"), path)

    def test_custom_proton_scripts_carry_required_bepinex_payload(self):
        build = (ROOT / "eng/build-proton.sh").read_text(encoding="utf-8")
        install = (ROOT / "eng/install-local.sh").read_text(encoding="utf-8")
        for text in (build, install):
            self.assertIn("bepinex/core/BepInEx.dll", text)
            self.assertIn("bepinex/plugins/Vrcrafter.BepInExControl.dll", text)
        self.assertIn(
            'rsync -a --delete artifacts/payload/bepinex/ "$stage_dir/vrcrafter/payload/bepinex/"',
            build)
        self.assertIn('rsync -a --delete "$stage_dir/vrcrafter/payload/" "$payload_dir/"', install)


class DiagnosticTests(unittest.TestCase):
    def test_staged_bridge_routes_success_and_error_to_host_log(self):
        bridge = PAYLOAD / "managed/Vrcrafter.BepInExBridge.dll"
        game_dir = Path(os.environ.get(
            "TPC_GAME_DIR", "/games/SteamLibrary/steamapps/common/The Planet Crafter"))
        mono_path = os.pathsep.join((
            str(CORE_SOURCE), str(game_dir / "Planet Crafter_Data/Managed"),
            os.environ.get("MONO_PATH", ""),
        ))
        environment = os.environ.copy()
        environment["MONO_PATH"] = mono_path
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as temporary:
            disassembly = Path(temporary) / "bridge.il"
            subprocess.run(["monodis", "--output=" + str(disassembly), str(bridge)],
                           cwd=ROOT, env=environment, check=True)
            il = disassembly.read_text(encoding="utf-8")
        self.assertEqual(3, il.count("Vrcrafter.Host.VrcrafterHost::Log(string)"))
        self.assertIn("BEPINEX_CHAINLOADER_OK", il)
        self.assertIn("BEPINEX_CHAINLOADER_ERROR", il)
        self.assertIn("BEPINEX_PATHS", il)
        self.assertIn("Paths::get_BepInExRootPath()", il)
        self.assertIn("Paths::get_BepInExAssemblyDirectory()", il)
        self.assertIn("Paths::get_PluginPath()", il)
        self.assertIn("System.IO.Directory::CreateDirectory(string)", il)

        disk_config = il.index('ldstr "Logging.Disk"')
        initialize = il.index("Chainloader::Initialize", disk_config)
        before_initialize = il[disk_config:initialize]
        self.assertIn('ldstr "Enabled"', before_initialize)
        self.assertIn("ldc.i4.0", before_initialize)
        self.assertIn("ConfigEntry`1<bool>::set_Value(!0)", before_initialize)
        self.assertIn("HideManagerGameObject", il[:disk_config])
        self.assertIn("Chainloader::Start", il[initialize:])
        self.assertIn("Chainloader::get_PluginInfos", il[initialize:])
        self.assertLess(initialize, il.index("BEPINEX_CHAINLOADER_OK", initialize))


if __name__ == "__main__":
    unittest.main()

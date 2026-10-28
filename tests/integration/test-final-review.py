#!/usr/bin/env python3
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class BuildInputTests(unittest.TestCase):
    def test_proton_backend_lock_records_revision_and_current_hash(self):
        document = json.loads((ROOT / "eng/dependencies.lock.json").read_text(encoding="utf-8"))
        self.assertIn("protonWinHttpBackend", document)
        backend = document["protonWinHttpBackend"]
        self.assertEqual("11.0-2", backend["version"])
        self.assertEqual("db9e6ffbf24a95b104fb699dd62532c70a2f9a51",
                         backend["sourceRevision"])
        self.assertEqual("c822ab64506d4dd7ba14c5af75e983e139a8d4141e459bfc28a4af23cf640509",
                         backend["sha256"])
        self.assertEqual("files/lib/wine/x86_64-windows/winhttp.dll", backend["relativePath"])

    def test_native_build_rejects_changed_backend_before_copy(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as temporary:
            root = Path(temporary) / "root"
            (root / "eng").mkdir(parents=True)
            for name in ("build-native.sh", "dependencies.lock.json",
                         "generate-winhttp-exports.py"):
                shutil.copy2(ROOT / "eng" / name, root / "eng" / name)
            proton = Path(temporary) / "proton"
            backend = proton / "files/lib/wine/x86_64-windows/winhttp.dll"
            backend.parent.mkdir(parents=True)
            backend.write_bytes(b"changed stock backend")
            environment = os.environ.copy()
            environment["PROTON_DIR"] = str(proton)
            result = subprocess.run(["bash", str(root / "eng/build-native.sh")],
                                    cwd=root, env=environment, capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("hash mismatch", result.stderr)
            self.assertIn("Proton 11.0-2", result.stderr)
            self.assertFalse((root / "artifacts/payload/vrcrafter-winhttp-backend.dll").exists())
            self.assertFalse((root / "artifacts/native/winhttp.def").exists())


class ControlLicenseTests(unittest.TestCase):
    def test_installer_stages_all_required_notices(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as temporary:
            base = Path(temporary)
            game = base / "game"
            control = base / "control"
            for depot in (game, control):
                (depot / "Planet Crafter_Data/Managed").mkdir(parents=True)
                (depot / "Planet Crafter.exe").write_bytes(b"test depot")
            environment = os.environ.copy()
            environment["TPC_GAME_DIR"] = str(game)
            environment["TPC_CONTROL_DIR"] = str(control)
            subprocess.run(["bash", "eng/install-control.sh"], cwd=ROOT, env=environment,
                           check=True, capture_output=True, text=True)
            expected = {
                "UnityDoorstop-LICENSE.txt",
                "BepInEx-LICENSE.txt",
                "HarmonyX-LICENSE.txt",
                "MonoMod-LICENSE.txt",
                "Mono.Cecil-LICENSE.txt",
                "VRCrafter-LICENSE.txt",
                "UPSTREAM-SOURCES.txt",
            }
            licenses = control / "licenses"
            self.assertTrue(licenses.is_dir())
            self.assertEqual(expected, {path.name for path in licenses.iterdir()})
            for name in expected:
                self.assertGreater((licenses / name).stat().st_size, 0)
            sources = (licenses / "UPSTREAM-SOURCES.txt").read_text(encoding="utf-8")
            self.assertIn("UnityDoorstop", sources)
            self.assertIn("v4.6.0", sources)


class ManagedExceptionPathTests(unittest.TestCase):
    def test_entry_point_and_bootstrap_state_logging_cannot_replace_return_code(self):
        for name in ("EntryPoint.cs", "BootstrapState.cs"):
            source = (ROOT / "src/Vrcrafter.Bootstrap" / name).read_text(encoding="utf-8")
            catch = source.split("catch (Exception ex)", 1)[1]
            self.assertIn("try", catch[:catch.index("return 2;")], name)
            self.assertIn("catch (Exception)", catch[:catch.index("return 2;")], name)

    def test_harmony_unpatches_exact_postfix_in_finally(self):
        source = (ROOT / "src/Vrcrafter.Bootstrap/HarmonyBootstrap.cs").read_text(encoding="utf-8")
        self.assertIn("Interlocked.Exchange(ref hostCreationStarted, 1)", source)
        self.assertIn("StartOptionalChainloader();", source)
        self.assertIn("finally", source)
        finally_block = source.rsplit("finally", 1)[1]
        self.assertIn("harmony.Unpatch(original, postfix);", finally_block)


if __name__ == "__main__":
    unittest.main()

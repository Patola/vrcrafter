#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("verify-loader.py")
SPEC = importlib.util.spec_from_file_location("verify_loader", MODULE_PATH)
verify_loader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_loader)


def successful_run():
    return "\n".join((
        "[10] PROCESS error=0 Planet Crafter.exe",
        "[10] START_QUEUED error=0 deferred entry queued",
        "[10] MANAGED_ENTRY error=0 Vrcrafter.Bootstrap.EntryPoint.Start():int",
        "START pid=10",
        "IDENTITY_ACCEPT",
        "HARMONY_PATCH owner=test thread=3",
        "HOST_CREATE thread=1",
        "HOST_UPDATE tick=1 thread=1",
        "WORKER_DISPATCH thread=1",
        "ORIGINAL_CONTINUES thread=1",
        "GC_STRESS_START duration=30s thread=4",
        "HOST_UPDATE tick=2 thread=1",
        "WORKER_DISPATCH source=gc-stress callback=1 thread=1",
        "HOST_UPDATE tick=3 thread=1",
        "WORKER_DISPATCH source=gc-stress callback=2 thread=1",
        "GC_STRESS_OK duration_ms=30010 allocations=1000 callbacks=2 thread=1",
        "HOST_DESTROY thread=1",
        "[10] MANAGED_RESULT error=0 MANAGED_RESULT=0",
    ))


class DirectVerificationTests(unittest.TestCase):
    def assertRejected(self, text, message):
        with self.assertRaisesRegex(AssertionError, message):
            verify_loader.verify(text)

    def test_accepts_complete_run(self):
        verify_loader.verify(successful_run())

    def test_rejects_duplicate_initialization(self):
        self.assertRejected(successful_run() + "\nSTART pid=10", "duplicate START")

    def test_rejects_duplicate_host_creation(self):
        self.assertRejected(successful_run() + "\nHOST_CREATE thread=1",
                            "duplicate HOST_CREATE")

    def test_rejects_unexpected_managed_exception(self):
        self.assertRejected(successful_run() + "\nEXCEPTION deliberate",
                            "EXCEPTION is not valid")

    def test_rejects_missing_original_continuation(self):
        text = successful_run().replace("ORIGINAL_CONTINUES thread=1\n", "")
        self.assertRejected(text, "missing ORIGINAL_CONTINUES")

    def test_rejects_missing_gc_stress(self):
        text = successful_run().replace("GC_STRESS_START duration=30s thread=4\n", "")
        self.assertRejected(text, "missing GC_STRESS_START")

    def test_rejects_unstable_gc_callbacks(self):
        text = successful_run().replace("callback=2", "callback=3")
        self.assertRejected(text, "GC callback sequence")

    def test_rejects_short_gc_stress(self):
        self.assertRejected(successful_run().replace("duration_ms=30010", "duration_ms=29999"),
                            "GC stress duration")


class AcceptanceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.write_run("normal", successful_run())
        self.write_run("clean-prefix", successful_run())
        self.write_run("disabled", "Proton: disabled launch without loader activation")
        self.write_run("process-exclusion", "\n".join((
            "[11] PROCESS error=0 helper.exe",
            "[11] ACTIVATION_SKIPPED error=0 executable is not Planet Crafter.exe",
        )))

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_run(self, name, text):
        run = self.root / name
        run.mkdir(exist_ok=True)
        (run / "managed.log").write_text(text, encoding="utf-8")

    def test_accepts_per_run_logs_and_ignores_intentional_negatives(self):
        self.write_run("managed-exception", "EXCEPTION deliberate\nHOST_CREATE\nHOST_CREATE")
        verify_loader.verify_acceptance(self.root)

    def test_rejects_missing_kill_switch_run(self):
        (self.root / "disabled" / "managed.log").unlink()
        with self.assertRaisesRegex(ValueError, "disabled.*no log files"):
            verify_loader.verify_acceptance(self.root)

    def test_rejects_failed_process_exclusion(self):
        self.write_run("process-exclusion", "\n".join((
            "[11] PROCESS error=0 Planet Crafter.exe",
            "[11] ACTIVATION_SKIPPED error=0 VRCRAFTER_ENABLE is not 1",
        )))
        with self.assertRaisesRegex(AssertionError, "process-exclusion.*PROCESS exclusion"):
            verify_loader.verify_acceptance(self.root)

    def test_rejects_missing_clean_prefix_run(self):
        for path in (self.root / "clean-prefix").iterdir():
            path.unlink()
        with self.assertRaisesRegex(ValueError, "clean-prefix.*no log files"):
            verify_loader.verify_acceptance(self.root)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("verify-loader.py")
SPEC = importlib.util.spec_from_file_location("verify_loader", MODULE_PATH)
verify_loader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_loader)


def successful_run(callback_count=120, callback_interval=250):
    lines = [
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
    ]
    for callback in range(1, callback_count + 1):
        lines.append("HOST_UPDATE tick={0} thread=1".format(callback + 1))
        lines.append("WORKER_DISPATCH source=gc-stress callback={0} elapsed_ms={1} thread=1".format(
            callback, callback * callback_interval))
    lines.extend((
        "GC_STRESS_OK duration_ms=30010 allocations=1000 callbacks={0} thread=1".format(
            callback_count),
        "HOST_DESTROY thread=1",
        "[10] MANAGED_RESULT error=0 MANAGED_RESULT=0",
    ))
    return "\n".join(lines)


def missing_managed_run():
    return "\n".join((
        "[10] PROCESS error=0 Planet Crafter.exe",
        "[10] START_QUEUED error=0 deferred entry queued",
        "[10] DEFERRED_START error=0 mono_host_start",
        "[10] MONO_MODULE error=0 mono-2.0-bdwgc.dll",
        "[10] MONO_DOMAIN error=0 existing root domain attached",
        "[10] MANAGED_ASSEMBLY_OPEN error=2 Z:\\payload\\managed\\Vrcrafter.Bootstrap.dll",
    ))


def managed_exception_run():
    return "\n".join((
        "[10] MANAGED_ENTRY error=0 Vrcrafter.Bootstrap.EntryPoint.Start():int",
        "START pid=10",
        "EXCEPTION System.InvalidOperationException: loader-self-test",
        "[10] MANAGED_RESULT error=2 MANAGED_RESULT=2",
    ))


def wrong_hash_run():
    return "\n".join((
        "[10] MANAGED_ENTRY error=0 Vrcrafter.Bootstrap.EntryPoint.Start():int",
        "START pid=10",
        "GAME_ASSEMBLY Assembly-CSharp path=S:\\Assembly-CSharp.dll",
        "IDENTITY_DETAIL executable=True unity=True",
        "IDENTITY_HASH actual=0000000000000000000000000000000000000000000000000000000000000000",
        "IDENTITY_REJECT",
        "[10] MANAGED_RESULT error=4 MANAGED_RESULT=4",
    ))


def control_run():
    return "\n".join((
        "BEPINEX_CONTROL_OK",
        "BEPINEX_CONTROL_HARMONY_OK ORIGINAL_CONTINUES",
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
        text = successful_run().replace("callback=2 elapsed", "callback=3 elapsed")
        self.assertRejected(text, "GC callback sequence")

    def test_rejects_unstable_ticks(self):
        text = successful_run().replace("HOST_UPDATE tick=3 ", "HOST_UPDATE tick=4 ")
        self.assertRejected(text, "tick sequence")

    def test_rejects_short_gc_stress(self):
        self.assertRejected(successful_run().replace("duration_ms=30010", "duration_ms=29999"),
                            "GC stress duration")

    def test_rejects_too_few_gc_callbacks(self):
        self.assertRejected(successful_run(callback_count=99), "at least 100")

    def test_rejects_short_gc_callback_span(self):
        self.assertRejected(successful_run(callback_interval=200), "span at least 25")

    def test_rejects_final_gc_callback_far_from_completion(self):
        self.assertRejected(successful_run(callback_interval=211), "final callback")


class ExpectedFailureVerificationTests(unittest.TestCase):
    def test_accepts_isolated_expected_failures_and_control(self):
        verify_loader.verify_expected_failure(missing_managed_run(), "missing-managed")
        verify_loader.verify_expected_failure(managed_exception_run(), "managed-exception")
        verify_loader.verify_expected_failure(wrong_hash_run(), "wrong-hash")
        verify_loader.verify(control_run(), "control")

    def test_rejects_unrelated_managed_exception(self):
        with self.assertRaisesRegex(AssertionError, "loader-self-test"):
            verify_loader.verify_expected_failure(
                managed_exception_run().replace("loader-self-test", "unexpected"),
                "managed-exception")

    def test_rejects_unavailable_wrong_hash(self):
        text = wrong_hash_run().replace("0" * 64, "<unavailable>")
        with self.assertRaisesRegex(AssertionError, "actual wrong-game hash"):
            verify_loader.verify_expected_failure(text, "wrong-hash")

    def test_control_rejects_native_host(self):
        with self.assertRaisesRegex(AssertionError, "not valid for custom-Proton control"):
            verify_loader.verify(control_run() + "\nMANAGED_ENTRY error=0", "control")


class AcceptanceVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.write_run("normal", successful_run())
        self.write_run("clean-prefix", successful_run())
        (self.root / "clean-prefix" / "proton.log").write_text(
            "Proton: Upgrading prefix from None to 11.0\n", encoding="utf-8")
        self.write_run("disabled", "\n".join((
            "[10] PROCESS error=0 Planet Crafter.exe",
            "[10] ACTIVATION_SKIPPED error=0 VRCRAFTER_ENABLE is not 1",
        )))
        self.write_run("process-exclusion", "\n".join((
            "[11] PROCESS error=0 helper.exe",
            "[11] ACTIVATION_SKIPPED error=0 executable is not Planet Crafter.exe",
        )))
        self.write_run("missing-managed", missing_managed_run())
        self.write_run("managed-exception", managed_exception_run())
        self.write_run("wrong-hash", wrong_hash_run())
        self.write_run("control", control_run())

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_run(self, name, text):
        run = self.root / name
        run.mkdir(exist_ok=True)
        (run / "managed.log").write_text(text, encoding="utf-8")

    def test_accepts_complete_isolated_acceptance_matrix(self):
        verify_loader.verify_acceptance(self.root)

    def test_rejects_missing_kill_switch_run(self):
        (self.root / "disabled" / "managed.log").unlink()
        with self.assertRaisesRegex(ValueError, "disabled.*no log files"):
            verify_loader.verify_acceptance(self.root)

    def test_rejects_unrelated_disabled_log(self):
        self.write_run("disabled", "Proton: unrelated disabled output")
        with self.assertRaisesRegex(AssertionError, "disabled.*PROCESS"):
            verify_loader.verify_acceptance(self.root)

    def test_rejects_disabled_log_with_managed_success(self):
        path = self.root / "disabled" / "managed.log"
        path.write_text(path.read_text(encoding="utf-8") + "\nMANAGED_RESULT=0\n",
                        encoding="utf-8")
        with self.assertRaisesRegex(AssertionError, "disabled.*MANAGED_RESULT"):
            verify_loader.verify_acceptance(self.root)

    def test_rejects_failed_process_exclusion(self):
        self.write_run("process-exclusion", "\n".join((
            "[11] PROCESS error=0 Planet Crafter.exe",
            "[11] ACTIVATION_SKIPPED error=0 VRCRAFTER_ENABLE is not 1",
        )))
        with self.assertRaisesRegex(AssertionError, "process-exclusion.*PROCESS exclusion"):
            verify_loader.verify_acceptance(self.root)

    def test_rejects_clean_prefix_without_creation_evidence(self):
        (self.root / "clean-prefix" / "proton.log").unlink()
        with self.assertRaisesRegex(AssertionError, "clean-prefix.*Upgrading prefix from None"):
            verify_loader.verify_acceptance(self.root)

    def test_rejects_missing_expected_failure_run(self):
        (self.root / "missing-managed" / "managed.log").unlink()
        with self.assertRaisesRegex(ValueError, "missing-managed.*no log files"):
            verify_loader.verify_acceptance(self.root)


if __name__ == "__main__":
    unittest.main()

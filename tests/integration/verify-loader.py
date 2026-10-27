#!/usr/bin/env python3
import re
import sys
from pathlib import Path

MARKERS = (
    "IDENTITY_ACCEPT",
    "HARMONY_PATCH",
    "HOST_CREATE",
    "HOST_UPDATE",
    "WORKER_DISPATCH",
    "ORIGINAL_CONTINUES",
)

STRESS_MARKERS = (
    "GC_STRESS_START",
    "HOST_UPDATE",
    "WORKER_DISPATCH",
    "GC_STRESS_OK",
    "HOST_DESTROY",
)

CONTROL_MARKERS = (
    "BEPINEX_CONTROL_OK",
    "BEPINEX_CONTROL_HARMONY_OK",
    "ORIGINAL_CONTINUES",
)

CHAINLOADER_MARKERS = (
    "BEPINEX_CONTROL_OK",
    "BEPINEX_CHAINLOADER_OK",
    "BEPINEX_CONTROL_HARMONY_OK",
    "ORIGINAL_CONTINUES",
)

NATIVE_HOST_ONLY_MARKERS = MARKERS[:-1] + STRESS_MARKERS + (
    "START",
    "EXCEPTION",
    "IDENTITY_REJECT",
    "IDENTITY_ERROR",
    "IDENTITY_DETAIL",
    "IDENTITY_HASH",
    "GAME_ASSEMBLY",
    "ASSEMBLY",
    "RESOLVER_INSTALL",
    "RESOLVE_LOADED",
    "RESOLVE_LOAD",
    "PING",
    "PROCESS",
    "PAYLOAD",
    "ACTIVATION_SKIPPED",
    "START_QUEUE",
    "START_QUEUED",
    "START_SKIPPED",
    "DEFERRED_START",
    "MONO_EXPORT",
    "MONO_MODULE",
    "MONO_DOMAIN",
    "MONO_ATTACH",
    "MANAGED_PATH",
    "MANAGED_PATH_UTF8",
    "MANAGED_ASSEMBLY_OPEN",
    "MANAGED_IMAGE",
    "MANAGED_CLASS",
    "MANAGED_METHOD",
    "MANAGED_ENTRY",
    "MANAGED_EXCEPTION",
    "MANAGED_RESULT",
    "MANAGED_UNBOX",
    "UTF8_CONVERSION_ERROR",
)


def read_logs(path):
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(candidate for candidate in path.rglob("*.log") if candidate.is_file())
    else:
        raise ValueError("log path does not exist: {0}".format(path))

    if not files:
        raise ValueError("no log files under {0}".format(path))
    return "\n".join(
        candidate.read_text(encoding="utf-8", errors="replace") for candidate in files
    )


def find_marker(text, marker, start=0):
    match = re.search(r"(?<![A-Z0-9_])" + re.escape(marker) + r"(?![A-Z0-9_])", text[start:])
    if match is None:
        return -1
    return start + match.start()


def count_marker(text, marker):
    return len(re.findall(r"(?<![A-Z0-9_])" + re.escape(marker) + r"(?![A-Z0-9_])", text))


def require_single(text, marker):
    count = count_marker(text, marker)
    if count == 0:
        raise AssertionError("missing " + marker)
    if count != 1:
        raise AssertionError("duplicate " + marker)


def require_ordered(text, markers, start=0):
    cursor = start
    previous = None
    for marker in markers:
        position = find_marker(text, marker, cursor)
        if position < 0:
            requirement = " after " + previous if previous is not None else ""
            raise AssertionError("missing " + marker + requirement)
        cursor = position + len(marker)
        previous = marker
    return cursor


def require_pattern(text, pattern, description):
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise AssertionError("missing " + description)
    return match


def reject_markers(text, markers, classification):
    for marker in markers:
        if find_marker(text, marker) >= 0:
            raise AssertionError(marker + " is not valid for " + classification)


def verify_gc_stress(text, host_thread):
    require_pattern(text, r"GC_STRESS_START duration=30s thread=\d+",
                    "30-second GC stress start")
    updates = [(int(match.group(1)), match.group(2)) for match in re.finditer(
        r"HOST_UPDATE tick=(\d+) thread=(\d+)", text)]
    ticks = [tick for tick, thread in updates]
    if not ticks or any(tick <= 0 for tick in ticks) or any(
            previous >= current for previous, current in zip(ticks, ticks[1:])):
        raise AssertionError("HOST_UPDATE tick sequence is not stable")
    if any(thread != host_thread for tick, thread in updates):
        raise AssertionError("HOST_UPDATE thread changed")

    callbacks = list(re.finditer(
        r"WORKER_DISPATCH source=gc-stress callback=(\d+) elapsed_ms=(\d+) thread=(\d+)", text))
    sequence = [int(match.group(1)) for match in callbacks]
    if sequence != list(range(1, len(sequence) + 1)):
        raise AssertionError("GC callback sequence is not stable")
    if len(sequence) < 100:
        raise AssertionError("GC stress requires at least 100 callbacks")
    elapsed = [int(match.group(2)) for match in callbacks]
    if elapsed != sorted(elapsed):
        raise AssertionError("GC callback timing is not monotonic")
    if elapsed[-1] - elapsed[0] < 25000:
        raise AssertionError("GC callbacks must span at least 25 seconds")
    if any(match.group(3) != host_thread for match in callbacks):
        raise AssertionError("GC callback did not run on the host thread")

    stress_start = find_marker(text, "GC_STRESS_START")
    stress_end = find_marker(text, "GC_STRESS_OK")
    if any(match.start() < stress_start or match.start() > stress_end for match in callbacks):
        raise AssertionError("GC callback appears outside the stress interval")
    result = require_pattern(
        text, r"GC_STRESS_OK duration_ms=(\d+) allocations=(\d+) callbacks=(\d+) thread=(\d+)",
        "GC stress result")
    duration = int(result.group(1))
    if duration < 30000:
        raise AssertionError("GC stress duration is shorter than 30 seconds")
    if abs(duration - elapsed[-1]) > 2000:
        raise AssertionError("final callback is not near GC stress completion")
    if int(result.group(2)) <= 0:
        raise AssertionError("GC stress allocated no objects")
    if int(result.group(3)) != len(callbacks):
        raise AssertionError("GC stress callback count does not match its result")
    if result.group(4) != host_thread:
        raise AssertionError("GC stress completion did not run on the host thread")


def verify(text, mode="direct"):
    if mode not in ("direct", "control", "chainloader"):
        raise ValueError("unknown verification mode: " + mode)

    if mode == "control":
        require_ordered(text, CONTROL_MARKERS)
        reject_markers(text, NATIVE_HOST_ONLY_MARKERS, "custom-Proton control")
        reject_markers(text, ("BEPINEX_CHAINLOADER_OK", "BEPINEX_CHAINLOADER_ERROR"),
                       "custom-Proton control")
        return

    host_create = find_marker(text, "HOST_CREATE")
    host_update = find_marker(text, "HOST_UPDATE")
    if host_update >= 0 and (host_create < 0 or host_update < host_create):
        raise AssertionError("HOST_UPDATE appears before HOST_CREATE")

    cursor = require_ordered(text, MARKERS)
    require_ordered(text, STRESS_MARKERS, cursor)
    for marker in ("START", "START_QUEUED", "MANAGED_ENTRY", "HOST_CREATE",
                   "GC_STRESS_START", "GC_STRESS_OK", "HOST_DESTROY"):
        require_single(text, marker)
    reject_markers(text, ("EXCEPTION", "MANAGED_EXCEPTION", "GC_STRESS_ERROR",
                          "IDENTITY_REJECT", "IDENTITY_ERROR"), "successful run")
    require_pattern(text, r"MANAGED_RESULT=0(?![0-9])", "zero managed result")
    updates = require_pattern(text, r"HOST_UPDATE tick=\d+ thread=(\d+)", "host thread")
    verify_gc_stress(text, updates.group(1))

    if mode == "chainloader":
        reject_markers(text, ("BEPINEX_CHAINLOADER_ERROR",), "Chainloader success")
        require_ordered(text, CHAINLOADER_MARKERS, cursor)


def verify_disabled(text, process_exclusion=False):
    require_ordered(text, ("PROCESS", "ACTIVATION_SKIPPED"))
    reject_markers(text, ("START", "START_QUEUED", "DEFERRED_START", "MONO_DOMAIN",
                          "MANAGED_ENTRY", "MANAGED_RESULT", "PING", "IDENTITY_ACCEPT",
                          "HARMONY_PATCH", "HOST_CREATE", "HOST_UPDATE", "WORKER_DISPATCH",
                          "ORIGINAL_CONTINUES", "HOST_DESTROY"), "disabled activation")
    if process_exclusion:
        require_pattern(text, r"ACTIVATION_SKIPPED error=0 executable is not Planet Crafter\.exe",
                        "PROCESS exclusion reason")
        if re.search(r"PROCESS error=\d+ Planet Crafter\.exe\s*$", text, re.MULTILINE):
            raise AssertionError("PROCESS exclusion used the game executable")
    else:
        require_pattern(text, r"ACTIVATION_SKIPPED error=0 VRCRAFTER_ENABLE is not 1",
                        "kill-switch reason")
        require_pattern(text, r"PROCESS error=0 Planet Crafter\.exe\s*$",
                        "game process for kill-switch run")


def verify_expected_failure(text, mode):
    if mode == "missing-managed":
        require_ordered(text, ("PROCESS", "START_QUEUED", "DEFERRED_START", "MONO_MODULE",
                               "MONO_DOMAIN", "MANAGED_ASSEMBLY_OPEN"))
        require_pattern(text, r"MANAGED_ASSEMBLY_OPEN error=2 .*Vrcrafter\.Bootstrap\.dll",
                        "missing-managed assembly-open failure")
        reject_markers(text, ("START", "MANAGED_ENTRY", "MANAGED_RESULT", "IDENTITY_ACCEPT",
                              "HARMONY_PATCH", "HOST_CREATE"), "missing-managed run")
        return

    if mode == "managed-exception":
        require_single(text, "MANAGED_ENTRY")
        require_pattern(text, r"EXCEPTION[^\r\n]*loader-self-test",
                        "deliberate loader-self-test exception")
        require_pattern(text, r"MANAGED_RESULT error=2 MANAGED_RESULT=2",
                        "managed-exception result")
    elif mode == "wrong-hash":
        require_single(text, "START")
        require_single(text, "MANAGED_ENTRY")
        require_pattern(text, r"GAME_ASSEMBLY .*Assembly-CSharp", "wrong-hash game assembly")
        actual = require_pattern(text, r"IDENTITY_HASH actual=([0-9a-f]{64})",
                                 "actual wrong-game hash")
        if actual.group(1) != "3d7457446cbbed551f938b5271f294f45ec100e1f295eeba9b0884b3cdd9191e":
            raise AssertionError("wrong-hash run did not contain the actual pinned game hash")
        require_single(text, "IDENTITY_REJECT")
        require_pattern(text, r"MANAGED_RESULT error=4 MANAGED_RESULT=4", "wrong-hash result")
    else:
        raise ValueError("unknown expected-failure mode: " + mode)

    reject_markers(text, ("IDENTITY_ACCEPT", "HARMONY_PATCH", "HOST_CREATE"),
                   mode + " run")
    if re.search(r"MANAGED_RESULT=0(?![0-9])", text):
        raise AssertionError("zero managed result is not valid for " + mode)


def verify_acceptance(path):
    if not path.is_dir():
        raise ValueError("acceptance path is not a directory: {0}".format(path))

    runs = (("normal", "direct"), ("clean-prefix", "direct"),
            ("disabled", "disabled"), ("process-exclusion", "process-exclusion"),
            ("missing-managed", "expected-failure"),
            ("managed-exception", "expected-failure"), ("wrong-hash", "expected-failure"),
            ("control", "control"))
    for name, mode in runs:
        try:
            text = read_logs(path / name)
            if mode == "direct":
                verify(text)
            elif mode == "expected-failure":
                verify_expected_failure(text, name)
            elif mode == "control":
                verify(text, "control")
            else:
                verify_disabled(text, mode == "process-exclusion")
            if name == "clean-prefix":
                proton_log = path / name / "proton.log"
                if not proton_log.is_file():
                    raise AssertionError("missing clean-prefix Proton evidence: "
                                         "Upgrading prefix from None")
                proton_text = proton_log.read_text(encoding="utf-8", errors="replace")
                require_pattern(proton_text, r"Upgrading prefix from None",
                                "clean-prefix Proton evidence: Upgrading prefix from None")
        except (AssertionError, OSError, ValueError) as error:
            raise type(error)(name + ": " + str(error))


def main():
    if len(sys.argv) == 2:
        mode = "acceptance"
        log_path = sys.argv[1]
    elif len(sys.argv) == 3:
        mode = sys.argv[1]
        log_path = sys.argv[2]
    else:
        print("usage: verify-loader.py [acceptance|direct|control|chainloader|"
              "missing-managed|managed-exception|wrong-hash] LOG_FILE_OR_DIRECTORY",
              file=sys.stderr)
        return 2

    try:
        path = Path(log_path)
        if mode == "acceptance":
            verify_acceptance(path)
        elif mode in ("missing-managed", "managed-exception", "wrong-hash"):
            verify_expected_failure(read_logs(path), mode)
        else:
            verify(read_logs(path), mode)
    except (AssertionError, OSError, ValueError) as error:
        print("FAIL " + str(error), file=sys.stderr)
        return 1

    markers = {"acceptance": MARKERS + STRESS_MARKERS,
               "direct": MARKERS + STRESS_MARKERS, "control": CONTROL_MARKERS,
               "chainloader": MARKERS + STRESS_MARKERS + CHAINLOADER_MARKERS,
               "missing-managed": ("MANAGED_ASSEMBLY_OPEN",),
               "managed-exception": ("EXCEPTION", "MANAGED_RESULT=2"),
               "wrong-hash": ("IDENTITY_REJECT", "MANAGED_RESULT=4")}[mode]
    print("LOADER_MARKERS_OK mode=" + mode + " ordered=" + ",".join(markers)
          + " negative=duplicates,exceptions,ordering,activation,GC")
    return 0


if __name__ == "__main__":
    sys.exit(main())

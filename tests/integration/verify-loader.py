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

NATIVE_HOST_ONLY_MARKERS = MARKERS[:-1] + (
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
    "HOST_DESTROY",
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

    return "\n".join(
        candidate.read_text(encoding="utf-8", errors="replace") for candidate in files
    )


def find_marker(text, marker, start=0):
    match = re.search(r"(?<![A-Z0-9_])" + re.escape(marker) + r"(?![A-Z0-9_])", text[start:])
    if match is None:
        return -1
    return start + match.start()


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


def reject_markers(text, markers, classification):
    for marker in markers:
        if find_marker(text, marker) >= 0:
            raise AssertionError(marker + " is not valid for " + classification)


def verify(text, mode="direct"):
    if mode not in ("direct", "stock", "chainloader"):
        raise ValueError("unknown verification mode: " + mode)

    if mode == "stock":
        require_ordered(text, CONTROL_MARKERS)
        reject_markers(text, NATIVE_HOST_ONLY_MARKERS, "stock control")
        reject_markers(text, ("BEPINEX_CHAINLOADER_OK", "BEPINEX_CHAINLOADER_ERROR"),
                       "stock control")
        return

    host_create = find_marker(text, "HOST_CREATE")
    host_update = find_marker(text, "HOST_UPDATE")
    if host_update >= 0 and (host_create < 0 or host_update < host_create):
        raise AssertionError("HOST_UPDATE appears before HOST_CREATE")

    cursor = require_ordered(text, MARKERS)
    if mode == "chainloader":
        reject_markers(text, ("BEPINEX_CHAINLOADER_ERROR",), "Chainloader success")
        require_ordered(text, CHAINLOADER_MARKERS, cursor)


def main():
    if len(sys.argv) == 2:
        mode = "direct"
        log_path = sys.argv[1]
    elif len(sys.argv) == 3:
        mode = sys.argv[1]
        log_path = sys.argv[2]
    else:
        print("usage: verify-loader.py [direct|stock|chainloader] LOG_FILE_OR_DIRECTORY",
              file=sys.stderr)
        return 2

    try:
        verify(read_logs(Path(log_path)), mode)
    except (AssertionError, OSError, ValueError) as error:
        print("FAIL " + str(error), file=sys.stderr)
        return 1

    markers = {"direct": MARKERS, "stock": CONTROL_MARKERS,
               "chainloader": MARKERS + CHAINLOADER_MARKERS}[mode]
    print("LOADER_MARKERS_OK mode=" + mode + " ordered=" + ",".join(markers)
          + " negative=HOST_UPDATE-before-HOST_CREATE")
    return 0


if __name__ == "__main__":
    sys.exit(main())

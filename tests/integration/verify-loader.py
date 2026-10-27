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


def verify(text):
    host_create = find_marker(text, "HOST_CREATE")
    host_update = find_marker(text, "HOST_UPDATE")
    if host_update >= 0 and (host_create < 0 or host_update < host_create):
        raise AssertionError("HOST_UPDATE appears before HOST_CREATE")

    cursor = 0
    previous = None
    for marker in MARKERS:
        position = find_marker(text, marker, cursor)
        if position < 0:
            requirement = " after " + previous if previous is not None else ""
            raise AssertionError("missing " + marker + requirement)
        cursor = position + len(marker)
        previous = marker


def main():
    if len(sys.argv) != 2:
        print("usage: verify-loader.py LOG_FILE_OR_DIRECTORY", file=sys.stderr)
        return 2

    try:
        verify(read_logs(Path(sys.argv[1])))
    except (AssertionError, OSError, ValueError) as error:
        print("FAIL " + str(error), file=sys.stderr)
        return 1

    print("LOADER_MARKERS_OK ordered=" + ",".join(MARKERS)
          + " negative=HOST_UPDATE-before-HOST_CREATE")
    return 0


if __name__ == "__main__":
    sys.exit(main())

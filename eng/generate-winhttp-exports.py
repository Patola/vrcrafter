#!/usr/bin/env python3
import argparse
import re
import subprocess
from pathlib import Path

EXPORT_ROW = re.compile(
    r"^\s*\[\s*\d+\]\s+\+base\[\s*\d+\]\s+[0-9a-fA-F]+\s+(\S+)\s*$"
)


def extract_exports(objdump_output: str) -> list[str]:
    in_name_table = False
    names = []
    for line in objdump_output.splitlines():
        if line.startswith("[Ordinal/Name Pointer] Table"):
            in_name_table = True
            continue
        if not in_name_table:
            continue
        match = EXPORT_ROW.match(line)
        if match:
            names.append(match.group(1))
        elif names:
            break
    if not names:
        raise ValueError("no named WinHTTP exports found in objdump output")
    if len(names) != len(set(names)):
        raise ValueError("duplicate named WinHTTP exports found in objdump output")
    return names


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backend", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    result = subprocess.run(
        ["objdump", "-p", str(args.backend)],
        check=True,
        capture_output=True,
        text=True,
    )
    exports = extract_exports(result.stdout)
    additions = {"VrcrafterPing", "VrcrafterStart"}
    if additions.intersection(exports):
        raise ValueError("backend unexpectedly exports a Vrcrafter symbol")

    lines = ["LIBRARY winhttp", "EXPORTS"]
    lines.extend(
        f"    {name}=vrcrafter-winhttp-backend.{name}" for name in exports
    )
    lines.extend(("    VrcrafterPing @1000", "    VrcrafterStart @1001"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

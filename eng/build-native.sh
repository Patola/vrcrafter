#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(CDPATH= cd -- "$script_dir/.." && pwd)"
cd "$root_dir"

proton_dir="${PROTON_DIR:-$HOME/.local/share/Steam/steamapps/common/Proton 11.0}"
IFS=$'\t' read -r proton_version proton_revision backend_relative expected_hash < <(
    python3 - "$root_dir/eng/dependencies.lock.json" <<'PY'
import json
from pathlib import Path
import sys

document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
backend = document["protonWinHttpBackend"]
print("\t".join((backend["version"], backend["sourceRevision"],
                 backend["relativePath"], backend["sha256"])))
PY
)
backend="$proton_dir/$backend_relative"

if [[ ! -f "$backend" ]]; then
    printf 'Pinned Proton %s WinHTTP backend is missing (source revision %s): %s\n' \
        "$proton_version" "$proton_revision" "$backend" >&2
    exit 1
fi
actual_hash="$(sha256sum -- "$backend")"
actual_hash="${actual_hash%% *}"
if [[ "$actual_hash" != "$expected_hash" ]]; then
    printf 'Pinned Proton %s WinHTTP backend hash mismatch (source revision %s).\n' \
        "$proton_version" "$proton_revision" >&2
    printf 'Expected SHA-256: %s\nActual SHA-256:   %s\n' \
        "$expected_hash" "$actual_hash" >&2
    printf 'Stock Proton update or modified backend detected; review a pristine backend and explicitly update the pin before building.\n' >&2
    exit 1
fi
printf 'PINNED_PROTON_BACKEND_OK version=%s revision=%s sha256=%s\n' \
    "$proton_version" "$proton_revision" "$actual_hash"

mkdir -p artifacts/native artifacts/payload
cp -f "$backend" artifacts/payload/vrcrafter-winhttp-backend.dll
python3 eng/generate-winhttp-exports.py "$backend" artifacts/native/winhttp.def
x86_64-w64-mingw32-gcc -shared -std=c11 -O2 -Wall -Wextra -Werror \
    src/native/winhttp_proxy.c src/native/log.c src/native/mono_host.c \
    artifacts/native/winhttp.def \
    -o artifacts/payload/winhttp.dll

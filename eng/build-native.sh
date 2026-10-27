#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(CDPATH= cd -- "$script_dir/.." && pwd)"
cd "$root_dir"

proton_dir="${PROTON_DIR:-$HOME/.local/share/Steam/steamapps/common/Proton 11.0}"
backend="$proton_dir/files/lib/wine/x86_64-windows/winhttp.dll"

test -f "$backend"
mkdir -p artifacts/native artifacts/payload
cp -f "$backend" artifacts/payload/vrcrafter-winhttp-backend.dll
python3 eng/generate-winhttp-exports.py "$backend" artifacts/native/winhttp.def
x86_64-w64-mingw32-gcc -shared -std=c11 -O2 -Wall -Wextra -Werror \
    src/native/winhttp_proxy.c src/native/log.c src/native/mono_host.c \
    artifacts/native/winhttp.def \
    -o artifacts/payload/winhttp.dll

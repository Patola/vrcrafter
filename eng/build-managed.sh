#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(CDPATH= cd -- "$script_dir/.." && pwd)"
cd "$root_dir"

test -f src/Vrcrafter.Bootstrap/EntryPoint.cs
test -f src/Vrcrafter.Host/VrcrafterHost.cs

dotnet build Vrcrafter.sln -c Release

rm -rf artifacts/payload/managed
mkdir -p artifacts/payload/managed
cp src/Vrcrafter.Bootstrap/bin/Release/net48/*.dll artifacts/payload/managed/
cp src/Vrcrafter.Host/bin/Release/net48/Vrcrafter.Host.dll artifacts/payload/managed/

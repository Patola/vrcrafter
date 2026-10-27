#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(CDPATH= cd -- "$script_dir/.." && pwd)"
cd "$root_dir"

test -f src/Vrcrafter.Bootstrap/EntryPoint.cs
test -f src/Vrcrafter.Host/VrcrafterHost.cs

dotnet build Vrcrafter.sln -c Release
dotnet build src/Vrcrafter.BepInExControl/Vrcrafter.BepInExControl.csproj -c Release

rm -rf artifacts/payload/managed artifacts/payload/bepinex
mkdir -p artifacts/payload/managed artifacts/payload/bepinex/plugins
cp src/Vrcrafter.Bootstrap/bin/Release/net48/*.dll artifacts/payload/managed/
cp src/Vrcrafter.Host/bin/Release/net48/Vrcrafter.Host.dll artifacts/payload/managed/
cp -a artifacts/deps/bepinex/BepInEx/core artifacts/payload/bepinex/core
cp src/Vrcrafter.BepInExControl/bin/Release/net48/Vrcrafter.BepInExControl.dll \
    artifacts/payload/bepinex/plugins/Vrcrafter.BepInExControl.dll

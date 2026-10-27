#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(CDPATH= cd -- "$script_dir/.." && pwd)"
stage_dir="$root_dir/artifacts/proton-dist/vrcrafter-proton"
tool_dir="$HOME/.local/share/Steam/compatibilitytools.d/vrcrafter-proton"
payload_dir="$HOME/.local/share/vrcrafter/payload"
log_dir="$HOME/.local/share/vrcrafter/logs"

for required_file in \
    "$stage_dir/proton" \
    "$stage_dir/compatibilitytool.vdf" \
    "$stage_dir/toolmanifest.vdf" \
    "$stage_dir/licenses/Proton-dist.LICENSE.txt" \
    "$stage_dir/vrcrafter/payload/winhttp.dll" \
    "$stage_dir/vrcrafter/payload/vrcrafter-winhttp-backend.dll" \
    "$stage_dir/vrcrafter/payload/managed/Vrcrafter.Bootstrap.dll"; do
    test -f "$required_file"
done

grep -q '"display_name" "vrcrafter-proton"' "$stage_dir/compatibilitytool.vdf"
mkdir -p "$(dirname "$tool_dir")" "$(dirname "$payload_dir")" "$log_dir"
rsync -a --delete "$stage_dir/" "$tool_dir/"
rsync -a --delete "$stage_dir/vrcrafter/payload/" "$payload_dir/"
mkdir -p "$payload_dir/licenses"
rsync -a --delete "$stage_dir/licenses/" "$payload_dir/licenses/"

printf 'Installed %s\n' "$tool_dir"
printf 'Installed payload %s\n' "$payload_dir"
printf 'Restart Steam and select vrcrafter-proton for The Planet Crafter.\n'

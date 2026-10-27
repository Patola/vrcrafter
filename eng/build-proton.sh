#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(CDPATH= cd -- "$script_dir/.." && pwd)"
cd "$root_dir"

proton_dir="$root_dir/third_party/Proton"
patch="$root_dir/proton/patches/0001-vrcrafter-launcher.patch"
build_dir="$root_dir/artifacts/proton-build"
stage_dir="$root_dir/artifacts/proton-dist/vrcrafter-proton"
expected_pin="db9e6ffbf24a95b104fb699dd62532c70a2f9a51"

actual_pin="$(git -C "$proton_dir" rev-parse HEAD)"
if [[ "$actual_pin" != "$expected_pin" ]]; then
    printf 'Proton must be pinned to proton-11.0-2 (%s), found %s\n' "$expected_pin" "$actual_pin" >&2
    exit 1
fi

git -C "$proton_dir" submodule update --init --recursive

for payload_file in \
    artifacts/payload/winhttp.dll \
    artifacts/payload/vrcrafter-winhttp-backend.dll \
    artifacts/payload/managed/Vrcrafter.Bootstrap.dll \
    artifacts/payload/bepinex/core/BepInEx.dll \
    artifacts/payload/bepinex/plugins/Vrcrafter.BepInExControl.dll; do
    test -f "$payload_file"
done

if git -C "$proton_dir" apply --reverse --check "$patch" >/dev/null 2>&1; then
    printf 'VRCrafter launcher patch is already applied.\n'
else
    (
        cd "$proton_dir"
        git apply --check "$patch"
        git apply "$patch"
    )
fi

mkdir -p "$proton_dir/vrcrafter"
rsync -a --delete artifacts/payload/ "$proton_dir/vrcrafter/payload/"
mkdir -p "$build_dir"

configure=(
    "$proton_dir/configure.sh"
    --enable-ccache
    --build-name=vrcrafter-proton
)
if [[ -n "${PROTON_CONTAINER_ENGINE:-}" ]]; then
    configure+=("--container-engine=$PROTON_CONTAINER_ENGINE")
fi

(
    cd "$build_dir"
    "${configure[@]}"
)
make -C "$build_dir" dist

mkdir -p "$root_dir/artifacts/proton-dist"
rsync -a --delete "$build_dir/dist/" "$stage_dir/"
rsync -a --delete artifacts/payload/bepinex/ "$stage_dir/vrcrafter/payload/bepinex/"
python3 eng/package-licenses.py "$stage_dir"
grep -q '"display_name" "vrcrafter-proton"' "$stage_dir/compatibilitytool.vdf"
test -f "$stage_dir/vrcrafter/payload/winhttp.dll"
test -f "$stage_dir/vrcrafter/payload/vrcrafter-winhttp-backend.dll"
test -f "$stage_dir/vrcrafter/payload/managed/Vrcrafter.Bootstrap.dll"
test -f "$stage_dir/vrcrafter/payload/bepinex/core/BepInEx.dll"
test -f "$stage_dir/vrcrafter/payload/bepinex/plugins/Vrcrafter.BepInExControl.dll"
printf 'Staged custom compatibility tool at %s\n' "$stage_dir"

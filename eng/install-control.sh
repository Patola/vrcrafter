#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(CDPATH= cd -- "$script_dir/.." && pwd)"
default_game_dir="/games/SteamLibrary/steamapps/common/The Planet Crafter"
game_dir="$(realpath -m -- "${TPC_GAME_DIR:-$default_game_dir}")"
control_dir="${TPC_CONTROL_DIR:-}"

if [[ -z "$control_dir" ]]; then
    printf 'Set TPC_CONTROL_DIR to a dedicated copied game depot; refusing the live installation.\n' >&2
    exit 2
fi
if [[ ! -d "$control_dir" ]]; then
    printf 'Control depot does not exist: %s\n' "$control_dir" >&2
    exit 2
fi

control_dir="$(realpath -e -- "$control_dir")"
if [[ "$control_dir" == "$game_dir" || "$control_dir" == "$default_game_dir" ]]; then
    printf 'Refusing to modify the original game installation: %s\n' "$control_dir" >&2
    exit 2
fi
if [[ ! -f "$control_dir/Planet Crafter.exe" \
    || ! -d "$control_dir/Planet Crafter_Data/Managed" ]]; then
    printf 'Control depot is not a Planet Crafter game copy: %s\n' "$control_dir" >&2
    exit 2
fi

for existing in winhttp.dll doorstop_config.ini BepInEx; do
    if [[ -e "$control_dir/$existing" ]]; then
        printf 'Refusing to overwrite existing control file: %s\n' "$control_dir/$existing" >&2
        exit 2
    fi
done

bepinex_dir="$root_dir/artifacts/deps/bepinex"
doorstop_dir="$root_dir/artifacts/deps/doorstop/x64"
license_dir="$root_dir/proton/licenses"
control_plugin="$root_dir/src/Vrcrafter.BepInExControl/bin/Release/net48/Vrcrafter.BepInExControl.dll"
for required in \
    "$bepinex_dir/BepInEx/core/BepInEx.dll" \
    "$bepinex_dir/BepInEx/core/0Harmony.dll" \
    "$bepinex_dir/doorstop_config.ini" \
    "$doorstop_dir/winhttp.dll" \
    "$doorstop_dir/../LICENSE" \
    "$license_dir/BepInEx-LICENSE.txt" \
    "$license_dir/HarmonyX-LICENSE.txt" \
    "$license_dir/MonoMod-LICENSE.txt" \
    "$license_dir/Mono.Cecil-LICENSE.txt" \
    "$license_dir/UPSTREAM-SOURCES.txt" \
    "$root_dir/LICENSE" \
    "$control_plugin"; do
    if [[ ! -f "$required" ]]; then
        printf 'Required pinned control input is missing: %s\n' "$required" >&2
        exit 1
    fi
done

staging="$(mktemp -d "$control_dir/.vrcrafter-control.XXXXXX")"
trap 'rm -rf -- "$staging"' EXIT
mkdir -p "$staging/BepInEx/plugins" "$staging/BepInEx/config" "$staging/licenses"
cp -a -- "$bepinex_dir/BepInEx/core" "$staging/BepInEx/core"
cp -- "$control_plugin" "$staging/BepInEx/plugins/Vrcrafter.BepInExControl.dll"
cp -- "$doorstop_dir/winhttp.dll" "$staging/winhttp.dll"
cp -- "$bepinex_dir/doorstop_config.ini" "$staging/doorstop_config.ini"
cp -- "$doorstop_dir/../LICENSE" "$staging/licenses/UnityDoorstop-LICENSE.txt"
cp -- "$root_dir/LICENSE" "$staging/licenses/VRCrafter-LICENSE.txt"
cp -- "$license_dir/BepInEx-LICENSE.txt" \
    "$license_dir/HarmonyX-LICENSE.txt" \
    "$license_dir/MonoMod-LICENSE.txt" \
    "$license_dir/Mono.Cecil-LICENSE.txt" \
    "$license_dir/UPSTREAM-SOURCES.txt" \
    "$staging/licenses/"
printf '[Chainloader]\nHideManagerGameObject = true\n' > "$staging/BepInEx/config/BepInEx.cfg"
cp -a -- "$staging/." "$control_dir/"

printf 'Installed the unmodified Doorstop/BepInEx control in %s\n' "$control_dir"
printf 'Runtime remains manual: use custom Proton without VRCRAFTER_ENABLE, with WINEDLLOVERRIDES=winhttp=n,b and one managed game instance.\n'
printf 'No game, Steam, GUI, Wine, or Proton process was launched. Remove the copied depot after validation.\n'

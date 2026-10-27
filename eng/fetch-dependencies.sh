#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
root_dir="$(CDPATH= cd -- "$script_dir/.." && pwd)"
lock_file="$script_dir/dependencies.lock.json"
deps_dir="$root_dir/artifacts/deps"
download_dir="$root_dir/artifacts/downloads"

mkdir -p "$deps_dir" "$download_dir"

package_records="$(python3 - "$lock_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as lock_file:
    document = json.load(lock_file)

for dependency in document["dependencies"]:
    print(dependency["name"], dependency["url"], dependency["sha256"], sep="\t")
PY
)"

while IFS=$'\t' read -r name url expected_sha256; do
    case "$name" in
        BepInEx)
            destination="$deps_dir/bepinex"
            ;;
        UnityDoorstop)
            destination="$deps_dir/doorstop"
            ;;
        *)
            printf 'Unknown dependency: %s\n' "$name" >&2
            exit 1
            ;;
    esac

    archive="$download_dir/${url##*/}"
    curl -fL --retry 3 --output "$archive" "$url"
    printf '%s  %s\n' "$expected_sha256" "$archive" | sha256sum --check --status -
    printf 'Verified %s\n' "$name"

    rm -rf -- "$destination"
    mkdir -p "$destination"
    unzip -q "$archive" -d "$destination"
done <<< "$package_records"

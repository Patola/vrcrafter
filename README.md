# vrcrafter

Linux-only Proton-based loader for The Planet Crafter (Steam appid `1284190`). This milestone only loads the managed bootstrap into Unity Mono; it has **no VR features**, OpenXR integration, camera changes, or gameplay changes.

## Custom Proton requirement

Real-game validation must use the separately built `vrcrafter-proton` compatibility tool. Do not use stock Proton for mod validation. The installer writes only to:

- `$HOME/.local/share/Steam/compatibilitytools.d/vrcrafter-proton`
- `$HOME/.local/share/vrcrafter/payload`
- `$HOME/.local/share/vrcrafter/logs` (created for native logs)

It never installs into stock Proton or the game directory. On an enabled launch, the custom launcher deploys `winhttp.dll` and `vrcrafter-winhttp-backend.dll` into the selected prefix's `drive_c/windows/system32`; it does not use `WINEPATH` or copy files beside `Planet Crafter.exe`.

## Build dependencies

Install these host tools using your distribution's packages:

- Git, Bash, Python 3, GNU Make, and rsync.
- Rootless Podman (recommended) or a working Docker-compatible container engine for Proton's Steam Runtime SDK build.
- .NET SDK with NuGet access for the pinned .NET Framework 4.8 reference assemblies.
- `x86_64-w64-mingw32-gcc` and MinGW/binutils tools, including `objdump`, for the native payload.
- curl, unzip, and `sha256sum` for pinned dependency retrieval.
- ccache if build caching is desired; `build-proton.sh` enables Proton's container-side ccache support.

The Proton source is pinned to Valve tag `proton-11.0-2` (`db9e6ffbf24a95b104fb699dd62532c70a2f9a51`). Initialize all source submodules before building:

```bash
git submodule update --init --recursive
git -C third_party/Proton describe --tags --exact-match
```

The second command must print `proton-11.0-2`.

## Build and stage

Build the managed and native payload first, then run Proton's documented container build. For example, with rootless Podman:

```bash
bash eng/fetch-dependencies.sh
bash eng/build-managed.sh
bash eng/build-native.sh
PROTON_CONTAINER_ENGINE=podman bash eng/build-proton.sh
```

`eng/build-native.sh` reads the pinned Wine builtin from `PROTON_DIR` (default: `$HOME/.local/share/Steam/steamapps/common/Proton 11.0`) to construct the forwarding backend. This is a build input only, not game validation.

`eng/build-proton.sh` verifies the Proton commit, applies `proton/patches/0001-vrcrafter-launcher.patch` with `git apply --check`, configures an out-of-tree build in `artifacts/proton-build`, runs `make dist`, and stages the result at:

```text
artifacts/proton-dist/vrcrafter-proton
```

The full Proton compilation is long and downloads the Proton SDK container. `eng/package-licenses.py` runs as part of staging and fails if any required project, managed-dependency, Proton, or Wine notice is absent. Notices and upstream source references are placed in the staged tool's `licenses` directory.

## Install and select in Steam

After reviewing and completing the staged build, run:

```bash
bash eng/install-local.sh
```

Restart Steam, open **The Planet Crafter → Properties → Compatibility**, and select **`vrcrafter-proton`**. Do not select stock Proton for loader validation.

The launcher is appid-gated and additionally requires an explicit opt-in:

- Disabled / ordinary flat run: leave launch options empty, or use `%command%` without `VRCRAFTER_ENABLE`.
- Enabled diagnostic run: `VRCRAFTER_ENABLE=1 PROTON_LOG=1 %command%`.

Only the enabled appid receives `WINEDLLOVERRIDES=winhttp=n,b`, `VRCRAFTER_PAYLOAD`, and `VRCRAFTER_LOG_DIR`. Unrelated DLL overrides are preserved. The default payload and native log paths are:

```text
$HOME/.local/share/vrcrafter/payload
$HOME/.local/share/vrcrafter/logs/vrcrafter-native.log
```

Optional `VRCRAFTER_PAYLOAD` and `VRCRAFTER_LOG_DIR` launch-option overrides use Linux paths; the launcher converts them to Wine `Z:` paths. Proton's diagnostic log defaults to `$HOME/steam-1284190.log` and can be redirected with `PROTON_LOG_DIR`. The managed log is `drive_c/users/steamuser/AppData/Local/vrcrafter/managed.log` inside the app's Proton prefix.

## Validation status and acceptance diagnostics

Custom-Proton runtime validation has demonstrated identity acceptance, Harmony patching, `PING=42`, host ticks, worker dispatch, original-method continuation, 30-second GC stress with 120 main-thread callbacks, clean host destruction, optional Chainloader startup, and the Doorstop 4.6.0 control. The complete verifier matrix passed normal direct, clean-prefix direct, disabled, process-exclusion, missing-managed, deliberate managed-exception, wrong-hash, and custom-Proton Doorstop control cases. VR, OpenXR, stereo rendering, and multiplayer compatibility remain **unverified** and are outside this loader milestone.

Every game launch requires explicit per-launch user permission and at most one game instance. Use a backed-up private test save. Do not launch the game as part of source builds or verifier tests, and do not use stock Proton for game validation. Confirm that no `BepInEx` directory or `winhttp.dll` appears in the game installation.

### Bounded source checks

Run these commands from the repository root. They do not launch a game or Proton:

```bash
bash eng/build-managed.sh
bash eng/build-native.sh
python3 eng/check_licenses.py
python3 tests/integration/test-verify-loader.py
python3 -m py_compile tests/integration/verify-loader.py tests/integration/test-verify-loader.py
bash -n eng/install-control.sh
git diff --check
```

Compare every native forwarding export and reject a Mono import with the existing export parser:

```bash
python3 - <<'PY'
import importlib.util
import subprocess
from pathlib import Path
spec = importlib.util.spec_from_file_location("exports", "eng/generate-winhttp-exports.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def exports(path):
    output = subprocess.check_output(["objdump", "-p", str(path)], text=True)
    assert "dll name: mono" not in output.lower()
    return set(module.extract_exports(output))
backend = exports(Path("artifacts/payload/vrcrafter-winhttp-backend.dll"))
proxy = exports(Path("artifacts/payload/winhttp.dll"))
assert backend <= proxy, sorted(backend - proxy)
assert {"VrcrafterPing", "VrcrafterStart"} <= proxy
print("NATIVE_EXPORTS_OK", len(backend), len(proxy))
PY
```

Inspect managed reference privacy and primary-payload hygiene exactly:

```bash
python3 - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
references = 0
for project in Path("src").glob("*/*.csproj"):
    root = ET.parse(project).getroot()
    for reference in root.iter("Reference"):
        hint = reference.find("HintPath")
        if hint is None or "Planet Crafter_Data/Managed" not in (hint.text or ""):
            continue
        private = reference.find("Private")
        assert private is not None and private.text.strip().lower() == "false"
        references += 1
assert references > 0
for path in Path("artifacts/payload").rglob("*"):
    if not path.is_file():
        continue
    name = path.name.lower()
    assert not name.startswith(("assembly-csharp", "unityengine", "uuvr", "bepinex.utility")), path
    assert name not in ("doorstop_config.ini", ".doorstop_version"), path
print("MANAGED_REFERENCES_OK", references)
print("PRIMARY_PAYLOAD_HYGIENE_OK")
PY
```

The primary payload must not contain game/Unity assemblies, UUVR, BepInEx.Utility, or Doorstop. Do not add those files or build utilities to source control.

### Acceptance setup

The following is a procedure for later, individually authorized runs, not a record of completed runtime checks. Start with a new acceptance directory and set paths explicitly. The direct `proton run` procedure does not edit Steam metadata:

```bash
ROOT="$PWD"
ACCEPT="$ROOT/artifacts/logs/acceptance"
PAYLOAD="$HOME/.local/share/vrcrafter/payload"
PROTON="$HOME/.local/share/Steam/compatibilitytools.d/vrcrafter-proton/proton"
TPC_GAME_DIR="/games/SteamLibrary/steamapps/common/The Planet Crafter"
NORMAL_COMPAT="$HOME/.local/share/Steam/steamapps/compatdata/1284190"
PREFIX="$NORMAL_COMPAT/pfx"
SAVE_DIR="$PREFIX/drive_c/users/steamuser/AppData/LocalLow/MijuGames/The Planet Crafter"
if [[ -e "$ACCEPT" ]]; then mv -- "$ACCEPT" "$ACCEPT.previous-$(date +%Y%m%d-%H%M%S)"; fi
mkdir -p "$ACCEPT"/{normal,clean-prefix,disabled,process-exclusion,missing-managed,managed-exception,wrong-hash,control}
cp -a -- "$SAVE_DIR" "$SAVE_DIR.pre-vrcrafter"
cp -a -- "$PREFIX" "$PREFIX.pre-vrcrafter"
```

Define these helpers in the same Bash shell. They archive any prior managed log outside the acceptance directory, then collect per-run managed and Player logs after process exit; Proton and enabled native logs are already written to the run directory:

```bash
wine_path() { printf 'Z:%s' "${1//\//\\}"; }
run_custom() {
    local run="$1" compat="$2"
    shift 2
    local prefix="$compat/pfx"
    local managed="$prefix/drive_c/users/steamuser/AppData/Local/vrcrafter/managed.log"
    local player="$prefix/drive_c/users/steamuser/AppData/LocalLow/MijuGames/The Planet Crafter/Player.log"
    mkdir -p "$ACCEPT/$run" "$compat" "$ROOT/artifacts/logs/previous"
    if [[ -f "$managed" ]]; then
        mv -- "$managed" "$ROOT/artifacts/logs/previous/$run-managed.log"
    fi
    env STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam" \
        STEAM_COMPAT_DATA_PATH="$compat" SteamGameId=1284190 \
        PROTON_LOG=1 PROTON_LOG_DIR="$ACCEPT/$run" "$@" \
        "$PROTON" run "${TPC_TEST_EXECUTABLE:-$TPC_GAME_DIR/Planet Crafter.exe}"
    if [[ -f "$managed" ]]; then cp -- "$managed" "$ACCEPT/$run/managed.log"; fi
    if [[ -f "$player" ]]; then cp -- "$player" "$ACCEPT/$run/Player.log"; fi
}
```

Use a separate compatibility directory for each intentional failure so old managed logs cannot contaminate its evidence. Obtain explicit permission immediately before every command that invokes `run_custom` or `proton run`, and confirm no other game instance is running.

### Authorized runtime matrix and gameplay steps

Run in this order, restoring normal files after each intentional failure:

1. **Disabled native gate:** stage the proxy in a dedicated test prefix, load it with an explicit WinHTTP override, but do not set `VRCRAFTER_ENABLE`. Required evidence is positive `PROCESS` and enable-based `ACTIVATION_SKIPPED`; an ordinary no-injection launch cannot produce native markers.

   ```bash
   DISABLED_COMPAT="$ROOT/artifacts/acceptance-compat/disabled"
   mkdir -p "$DISABLED_COMPAT/pfx/drive_c/windows/system32"
   cp -- "$PAYLOAD/winhttp.dll" "$PAYLOAD/vrcrafter-winhttp-backend.dll" \
       "$DISABLED_COMPAT/pfx/drive_c/windows/system32/"
   run_custom disabled "$DISABLED_COMPAT" WINEDLLOVERRIDES=winhttp=n,b \
       VRCRAFTER_PAYLOAD="$(wine_path "$PAYLOAD")" \
       VRCRAFTER_LOG_DIR="$(wine_path "$ACCEPT/disabled")"
   ```

2. **Process exclusion:** use a renamed executable only in a dedicated copied depot. Require `PROCESS`, then `ACTIVATION_SKIPPED error=0 executable is not Planet Crafter.exe`, and no managed startup:

   ```bash
   HELPER_DEPOT="$ROOT/artifacts/helper-depot/The Planet Crafter"
   mkdir -p "$HELPER_DEPOT"
   cp -a -- "$TPC_GAME_DIR/." "$HELPER_DEPOT/"
   cp -- "$HELPER_DEPOT/Planet Crafter.exe" "$HELPER_DEPOT/vrcrafter-helper.exe"
   TPC_TEST_EXECUTABLE="$HELPER_DEPOT/vrcrafter-helper.exe" \
       run_custom process-exclusion "$ROOT/artifacts/acceptance-compat/process-exclusion" \
       VRCRAFTER_ENABLE=1 VRCRAFTER_LOG_DIR="$ACCEPT/process-exclusion"
   ```
3. **Missing managed DLL:** move only the installed bootstrap aside, run, then restore it immediately:

   ```bash
   mv -- "$PAYLOAD/managed/Vrcrafter.Bootstrap.dll" "$PAYLOAD/managed/Vrcrafter.Bootstrap.dll.off"
   run_custom missing-managed "$ROOT/artifacts/acceptance-compat/missing-managed" \
       VRCRAFTER_ENABLE=1 VRCRAFTER_LOG_DIR="$ACCEPT/missing-managed"
   mv -- "$PAYLOAD/managed/Vrcrafter.Bootstrap.dll.off" "$PAYLOAD/managed/Vrcrafter.Bootstrap.dll"
   ```

4. **Deliberate managed exception:** back up the source, inject `loader-self-test` inside the entry-point `try`, rebuild/install, run, then restore and rebuild/install immediately:

   ```bash
   cp -- src/Vrcrafter.Bootstrap/EntryPoint.cs artifacts/EntryPoint.cs.task9-backup
   python3 - <<'PY'
   from pathlib import Path
   path = Path("src/Vrcrafter.Bootstrap/EntryPoint.cs")
   text = path.read_text()
   old = "            try\n            {\n"
   assert text.count(old) == 1
   path.write_text(text.replace(old, old + "                throw new InvalidOperationException(\"loader-self-test\");\n", 1))
   PY
   bash eng/build-managed.sh && bash eng/install-local.sh
   run_custom managed-exception "$ROOT/artifacts/acceptance-compat/managed-exception" \
       VRCRAFTER_ENABLE=1 VRCRAFTER_LOG_DIR="$ACCEPT/managed-exception"
   cp -- artifacts/EntryPoint.cs.task9-backup src/Vrcrafter.Bootstrap/EntryPoint.cs
   bash eng/build-managed.sh && bash eng/install-local.sh
   ```

5. **Wrong game hash:** preserve the source, replace only the expected hash with 64 zeroes, rebuild/install, run, then restore and rebuild/install immediately. Because the untouched game still has the pinned real hash, the evidence must contain `IDENTITY_HASH actual=3d7457446cbbed551f938b5271f294f45ec100e1f295eeba9b0884b3cdd9191e`, `IDENTITY_REJECT`, and `MANAGED_RESULT=4`:

   ```bash
   cp -- src/Vrcrafter.Bootstrap/GameIdentity.cs artifacts/GameIdentity.cs.task9-backup
   python3 - <<'PY'
   from pathlib import Path
   path = Path("src/Vrcrafter.Bootstrap/GameIdentity.cs")
   text = path.read_text()
   old = "3d7457446cbbed551f938b5271f294f45ec100e1f295eeba9b0884b3cdd9191e"
   assert text.count(old) == 1
   path.write_text(text.replace(old, "0" * 64, 1))
   PY
   bash eng/build-managed.sh && bash eng/install-local.sh
   run_custom wrong-hash "$ROOT/artifacts/acceptance-compat/wrong-hash" \
       VRCRAFTER_ENABLE=1 VRCRAFTER_LOG_DIR="$ACCEPT/wrong-hash"
   cp -- artifacts/GameIdentity.cs.task9-backup src/Vrcrafter.Bootstrap/GameIdentity.cs
   bash eng/build-managed.sh && bash eng/install-local.sh
   ```
6. **Normal direct run:** enter gameplay with the backed-up private save, exercise the original input path, perform at least one scene transition, remain in gameplay until `GC_STRESS_OK`, and exit cleanly:

   ```bash
   run_custom normal "$NORMAL_COMPAT" VRCRAFTER_ENABLE=1 VRCRAFTER_LOG_DIR="$ACCEPT/normal"
   ```

7. **Clean prefix:** repeat the same gameplay, input, scene-transition, GC, and clean-exit steps in a new compatibility directory, then preserve its Proton log under the required name:

   ```bash
   CLEAN_COMPAT="$ROOT/artifacts/acceptance-compat/clean-prefix"
   run_custom clean-prefix "$CLEAN_COMPAT" VRCRAFTER_ENABLE=1 VRCRAFTER_LOG_DIR="$ACCEPT/clean-prefix"
   cp -- "$ACCEPT/clean-prefix/steam-1284190.log" "$ACCEPT/clean-prefix/proton.log"
   ```

   `proton.log` must contain `Upgrading prefix from None`; copied direct-run logs are not clean-prefix evidence.
8. **Custom-Proton Doorstop control:** build and install only into a dedicated copied depot. Do not set `VRCRAFTER_ENABLE`; the custom launcher therefore does not deploy the primary native host:

   ```bash
   dotnet build src/Vrcrafter.BepInExControl/Vrcrafter.BepInExControl.csproj -c Release
   CONTROL_DEPOT="$ROOT/artifacts/control-depot/The Planet Crafter"
   CONTROL_COMPAT="$ROOT/artifacts/acceptance-compat/control"
   mkdir -p "$CONTROL_DEPOT"
   cp -a -- "$TPC_GAME_DIR/." "$CONTROL_DEPOT/"
   TPC_GAME_DIR="$TPC_GAME_DIR" TPC_CONTROL_DIR="$CONTROL_DEPOT" bash eng/install-control.sh
   env STEAM_COMPAT_CLIENT_INSTALL_PATH="$HOME/.local/share/Steam" \
       STEAM_COMPAT_DATA_PATH="$CONTROL_COMPAT" SteamGameId=1284190 \
       PROTON_LOG=1 PROTON_LOG_DIR="$ACCEPT/control" WINEDLLOVERRIDES=winhttp=n,b \
       "$PROTON" run "$CONTROL_DEPOT/Planet Crafter.exe"
   cp -- "$CONTROL_DEPOT/BepInEx/LogOutput.log" "$ACCEPT/control/managed.log"
   ```

   Enter gameplay and exercise original input. The control requires `BEPINEX_CONTROL_OK`, `BEPINEX_CONTROL_HARMONY_OK`, and `ORIGINAL_CONTINUES`, with no native-host or Chainloader markers. Never install this control into the real depot.

### Verifier commands and expected markers

Run each isolated mode, then the complete matrix:

```bash
python3 tests/integration/verify-loader.py direct "$ACCEPT/normal"
python3 tests/integration/verify-loader.py missing-managed "$ACCEPT/missing-managed"
python3 tests/integration/verify-loader.py managed-exception "$ACCEPT/managed-exception"
python3 tests/integration/verify-loader.py wrong-hash "$ACCEPT/wrong-hash"
python3 tests/integration/verify-loader.py control "$ACCEPT/control"
python3 tests/integration/verify-loader.py "$ACCEPT"
```

Acceptance requires all eight directories: `normal`, `clean-prefix`, `disabled`, `process-exclusion`, `missing-managed`, `managed-exception`, `wrong-hash`, and `control`. Expected failures must match their specific signatures: `MANAGED_ASSEMBLY_OPEN error=2`; `loader-self-test` with result 2; or the actual pinned game hash, `IDENTITY_REJECT`, and result 4. Empty, unrelated, or success-contaminated evidence fails. General marker checks exclude `proton.log` and `steam-*.log`, so unrelated Proton/.NET messages cannot masquerade as managed failures; clean-prefix creation evidence is read separately from its `proton.log`.

Expected ordered direct markers are:

```text
IDENTITY_ACCEPT HARMONY_PATCH HOST_CREATE HOST_UPDATE WORKER_DISPATCH ORIGINAL_CONTINUES
GC_STRESS_START HOST_UPDATE WORKER_DISPATCH GC_STRESS_OK HOST_DESTROY
```

The GC diagnostic allocates for at least 30 seconds and posts every 250 ms. Verification requires at least 100 contiguous same-thread callbacks, `elapsed_ms` spanning at least 25 seconds, and a final callback within two seconds of the reported completion. Sparse host ticks are valid when their positive numbers are strictly increasing on an unchanged host thread; allocation count must be positive and callback count exact. A successful verifier prints `LOADER_MARKERS_OK`; no runtime marker is claimed from source checks.

The optional Chainloader bridge can be checked separately with `python3 tests/integration/verify-loader.py chainloader LOG_DIRECTORY` after its runtime evidence exists. Programmatic `Chainloader.Initialize`/`Start` is **not Cecil preloader-patcher compatibility**: it does not establish preloader-patcher execution or general BepInEx compatibility.

### Restoration

After the game has exited, restore the source backups and managed bootstrap with the commands paired with each negative case above. Move test saves/prefixes aside rather than deleting them, then restore the backups:

```bash
mv -- "$SAVE_DIR" "$SAVE_DIR.rejected"
mv -- "$SAVE_DIR.pre-vrcrafter" "$SAVE_DIR"
mv -- "$PREFIX" "$PREFIX.rejected"
mv -- "$PREFIX.pre-vrcrafter" "$PREFIX"
bash eng/build-managed.sh && bash eng/install-local.sh
```

Keep the copied control depot, failed prefixes, and logs only for review; they are not part of the primary payload or a successful restoration.

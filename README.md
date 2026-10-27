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

The direct custom-Proton run has demonstrated identity acceptance, Harmony patching, `PING=42`, host ticks, worker dispatch, original-method continuation, and `HOST_DESTROY`. The new 30-second GC stress run, expanded acceptance matrix, clean-prefix run, and optional Chainloader runtime remain **unverified**. Source checks do not prove runtime behavior, VR, OpenXR, stereo rendering, or multiplayer compatibility.

Every game launch requires explicit per-launch user permission and at most one game instance. Use a backed-up private test save. Do not launch the game as part of source builds or verifier tests, and do not use stock Proton for game validation. Confirm that no `BepInEx` directory or `winhttp.dll` appears in the game installation.

Run the bounded source checks from the repository root:

```bash
bash eng/build-managed.sh
bash eng/build-native.sh
python3 eng/check_licenses.py
python3 tests/integration/test-verify-loader.py
python3 -m py_compile tests/integration/verify-loader.py tests/integration/test-verify-loader.py
git diff --check
```

`eng/build-native.sh` regenerates `artifacts/native/winhttp.def` from the pinned backend and fails on missing, duplicate, or unexpected Vrcrafter exports. Inspect the resulting export table with:

```bash
objdump -p artifacts/payload/winhttp.dll
```

The table must contain every backend WinHTTP forwarding export plus `VrcrafterPing` and `VrcrafterStart`, and no Mono import. The managed project files must keep all game and Unity references non-private (`<Private>false</Private>`). The primary payload must not contain game/Unity assemblies, UUVR, BepInEx.Utility, or Doorstop; none of those files may be added to source control.

### Per-run logs and verifier commands

Keep each launch in its own directory so intentional failures cannot satisfy or contaminate a successful run:

```text
artifacts/logs/acceptance/
├── normal/             # enabled direct run, including GC stress and clean exit
├── clean-prefix/       # same successful sequence in a newly created prefix
├── disabled/           # Proton log with VRCRAFTER_ENABLE absent; no loader startup markers
├── process-exclusion/  # enabled helper/crash process; native exclusion markers only
├── missing-managed/    # intentional negative evidence; not part of success verification
├── managed-exception/  # intentional negative evidence; not part of success verification
└── wrong-hash/         # intentional negative evidence; not part of success verification
```

Collect native, managed, Unity Player, and Proton logs for each run. A successful `normal` or `clean-prefix` directory must contain native and managed evidence. A fully disabled launch does not inject the proxy, so its required evidence is an isolated Proton log with no `START`, `START_QUEUED`, `MANAGED_ENTRY`, identity, host-creation, or host-update marker. Process exclusion instead requires `PROCESS`, followed by `ACTIVATION_SKIPPED error=0 executable is not Planet Crafter.exe`, with no loader startup.

After a successful direct run, and after collecting all four required run directories, run:

```bash
python3 tests/integration/verify-loader.py direct artifacts/logs/acceptance/normal
python3 tests/integration/verify-loader.py artifacts/logs/acceptance
```

The second command defaults to `acceptance` mode. It ignores the intentional-negative directories and fails if `normal`, `clean-prefix`, `disabled`, or `process-exclusion` evidence is absent or invalid. It rejects duplicate initialization/host creation, managed exceptions, identity rejection, nonzero managed results, missing original continuation, wrong marker order, and invalid activation controls.

Expected ordered direct markers are:

```text
IDENTITY_ACCEPT HARMONY_PATCH HOST_CREATE HOST_UPDATE WORKER_DISPATCH ORIGINAL_CONTINUES
GC_STRESS_START HOST_UPDATE WORKER_DISPATCH GC_STRESS_OK HOST_DESTROY
```

`GC_STRESS_START duration=30s` starts the diagnostic automatically on the host's first update. It allocates short-lived managed byte arrays for at least 30 seconds and queues a callback every 250 ms. During stress, `HOST_UPDATE tick=N thread=T` must remain sequential on one thread; each `WORKER_DISPATCH source=gc-stress callback=N thread=T` must use that same thread. `GC_STRESS_OK` must report at least 30000 ms, a positive allocation count, and the exact number of observed callbacks. `GC_STRESS_ERROR`, duplicate stress/destroy markers, missing ticks/callbacks, or thread changes fail verification. A successful verifier prints `LOADER_MARKERS_OK`.

The optional Chainloader bridge can be checked separately with `python3 tests/integration/verify-loader.py chainloader LOG_DIRECTORY` after its runtime evidence exists. Programmatic `Chainloader.Initialize`/`Start` is **not Cecil preloader-patcher compatibility**: it does not establish preloader-patcher execution or general BepInEx compatibility.

### Save and prefix restoration

Before any authorized runtime test, set `PREFIX` to the actual app prefix and preserve both the save and prefix while the game is closed:

```bash
SAVE_DIR="$PREFIX/drive_c/users/steamuser/AppData/LocalLow/MijuGames/The Planet Crafter"
cp -a -- "$SAVE_DIR" "$SAVE_DIR.pre-vrcrafter"
cp -a -- "$PREFIX" "$PREFIX.pre-vrcrafter"
```

To restore after the game has exited, move the test versions aside rather than deleting them, then move the backups back:

```bash
mv -- "$SAVE_DIR" "$SAVE_DIR.rejected"
mv -- "$SAVE_DIR.pre-vrcrafter" "$SAVE_DIR"
mv -- "$PREFIX" "$PREFIX.rejected"
mv -- "$PREFIX.pre-vrcrafter" "$PREFIX"
```

Restore moved managed payload files immediately after each intentional failure and rerun source builds before any later authorized launch. Keep failed prefixes and logs until their evidence has been reviewed.

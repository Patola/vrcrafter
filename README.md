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

## Validation status and runtime checks

Source pinning and static packaging checks do not prove a Proton build or runtime launch. Build, installation, disabled/enabled launches, clean-prefix behavior, helper-process exclusion, ordinary WinHTTP forwarding, and the ordered loader assertions still require their monitored verification steps. Use a backed-up private test save and at most one controlled game instance. Confirm that no `BepInEx` directory or `winhttp.dll` appears in the game installation, and collect native, managed, Unity Player, and Proton logs for every runtime validation.

# Proton Mono Host Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate a custom Proton 11.0-2 compatibility tool that loads an MIT-licensed managed bootstrap into The Planet Crafter's existing Unity Mono runtime without Doorstop, while retaining stock Proton/Doorstop/BepInEx as a control path.

**Architecture:** A Proton launcher patch supplies appid-gated settings and a payload directory. An x64 Windows `winhttp.dll` proxy forwards the real WinHTTP API and starts a deferred Mono host; the host attaches to Unity's existing root domain and invokes a minimal managed bootstrap. HarmonyX installs a one-shot postfix on `SpaceCraft.PlayerInputDispatcher.Update()`, which creates the persistent Unity main-thread host. No VR rendering or game behavior changes are included in this milestone.

**Tech Stack:** Proton 11.0-2, Wine, C11/Win32, x86_64-w64-mingw32, C#/.NET Framework 4.8 reference assemblies, Unity Mono, HarmonyX/MonoMod, BepInEx 5 control, Python 3, Bash, Podman, Steam.

## Global Constraints

- Project-owned code and assets use the repository's MIT `LICENSE`; preserve third-party notices and upstream Proton/Wine licenses.
- Do not copy, translate, port, link, require, or bundle UUVR, BepInEx.Utility, BepInEx.ConfigurationManager, or other copyleft VR-mod code.
- BepInEx core, HarmonyX, and MonoMod are permitted MIT dependencies. Doorstop is LGPL-2.1 and is used unmodified only in the control path.
- Never redistribute game assemblies. Reference them from `TPC_GAME_DIR`, defaulting to `/games/SteamLibrary/steamapps/common/The Planet Crafter`.
- Never initialize a second Mono runtime, unload Unity's root domain, call `mono_jit_cleanup`, or perform Unity object access on the native worker.
- Keep stock Proton and original game assemblies unchanged. Install only a separately selected compatibility tool and payload.
- Native bootstrap work must occur outside `DllMain`; native/managed callbacks must remain valid for process lifetime.
- Unknown game identity fails without game patches. The accepted initial identity is game version 2.103, Unity 6000.3.2f1, x64 Mono.
- OpenXR, camera changes, multiplayer behavior changes, and VR features are outside this plan.
- Every real-game validation uses a private test save backed up before launch and collects native, managed, BepInEx, Unity Player, and Proton logs.

---

## File map

- `Vrcrafter.sln`: managed loader/control solution.
- `Directory.Build.props`: shared C# build settings and `TPC_GAME_DIR` default.
- `eng/dependencies.lock.json`: exact dependency URLs, versions, licenses, and recorded SHA-256 values.
- `eng/fetch-dependencies.sh`: reproducibly downloads and unpacks pinned dependencies into ignored `artifacts/deps`.
- `eng/check_licenses.py`: rejects missing or disallowed dependency licenses.
- `eng/build-managed.sh`, `eng/build-native.sh`: build managed/native payload from Linux.
- `eng/build-proton.sh`, `eng/install-local.sh`: patch/build Proton and stage the separate compatibility tool/payload.
- `proton/patches/0001-vrcrafter-launcher.patch`: appid-gated launcher integration against pinned Proton.
- `src/native/winhttp_proxy.c`: proxy process gate, deferred startup, exported round-trip function.
- `src/native/mono_host.c`, `src/native/mono_host.h`: dynamic Mono ABI declarations and managed invocation.
- `src/native/log.c`, `src/native/log.h`: native diagnostic logging.
- `eng/generate-winhttp-exports.py`: generates complete forwarders from the pinned Wine builtin DLL.
- `src/Vrcrafter.Bootstrap/`: assembly resolution, managed logging, startup state, Harmony bootstrap.
- `src/Vrcrafter.Host/`: persistent Unity `MonoBehaviour` and main-thread queue.
- `src/Vrcrafter.BepInExControl/`: harmless ordinary BepInEx plugin for the control/fallback.
- `src/Vrcrafter.BepInExBridge/`: optional programmatic BepInEx Chainloader gate after direct-host tests pass.
- `tests/native/probe.c`: Windows console probe for exports and native round trip.
- `tests/integration/verify-loader.py`: structured log assertion and negative-case runner.
- `artifacts/`: ignored dependencies, builds, staged payload, and logs.

### Task 1: Reproducible dependency and license baseline

**Files:**
- Create: `eng/dependencies.lock.json`
- Create: `eng/fetch-dependencies.sh`
- Create: `eng/check_licenses.py`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `.gitignore`
- Create: `Directory.Build.props`

**Interfaces:**
- Produces: `artifacts/deps/bepinex/` containing the matched BepInEx 5 core distribution and `artifacts/deps/doorstop/` containing the unmodified control package.
- Produces: `TPC_GAME_DIR` MSBuild property consumed by every game-reference project.

- [ ] **Step 1: Write the failing license policy test input**

Create `eng/dependencies.lock.json` with these pinned entries and hashes already verified from the official release archives:

```json
{
  "game": {
    "appid": "1284190",
    "version": "2.103",
    "unity": "6000.3.2f1",
    "assemblyCSharpSha256": "3d7457446cbbed551f938b5271f294f45ec100e1f295eeba9b0884b3cdd9191e"
  },
  "allowedLicenses": ["MIT", "LGPL-2.1-only-control"],
  "dependencies": [
    {
      "name": "BepInEx",
      "version": "5.4.23.5",
      "license": "MIT",
      "url": "https://github.com/BepInEx/BepInEx/releases/download/v5.4.23.5/BepInEx_win_x64_5.4.23.5.zip",
      "sha256": "82f9878551030f54657792c0740d9d51a09500eeae1fba21106b0c441e6732c4",
      "role": "managed-core-and-control"
    },
    {
      "name": "UnityDoorstop",
      "version": "4.3.0",
      "license": "LGPL-2.1-only-control",
      "url": "https://github.com/NeighTools/UnityDoorstop/releases/download/v4.3.0/doorstop_win_release_4.3.0.zip",
      "sha256": "e23fec7a6adfa07ba26a3e209b617584d0319a1145506ae4e1b892c44e86f679",
      "role": "control-only"
    }
  ]
}
```

Create `eng/check_licenses.py` using only `json`, `pathlib`, and `sys`. It must reject any entry whose license is absent or not in `allowedLicenses`, reject `GPL-3.0`, and reject a Doorstop role other than `control-only`. Include this executable check:

```python
for dep in document["dependencies"]:
    assert dep["license"] in document["allowedLicenses"], dep["name"]
    if dep["name"] == "UnityDoorstop":
        assert dep["role"] == "control-only"
```

- [ ] **Step 2: Verify the policy rejects a GPL test record**

Run `python3 eng/check_licenses.py` with a temporary in-memory record setting BepInEx.Utility's license to `GPL-3.0-only`. Expected: nonzero exit naming `BepInEx.Utility`; no repository dependency is added.

- [ ] **Step 3: Fetch pinned packages and lock their hashes**

Implement `eng/fetch-dependencies.sh` with `set -euo pipefail`, Python JSON parsing, `curl -fL --retry 3`, `sha256sum`, and archive extraction into `artifacts/deps`. Verify each downloaded archive against the locked digest before extraction and fail on mismatch. Use `unzip -q` for the two pinned ZIP packages and stop on download or archive errors.

- [ ] **Step 4: Add notices and build defaults**

Create `THIRD_PARTY_NOTICES.md` listing BepInEx/HarmonyX/MonoMod as MIT, Doorstop as LGPL-2.1 control-only, and Proton/Wine under their component licenses. Include source URLs and require full license texts beside staged binaries. Create `.gitignore` containing `artifacts/`, `bin/`, `obj/`, `*.user`, and `*.log`. Create:

```xml
<Project>
  <PropertyGroup>
    <TPC_GAME_DIR Condition="'$(TPC_GAME_DIR)' == ''">/games/SteamLibrary/steamapps/common/The Planet Crafter</TPC_GAME_DIR>
    <LangVersion>latest</LangVersion>
    <Nullable>disable</Nullable>
    <Deterministic>true</Deterministic>
  </PropertyGroup>
</Project>
```

- [ ] **Step 5: Verify and commit**

Run `bash eng/fetch-dependencies.sh && python3 eng/check_licenses.py`. Expected: downloaded hashes match and policy passes. Commit with `git add eng THIRD_PARTY_NOTICES.md .gitignore Directory.Build.props && git commit -m "build: pin loader dependencies and licenses"`.

### Task 2: Managed bootstrap skeleton and native round-trip contract

**Files:**
- Create: `Vrcrafter.sln`
- Create: `src/Vrcrafter.Bootstrap/Vrcrafter.Bootstrap.csproj`
- Create: `src/Vrcrafter.Bootstrap/EntryPoint.cs`
- Create: `src/Vrcrafter.Bootstrap/NativeBridge.cs`
- Create: `src/Vrcrafter.Bootstrap/ManagedLog.cs`
- Create: `eng/build-managed.sh`

**Interfaces:**
- Consumes: `artifacts/deps/bepinex/core/0Harmony.dll` and matched MonoMod assemblies.
- Produces: `Vrcrafter.Bootstrap.EntryPoint.Start()` and `Vrcrafter.Bootstrap.NativeBridge.Ping(int value)`.
- Produces: `artifacts/payload/managed/Vrcrafter.Bootstrap.dll` and matched dependency DLLs.

- [ ] **Step 1: Create a build that initially fails because the entry point is absent**

Create the SDK project targeting `net48`, referencing `Microsoft.NETFramework.ReferenceAssemblies.net48` version `1.0.3` as a private build asset. Add non-private references to `0Harmony`, `MonoMod.RuntimeDetour`, and `MonoMod.Utils` from the pinned BepInEx core directory. Add `eng/build-managed.sh` beginning with `set -euo pipefail` and `test -f src/Vrcrafter.Bootstrap/EntryPoint.cs`, then running `dotnet build Vrcrafter.sln -c Release` and staging outputs without Unity/game DLLs. Create `NativeBridge.cs`:

```csharp
using System.Runtime.InteropServices;

namespace Vrcrafter.Bootstrap
{
    internal static class NativeBridge
    {
        [DllImport("winhttp", EntryPoint = "VrcrafterPing")]
        internal static extern int Ping(int value);
    }
}
```

- [ ] **Step 2: Run the build and verify failure**

Run `bash eng/build-managed.sh`. Expected: FAIL because `EntryPoint.cs`/startup contract is missing from the initially empty solution. This establishes that staging cannot silently omit the entry assembly.

- [ ] **Step 3: Implement the minimal managed entry point and diagnostics**

Create `EntryPoint.cs` with `Start()` writing UTC timestamp, PID, `Environment.Version`, `AppDomain.CurrentDomain.FriendlyName`, loaded assembly names, and `NativeBridge.Ping(41) == 42` to `%LOCALAPPDATA%/vrcrafter/managed.log`. Create the directory before writing. Catch all exceptions, write `EXCEPTION <type> <message> <stack>`, and return a nonzero `int` to native. Keep Harmony types out of this file's initial type-loading path.

```csharp
public static int Start()
{
    try
    {
        ManagedLog.Write("START unity-mono=" + Environment.Version);
        ManagedLog.Write("PING=" + NativeBridge.Ping(41));
        return NativeBridge.Ping(41) == 42 ? 0 : 3;
    }
    catch (Exception ex)
    {
        ManagedLog.Write("EXCEPTION " + ex);
        return 2;
    }
}
```

Implement `ManagedLog.Write` as a small lock-protected UTF-8 appender; do not use BepInEx.Utility or a GPL logging package.

- [ ] **Step 4: Verify build, references, and absence of redistributed game assemblies**

Run `bash eng/build-managed.sh`, then `monodis --assemblyref artifacts/payload/managed/Vrcrafter.Bootstrap.dll`. Expected: build succeeds, `mscorlib` and framework references are present, and `find artifacts/payload -name 'Assembly-CSharp.dll' -o -name 'UnityEngine*.dll'` returns nothing.

- [ ] **Step 5: Commit**

Run `git add Vrcrafter.sln Directory.Build.props src/Vrcrafter.Bootstrap eng/build-managed.sh && git commit -m "feat: add managed Mono bootstrap contract"`.

### Task 3: Complete WinHTTP forwarding and executable process gate

**Files:**
- Create: `src/native/winhttp_proxy.c`
- Create: `src/native/log.h`
- Create: `src/native/log.c`
- Create: `eng/generate-winhttp-exports.py`
- Create: `eng/build-native.sh`
- Create: `tests/native/probe.c`

**Interfaces:**
- Produces: `VrcrafterPing(int value)` returning `value + 1` and exported `VrcrafterStart()` for deferred initialization.
- Produces: `artifacts/payload/winhttp.dll` and `artifacts/payload/vrcrafter-winhttp-backend.dll`.
- Consumes: `VRCRAFTER_ENABLE=1`, `VRCRAFTER_PAYLOAD`, and `VRCRAFTER_LOG_DIR` as Windows-visible environment variables.

- [ ] **Step 1: Write the failing native probe**

Create `tests/native/probe.c` to call `GetModuleHandleW(L"winhttp.dll")`, resolve `VrcrafterPing`, require `ping(41) == 42`, call `WinHttpGetDefaultProxyConfiguration` with a zeroed `WINHTTP_PROXY_INFO`, free `lpszProxy`/`lpszProxyBypass` with `GlobalFree` on success, and print `PROBE_OK`. Compile it with `x86_64-w64-mingw32-gcc -municode tests/native/probe.c -lwinhttp -o artifacts/tests/probe.exe`.

- [ ] **Step 2: Run probe against the absent proxy and verify failure**

Run the probe in a dedicated Proton prefix before staging `winhttp.dll`. Expected: FAIL because `VrcrafterPing` is missing. Do not treat this as a game failure.

- [ ] **Step 3: Generate every forwarder and implement the process gate**

`eng/generate-winhttp-exports.py` must parse `objdump -p` output for the pinned Wine x64 `winhttp.dll`, extract every named export, reject an empty export set, and emit a MinGW `.def` file:

```text
LIBRARY winhttp
EXPORTS
    WinHttpGetDefaultProxyConfiguration=vrcrafter-winhttp-backend.WinHttpGetDefaultProxyConfiguration
    VrcrafterPing @1000
    VrcrafterStart @1001
```

Repeat the real extracted export names for every entry; never maintain a partial handwritten list. `build-native.sh` must copy the pinned builtin DLL to `vrcrafter-winhttp-backend.dll`, generate the `.def`, and link the proxy with `x86_64-w64-mingw32-gcc -shared`.

In `winhttp_proxy.c`, export `VrcrafterPing` and a `VrcrafterStart` stub returning `0`. In `DllMain(DLL_PROCESS_ATTACH)`, disable thread calls, read `VRCRAFTER_ENABLE`, compare the executable filename case-insensitively to `Planet Crafter.exe`, and only then queue a deferred start using `CreateThread`; perform no Mono or managed work in `DllMain`. Use an atomic one-time state so helper/crash processes and duplicate starts cannot initialize the mod.

Implement `log.c` as lock-protected UTF-8 file output with phase and Win32 error codes. Log process name, payload path, and why activation was skipped.

- [ ] **Step 4: Verify exports and forwarding under Proton**

Run `bash eng/build-native.sh`, stage the two DLLs beside the probe, and run it with `WINEDLLOVERRIDES=winhttp=n,b`. Compare proxy/backend export-name sets after removing the two `Vrcrafter*` additions. Expected: all original WinHTTP exports exist, `PROBE_OK` prints, and ordinary default-proxy querying succeeds.

- [ ] **Step 5: Verify negative process gating and commit**

Rename a copy of the probe to a helper-like name and confirm `VrcrafterStart` remains uncalled when `VRCRAFTER_ENABLE` is unset. Then commit `git add src/native eng/build-native.sh eng/generate-winhttp-exports.py tests/native/probe.c && git commit -m "feat: add forwarding WinHTTP activation proxy"`.

### Task 4: Attach to Unity Mono and invoke managed code

**Files:**
- Create: `src/native/mono_host.h`
- Create: `src/native/mono_host.c`
- Modify: `src/native/winhttp_proxy.c`
- Modify: `eng/build-native.sh`

**Interfaces:**
- Consumes: managed `Vrcrafter.Bootstrap.EntryPoint.Start(): int` from Task 2.
- Produces: `mono_host_start(const wchar_t *payload_dir): DWORD`, called exactly once by the deferred proxy thread.
- Produces: structured native log markers `MONO_MODULE`, `MONO_DOMAIN`, `MANAGED_ENTRY`, `MANAGED_RESULT`.

- [ ] **Step 1: Define the dynamic Mono ABI**

In `mono_host.h`, declare opaque `MonoDomain`, `MonoThread`, `MonoAssembly`, `MonoImage`, `MonoClass`, `MonoMethod`, and `MonoObject` types plus function-pointer types for:

```c
MonoDomain *(*mono_get_root_domain)(void);
MonoThread *(*mono_thread_attach)(MonoDomain *);
void (*mono_thread_detach)(MonoThread *);
MonoAssembly *(*mono_domain_assembly_open)(MonoDomain *, const char *);
MonoImage *(*mono_assembly_get_image)(MonoAssembly *);
MonoClass *(*mono_class_from_name)(MonoImage *, const char *, const char *);
MonoMethod *(*mono_class_get_method_from_name)(MonoClass *, const char *, int);
MonoObject *(*mono_runtime_invoke)(MonoMethod *, void *, void **, MonoObject **);
void *(*mono_object_unbox)(MonoObject *);
void (*mono_free)(void *);
```

Resolve every function with `GetProcAddress` from the game's loaded `mono-2.0-bdwgc.dll`; do not link host Mono or call `mono_jit_init`.

- [ ] **Step 2: Implement deferred discovery with bounded waiting**

The deferred thread polls `GetModuleHandleW(L"mono-2.0-bdwgc.dll")` with `Sleep(100)` for at most 120 seconds. Once present, resolve exports, require a non-null root domain, attach once, convert the managed DLL path to UTF-8 with `WideCharToMultiByte(CP_UTF8, ...)`, and load it with `mono_domain_assembly_open`. Check every result and log the exact failed phase. Do not load `Assembly-CSharp.dll` from native code.

- [ ] **Step 3: Invoke and unbox the managed entry**

Resolve namespace `Vrcrafter.Bootstrap`, class `EntryPoint`, method `Start`, parameter count `0`. Invoke with null instance/arguments and a non-null exception pointer. If an exception is returned, log `MANAGED_EXCEPTION`; otherwise unbox the returned `int`, log `MANAGED_RESULT=<n>`, and return failure for nonzero values. Keep the thread attached until process exit so future native callbacks remain valid; never call `mono_jit_cleanup`.

- [ ] **Step 4: Verify missing-runtime and success behavior in the real game**

First run with the managed DLL deliberately absent. Expected: native log identifies `MANAGED_ASSEMBLY_OPEN` failure and the flat game remains usable. Restore it and launch with `PROTON_LOG=1`. Expected log order: `MONO_MODULE`, `MONO_DOMAIN`, `MANAGED_ENTRY`, `PING=42`, `MANAGED_RESULT=0`; no second Mono runtime is created.

- [ ] **Step 5: Verify exception capture and commit**

Temporarily make `EntryPoint.Start` throw `InvalidOperationException("loader-self-test")`. Expected: managed log contains the deliberate exception and native result is nonzero. Restore the real entry immediately and rerun `PING=42`. Commit `git add src/native eng/build-native.sh src/Vrcrafter.Bootstrap && git commit -m "feat: invoke managed bootstrap in Unity Mono"`.

### Task 5: Safe assembly resolution and game identity gate

**Files:**
- Create: `src/Vrcrafter.Bootstrap/AssemblyResolver.cs`
- Create: `src/Vrcrafter.Bootstrap/GameIdentity.cs`
- Create: `src/Vrcrafter.Bootstrap/BootstrapState.cs`
- Modify: `src/Vrcrafter.Bootstrap/EntryPoint.cs`
- Modify: `src/Vrcrafter.Bootstrap/Vrcrafter.Bootstrap.csproj`

**Interfaces:**
- Produces: `AssemblyResolver.Install(string payloadDirectory): void`.
- Produces: `GameIdentity.Validate(): bool`, accepting only the configured executable, Unity version, and game assembly hash.
- Produces: `BootstrapState.RunAfterResolver(): int`, keeping Harmony types out of initial resolution.

- [ ] **Step 1: Add a failing unresolved-dependency probe**

Create `BootstrapState.cs` with `RunAfterResolver(): int`; its project references `UnityEngine.CoreModule.dll` and `Assembly-CSharp.dll` from `$(TPC_GAME_DIR)/Planet Crafter_Data/Managed` with `<Private>false</Private>`. Before installing the resolver, run with the payload dependency directory renamed to `managed.off`. Expected: managed exception identifies the missing dependency and no game patch is applied. Rename it back immediately after the negative run.

- [ ] **Step 2: Install deterministic resolution before touching game types**

`AssemblyResolver.Install` subscribes once to `AppDomain.CurrentDomain.AssemblyResolve`. It first returns an already loaded assembly whose `FullName` matches the requested name, then probes only `<payload>/<simpleName>.dll` using `Assembly.LoadFrom`, and otherwise returns null. Never probe the game directory for mod dependencies and never load a second resolver. Log resolved names and paths.

- [ ] **Step 3: Validate identity before patching**

`GameIdentity.Validate` requires the process executable filename `Planet Crafter.exe` and locates already loaded `Assembly-CSharp` by simple name. Read the sibling `Planet Crafter_Data/globalgamemanagers` as binary data and require ASCII `6000.3.2f1` in its first 64 KiB; this uses file I/O rather than calling Unity APIs on the native worker. Compute SHA-256 over the assembly's on-disk `Location` using `System.Security.Cryptography.SHA256` and require lowercase hex `3d7457446cbbed551f938b5271f294f45ec100e1f295eeba9b0884b3cdd9191e`, matching `game.assemblyCSharpSha256` in `eng/dependencies.lock.json`. Log the actual hash and `IDENTITY_ACCEPT` or `IDENTITY_REJECT`; reject any mismatch before Harmony initialization.

- [ ] **Step 4: Verify rejection and acceptance**

Run with an intentionally incorrect accepted hash. Expected: `IDENTITY_REJECT` and no `HARMONY_PATCH` marker. Restore the computed hash and run normally. Expected: `IDENTITY_ACCEPT`, loaded game/Unity assembly identities in the log, and no duplicate `0Harmony`, MonoMod, Unity, or contract assemblies.

- [ ] **Step 5: Commit**

Run `git add eng/dependencies.lock.json src/Vrcrafter.Bootstrap && git commit -m "feat: add deterministic resolution and game identity checks"`.

### Task 6: Harmony hook and persistent Unity main-thread host

**Files:**
- Create: `src/Vrcrafter.Bootstrap/HarmonyBootstrap.cs`
- Create: `src/Vrcrafter.Host/Vrcrafter.Host.csproj`
- Create: `src/Vrcrafter.Host/VrcrafterHost.cs`
- Create: `src/Vrcrafter.Host/MainThreadQueue.cs`
- Modify: `Vrcrafter.sln`
- Modify: `eng/build-managed.sh`

**Interfaces:**
- Produces: `HarmonyBootstrap.Install(): void` using owner ID `com.github.patola.vrcrafter.loader`.
- Produces: `MainThreadQueue.Post(Action action): void` and `MainThreadQueue.RunPending(): void`.
- Produces: persistent `Vrcrafter.Host.VrcrafterHost` with `Update()` ticking on Unity's main thread.

- [ ] **Step 1: Write the failing integration assertions**

Create `tests/integration/verify-loader.py` requiring, in order, `IDENTITY_ACCEPT`, `HARMONY_PATCH`, `HOST_CREATE`, `HOST_UPDATE`, `WORKER_DISPATCH`, and `ORIGINAL_CONTINUES`. Also require failure when `HOST_UPDATE` appears before `HOST_CREATE`. Run before Harmony implementation; expected: FAIL at missing `HARMONY_PATCH`.

- [ ] **Step 2: Install one managed one-shot postfix**

`HarmonyBootstrap.Install` obtains `SpaceCraft.PlayerInputDispatcher` from loaded `Assembly-CSharp`, gets its public/nonpublic instance `Update()` with `BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic`, and applies a postfix. The postfix checks `Thread.CurrentThread.ManagedThreadId`, logs `ORIGINAL_CONTINUES` after the original returns, and on first call creates `new GameObject("Vrcrafter.Host")`, adds `VrcrafterHost`, calls `UnityEngine.Object.DontDestroyOnLoad`, logs `HOST_CREATE`, and unpatches only this loader's one-shot patch. Guard first call with `Interlocked.Exchange`; do not create Unity objects on the native worker.

- [ ] **Step 3: Implement the persistent queue and lifecycle**

`MainThreadQueue` holds `ConcurrentQueue<Action>`; `Post` only enqueues and `RunPending` drains with a per-frame budget of 64 actions. `VrcrafterHost.Update` increments a counter, calls `RunPending`, and logs the first three ticks with Unity's main-thread ID. During bootstrap, post a delegate from the native/managed worker that logs `WORKER_DISPATCH` only when executed by the host. `OnDestroy` writes `HOST_DESTROY`; no root-domain unload is attempted.

- [ ] **Step 4: Verify gameplay, scene survival, and clean exit**

Load a backed-up private save, walk until input dispatch is active, open/close the menu, and load a different scene/planet. Expected: one host, original input continues, repeated updates, worker delegate executes on the host thread, and no duplicate `HOST_CREATE`. Exit through the game menu and verify no deadlock, recurring exception, or call into unloaded native code.

- [ ] **Step 5: Run assertions and commit**

Run `python3 tests/integration/verify-loader.py artifacts/logs/current`. Expected: all ordered markers pass and negative ordering check passes. Commit `git add src tests/integration Vrcrafter.sln eng/build-managed.sh && git commit -m "feat: start persistent Unity main-thread host"`.

### Task 7: Custom Proton appid integration and local packaging

**Files:**
- Create: `proton/patches/0001-vrcrafter-launcher.patch`
- Create: `eng/build-proton.sh`
- Create: `eng/install-local.sh`
- Create: `eng/package-licenses.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: native/managed payload from Tasks 2–6.
- Produces: compatibility tool named `vrcrafter-proton`, disabled unless `VRCRAFTER_ENABLE=1`.
- Produces: `VRCRAFTER_PAYLOAD`, `VRCRAFTER_LOG_DIR`, and `WINEDLLOVERRIDES=winhttp=n,b` only for appid `1284190`.

- [ ] **Step 1: Pin Proton and write the launcher patch**

Add Valve Proton as `third_party/Proton`, checkout `proton-11.0-2`, and initialize submodules recursively. Patch only its Python launcher, compatibility-tool manifest, and payload file list. In `Session`, gate on `self.env.get('SteamGameId') == '1284190' and self.env.get('VRCRAFTER_ENABLE') == '1'`; then set `self.dlloverrides['winhttp'] = 'n,b'` and preserve unrelated overrides. Convert the Linux payload/log paths to Wine paths with `'Z:' + path.replace('/', '\\')`, defaulting to `Z:\\home\\patola\\.local\\share\\vrcrafter\\payload` and `Z:\\home\\patola\\.local\\share\\vrcrafter\\logs` on this machine. Do not change Wine, DXVK, vkd3d-proton, or wineopenxr.

- [ ] **Step 2: Build and inspect the custom tool**

`eng/build-proton.sh` applies the patch with `git apply --check`, runs Proton's documented container build, and stages `dist`. `eng/package-licenses.py` copies MIT notices for managed dependencies and upstream Proton/Wine license/source references; it must fail if a required notice is missing. `eng/install-local.sh` installs only to `$HOME/.local/share/Steam/compatibilitytools.d/vrcrafter-proton` and a separate `$HOME/.local/share/vrcrafter/payload`, never to stock Proton or the game directory.

- [ ] **Step 3: Verify activation and kill switch**

Select `vrcrafter-proton` in Steam. Launch without `VRCRAFTER_ENABLE`; expected: normal flat game and no `MANAGED_ENTRY`. Launch with `VRCRAFTER_ENABLE=1 PROTON_LOG=1 %command%`; expected: the complete ordered loader assertions pass. Confirm no `BepInEx` directory or `winhttp.dll` is copied into the game installation.

- [ ] **Step 4: Verify clean-prefix behavior and helper exclusion**

Back up the existing compat-data path, create a fresh test prefix, and repeat activation. Inspect process/module logs for launchers/crash handlers. Expected: only `Planet Crafter.exe` initializes the payload; ordinary WinHTTP behavior works; a second launch creates one initialization per process.

- [ ] **Step 5: Document and commit**

Update `README.md` with exact build dependencies, build/install commands, Steam selection, enable/disable launch options, log paths, and the fact that this milestone has no VR features. Commit `git add proton third_party/Proton eng README.md .gitmodules && git commit -m "feat: package appid-gated VRC Proton loader"`.

### Task 8: Stock Doorstop/BepInEx control and optional Chainloader compatibility

**Files:**
- Create: `src/Vrcrafter.BepInExControl/Vrcrafter.BepInExControl.csproj`
- Create: `src/Vrcrafter.BepInExControl/ControlPlugin.cs`
- Create: `src/Vrcrafter.BepInExBridge/Vrcrafter.BepInExBridge.csproj`
- Create: `src/Vrcrafter.BepInExBridge/ChainloaderBridge.cs`
- Create: `eng/install-control.sh`
- Modify: `tests/integration/verify-loader.py`

**Interfaces:**
- Produces: ordinary `BaseUnityPlugin` marker `BEPINEX_CONTROL_OK` under stock Proton/Doorstop.
- Produces: separate `BEPINEX_CHAINLOADER_OK` marker under the custom native host, only after direct-host tests pass.

- [ ] **Step 1: Build the harmless control plugin**

`ControlPlugin` derives from `BaseUnityPlugin`, uses GUID `com.github.patola.vrcrafter.control`, logs `BEPINEX_CONTROL_OK` in `Awake`, and applies the same harmless `PlayerInputDispatcher.Update` postfix used for diagnostics without changing original behavior. Reference BepInEx core and HarmonyX from pinned packages and game assemblies non-privately.

- [ ] **Step 2: Verify the stock-Proton control**

`eng/install-control.sh` installs the unmodified pinned Doorstop/BepInEx control into a backup/copy of the game installation or a dedicated test depot, sets `HideManagerGameObject = true`, and uses stock Proton with `WINEDLLOVERRIDES=winhttp=n,b`. Expected: `BEPINEX_CONTROL_OK`, original input continues, and no custom native-host markers. Restore original game files after the control run.

- [ ] **Step 3: Test programmatic BepInEx separately**

`ChainloaderBridge` runs only when `VRCRAFTER_BEPINEX=1`. Before touching Chainloader types, install the resolver, initialize BepInEx paths to the executable and `Planet Crafter_Data/Managed`, preload the matched critical assemblies, set `HideManagerGameObject=true`, and invoke `Chainloader.Initialize`/`Start` from Unity's main thread. Do not claim Cecil preloader-patcher compatibility. Load the unmodified `ControlPlugin` and require `BEPINEX_CHAINLOADER_OK` plus its Harmony marker.

- [ ] **Step 4: Verify failure classification**

Run direct native mode with BepInEx disabled, stock control, then Chainloader mode. Expected: direct-host assertions pass independently; a Chainloader failure cannot make the direct host appear broken; Doorstop is absent from primary mode.

- [ ] **Step 5: Commit**

Run `git add src/Vrcrafter.BepInExControl src/Vrcrafter.BepInExBridge eng/install-control.sh tests/integration && git commit -m "test: validate BepInEx control and Chainloader bridge"`.

### Task 9: Full loader acceptance run

**Files:**
- Modify: `README.md`
- Modify: `tests/integration/verify-loader.py`

**Interfaces:**
- Consumes: every earlier deliverable.
- Produces: reproducible acceptance commands and machine-checked logs for all Gate 1 criteria.

- [ ] **Step 1: Add negative and stability assertions**

Extend the verifier to reject duplicate initialization, duplicate host creation, unexpected managed exceptions, missing original-method continuation, missing process exclusion, missing kill switch, and missing clean-prefix run. Add a GC stress diagnostic that allocates managed objects for 30 seconds while worker dispatch continues; expect stable ticks and valid callbacks.

- [ ] **Step 2: Run the complete acceptance matrix**

Run in this order: disabled custom Proton; native custom Proton; missing managed DLL; deliberate managed exception; wrong game hash; normal native custom Proton; clean prefix; stock Proton Doorstop control; optional Chainloader bridge. Restore normal files/settings after every intentional failure. For normal runs, enter gameplay, change scenes, stress GC, and exit cleanly.

- [ ] **Step 3: Verify repository and payload hygiene**

Run `git diff --check`, `python3 eng/check_licenses.py`, both build scripts, native export comparison, managed assembly-reference inspection, and `python3 tests/integration/verify-loader.py artifacts/logs/acceptance`. Expected: all pass; payload contains no game/Unity assemblies, UUVR, BepInEx.Utility, or Doorstop in primary mode.

- [ ] **Step 4: Record verified commands in README**

Document the exact acceptance commands, expected log markers, known limitation that programmatic Chainloader is not Cecil preloader compatibility, and restoration steps for saves/prefixes. Do not claim VR, OpenXR, stereo, or multiplayer validation.

- [ ] **Step 5: Commit the validated loader milestone**

Run `git add README.md tests/integration && git commit -m "test: complete Proton Mono host acceptance checks"`. Report any criterion that could not be exercised as unverified rather than marking the milestone complete.

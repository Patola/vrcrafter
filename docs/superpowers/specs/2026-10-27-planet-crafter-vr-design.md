# The Planet Crafter VR and Proton Mono Host Design

Date: 2026-10-27
Status: Approved architecture; loader milestone to be planned first

## Purpose

Create a VR mod for The Planet Crafter (Steam appid 1284190) that provides genuine 6DOF head tracking, stereo rendering, tracked-hand interaction, a right-hand multitool, and compatibility with unmodified flatscreen co-op players. Use the project to investigate a reusable alternative to the usual UnityDoorstop installation path: a custom Proton compatibility tool that can load managed mods into Unity Mono games.

The immediate implementation milestone is the custom Proton native Mono host and its validation. The playable VR vertical slice is the following milestone and will receive its own implementation plan.

## Observed installation

The installed game at `/games/SteamLibrary/steamapps/common/The Planet Crafter` currently uses:

- The Planet Crafter 2.103.
- Unity 6000.3.2f1.
- A 64-bit Windows executable.
- Unity Mono, not IL2CPP, with `mono-2.0-bdwgc.dll` and readable managed assemblies.
- URP, Cinemachine, Unity Input System, Unity Netcode, and Steam networking.
- `Assembly-CSharp.dll` types including `PlayerMainController`, `PlayerAimController`, `PlayerMultitool`, `PlayerActionController`, `PlayerInputDispatcher`, and `PlayerShareState`.

Proton 11.0-2 is the compatibility baseline. Arch Linux, the .NET SDK, Podman, and Proton build dependencies are available. All native Windows-ABI components will be cross-compiled on Linux through Proton's normal build environment; Windows and Windows development tools are not required.

## Feasibility conclusions

### Why Proton alone is not the VR mod

Proton can orchestrate launch, inject native components, and translate D3D/OpenXR APIs. It cannot infer or directly patch Unity managed objects and methods. Camera ownership, Cinemachine update ordering, equipment transforms, game interaction, and network-safe action dispatch belong in managed code running in Unity's Mono domain.

The reusable Proton feature is therefore a mod-hosting and activation mechanism. It is not a replacement for game-specific VR behavior.

### Why the native Mono host is feasible

Unity already initializes Mono. A native component in the Windows game process can dynamically resolve Mono exports, obtain the existing root domain, attach a native thread, load a managed assembly, and invoke an entry point. It must not call `mono_jit_init` to create a second runtime or unload Unity's root domain.

A native worker attached to Mono is not automatically Unity's main thread. The managed bootstrap must establish a one-shot hook on a guaranteed main-thread managed method, then create a persistent `MonoBehaviour` host there. Game and Unity object access remains on Unity's main thread.

HarmonyX and MonoMod must execute in the same Mono runtime and AppDomain as the target methods. A separate CoreCLR runtime cannot directly manipulate Mono Unity objects or patch Mono methods and is outside the initial architecture.

### Why retain BepInEx compatibility

BepInEx supplies plugin discovery, dependency handling, logging, configuration, HarmonyX, MonoMod, Cecil, and an established Planet Crafter mod ecosystem. The project will not recreate those facilities unnecessarily.

Two activation routes will share the same managed VR code:

1. Custom Proton native Mono bootstrap, without Doorstop.
2. Stock Proton with ordinary Doorstop/BepInEx as control and fallback.

Programmatic BepInEx `Chainloader` hosting without Doorstop is a separate compatibility gate, not part of the minimal native-loader proof. It must account for preloader initialization, assembly resolution, dependencies, and main-thread requirements rather than assuming `Chainloader.Start()` is sufficient by itself.

## Alternatives considered

### Custom Proton launcher plus existing Doorstop/BepInEx

This is the lowest-risk distribution option and will be retained as a fallback. It automates appid-specific configuration and payload activation but does not prove the new native managed-hosting concept.

### Generic UUVR-led implementation

UUVR Mono Modern provides useful OpenXR and camera infrastructure, but current released UUVR intentionally disables positional tracking and applies rotation-only poses. Motion-controller emulation is unfinished. Its generic camera handling does not establish Planet Crafter-specific camera ownership, tool attachment, or interaction behavior.

UUVR is excluded as an implementation dependency. No UUVR source code, assets, patches, or derived implementation will be copied into or linked with this project. Its observed behavior and public documentation may inform requirements and diagnosis, but OpenXR initialization, camera handling, tracking, and input will be implemented independently from OpenXR/Unity specifications and MIT-compatible sources. Game-specific behavior will not be delegated to UUVR configuration alone.

### Custom Proton with CoreCLR and IPC

CoreCLR may be useful for isolated helpers, but cannot replace the in-Mono adapter. It adds a second runtime and a serialization boundary without eliminating managed Unity code. It is excluded from the loader and vertical-slice milestones.

### Native-only graphics and OpenXR interception

Native OpenXR API layers and D3D/DXGI interception are appropriate only for defects or features at those API boundaries. They cannot provide Harmony-style game behavior. Wine, DXVK, vkd3d-proton, and wineopenxr will remain unmodified unless testing identifies a specific defect requiring a change there.

## Architecture

### 1. Proton integration

Maintain a pinned Proton 11.0-2 fork with a narrowly scoped appid-1284190 integration:

- Default-disabled mod activation and an explicit kill switch.
- Configurable payload location outside the game installation where supported.
- DLL-loading configuration for the native bootstrap.
- Separate diagnostic logging and predictable environment propagation.
- Executable identity and initialization guards to avoid injecting into launchers, crash handlers, and unrelated child processes.
- No modifications to the user's stock Proton installation.

The exact proxy or built-in DLL mechanism will be selected from the game's imports and Proton's module-loading behavior during the loader spike. Any proxy must preserve the complete exported API and forward to the real implementation. Complex managed initialization must not occur under DLL loader lock.

The Proton launcher may select settings by appid, but it runs outside the game process and cannot invoke Unity managed code itself.

### 2. Native Mono bootstrap

The x64 Windows-ABI native component will:

1. Load through the selected Proton/Wine mechanism and defer substantive work until safe.
2. Discover the Mono module actually loaded by the game and dynamically resolve required exports.
3. Confirm that the Unity root domain exists without creating another runtime.
4. Attach its worker thread to that domain before managed calls.
5. Load a minimal managed bootstrap from bytes or a controlled payload path.
6. Resolve and invoke its static entry point with `mono_runtime_invoke`.
7. Surface managed exceptions and native failures in diagnostic logs.
8. Retain managed delegates/objects through GC handles where required.
9. Remain loaded for process lifetime and never unload code still referenced by managed callbacks or JITted patches.

The initial VR path does not require per-frame native IPC. OpenXR poses and actions will enter through Unity's XR APIs. If a native bridge is needed for small control records, it will use nonblocking blittable buffers or P/Invoke rather than a `mono_runtime_invoke` call every frame.

### 3. Managed bootstrap and lifecycle

The minimal managed bootstrap will install logging and assembly resolution before loading dependencies with complex type requirements. It will:

- Resolve already loaded compatible assemblies before searching designated payload directories.
- Never ship replacement copies of game or Unity assemblies.
- Avoid duplicate contract, Harmony, MonoMod, or Unity assembly identities.
- Load matched HarmonyX/MonoMod dependencies.
- Install a one-shot main-thread hook selected from a real managed game method.
- Create a persistent host `GameObject` and `MonoBehaviour` on Unity's main thread.
- Mark the host `DontDestroyOnLoad` and remove the one-shot bootstrap hook.
- Treat the root domain, mod assemblies, native component, and patch infrastructure as process-lifetime resources.

No hot unload or root-domain reload is promised. Orderly shutdown must stop callbacks and release resources where safe without calling `mono_jit_cleanup`.

### 4. Managed VR core

The VR core will be independent of Planet Crafter gameplay types where practical. It will own:

- OpenXR initialization through Unity XR Management.
- D3D11 multipass stereo as the initial compatibility baseline.
- A dedicated tracked player rig and VR camera rather than generic mutation of every active camera.
- Genuine rotational and positional tracking with a defined tracking origin.
- Recentering, seated/standing eye-height calibration, and metric scale validation.
- Left/right hand poses and OpenXR action mapping.
- Stick locomotion/turning inputs and comfort settings.
- World-space UI and desktop mirror support.
- Runtime diagnostics that distinguish session, tracking, stereo, and camera failures.

OpenXR is the mod-facing API. The expected Proton paths are:

- `Unity OpenXR -> wineopenxr -> Linux OpenXR -> SteamVR`.
- `Unity OpenXR -> wineopenxr -> Linux OpenXR -> WiVRn/Monado`.

WiVRn/Monado does not require xrizer or OpenComposite on the native OpenXR path. Those translators belong only to an optional OpenVR fallback. Steam pressure-vessel runtime/socket importing will use the launch settings generated or documented by the installed WiVRn version.

D3D12 and OpenVR are deferred until the D3D11/OpenXR baseline works. WineD3D is not a VR baseline because Proton's OpenXR path requires DXVK/vkd3d-proton interoperability.

### 5. Planet Crafter adapter

The game adapter will compile against the installed game's actual assemblies and contain all game-specific behavior:

- Discover the active player, camera, Cinemachine brain, and relevant camera stack.
- Apply the final head pose after Cinemachine has updated the camera.
- Preserve required URP additional camera data, renderer selection, and camera-stack behavior.
- Separate visual head/tool transforms from authoritative player body movement.
- Drive the existing multitool viewmodel from the right-hand pose with a calibrated grip offset.
- Replace camera-centered tool aiming with a right-hand aim ray while invoking existing tool actions.
- Provide basic left-hand world interaction through existing `Actionnable`/player action paths.
- Map VR actions into existing movement, use, menu, inventory, and recentering behavior.
- Handle menu, gameplay, death/respawn, and scene transitions without duplicate rigs or patch ownership.

The vertical slice will use existing game assets or procedural assets and will not require a Unity editor or asset-bundle build. Custom hand models, physical free grabbing, advanced gestures, vehicles, and replicated VR hand animation are deferred.

## Multiplayer compatibility boundary

VR is a local presentation and input adaptation. The mod must not introduce a parallel gameplay or networking implementation.

- Controller poses are local inputs and visual transforms.
- World movement continues through the existing player controller and authority model.
- Mining, building, crafting, inventory, interaction, damage, and death use existing game methods and network messages.
- The initial mod adds no custom network serialization or protocol messages.
- Head/hand poses are not replicated initially; remote players see the ordinary game avatar/state.
- No gameplay advantage, changed range, changed damage, or alternate inventory authority is part of the design.

Compatibility must be demonstrated with an unmodified client, not inferred from the absence of protocol edits.

## Vertical-slice scope

After the loader gate, the playable vertical slice will include:

- OpenXR stereo rendering with D3D11 and a desktop mirror.
- Genuine 6DOF head tracking and positional parallax.
- Correct eye-height calibration and world scale.
- Stick locomotion, turning, and recentering.
- Right-hand multitool positioning, aiming, and use.
- Basic left-hand interaction with existing world actions.
- Access to readable existing UI.
- Stable menu, gameplay, death/respawn, and scene transitions.
- Vanilla-compatible co-op behavior in the defined test matrix.

Advanced physical hands, custom avatars, replicated gestures, all vehicles, comprehensive comfort tuning, and performance optimization beyond a usable baseline are separate later milestones.

## Failure handling

- A launch option disables the complete mod stack without uninstalling it.
- Native and managed logs identify startup phase, runtime/assembly identities, patch installation, OpenXR state, and managed exceptions.
- Missing Mono exports or bootstrap failures prevent VR initialization; the game remains flatscreen-safe where continuing is safe.
- Unknown game versions or assembly identities reject game-specific patches by default.
- No original game managed assemblies are replaced.
- Stock Proton and Doorstop/BepInEx remain independent fallback paths.
- Saves are backed up before gameplay or multiplayer testing.
- Testing uses private co-op sessions rather than public sessions.

## Verification

### Gate 1: custom Proton Mono host

The first implementation plan is complete only when the actual installed game under the custom Proton demonstrates all of the following:

1. The native component loads only into the intended game process and forwarding of the real DLL API remains intact.
2. The real Mono module and root domain are discovered without initializing a second runtime.
3. A managed entry point executes and a blittable native/managed round trip succeeds.
4. A deliberate managed exception is captured and logged.
5. A second managed assembly resolves references to the game's actual `UnityEngine.CoreModule` and `Assembly-CSharp` without duplicate Unity/contract assemblies.
6. HarmonyX patches a guaranteed managed game method before relevant JIT/inlining, the patch executes, and the original behavior continues.
7. The main-thread hook creates a persistent `MonoBehaviour`, repeated `Update` ticks occur, and native-worker to main-thread dispatch works.
8. The host survives scene transitions and an orderly game exit occurs without deadlocks or calls into unloaded code.
9. The kill switch, stock-Proton fallback, clean-prefix activation, and helper/crash-process exclusion work.
10. A launcher-only Doorstop control proves that failures can be classified as native-host problems rather than general Proton/game/mod problems.

Programmatic BepInEx `Chainloader` compatibility is tested separately by loading one unmodified ordinary `BaseUnityPlugin` and firing a harmless Harmony patch without Doorstop. It is not allowed to mask the results of the minimal host tests.

### Gate 2: playable VR vertical slice

On both SteamVR and WiVRn/Monado with D3D11/OpenXR:

1. Left and right headset views are genuinely different; a single-eye desktop mirror is not accepted as stereo proof.
2. Leaning and crouching produce real positional parallax, distinguishing 6DOF from rotational reprojection.
3. Known-size doors, consoles, and the multitool have plausible metric scale and eye height.
4. Head tracking remains stable through Cinemachine and camera transitions without transform fighting.
5. Stick movement/turning, recentering, right-hand mining/tool use, left-hand interaction, and UI access work.
6. Menu-to-gameplay, death/respawn, and scene transitions do not duplicate or lose the rig.
7. Logs contain no recurring managed exceptions or OpenXR/session failures.

D3D12 and OpenVR are later one-variable-at-a-time compatibility tests, not prerequisites for the first vertical slice.

### Gate 3: vanilla co-op interoperability

Using a private session with an unmodified flatscreen client, test both VR-host/flatscreen-client and flatscreen-host/VR-client arrangements:

- Join, leave, and rejoin.
- Mine and deconstruct.
- Construct objects.
- Transfer items through containers and inventory.
- Craft and consume items.
- Take damage, die, and respawn.
- Traverse relevant scene/planet transitions.

Results must match vanilla gameplay rules and state on both clients. Merely joining a server is not sufficient evidence of compatibility.

## Licensing

All project-owned source code and assets are licensed under the MIT License in the repository's `LICENSE` file. The canonical repository is `https://github.com/Patola/vrcrafter`.

UUVR and other copyleft VR-mod implementations are not code or asset sources for this project. Do not copy, translate, port, or derive implementation from their source. Implementation must use public API specifications, engine documentation, observed behavior, and dependencies whose licenses are compatible with MIT-licensed project code. Record third-party dependencies and their licenses with the corresponding component.

MIT licensing applies to project-owned code; it does not relicense upstream Proton/Wine, BepInEx, Unity, or other third-party components. Their existing license and notice obligations still apply. In particular, modifications distributed within the Proton/Wine fork remain subject to the upstream component licenses even when the separately developed VR mod and original integration files are MIT-licensed. Proprietary game assemblies are compile-time references only and are not redistributed.

## Build and maintenance strategy

- Build native code through Proton's pinned containerized SDK and managed code with the Linux .NET SDK.
- Reference game assemblies from a configurable local installation path and mark those references non-private.
- Keep the custom Proton separate from stock Proton and distribute it as a distinct compatibility tool.
- Pin the Proton/Wine baseline and rebase launcher changes deliberately rather than tracking updates automatically.
- Keep game-specific Harmony patches isolated from reusable loader and VR-core code so game and Proton upgrades can be diagnosed independently.
- Preserve source offers and license notices for modified Proton/Wine components and all third-party dependencies.

## Primary references

- [BepInEx Proton/Wine installation](https://docs.bepinex.dev/articles/advanced/proton_wine.html)
- [UnityDoorstop bootstrap and runtime model](https://github.com/NeighTools/UnityDoorstop)
- [Mono embedding APIs](https://www.mono-project.com/docs/advanced/embedding/)
- [Unity Mono backend](https://docs.unity3d.com/6000.2/Documentation/Manual/scripting-backends-mono.html)
- [Harmony patching edge cases](https://harmony.pardeike.net/articles/patching-edgecases.html)
- [BepInEx Chainloader](https://github.com/BepInEx/BepInEx/blob/v5-lts/BepInEx/Bootstrap/Chainloader.cs)
- [Proton 11.0-2 source and build instructions](https://github.com/ValveSoftware/Proton/tree/proton-11.0-2)
- [Unity OpenXR 1.14 documentation](https://docs.unity3d.com/Packages/com.unity.xr.openxr@1.14/manual/index.html)
- [WiVRn Steam documentation](https://github.com/WiVRn/WiVRn/blob/master/docs/steamvr.md)
- [Existing Planet Crafter BepInEx/Harmony mods](https://github.com/akarnokd/ThePlanetCrafterMods)

# DFCapture Linux port

This repository carries a minimal Linux enablement layer for
`SourceAirbender/multi-dwarf`.

Pinned upstream commit:

```text
11ea5b1df1efe599bdb4746f21773f051345a6fe
```

Target:

```text
Dwarf Fortress 53.16 Premium Linux
DFHack 53.16-r1.1 Linux
amd64 / x86-64
```

## What upstream already provides

The important part is that `capture_shifted()` already contains a non-Windows
fallback. On Linux it temporarily applies the requesting player's `window_x`,
`window_y` and `window_z`, renders the current viewscreen, captures the SDL
render target, restores the original camera and redraws the host state.

The first Linux MVP therefore does not reuse the private Windows
`Dwarf Fortress.exe` RVA renderer.

## What this port changes

The build-time patcher:

- links `libjpeg`, `libpng` and `libdl` on Linux instead of GDI+/WinSock/CNG
- resolves SDL2 symbols with `dlsym(RTLD_DEFAULT, ...)`
- enables the existing HTTP server commands on Linux
- adds Linux JPEG and PNG encoding
- populates capture geometry directly from `renderer_2d`
- enables read-only SDL portrait texture access where possible
- keeps native Windows barter hooks unavailable
- keeps the Windows-only private renderer and SEH optimizations untouched
- preserves DFHack's global `-Werror`, while downgrading only the expected
  `unused-function`/`unused-label` warnings for the external DFCapture target on Linux
- rewrites an upstream one-line `if` pattern that GCC flags as misleading indentation

## Additional patches

`patch-multidwarf-zoom.py` enables the typed `ViewportZoomGuard` on Linux.
It temporarily substitutes viewport buffers and dimensions, applies the player's
zoom, captures the frame and restores the host state. It calls the typed renderer
interface rather than Windows RVA hooks. The same patch re-arms the save barrier
on plugin initialization and waits for a loaded world and save cleanup before
allowing browser world operations.

The Linux patch permits own-civilization tame animals in pasture candidate lists.
`patch-dfcapture-stockpiles.py` explicitly clears category flags when disabling
stockpile presets. Browser layout overrides live in `web/dfcapture-layout.css`
and `web/dfcapture-layout.js`; both image variants install them alongside live audio.

Local source-image builds completed successfully. The stockpile toggle was checked
against all 17 category flags with the original settings restored afterward. Further
live zoom/isolation and final responsive-layout tests were skipped at the operator's
request. Treat those as unverified rather than completed acceptance checks.

## Known limitations

The Windows build has extra fast/private paths that are intentionally not
ported yet. The Linux MVP may therefore have:

- higher capture cost
- experimental per-player zoom with runtime isolation validation still outstanding
- no native barter commit bridge
- reduced portrait-generation fallbacks
- possible panel incompatibilities where upstream depends on Windows internals

Independent X/Y/Z cameras use upstream's existing Linux fallback and are the
main target of this first port.

## Why the port is conservative

Upstream's Windows path contains exact DF 53.16 `Dwarf Fortress.exe` RVAs and
Structured Exception Handling. Reusing those offsets against the Linux ELF
would be unsafe. This project does not guess Linux addresses.

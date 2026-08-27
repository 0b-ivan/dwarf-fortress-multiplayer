# Dwarf Fortress Multiplayer — native Linux Docker

Experimental native-Linux Docker packaging for one shared **Dwarf Fortress
53.16** fortress with multiple browser players through
[Multi Dwarf / DFCapture](https://github.com/SourceAirbender/multi-dwarf).

```text
one container
    │
    ├── Dwarf Fortress 53.16 Premium Linux
    ├── DFHack 53.16-r1.1 Linux
    ├── DFCapture / Multi Dwarf
    ├── :8765  multiplayer lobby + browser players
    └── :6080  local noVNC admin/bootstrap only
```

There is **no Windows Dwarf Fortress, Wine, Proton, Authentik, session broker,
or container-per-player architecture** in this version.

## Status

This is an **experimental Linux port** of DFCapture.

Upstream currently targets DF 53.16 + DFHack 53.16-r1.1 on Windows x64. The
source already contains a Linux fallback for shifted camera capture, but Linux
is disabled in several surrounding components. This repository enables that
fallback without attempting to reuse Windows binary offsets against the Linux
ELF.

See [`docs/linux-port.md`](docs/linux-port.md).

## Requirements

- Docker Desktop / Docker Engine
- x86-64 Linux, or Apple Silicon Docker Desktop with `linux/amd64` emulation
- your purchased Linux archive:

```text
dwarf_fortress_53_16_linux.tar.bz2
```

The closed-source `dwarfort` binary is x86-64, so Apple Silicon still needs
Docker's amd64 emulation/Rosetta.

## 1. Add the purchased game archive

```bash
mkdir -p assets/private
cp ~/Downloads/dwarf_fortress_53_16_linux.tar.bz2 assets/private/
```

The directory is gitignored. Never commit the purchased game.

## 2. Build

```bash
make check
make build
```

The image build:

1. extracts your Linux Premium 53.16 archive
2. builds DFHack `53.16-r1.1`
3. checks out Multi Dwarf at a pinned commit
4. applies the native-Linux and multiplayer-lobby patches
5. compiles the Linux `.plug.so`
6. assembles the runtime image

The builder uses a persistent BuildKit `ccache`, so compiler retries after a
failed Linux-port build can reuse already compiled translation units.

## 3. Start

```bash
make up
```

Check:

```bash
docker compose ps
docker compose logs -f dwarf-fortress
```

## 4. Load or create a fortress

Use the local admin display:

```text
http://localhost:6080/
```

This noVNC endpoint is only for bootstrap/local administration and includes the
live game-audio bar.

## 5. Join as a player

Open:

```text
http://localhost:8765/
```

The lobby asks for a player name before DFCapture is opened. Names are reserved
server-side, case-insensitively, and must use 3–24 characters from `A-Z`, `a-z`,
`0-9`, `_` or `-`.

If the name is free, the browser receives a stable player id and is forwarded to
`/view`. If the name is already active, the server responds with `409 Conflict`
and the lobby asks for another name.

Direct access to `/view` without an active join reservation is redirected back
to the lobby.

All players share **one actual fortress**. DFCapture supplies separate browser
camera/control state.

## Persistence

```text
./data/save
  →
/root/.local/share/Bay 12 Games/Dwarf Fortress/save
```

The container also points `/opt/df/save` at the same location so DFCapture's
per-fort metadata follows the persistent save.

## Ports

| Port | Purpose | Exposure |
|---|---|---|
| `8765` | Lobby + DFCapture player UI/API | localhost by default |
| `6080` | noVNC admin/bootstrap | localhost only |

## Production / Cloudflare

The intended hosted URL is:

```text
https://dwarfs.obivan.org
```

Only the multiplayer gateway (`8765`) belongs behind Cloudflare Tunnel +
Cloudflare Access. The optional `docker-compose.cloudflare.yml` starts
`cloudflared`; local `make up` does not. See [`docs/cloudflare.md`](docs/cloudflare.md).

## CI

The repository includes a Linux compile smoke test that clones the exact pinned
DFHack and Multi Dwarf revisions, applies both source patches and builds the
`dfcapture_public` plugin. It does not require or upload the purchased DF archive.

## Important limitations

The first Linux MVP deliberately does not port the Windows-only private renderer
RVA hooks. Expect differences from upstream Windows behavior around per-player
zoom, some portraits, native barter, and capture performance.

This code does **not** fake Linux compatibility by running Windows DF through
Wine.

## Licenses

- DFCapture / Multi Dwarf: AGPL-3.0-only
- DFHack: Zlib
- Dwarf Fortress Premium: proprietary/purchased content; not included here

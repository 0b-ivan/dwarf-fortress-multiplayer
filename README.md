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
4. applies the Linux, lobby, ownership, camera-zoom and stockpile patches
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

## Browser controls and recent fixes

- **Map zoom:** use the Map − / + / reset buttons or Settings → Map zoom.
  Linux capture now uses a temporary viewport-buffer guard to render the requesting
  player's zoom and restore the host renderer afterward. This is experimental;
  isolation across simultaneous players and the noVNC admin still needs runtime
  validation. It is not browser-image scaling.
- **UI scale:** Settings → UI scale resizes browser controls independently of the
  map. Small windows automatically limit the effective scale to keep controls reachable.
- Toolbars reserve space above the audio bar. Chat is part of the left toolbar;
  designation submenus sit above the main toolbar. Unit headers retain their height,
  and settings/panels scroll when they exceed the available space.
- **Pastures:** tame animals belonging to the fortress civilization are no longer
  excluded from the assignable-animal list by the civilization filter.
- **Stockpiles:** disabling a category now clears its category flag as well as
  supporting the existing enable/customize workflow.
- Audio reconnects after stream errors. Browser autoplay restrictions may still
  require a click on **Enable audio**.

After a web UI update, hard-refresh the player page (macOS: **⌘⇧R**).
The image also reinitializes the save barrier on plugin load so a stale shutdown
state does not permanently block browser access. Active saving/loading still blocks
world operations until cleanup completes.

## Home network: http://dwarf.local

The optional LAN gateway exposes the noVNC admin display, WebSockets and live audio on
port 80. `client.dwarf.local` opens the multiplayer lobby and player UI with audio.
On a macOS Docker host, a Bonjour helper announces both names without
router DNS configuration or renaming the Mac:

```bash
# With the game already running from the current image:
make lan-up
make lan-bonjour
```

Open **http://dwarf.local/** on devices in the same network. Audio may require
one click on **Enable audio**. This grants devices on the LAN shared admin control.
The local admin URL remains localhost:6080; players use **http://client.dwarf.local/**
or the configured Cloudflare hostname.
See [`docs/lan.md`](docs/lan.md) for GHCR, network interfaces, startup and removal.

## Persistence

```text
./data/save
  →
/root/.local/share/Bay 12 Games/Dwarf Fortress/save
```

The container also points `/opt/df/save` at the same location so DFCapture's
per-fort metadata follows the persistent save.

Backup snapshots are created automatically every 15 minutes by default in
`./data/backups`. They are written as complete `.tar.gz` snapshots after the
save directory has been stable for a short period. The default retention is 20
snapshots. These copy existing on-disk saves; they do not trigger an in-game save
and do not include progress since the last save. The stability check is best-effort,
not a transactional snapshot of a running save. Configure `BACKUP_INTERVAL_SECONDS`, `BACKUP_RETENTION`, or set
`BACKUP_ENABLED=0` in the environment to change this behavior.

## Ports

| Port | Purpose | Exposure |
|---|---|---|
| `8765` | Lobby + DFCapture player UI/API | localhost by default; Cloudflare tunnel target |
| `6080` | noVNC admin/bootstrap | localhost only |
| `80` | Optional LAN gateway: admin + multiplayer + audio, selected by hostname | host IPv4 interfaces with `docker-compose.lan.yml` |

## Cloudflare multiplayer access

`cloudflared` is integrated into both Compose files under the optional
`cloudflare` profile. Configure the Cloudflare Tunnel hostname to point to:

```text
http://dwarf-fortress:8765
```

Export the remotely managed tunnel token:

```bash
export CLOUDFLARE_TUNNEL_TOKEN='...'
```

For the published GHCR image start the complete local game + tunnel stack with:

```bash
docker compose -f docker-compose.ghcr.yml --profile cloudflare up -d
```

The intended public URL is:

```text
https://dwarfs.obivan.org
```

The noVNC admin endpoint on `6080` remains localhost-only and must not be added
to the Cloudflare Tunnel. See [`docs/cloudflare.md`](docs/cloudflare.md).

## CI

The repository includes a Linux compile smoke test that clones the exact pinned
DFHack and Multi Dwarf revisions, applies the Linux, join, ownership and zoom
source patches and builds the
`dfcapture_public` plugin. It does not require or upload the purchased DF archive.

## Important limitations

The first Linux MVP deliberately does not port the Windows-only private renderer
RVA hooks. Expect differences from upstream Windows behavior around some portraits,
native barter, and capture performance. The Linux per-player zoom implementation is
experimental; successful compilation does not establish runtime isolation or visual correctness.

This code does **not** fake Linux compatibility by running Windows DF through
Wine.

## Licenses

- DFCapture / Multi Dwarf: AGPL-3.0-only
- DFHack: Zlib
- Dwarf Fortress Premium: proprietary/purchased content; not included here

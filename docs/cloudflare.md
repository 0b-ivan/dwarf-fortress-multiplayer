# Cloudflare deployment

`cloudflared` is part of the normal Compose files and is disabled by default through the `cloudflare` profile.

```text
Browser
  ↓
https://dwarfs.obivan.org
  ↓
Cloudflare Access
  ↓
Cloudflare Tunnel
  ↓
cloudflared container
  ↓
http://dwarf-fortress:8765
  ↓
Lobby + DFCapture
  ↓
one shared Dwarf Fortress
```

Port `6080` remains bound to localhost and is never routed through the tunnel.

## 1. Configure the tunnel

Create a remotely managed Cloudflare Tunnel and add a public hostname:

```text
Hostname: dwarfs.obivan.org
Service:  http://dwarf-fortress:8765
```

Get the tunnel token from Cloudflare and export it locally:

```bash
export CLOUDFLARE_TUNNEL_TOKEN='...'
```

## 2. Start with the GHCR image

```bash
docker compose -f docker-compose.ghcr.yml --profile cloudflare up -d
```

This starts both:

```text
dwarf-fortress-multiplayer
dwarf-fortress-cloudflared
```

Check:

```bash
docker compose -f docker-compose.ghcr.yml --profile cloudflare ps
docker compose -f docker-compose.ghcr.yml --profile cloudflare logs -f cloudflared
```

Stop:

```bash
docker compose -f docker-compose.ghcr.yml --profile cloudflare down
```

## Local source-build variant

The same profile exists in `docker-compose.yml`:

```bash
make cloudflare-up
make cloudflare-logs
```

or directly:

```bash
docker compose --profile cloudflare up -d
```

## Access

Put a Cloudflare Access policy in front of `dwarfs.obivan.org` if the game should not be publicly reachable. No additional Authentik service is required.

## Admin endpoint

Do **not** add a public hostname for port `6080`.

```text
http://127.0.0.1:6080/
```

is the local noVNC/bootstrap admin interface only.

## AGPL note

DFCapture is AGPL-3.0-only. If a modified build is used over the network, make the corresponding modified source available to those users. The purchased Dwarf Fortress archive remains excluded from Git and the published image.

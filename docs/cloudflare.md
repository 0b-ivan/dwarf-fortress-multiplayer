# Cloudflare deployment

Local Docker does not require Cloudflare. `make up` starts only Dwarf Fortress.

For the hosted deployment:

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
DFCapture
  ↓
one shared Dwarf Fortress
```

No Authentik is used.

## Tunnel

Create a remotely managed Cloudflare Tunnel and configure its public hostname:

```text
Hostname: dwarfs.obivan.org
Service:  http://dwarf-fortress:8765
```

Then export the tunnel token:

```bash
export CLOUDFLARE_TUNNEL_TOKEN='...'
```

Start the application plus tunnel:

```bash
make cloudflare-up
```

Logs:

```bash
make cloudflare-logs
```

The optional Compose overlay is `docker-compose.cloudflare.yml`.

## Access

Put a Cloudflare Access policy in front of `dwarfs.obivan.org`. Cloudflare is
therefore both the public ingress and the authentication boundary. There is no
additional Authentik login in this design.

## Admin endpoint

Do **not** add a public hostname for port `6080`. noVNC is bound to
`127.0.0.1` on the Docker host and is intended only for local/bootstrap admin
use.

## AGPL note

DFCapture is AGPL-3.0-only. If a modified build is used over the network, make
the corresponding modified source available to those users. This repository
contains the pinned upstream revision and the Linux patch/build logic; the
purchased Dwarf Fortress archive is deliberately excluded.

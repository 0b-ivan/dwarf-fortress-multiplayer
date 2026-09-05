# Home network access

The optional `docker-compose.lan.yml` adds an Nginx gateway on host port 80.
It opens the noVNC admin display, forwarding WebSockets and `/audio` to the
admin gateway on port 6080. `http://client.dwarf.local` opens the multiplayer lobby
and player UI with audio through port 8765. Both source-build
and GHCR Compose variants are supported.

## Prerequisites

- The game container must be running from the current image, including Nginx,
  admin wrapper and the PulseAudio/FFmpeg/Icecast audio pipeline. The LAN gateway
  serves the wrapper itself, so older images can already show the admin display;
  they cannot provide the new audio pipeline.
- Port 80 must be available. The Mac must stay awake, with Docker Desktop running.
- Clients must be on the same LAN and support mDNS/Bonjour. Guest Wi-Fi, client
  isolation, VPNs or multicast filtering can prevent discovery or access.
- Allow incoming connections for Docker in the host firewall when necessary.

## Start on macOS

With the game already running:

```bash
make lan-up
make lan-bonjour
```

For the GHCR stack use `make lan-up LAN_COMPOSE=docker-compose.ghcr.yml`.
`lan-up` starts only the gateway and does not restart the game. Building or
pulling a new game image is separate; save in-game before recreating its container.

`lan-bonjour` installs the per-user login agent
`~/Library/LaunchAgents/org.dwarf-fortress.bonjour.plist` and starts it immediately.
It uses the Python interpreter used for installation and this checkout's script;
keep both paths available. It runs while that macOS user is logged in and starts
again at login. Docker containers restart when Docker Desktop starts.

The default interface is `en0`. Use `ifconfig` to identify your active LAN
interface, then, for example, `make lan-bonjour LAN_INTERFACE=en1` for another
interface. Reinstalling updates the existing agent. Every 15 seconds it checks
the interface's IPv4 address, removes the old advertisement and announces the
new address when the network changes. It does not change the Mac's own hostname.
Only one host in a network should advertise these names. Both resolve to the same
IPv4 address; Nginx selects the admin or player backend from the HTTP hostname.

The helper uses macOS `dns-sd -P` to register both hostnames and HTTP services;
see the [dns-sd manual](https://man.netbsd.org/NetBSD-9.4/dns-sd.1).

Open **http://dwarf.local/** explicitly if the browser treats the name as a search
or attempts HTTPS. The shared admin screen opens directly; enable audio if the
browser blocks autoplay. This is the shared game's sound, not a voice-chat channel.

The LAN gateway listens on all host IPv4 interfaces by default. It is available
to devices that can reach the host, without adding an authentication layer. They
can control the shared admin desktop. Use this on your trusted home network. Set
`LAN_BIND_IP` in `.env` to a specific LAN IPv4 address if needed; update that value
and recreate the gateway after an address change. No router port forwarding is
required. Existing Cloudflare configuration continues to target the player lobby
on port 8765; it must not target this admin gateway on port 80.

## Verify

```bash
python3 scripts/lan-bonjour.py status
dscacheutil -q host -a name dwarf.local
dscacheutil -q host -a name client.dwarf.local
curl --noproxy '*' -I http://dwarf.local/
curl --noproxy '*' http://client.dwarf.local/health
docker compose -f docker-compose.yml -f docker-compose.lan.yml logs lan-gateway
```

Also open the URL on a second device: a host-only check cannot verify Wi-Fi
isolation or that device's mDNS support. If discovery fails, try
`http://<Mac-LAN-IP>/` to distinguish DNS from connectivity problems.
The agent logs to `data/lan/bonjour.log` and `data/lan/bonjour-error.log`.

## Stop or remove

```bash
make lan-down
make lan-bonjour-remove
```

For GHCR, append `LAN_COMPOSE=docker-compose.ghcr.yml` to `lan-down`.
These commands leave the game running and save data intact. Remove the login
agent before moving or deleting the checkout. No system hostname or router
configuration needs reverting.

## Other host operating systems

The gateway Compose file is independent of macOS. The Bonjour helper is macOS
only. A Linux host needs its own mDNS publisher (for example Avahi) configured
to announce `dwarf.local` and `client.dwarf.local` with that host's LAN address; mDNS must run on the host
network, not just inside Docker's bridge network.

.PHONY: check build up down logs shell clean cloudflare-up cloudflare-down cloudflare-logs lan-up lan-down lan-bonjour lan-bonjour-remove

LAN_COMPOSE ?= docker-compose.yml
LAN_INTERFACE ?= en0

check:
	@test -f assets/private/dwarf_fortress_53_16_linux.tar.bz2 || \
	  (echo "missing: assets/private/dwarf_fortress_53_16_linux.tar.bz2" >&2; exit 1)
	@echo "private DF archive found"

build: check
	docker compose build

up:
	docker compose up -d
	@echo "Admin/noVNC: http://localhost:$${ADMIN_PORT:-6080}/"
	@echo "Players:      http://localhost:$${DFCAPTURE_PORT:-8765}/"

down:
	docker compose down

logs:
	docker compose logs -f dwarf-fortress

shell:
	docker compose exec dwarf-fortress bash

cloudflare-up: check
	@test -n "$${CLOUDFLARE_TUNNEL_TOKEN:-}" || \
	  (echo "missing: CLOUDFLARE_TUNNEL_TOKEN" >&2; exit 1)
	docker compose --profile cloudflare up -d

cloudflare-down:
	docker compose --profile cloudflare down

cloudflare-logs:
	docker compose --profile cloudflare logs -f cloudflared

clean:
	docker compose --profile cloudflare down --remove-orphans

# Starts only the gateway; never restarts a running game implicitly.
lan-up:
	docker compose -f $(LAN_COMPOSE) -f docker-compose.lan.yml up -d --no-deps lan-gateway
	@echo "Admin + audio: http://dwarf.local/ (requires Bonjour; see docs/lan.md)"
	@echo "Multiplayer:   http://client.dwarf.local/"

lan-down:
	docker compose -f $(LAN_COMPOSE) -f docker-compose.lan.yml rm -sf lan-gateway

lan-bonjour:
	python3 scripts/lan-bonjour.py install --interface $(LAN_INTERFACE)

lan-bonjour-remove:
	python3 scripts/lan-bonjour.py uninstall

.PHONY: check build up down logs shell clean cloudflare-up cloudflare-down cloudflare-logs

check:
	@test -f assets/private/dwarf_fortress_53_16_linux.tar.bz2 || \
	  (echo "missing: assets/private/dwarf_fortress_53_16_linux.tar.bz2" >&2; exit 1)
	@echo "private DF archive found"

build: check
	docker compose build

up:
	docker compose up -d
	@echo "Admin/noVNC: http://localhost:$${ADMIN_PORT:-6080}/vnc.html?autoconnect=true&resize=remote"
	@echo "Players:      http://localhost:$${DFCAPTURE_PORT:-8765}/view?player=YOURNAME"

down:
	docker compose down

logs:
	docker compose logs -f dwarf-fortress

shell:
	docker compose exec dwarf-fortress bash

cloudflare-up: check
	@test -n "$${CLOUDFLARE_TUNNEL_TOKEN:-}" || \
	  (echo "missing: CLOUDFLARE_TUNNEL_TOKEN" >&2; exit 1)
	docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml up -d

cloudflare-down:
	docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml down

cloudflare-logs:
	docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml logs -f cloudflared

clean:
	docker compose down --remove-orphans

#!/usr/bin/env bash
set -Eeuo pipefail

GAME_DIR="${DF_GAME_DIR:-/opt/df}"
OVERLAY_DIR="${DF_OVERLAY_DIR:-/opt/df-overlay}"
ARCHIVE="${DF_ARCHIVE:-/bootstrap/dwarf_fortress_53_16_linux.tar.bz2}"

mkdir -p "$GAME_DIR"

if [ ! -x "$GAME_DIR/dwarfort" ]; then
  if [ ! -r "$ARCHIVE" ]; then
    cat >&2 <<EOF
Dwarf Fortress 53.16 is not installed in $GAME_DIR.
Mount your purchased Linux archive read-only at:
  $ARCHIVE

Example:
  ./assets/private/dwarf_fortress_53_16_linux.tar.bz2:$ARCHIVE:ro
EOF
    exit 1
  fi

  echo "[bootstrap] installing private Dwarf Fortress archive into persistent game volume"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  tar -xjf "$ARCHIVE" -C "$tmp"

  if [ -f "$tmp/dwarfort" ]; then
    source_root="$tmp"
  else
    source_root="$(find "$tmp" -mindepth 1 -maxdepth 1 -type d | head -1)"
  fi

  if [ -z "${source_root:-}" ] || [ ! -f "$source_root/dwarfort" ]; then
    echo "[bootstrap] archive does not contain a Dwarf Fortress Linux dwarfort binary" >&2
    exit 1
  fi

  cp -a "$source_root"/. "$GAME_DIR"/
  chmod +x "$GAME_DIR/dwarfort"
  rm -rf "$tmp"
  trap - EXIT
fi

if [ ! -d "$OVERLAY_DIR/hack" ]; then
  echo "[bootstrap] DFHack overlay is missing from the image" >&2
  exit 1
fi

# Refresh the open-source DFHack/DFCapture overlay on every image update while
# keeping the proprietary game and user data outside the container image.
cp -a "$OVERLAY_DIR"/. "$GAME_DIR"/

test -x "$GAME_DIR/dwarfort"
test -f "$GAME_DIR/hack/libdfhack.so"
test -n "$(find "$GAME_DIR/hack/plugins" -maxdepth 1 -type f -name 'dfcapture*.so' -print -quit)"

exec /usr/local/bin/entrypoint.sh

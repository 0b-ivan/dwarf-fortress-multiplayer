#!/usr/bin/env bash
set -Eeuo pipefail

export DISPLAY="${DISPLAY:-:99}"
export HOME="${HOME:-/root}"
export LD_LIBRARY_PATH="/opt/df:/opt/df/hack/libs:/opt/df/hack:${LD_LIBRARY_PATH:-}"

SAVE_DIR="${HOME}/.local/share/Bay 12 Games/Dwarf Fortress/save"
mkdir -p "$SAVE_DIR" /backups /var/log/df

if [ -e /opt/df/save ] && [ ! -L /opt/df/save ]; then
  mv /opt/df/save "/opt/df/save.image.$(date +%s)"
fi
ln -sfn "$SAVE_DIR" /opt/df/save

Xvnc "$DISPLAY" \
  -geometry "${GEOM:-1280x800}" \
  -depth 24 \
  -rfbport 5900 \
  -SecurityTypes None \
  -localhost yes \
  -AlwaysShared \
  >/var/log/df/xvnc.log 2>&1 &

for _ in $(seq 1 80); do
  if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done

if ! xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
  echo "Xvnc failed to become ready" >&2
  cat /var/log/df/xvnc.log >&2 || true
  exit 1
fi

DISPLAY="$DISPLAY" matchbox-window-manager \
  -use_titlebar no \
  -use_desktop_mode plain \
  >/var/log/df/wm.log 2>&1 &

websockify --web=/usr/share/novnc 6080 127.0.0.1:5900 \
  >/var/log/df/novnc.log 2>&1 &

mkdir -p /opt/df/dfhack-config/init
cat >/opt/df/dfhack-config/init/dfhack-dfcapture.init <<EOF
capture-stream-start ${DFCAPTURE_PORT:-8765} 0.0.0.0
EOF

cd /opt/df

echo "[start] Dwarf Fortress 53.16 + DFHack + DFCapture (Linux port)"
echo "[start] DFCapture: http://127.0.0.1:${DFCAPTURE_PORT:-8765}/"
echo "[start] noVNC admin: http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=remote"

exec env \
  LD_PRELOAD="/opt/df/hack/libdfhack.so" \
  LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
  /opt/df/dwarfort

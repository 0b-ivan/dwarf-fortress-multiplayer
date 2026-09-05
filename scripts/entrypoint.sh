#!/usr/bin/env bash
set -Eeuo pipefail

export DISPLAY="${DISPLAY:-:99}"
export HOME="${HOME:-/root}"
export LANG="${LANG:-C.UTF-8}"
export LC_ALL="${LC_ALL:-C.UTF-8}"
export LD_LIBRARY_PATH="/opt/df:/opt/df/hack/libs:/opt/df/hack:${LD_LIBRARY_PATH:-}"
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-pulseaudio}"

PUBLIC_PORT="${DFCAPTURE_PUBLIC_PORT:-8765}"
BACKEND_PORT="${DFCAPTURE_BACKEND_PORT:-8766}"
SAVE_DIR="${HOME}/.local/share/Bay 12 Games/Dwarf Fortress/save"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
mkdir -p "$SAVE_DIR" "$BACKUP_DIR" /var/log/df

export SAVE_DIR BACKUP_DIR

if [ "${BACKUP_ENABLED:-1}" = "1" ]; then
  BACKUP_INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-900}" \
    BACKUP_RETENTION="${BACKUP_RETENTION:-20}" \
    /usr/local/bin/backup-save.sh >/var/log/df/backup.log 2>&1 &
  backup_pid=$!
else
  backup_pid=""
fi

if [ -e /opt/df/save ] && [ ! -L /opt/df/save ]; then
  mv /opt/df/save "/opt/df/save.image.$(date +%s)"
fi
ln -sfn "$SAVE_DIR" /opt/df/save

# Ensure game audio is enabled even if the archive shipped with SOUND:NO.
for init_file in /opt/df/prefs/init.txt /opt/df/data/init/init.txt; do
  if [ -f "$init_file" ]; then
    sed -i 's/\[SOUND:NO\]/[SOUND:YES]/g' "$init_file"
  fi
done

# A container restart reuses its writable layer. If Xvnc did not remove its
# lock/socket cleanly, the next start would otherwise fail forever with
# "Server is already active for display 99".
display_num="${DISPLAY#:}"
x_lock="/tmp/.X${display_num}-lock"
x_socket="/tmp/.X11-unix/X${display_num}"
if [ -f "$x_lock" ]; then
  x_pid="$(tr -dc '0-9' <"$x_lock" || true)"
  x_comm="$(ps -p "${x_pid:-0}" -o comm= 2>/dev/null || true)"
  if [ -z "$x_pid" ] || ! kill -0 "$x_pid" 2>/dev/null || [[ "$x_comm" != *Xvnc* && "$x_comm" != *Xtigervnc* ]]; then
    echo "[start] removing stale X11 lock for display $DISPLAY"
    rm -f "$x_lock" "$x_socket"
  fi
fi

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

# Keep noVNC internal; nginx owns public :6080 so it can add the audio bar.
websockify --web=/usr/share/novnc 6081 127.0.0.1:5900 \
  >/var/log/df/novnc.log 2>&1 &

# Real DF audio: PulseAudio null sink -> ffmpeg Opus -> Icecast.
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/pulse-runtime}"
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"

pulseaudio --daemonize=yes --exit-idle-time=-1 \
  --load="module-null-sink sink_name=virtual_out sink_properties=device.description=VirtualOutput" \
  --load="module-always-sink" \
  >/var/log/df/pulse.log 2>&1 || true

pulse_ready=0
for _ in $(seq 1 50); do
  if pactl info >/dev/null 2>&1; then
    pulse_ready=1
    break
  fi
  sleep 0.1
done

if [ "$pulse_ready" -eq 1 ]; then
  pactl set-default-sink virtual_out >/dev/null 2>&1 || true
  export PULSE_SINK=virtual_out
else
  echo "[audio] PulseAudio did not become ready; DF will start without live audio" >&2
fi

chown icecast2:icecast /var/log/df >/dev/null 2>&1 || true
icecast2 -c /etc/icecast2/icecast.xml >/var/log/df/icecast.log 2>&1 &

if [ "$pulse_ready" -eq 1 ]; then
  (
    while true; do
      ffmpeg -nostdin -hide_banner -loglevel warning \
        -f pulse -i virtual_out.monitor \
        -ac 2 -ar 48000 -b:a 96k -c:a libopus -f ogg \
        -content_type audio/ogg \
        "icecast://source:dfsource@127.0.0.1:8000/df.ogg" \
        >>/var/log/df/audio.log 2>&1 || true
      sleep 1
    done
  ) &
fi

# Public gateways. DFCapture and noVNC only listen on loopback behind nginx.
nginx -t
nginx

mkdir -p /opt/df/dfhack-config/init
cat >/opt/df/dfhack-config/init/dfhack-dfcapture.init <<EOF
capture-stream-start ${BACKEND_PORT} 127.0.0.1
EOF

cd /opt/df

echo "[start] Dwarf Fortress 53.16 + DFHack + DFCapture (Linux port)"
echo "[start] DFCapture: http://127.0.0.1:${PUBLIC_PORT}/"
echo "[start] Live audio: http://127.0.0.1:${PUBLIC_PORT}/audio"
echo "[start] noVNC admin + audio: http://127.0.0.1:6080/"

# Quitting DF from VNC is an application-level exit, not a reason to tear down
# the service. Keep Xvnc, DFCapture gateway and audio alive and relaunch only DF.
shutting_down=0
df_pid=""
shutdown() {
  shutting_down=1
  if [ -n "${backup_pid:-}" ]; then
    kill "$backup_pid" 2>/dev/null || true
  fi
  if [ -n "$df_pid" ]; then
    kill -TERM "$df_pid" 2>/dev/null || true
  fi
}
trap shutdown TERM INT

while [ "$shutting_down" -eq 0 ]; do
  set +e
  env \
    LD_PRELOAD="/opt/df/hack/libdfhack.so" \
    LD_LIBRARY_PATH="$LD_LIBRARY_PATH" \
    SDL_AUDIODRIVER="$SDL_AUDIODRIVER" \
    PULSE_SINK="${PULSE_SINK:-virtual_out}" \
    /opt/df/dwarfort &
  df_pid=$!
  wait "$df_pid"
  rc=$?
  df_pid=""
  set -e

  if [ "$shutting_down" -ne 0 ]; then
    break
  fi

  echo "[start] dwarfort exited rc=$rc; restarting in 2s"
  sleep 2
done

exit 0

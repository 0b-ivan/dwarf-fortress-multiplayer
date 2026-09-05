#!/usr/bin/env bash
set -Eeuo pipefail

save_dir="${SAVE_DIR:?SAVE_DIR is required}"
backup_dir="${BACKUP_DIR:-/backups}"
interval="${BACKUP_INTERVAL_SECONDS:-900}"
retention="${BACKUP_RETENTION:-20}"

mkdir -p "$backup_dir"

snapshot_signature() {
  find "$save_dir" -type f -printf '%T@ %s %p\n' 2>/dev/null | sort | sha256sum | cut -d' ' -f1
}

make_backup() {
  [ -d "$save_dir" ] || return 0
  local first second stamp tmp target
  first="$(snapshot_signature)"
  sleep 2
  second="$(snapshot_signature)"
  [ "$first" = "$second" ] || return 0

  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="$backup_dir/save-$stamp.tar.gz"
  tmp="$target.tmp"
  tar -C "$save_dir" -czf "$tmp" . && mv -f "$tmp" "$target"

  find "$backup_dir" -maxdepth 1 -type f -name 'save-*.tar.gz' -printf '%T@ %p\n' \
    | sort -nr | tail -n +$((retention + 1)) | cut -d' ' -f2- \
    | while IFS= read -r old; do [ -n "$old" ] && rm -f -- "$old"; done
}

while :; do
  make_backup || echo "[backup] snapshot failed; will retry" >&2
  sleep "$interval"
done

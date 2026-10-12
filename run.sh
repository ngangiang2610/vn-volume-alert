#!/bin/bash
# Chạy alert.py trên máy local. Bí mật (webhook) lấy từ file ngoài repo.
cd "$(dirname "$0")" || exit 1
ENV_FILE="$HOME/.config/vn-volume-alert/env"
if [ -f "$ENV_FILE" ]; then
  set -a; . "$ENV_FILE"; set +a
fi
exec /usr/bin/python3 alert.py "$@"

#!/bin/bash
# Cài launchd job: chạy run.sh mỗi 5 phút (alert.py tự bỏ qua ngoài 9h15-11h, T2-T6).
# macOS không cho job nền đọc folder Documents, nên chạy từ bản sao ở ~/.local/share.
# Sửa code xong thì chạy lại file này để cập nhật bản sao.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DIR="$HOME/.local/share/vn-volume-alert"
mkdir -p "$DIR"
cp "$SRC/alert.py" "$SRC/run.sh" "$DIR/"
LABEL=com.vnvolumealert
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/vn-volume-alert.log"
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/.config/vn-volume-alert"
cat > "$PLIST" <<P
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$DIR/run.sh</string></array>
  <key>StartInterval</key><integer>300</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict></plist>
P
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Đã cài $LABEL. Log: $LOG"

#!/bin/bash
# macOS launchd 設定腳本
# 自動在每日下午 2:30 (台股收盤後) 執行數據更新

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.finlab.daily-update"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

# Python 路徑 (請根據您的環境調整)
PYTHON_PATH=$(which python3)

echo "設定每日自動更新任務..."
echo "腳本路徑: $ROOT_DIR/scripts/daily_update.py"
echo "Python 路徑: $PYTHON_PATH"

# 建立 plist 檔案
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>${ROOT_DIR}/scripts/daily_update.py</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>14</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>

    <key>WorkingDirectory</key>
    <string>${ROOT_DIR}</string>

    <key>StandardOutPath</key>
    <string>${ROOT_DIR}/logs/launchd_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${ROOT_DIR}/logs/launchd_stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

# 建立 logs 資料夾
mkdir -p "$ROOT_DIR/logs"

echo "plist 檔案已建立: $PLIST_PATH"

# 載入 launchd 任務
launchctl unload "$PLIST_PATH" 2>/dev/null
launchctl load "$PLIST_PATH"

echo "launchd 任務已載入"
echo ""
echo "管理指令:"
echo "  查看狀態: launchctl list | grep finlab"
echo "  停止任務: launchctl unload $PLIST_PATH"
echo "  啟動任務: launchctl load $PLIST_PATH"
echo "  手動執行: python3 $ROOT_DIR/scripts/daily_update.py"
echo ""
echo "任務將在每日 14:30 自動執行"

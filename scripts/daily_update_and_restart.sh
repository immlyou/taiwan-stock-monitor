#!/bin/bash
# 每日更新資料並重啟 API Server
# 由 launchd 排程於每天 07:00 執行

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=========================================="
echo "每日資料更新 - $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# 載入環境變數
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 執行資料更新
echo "開始更新資料..."
python3 scripts/daily_update.py 2>&1

# 重啟 API Server（清除快取）
echo "重啟 API Server..."
launchctl kickstart -k gui/$(id -u)/com.stockapi.server 2>/dev/null || true

# 等待 API Server 啟動
sleep 3

# 驗證
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo "✅ API Server 重啟成功"
else
    echo "⚠️ API Server 可能未啟動，請檢查日誌"
fi

echo "更新完成 - $(date '+%Y-%m-%d %H:%M:%S')"

# 檢查警報並發送通知
echo "開始檢查警報..."
python3 scripts/check_alerts.py 2>&1
if [ $? -eq 0 ]; then
    echo "✅ 警報檢查完成"
else
    echo "⚠️ 警報檢查失敗，請查看 alerts.log"
fi

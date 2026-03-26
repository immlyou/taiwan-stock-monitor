#!/bin/bash
# 龍蝦端安裝腳本
# 在龍蝦電腦上執行，設定 API Server 為 launchd 常駐服務

set -e

INSTALL_DIR="$HOME/taiwan-stock-monitor"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

echo "=========================================="
echo "台股 API Server 安裝腳本"
echo "安裝目錄: $INSTALL_DIR"
echo "=========================================="

cd "$INSTALL_DIR"

# 1. 找到 python3 路徑
PYTHON3=$(which python3 2>/dev/null || echo "/usr/local/bin/python3")
if [ ! -x "$PYTHON3" ]; then
    echo "❌ 找不到 python3，請先安裝 Python 3"
    echo "   brew install python3"
    exit 1
fi
echo "Python3: $PYTHON3"
echo "版本: $($PYTHON3 --version)"

# 2. 安裝依賴
echo ""
echo "📦 安裝 Python 依賴..."
$PYTHON3 -m pip install -r requirements-api.txt --quiet

# 3. 建立 logs 目錄
mkdir -p "$INSTALL_DIR/logs"

# 4. 設定 launchd plist
echo ""
echo "⚙️ 設定 launchd 服務..."
mkdir -p "$LAUNCH_AGENTS_DIR"

# 取得 python3 的完整路徑（給 plist 用）
PYTHON3_FULL=$($PYTHON3 -c "import sys; print(sys.executable)")

for plist_file in launchd/*.plist; do
    filename=$(basename "$plist_file")

    # 先卸載舊服務（如果存在）
    label="${filename%.plist}"
    launchctl bootout gui/$(id -u)/"$label" 2>/dev/null || true

    # 替換路徑佔位符
    sed -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
        -e "s|/usr/local/bin/python3|$PYTHON3_FULL|g" \
        "$plist_file" > "$LAUNCH_AGENTS_DIR/$filename"

    echo "  ✓ 已安裝 $filename"
done

# 5. 設定腳本執行權限
chmod +x scripts/daily_update_and_restart.sh

# 6. 載入服務
echo ""
echo "🚀 啟動服務..."
launchctl bootstrap gui/$(id -u) "$LAUNCH_AGENTS_DIR/com.stockapi.server.plist"
launchctl bootstrap gui/$(id -u) "$LAUNCH_AGENTS_DIR/com.stockapi.daily-update.plist"

# 7. 等待 API 啟動
echo ""
echo "等待 API Server 啟動..."
sleep 3

# 8. 驗證
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo ""
    echo "=========================================="
    echo "✅ 安裝成功！"
    echo ""
    echo "API Server: http://localhost:8000"
    echo "API 文件:   http://localhost:8000/docs"
    echo ""
    echo "測試指令:"
    echo "  curl http://localhost:8000/stock/2330"
    echo "  curl http://localhost:8000/morning-report"
    echo ""
    echo "服務管理:"
    echo "  launchctl list | grep stockapi"
    echo "  launchctl kickstart -k gui/\$(id -u)/com.stockapi.server  # 重啟"
    echo "  tail -f ~/taiwan-stock-monitor/logs/api_server.out.log    # 看日誌"
    echo "=========================================="
else
    echo ""
    echo "⚠️ API Server 似乎未啟動，請檢查日誌:"
    echo "  cat $INSTALL_DIR/logs/api_server.err.log"
    exit 1
fi

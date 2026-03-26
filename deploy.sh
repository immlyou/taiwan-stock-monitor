#!/bin/bash
# 一鍵部署台股 API Server 到龍蝦電腦
#
# 使用方式:
#   ./deploy.sh user@lobster-mac.local
#   ./deploy.sh user@192.168.1.100
#   ./deploy.sh user@lobster-mac.local --skip-data   # 跳過資料同步（快速更新程式碼）
#   ./deploy.sh user@lobster-mac.local --skill-dir ~/openclaw/skills  # 指定 OpenClaw skill 目錄

set -e

# ─── 參數解析 ───────────────────────────────────────────
REMOTE_HOST=""
SKIP_DATA=false
OPENCLAW_SKILL_DIR="~/openclaw/skills"
REMOTE_DIR="~/taiwan-stock-monitor"

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-data)
            SKIP_DATA=true
            shift
            ;;
        --skill-dir)
            OPENCLAW_SKILL_DIR="$2"
            shift 2
            ;;
        --remote-dir)
            REMOTE_DIR="$2"
            shift 2
            ;;
        *)
            REMOTE_HOST="$1"
            shift
            ;;
    esac
done

if [ -z "$REMOTE_HOST" ]; then
    echo "使用方式: $0 user@hostname [選項]"
    echo ""
    echo "選項:"
    echo "  --skip-data              跳過 pickle 資料同步（快速更新程式碼）"
    echo "  --skill-dir <path>       OpenClaw skills 目錄 (預設: ~/openclaw/skills)"
    echo "  --remote-dir <path>      遠端安裝目錄 (預設: ~/taiwan-stock-monitor)"
    echo ""
    echo "範例:"
    echo "  $0 chris@lobster-mac.local"
    echo "  $0 chris@192.168.1.100 --skip-data"
    exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "=========================================="
echo "🚀 部署台股 API Server"
echo "目標: $REMOTE_HOST:$REMOTE_DIR"
echo "=========================================="

# ─── 1. 確認 SSH 連線 ──────────────────────────────────
echo ""
echo "📡 測試 SSH 連線..."
if ! ssh -o ConnectTimeout=5 "$REMOTE_HOST" "echo '✅ SSH 連線成功'" 2>/dev/null; then
    echo "❌ 無法連線到 $REMOTE_HOST"
    echo "請確認:"
    echo "  1. 龍蝦電腦已開機且在同一網路"
    echo "  2. SSH 已啟用（系統設定 → 一般 → 共享 → 遠端登入）"
    echo "  3. 目標位址正確"
    exit 1
fi

# ─── 2. 建立遠端目錄 ───────────────────────────────────
echo ""
echo "📁 建立遠端目錄..."
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR/logs $REMOTE_DIR/reports"

# ─── 3. 同步程式碼 ─────────────────────────────────────
echo ""
echo "📤 同步程式碼..."
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.streamlit' \
    --exclude='app/' \
    --exclude='legacy/' \
    --exclude='*.pickle' \
    --exclude='*.pkl' \
    --exclude='node_modules' \
    --exclude='.DS_Store' \
    --exclude='logs/' \
    --exclude='reports/' \
    --exclude='venv/' \
    "$PROJECT_DIR/" \
    "$REMOTE_HOST:$REMOTE_DIR/"

# ─── 4. 同步資料檔 ─────────────────────────────────────
if [ "$SKIP_DATA" = true ]; then
    echo ""
    echo "⏭️ 跳過資料同步 (--skip-data)"
else
    echo ""
    echo "📊 同步資料檔 (pickle)... 首次約 1.6GB，請稍候..."
    rsync -avz --progress \
        --include='*.pickle' \
        --include='*.pkl' \
        --exclude='*' \
        "$PROJECT_DIR/" \
        "$REMOTE_HOST:$REMOTE_DIR/"
fi

# ─── 5. 同步環境變數 ───────────────────────────────────
echo ""
echo "🔑 同步環境變數..."
if [ -f "$PROJECT_DIR/.env" ]; then
    rsync -avz "$PROJECT_DIR/.env" "$REMOTE_HOST:$REMOTE_DIR/.env"
    echo "  ✓ .env 已同步"
else
    echo "  ⚠️ 本地找不到 .env，請手動在龍蝦建立"
fi

# ─── 6. 部署 OpenClaw Skill ────────────────────────────
echo ""
echo "🦞 部署 OpenClaw Skill..."
ssh "$REMOTE_HOST" "mkdir -p $OPENCLAW_SKILL_DIR" 2>/dev/null || true
rsync -avz \
    "$PROJECT_DIR/openclaw_skill/taiwan_stock_skill.py" \
    "$REMOTE_HOST:$OPENCLAW_SKILL_DIR/taiwan_stock_skill.py" 2>/dev/null || {
    echo "  ⚠️ 無法部署到 $OPENCLAW_SKILL_DIR，請手動複製 openclaw_skill/taiwan_stock_skill.py"
}

# ─── 7. 遠端安裝 ───────────────────────────────────────
echo ""
echo "⚙️ 執行遠端安裝..."
ssh "$REMOTE_HOST" "cd $REMOTE_DIR && chmod +x scripts/install_remote.sh scripts/daily_update_and_restart.sh && bash scripts/install_remote.sh"

echo ""
echo "=========================================="
echo "🎉 部署完成！"
echo ""
echo "龍蝦端 API: http://$REMOTE_HOST:8000 (外部存取)"
echo "龍蝦本機:   http://localhost:8000"
echo "API 文件:   http://$REMOTE_HOST:8000/docs"
echo ""
echo "OpenClaw Skill 已部署到: $OPENCLAW_SKILL_DIR"
echo "記得重啟 OpenClaw 讓 Skill 生效"
echo "=========================================="

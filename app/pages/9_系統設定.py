"""
系統設定頁面 - LINE 通知設定與自動更新排程
"""
import streamlit as st
import json
import sys
import os
from pathlib import Path
from datetime import datetime


from config import DATA_DIR
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_global_ticker_bar
from app.components.error_handler import show_error
from app.components.theme import (
    COLORS,
    create_page_title,
    create_section_header,
    render_data_table,
)

st.set_page_config(page_title='系統設定', page_icon='⚙️', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='settings')

# 全域報價列（sidebar 後、標題前）
render_global_ticker_bar()

st.markdown(
    create_page_title(
        '系統設定',
        subtitle='通知整合、自動排程、手動更新與版本資訊',
        icon='⚙️',
    ),
    unsafe_allow_html=True,
)

# 設定檔路徑
SETTINGS_FILE = Path(__file__).parent.parent.parent / 'data' / 'settings.json'
SETTINGS_FILE.parent.mkdir(exist_ok=True)

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'line_notify': {'enabled': False, 'token': ''},
        'telegram': {'enabled': False, 'token': '', 'chat_id': ''},
        'email': {'enabled': False, 'sender': '', 'password': '', 'recipients': []},
        'auto_update': {'enabled': False, 'time': '08:00'},
    }

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

settings = load_settings()

# ========== 通知設定（三方案分頁）==========
st.markdown(create_section_header('通知設定', icon='🔔'), unsafe_allow_html=True)

tab_tg, tab_line, tab_email = st.tabs(['✈️ Telegram Bot', '📱 LINE Notify', '📧 Email'])

with tab_tg:
    st.warning('LINE Notify 已於 2025/04 停止服務，建議改用 Telegram Bot')

    st.markdown('''
Telegram Bot 可以讓系統自動推送選股結果和警報到您的 Telegram。

**如何設定 Telegram Bot：**
1. 在 Telegram 搜尋 [@BotFather](https://t.me/BotFather) 並傳送 `/newbot`
2. 依指示設定 Bot 名稱，取得 **Bot Token**
3. 搜尋 [@userinfobot](https://t.me/userinfobot) 傳送任意訊息取得 **Chat ID**
4. 也可將 Bot 加入群組，再用 `https://api.telegram.org/bot<TOKEN>/getUpdates` 取得群組 Chat ID
''')

    tg_col1, tg_col2 = st.columns([3, 1])

    with tg_col1:
        tg_token = st.text_input(
            'Telegram Bot Token',
            value=settings.get('telegram', {}).get('token', ''),
            type='password',
            placeholder='123456789:AABBccDDeeFFggHH...',
            help='從 @BotFather 取得的 Bot Token',
        )

    with tg_col2:
        tg_enabled = st.checkbox(
            '啟用 Telegram 通知',
            value=settings.get('telegram', {}).get('enabled', False),
        )

    tg_chat_id = st.text_input(
        'Chat ID',
        value=settings.get('telegram', {}).get('chat_id', ''),
        placeholder='123456789 或 -100123456789（群組）',
        help='您的 Telegram User ID 或群組 Chat ID',
    )

    if st.button('💾 儲存 Telegram 設定'):
        settings['telegram'] = {
            'enabled': tg_enabled,
            'token': tg_token,
            'chat_id': tg_chat_id,
        }
        save_settings(settings)
        # 同步寫入環境變數提示（實際生效需在 .env 設定）
        st.success('Telegram 設定已儲存！')
        if tg_token and tg_chat_id:
            st.info('提示：若使用排程執行，請同時將 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 加入 .env 檔案')

    # 測試 Telegram 通知
    if tg_token and tg_chat_id and st.button('🔔 測試 Telegram 通知'):
        try:
            import requests

            url = f'https://api.telegram.org/bot{tg_token}/sendMessage'
            payload = {
                'chat_id': tg_chat_id,
                'text': f'*台股分析系統 - 測試通知*\n{"─" * 20}\n這是一則測試通知。\n時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
                'parse_mode': 'Markdown',
            }

            response = requests.post(url, data=payload, timeout=10)
            result = response.json()

            if response.status_code == 200 and result.get('ok'):
                st.success('✅ 測試通知發送成功！請檢查您的 Telegram。')
            else:
                st.error(f'❌ 發送失敗: {result.get("description", response.text)}')

        except Exception as e:
            show_error(e, title='發送通知失敗', suggestion='請確認 Bot Token 和 Chat ID 是否正確')

with tab_line:
    st.warning('LINE Notify 已於 2025/04 停止服務，建議改用 Telegram Bot')

    st.markdown('''
LINE Notify 可以讓系統自動推送選股結果和警報到您的 LINE。

**如何取得 Token：**
1. 前往 [LINE Notify](https://notify-bot.line.me/)
2. 登入您的 LINE 帳號
3. 點擊「發行權杖」
4. 選擇要接收通知的聊天室（個人或群組）
5. 複製產生的 Token
''')

    col1, col2 = st.columns([3, 1])

    with col1:
        line_token = st.text_input(
            'LINE Notify Token',
            value=settings.get('line_notify', {}).get('token', ''),
            type='password',
            help='您的 LINE Notify 存取權杖'
        )

    with col2:
        line_enabled = st.checkbox(
            '啟用 LINE 通知',
            value=settings.get('line_notify', {}).get('enabled', False),
        )

    if st.button('💾 儲存 LINE 設定'):
        settings['line_notify'] = {
            'enabled': line_enabled,
            'token': line_token,
        }
        save_settings(settings)
        st.success('LINE 設定已儲存！')

    # 測試 LINE 通知
    if line_token and st.button('🔔 測試 LINE 通知'):
        try:
            import requests

            headers = {'Authorization': f'Bearer {line_token}'}
            data = {'message': f'\n\n🧪 測試通知\n{"-" * 20}\n這是一則來自台股分析系統的測試通知。\n時間: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'}

            response = requests.post(
                'https://notify-api.line.me/api/notify',
                headers=headers,
                data=data,
                timeout=10,
            )

            if response.status_code == 200:
                st.success('✅ 測試通知發送成功！請檢查您的 LINE。')
            else:
                st.error(f'❌ 發送失敗: {response.text}')

        except Exception as e:
            show_error(e, title='發送通知失敗', suggestion='請確認 LINE Notify Token 是否正確')

with tab_email:
    st.markdown('''
設定 Email 通知以接收每日選股報告。

**Gmail 用戶注意：**
- 需要使用「應用程式密碼」而非您的 Gmail 密碼
- 前往 [Google 帳戶設定](https://myaccount.google.com/security) → 應用程式密碼
''')

    col1, col2 = st.columns(2)

    with col1:
        email_sender = st.text_input(
            '發送者 Email',
            value=settings.get('email', {}).get('sender', ''),
            placeholder='your.email@gmail.com',
        )

        email_password = st.text_input(
            'Email 密碼/應用程式密碼',
            value=settings.get('email', {}).get('password', ''),
            type='password',
        )

    with col2:
        email_recipients = st.text_area(
            '收件人 (每行一個)',
            value='\n'.join(settings.get('email', {}).get('recipients', [])),
            placeholder='recipient1@email.com\nrecipient2@email.com',
            height=100,
        )

        email_enabled = st.checkbox(
            '啟用 Email 通知',
            value=settings.get('email', {}).get('enabled', False),
        )

    if st.button('💾 儲存 Email 設定'):
        recipients = [r.strip() for r in email_recipients.split('\n') if r.strip()]
        settings['email'] = {
            'enabled': email_enabled,
            'sender': email_sender,
            'password': email_password,
            'recipients': recipients,
        }
        save_settings(settings)
        st.success('Email 設定已儲存！')

st.markdown('---')

# ========== 自動更新排程 ==========
st.markdown(create_section_header('自動更新排程', icon='🔄'), unsafe_allow_html=True)

st.markdown('''
設定每日自動更新股票數據並執行選股分析。

**macOS 用戶：** 系統會建立 launchd 排程任務
**其他系統：** 請手動設定 cron job
''')

col1, col2 = st.columns(2)

with col1:
    update_time = st.time_input(
        '每日更新時間',
        value=datetime.strptime(settings.get('auto_update', {}).get('time', '08:00'), '%H:%M').time(),
        help='建議設定在開盤前（9:00）或收盤後（14:00）'
    )

with col2:
    auto_update_enabled = st.checkbox(
        '啟用自動更新',
        value=settings.get('auto_update', {}).get('enabled', False),
    )

if st.button('💾 儲存排程設定'):
    settings['auto_update'] = {
        'enabled': auto_update_enabled,
        'time': update_time.strftime('%H:%M'),
    }
    save_settings(settings)

    if auto_update_enabled:
        # 建立 launchd plist 檔案
        plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.finlab.daily-update</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{Path(__file__).parent.parent.parent / 'scripts' / 'daily_update.py'}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{Path(__file__).parent.parent.parent}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{update_time.hour}</integer>
        <key>Minute</key>
        <integer>{update_time.minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{Path(__file__).parent.parent.parent / 'logs' / 'daily_update.log'}</string>
    <key>StandardErrorPath</key>
    <string>{Path(__file__).parent.parent.parent / 'logs' / 'daily_update_error.log'}</string>
</dict>
</plist>'''

        plist_path = Path.home() / 'Library' / 'LaunchAgents' / 'com.finlab.daily-update.plist'

        try:
            plist_path.parent.mkdir(parents=True, exist_ok=True)
            (Path(__file__).parent.parent.parent / 'logs').mkdir(exist_ok=True)

            with open(plist_path, 'w') as f:
                f.write(plist_content)

            # 載入排程
            os.system(f'launchctl unload {plist_path} 2>/dev/null')
            os.system(f'launchctl load {plist_path}')

            st.success(f'✅ 自動更新排程已設定！每日 {update_time.strftime("%H:%M")} 執行')
            st.info(f'排程檔案: {plist_path}')

        except Exception as e:
            show_error(e, title='設定排程失敗', suggestion='請確認系統權限設定')
    else:
        # 停用排程
        plist_path = Path.home() / 'Library' / 'LaunchAgents' / 'com.finlab.daily-update.plist'
        if plist_path.exists():
            os.system(f'launchctl unload {plist_path} 2>/dev/null')
            plist_path.unlink()
            st.info('自動更新排程已停用')

    st.success('排程設定已儲存！')

st.markdown('---')

# ========== 手動更新 ==========
st.markdown(create_section_header('手動更新數據', icon='📥'), unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    if st.button('📥 立即更新數據', use_container_width=True):
        with st.spinner('正在更新數據，請稍候...'):
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).parent.parent.parent / 'scripts' / 'daily_update.py'), '--update-only'],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode == 0:
                    st.success('✅ 數據更新完成！')
                    st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                else:
                    st.error('更新失敗')
                    st.code(result.stderr)

            except subprocess.TimeoutExpired:
                st.warning('更新超時，請稍後重試')
            except Exception as e:
                show_error(e, title='數據更新失敗', suggestion='請確認更新腳本是否存在')

with col2:
    if st.button('📊 立即執行選股', use_container_width=True):
        with st.spinner('正在執行選股分析...'):
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(Path(__file__).parent.parent.parent / 'scripts' / 'daily_update.py'), '--screen-only'],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                if result.returncode == 0:
                    st.success('✅ 選股完成！報告已儲存到 reports 資料夾')
                    st.code(result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout)
                else:
                    st.error('選股失敗')
                    st.code(result.stderr)

            except subprocess.TimeoutExpired:
                st.warning('執行超時')
            except Exception as e:
                show_error(e, title='選股執行失敗', suggestion='請確認選股腳本是否存在')

st.markdown('---')

# ========== 版本更新紀錄 ==========
st.markdown(create_section_header('版本更新紀錄', icon='📋'), unsafe_allow_html=True)

# 定義版本更新歷史
VERSION_HISTORY = [
    {
        'version': 'v2.1.0',
        'date': '2026-01-26',
        'type': '功能更新',
        'changes': [
            '🆕 新增「參數優化」頁面 - Grid Search 自動尋找最佳策略參數',
            '🆕 新增「風險分析」頁面 - VaR、CVaR、壓力測試、蒙地卡羅模擬',
            '🆕 新增「產業分析」頁面 - 產業輪動、風險報酬象限、個股詳細分析',
            '🆕 新增「投資組合」頁面 - 建立並追蹤投資組合績效',
            '🆕 新增「系統設定」頁面 - LINE 通知、Email、自動排程設定',
            '✨ 產業分析新增可點擊展開的個股詳細技術分析',
            '✨ 側邊欄新增更多頁面導航支援',
        ],
    },
    {
        'version': 'v2.0.0',
        'date': '2026-01-20',
        'type': '重大更新',
        'changes': [
            '🎉 全新 Streamlit 網頁介面',
            '🆕 新增「選股篩選」頁面 - 價值/成長/動能/複合策略',
            '🆕 新增「回測分析」頁面 - 完整回測引擎與績效報告',
            '🆕 新增「個股分析」頁面 - 技術面深度分析',
            '✨ 新增策略預設組合（保守/標準/積極）',
            '✨ 統一側邊欄樣式與數據摘要',
            '🔧 重構數據載入模組，支援快取機制',
            '🔧 新增輸入驗證與異常處理',
        ],
    },
    {
        'version': 'v1.5.0',
        'date': '2026-01-10',
        'type': '功能更新',
        'changes': [
            '🆕 新增 KDJ、BIAS、Williams %R 技術指標',
            '🆕 新增通知系統模組（LINE Notify / Email）',
            '✨ 改進回測引擎 - 新增最低手續費 20 元',
            '🔧 修復 Sharpe Ratio 除以零的問題',
            '🔧 優化 index 映射搜索效能',
        ],
    },
    {
        'version': 'v1.4.0',
        'date': '2025-12-25',
        'type': '功能更新',
        'changes': [
            '🆕 新增複合策略 - 結合多種選股因子',
            '✨ 回測支援停損停利設定',
            '✨ 新增交易成本計算（手續費折扣）',
            '🔧 改進數據對齊邏輯',
        ],
    },
    {
        'version': 'v1.3.0',
        'date': '2025-12-15',
        'type': '功能更新',
        'changes': [
            '🆕 新增動能策略 - 創新高突破',
            '🆕 新增 RSI、MACD 技術指標',
            '✨ 支援產業分類篩選',
            '🔧 優化記憶體使用',
        ],
    },
    {
        'version': 'v1.2.0',
        'date': '2025-12-01',
        'type': '功能更新',
        'changes': [
            '🆕 新增成長策略 - 營收成長選股',
            '✨ 支援月營收年增率篩選',
            '✨ 新增連續成長月數條件',
            '🔧 改進數據載入速度',
        ],
    },
    {
        'version': 'v1.1.0',
        'date': '2025-11-15',
        'type': '功能更新',
        'changes': [
            '🆕 新增價值策略 - 本益比/股價淨值比',
            '✨ 支援殖利率篩選',
            '🔧 修復已下市股票過濾問題',
        ],
    },
    {
        'version': 'v1.0.0',
        'date': '2025-11-01',
        'type': '首次發布',
        'changes': [
            '🎉 專案初始化',
            '🆕 基礎數據載入模組',
            '🆕 回測引擎核心功能',
            '🆕 基本選股框架',
        ],
    },
]

# 當前版本
CURRENT_VERSION = VERSION_HISTORY[0]['version']

# 根據類型設定標籤色（採用設計系統 COLORS，不再硬編 hex）
TYPE_COLORS = {
    '重大更新': COLORS['accent'],
    '功能更新': COLORS['info'],
    '首次發布': COLORS['success'],
    '修復更新': COLORS['warning'],
}

# 顯示當前版本（深色 token，取代手刻紫色漸層）
st.markdown(f'''
<div style="background:{COLORS['secondary']};
            border:1px solid {COLORS['border']};
            border-left:4px solid {COLORS['accent']};
            padding:20px; border-radius:12px; margin-bottom:20px;">
    <div style="color:{COLORS['text_primary']}; font-size:1.5rem; font-weight:bold;">
        📊 台股分析系統 {CURRENT_VERSION}
    </div>
    <div style="color:{COLORS['text_muted']}; font-size:0.9rem; margin-top:5px;">
        最後更新：{VERSION_HISTORY[0]['date']}
    </div>
</div>
''', unsafe_allow_html=True)

# 版本歷史總覽：以資料表呈現（取代 8 個過長 expander），詳細內容改用下方選擇器分頁
import pandas as pd

_history_df = pd.DataFrame([
    {
        '版本': ('🔥 ' if i == 0 else '') + release['version'],
        '發布日期': release['date'],
        '類型': release['type'],
        '更新項目': len(release['changes']),
    }
    for i, release in enumerate(VERSION_HISTORY)
])
render_data_table(_history_df, freeze_cols=1, numeric_cols=['更新項目'], height=320)

# 版本詳細內容（單一選擇器分頁，避免 expander 堆疊過長）
_version_labels = [f"{r['version']} - {r['date']}" for r in VERSION_HISTORY]
_selected_label = st.selectbox('查看版本詳細內容', _version_labels, index=0)
_selected = VERSION_HISTORY[_version_labels.index(_selected_label)]
_sel_is_current = (_selected['version'] == CURRENT_VERSION)
_type_color = TYPE_COLORS.get(_selected['type'], COLORS['flat'])

# 版本標籤
st.markdown(f'''
<span style="background:{_type_color}; color:#fff; padding:4px 12px;
             border-radius:15px; font-size:0.8rem; font-weight:500;">
    {_selected['type']}
</span>
''', unsafe_allow_html=True)

st.markdown('')

# 更新內容列表
for change in _selected['changes']:
    st.markdown(f"- {change}")

if _sel_is_current:
    st.info('📌 這是您目前使用的版本')

st.markdown('---')

# ========== 系統資訊 ==========
st.markdown(create_section_header('系統資訊', icon='ℹ️'), unsafe_allow_html=True)

from core.data_loader import get_data_summary

try:
    summary = get_data_summary()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric('活躍股票數', summary.get('total_stocks', '-'))

    with col2:
        st.metric('資料日期範圍', summary.get('date_range', '-').split(' ~ ')[1] if '~' in summary.get('date_range', '') else '-')

    with col3:
        st.metric('總交易日', summary.get('total_days', '-'))

    with col4:
        st.metric('已下市股票', summary.get('delisted_stocks', '-'))

except Exception as e:
    show_error(e, title='無法載入系統資訊', suggestion='請確認資料檔案是否存在')

# 顯示設定檔位置
st.markdown('**設定檔位置：**')
st.code(str(SETTINGS_FILE))

st.markdown('**數據資料夾：**')
st.code(str(DATA_DIR))

# ========== 說明 ==========
with st.expander('📖 使用說明'):
    st.markdown('''
    ### LINE Notify 設定

    1. 前往 [LINE Notify 官網](https://notify-bot.line.me/)
    2. 登入您的 LINE 帳號
    3. 點擊「發行權杖」
    4. 選擇通知接收對象（個人或群組）
    5. 複製權杖並貼到上方欄位

    ### Email 設定

    **Gmail 用戶：**
    1. 前往 [Google 帳戶安全性設定](https://myaccount.google.com/security)
    2. 啟用兩步驟驗證
    3. 建立「應用程式密碼」
    4. 使用應用程式密碼而非 Gmail 密碼

    ### 自動更新排程

    - macOS 使用 launchd 排程
    - 建議時間：開盤前 08:00 或收盤後 14:30
    - 排程任務會自動下載最新數據並執行選股
    ''')

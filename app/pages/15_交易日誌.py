"""
交易日誌頁面 - 記錄交易決策與心得
"""
import streamlit as st
import pandas as pd
import json
import uuid
import sys
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error
from app.components.portfolio_utils import (
    get_portfolio_names, load_portfolios, save_portfolios
)

st.set_page_config(page_title='交易日誌', page_icon='📝', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='journal')

render_page_header('交易日誌', icon='📝')

# 日誌檔案路徑
JOURNAL_FILE = Path(__file__).parent.parent.parent / 'data' / 'trading_journal.json'
JOURNAL_FILE.parent.mkdir(exist_ok=True)

def load_journal():
    if JOURNAL_FILE.exists():
        with open(JOURNAL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'entries': []}

def save_journal(journal_data):
    with open(JOURNAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(journal_data, f, ensure_ascii=False, indent=2, default=str)

# 載入數據
@st.cache_data(ttl=CACHE_TTL['daily'])
def load_stock_info():
    loader = get_loader()
    return loader.get_stock_info()

try:
    stock_info = load_stock_info()
    active_stocks = get_active_stocks()
except Exception as e:
    show_error(e, title='載入數據失敗', suggestion='請確認 FinLab API 設定是否正確')
    stock_info = pd.DataFrame()
    active_stocks = []

# 股票選項
stock_options = [''] + [f"{row['stock_id']} {row['name']}"
                        for _, row in stock_info.iterrows()
                        if row['stock_id'] in active_stocks]

# 載入日誌
journal_data = load_journal()
entries = journal_data.get('entries', [])

# Tab 選擇
tab1, tab2, tab3 = st.tabs(['📝 新增日誌', '📋 日誌列表', '📊 統計分析'])

# ========== 新增日誌 ==========
with tab1:
    st.markdown('### 新增交易日誌')

    col1, col2 = st.columns(2)

    with col1:
        entry_date = st.date_input('日期', value=date.today())

        entry_type = st.selectbox(
            '交易類型',
            ['買入', '賣出', '加碼', '減碼', '觀察', '心得']
        )

        entry_stock = st.selectbox(
            '相關股票 (選填)',
            stock_options
        )

        tags = st.multiselect(
            '標籤',
            ['技術分析', '基本面', '消息面', '情緒', '風控', '策略', '檢討', '計畫'],
        )

    with col2:
        entry_title = st.text_input('標題', placeholder='例如：2330 突破壓力位買入')

        entry_price = st.number_input('價格 (選填)', 0.0, 10000.0, 0.0, 1.0)

        entry_shares = st.number_input('股數 (選填)', 0, 100000, 0, 100)

        entry_reason = st.text_area(
            '交易原因/觀察重點',
            placeholder='為什麼進行這筆交易？或者觀察到什麼重要訊號？',
            height=100
        )

    entry_content = st.text_area(
        '詳細內容/心得',
        placeholder='記錄更多細節、市場觀察、心理狀態等...',
        height=150
    )

    entry_lesson = st.text_area(
        '經驗教訓 (選填)',
        placeholder='這次交易學到了什麼？下次應該如何改進？',
        height=80
    )

    # ========== 同步投資組合選項 ==========
    sync_to_portfolio = False
    sync_portfolio_name = None

    is_trade_type = entry_type in ['買入', '賣出', '加碼', '減碼']
    entry_stock_id = entry_stock.split(' ')[0] if entry_stock else None

    if is_trade_type and entry_stock_id:
        portfolio_names = get_portfolio_names()
        if portfolio_names:
            st.markdown('---')
            sync_col1, sync_col2 = st.columns([1, 2])
            with sync_col1:
                sync_to_portfolio = st.checkbox(
                    '同步更新投資組合',
                    value=False,
                    help='儲存日誌時同時更新對應投資組合的持股'
                )
            if sync_to_portfolio:
                with sync_col2:
                    sync_portfolio_name = st.selectbox(
                        '選擇要同步的投資組合',
                        portfolio_names,
                        key='journal_sync_portfolio'
                    )

    if st.button('💾 儲存日誌', type='primary', use_container_width=True):
        if entry_title:
            new_entry = {
                'id': str(uuid.uuid4())[:8],
                'date': entry_date.isoformat(),
                'type': entry_type,
                'title': entry_title,
                'stock': entry_stock.split(' ')[0] if entry_stock else None,
                'price': entry_price if entry_price > 0 else None,
                'shares': entry_shares if entry_shares > 0 else None,
                'reason': entry_reason,
                'content': entry_content,
                'lesson': entry_lesson,
                'tags': tags,
                'created_at': datetime.now().isoformat(),
            }

            journal_data['entries'].insert(0, new_entry)  # 新的放最前面
            save_journal(journal_data)
            st.success('日誌已儲存！')

            # ========== 同步更新投資組合 ==========
            if sync_to_portfolio and sync_portfolio_name and entry_stock_id:
                try:
                    portfolios = load_portfolios()
                    if sync_portfolio_name not in portfolios:
                        st.warning(f'找不到投資組合「{sync_portfolio_name}」，同步失敗。')
                    else:
                        holdings = portfolios[sync_portfolio_name]['holdings']
                        cost = float(entry_price) if entry_price > 0 else 0.0
                        qty = int(entry_shares) if entry_shares > 0 else 0

                        if entry_type in ['買入', '加碼'] and cost <= 0 and qty > 0:
                            st.warning('同步失敗：買入 / 加碼時價格必須大於 0，請填入正確的成交價格。')
                        elif entry_type in ['買入', '加碼']:
                            # 買入 / 加碼：新增或增加持股
                            existing = next((h for h in holdings if h['stock_id'] == entry_stock_id), None)
                            if existing:
                                # 加碼：更新加權平均成本與股數
                                old_shares = existing['shares']
                                old_cost = existing['cost_price']
                                new_shares = old_shares + qty
                                if new_shares > 0:
                                    existing['cost_price'] = round(
                                        (old_cost * old_shares + cost * qty) / new_shares, 2
                                    )
                                existing['shares'] = new_shares
                                st.success(f'✅ 已更新「{sync_portfolio_name}」中 {entry_stock_id} 的持股（加碼至 {new_shares} 股）')
                            else:
                                holdings.append({
                                    'stock_id': entry_stock_id,
                                    'shares': qty,
                                    'cost_price': cost,
                                    'buy_date': entry_date.isoformat(),
                                })
                                st.success(f'✅ 已將 {entry_stock_id}（{qty} 股）加入「{sync_portfolio_name}」')

                        elif entry_type in ['賣出', '減碼']:
                            # 賣出 / 減碼：減少持股
                            existing = next((h for h in holdings if h['stock_id'] == entry_stock_id), None)
                            if existing:
                                if qty >= existing['shares']:
                                    holdings.remove(existing)
                                    st.success(f'✅ 已從「{sync_portfolio_name}」移除 {entry_stock_id}（全部出清）')
                                else:
                                    existing['shares'] -= qty
                                    st.success(f'✅ 已減少「{sync_portfolio_name}」中 {entry_stock_id} 的持股（剩 {existing["shares"]} 股）')
                            else:
                                st.warning(f'「{sync_portfolio_name}」中找不到 {entry_stock_id}，無法執行減碼。')

                        save_portfolios(portfolios)
                except Exception as e:
                    st.error(f'同步投資組合失敗：{e}')

            st.rerun()
        else:
            st.warning('請輸入標題')

# ========== 日誌列表 ==========
with tab2:
    st.markdown('### 日誌列表')

    # 篩選器
    filter_col1, filter_col2, filter_col3 = st.columns(3)

    with filter_col1:
        filter_type = st.selectbox('交易類型', ['全部', '買入', '賣出', '加碼', '減碼', '觀察', '心得'])

    with filter_col2:
        filter_tag = st.selectbox('標籤', ['全部'] + ['技術分析', '基本面', '消息面', '情緒', '風控', '策略', '檢討', '計畫'])

    with filter_col3:
        search_text = st.text_input('搜尋', placeholder='關鍵字搜尋')

    # 篩選日誌
    filtered_entries = entries

    if filter_type != '全部':
        filtered_entries = [e for e in filtered_entries if e.get('type') == filter_type]

    if filter_tag != '全部':
        filtered_entries = [e for e in filtered_entries if filter_tag in e.get('tags', [])]

    if search_text:
        search_lower = search_text.lower()
        filtered_entries = [
            e for e in filtered_entries
            if search_lower in e.get('title', '').lower()
            or search_lower in e.get('content', '').lower()
            or search_lower in e.get('reason', '').lower()
        ]

    st.caption(f'共 {len(filtered_entries)} 筆日誌')

    if filtered_entries:
        for entry in filtered_entries[:20]:  # 最多顯示 20 筆
            with st.expander(f"**{entry['date']}** | {entry['type']} | {entry['title']}"):
                col1, col2 = st.columns([3, 1])

                with col1:
                    # 股票資訊
                    if entry.get('stock'):
                        stock_id = entry['stock']
                        info = stock_info[stock_info['stock_id'] == stock_id]
                        name = info['name'].values[0] if len(info) > 0 else ''
                        st.markdown(f"**股票：** {stock_id} {name}")

                    if entry.get('price'):
                        st.markdown(f"**價格：** {entry['price']:.2f}")

                    if entry.get('shares'):
                        st.markdown(f"**股數：** {entry['shares']}")

                    # 標籤
                    if entry.get('tags'):
                        tags_str = ' '.join([f'`{t}`' for t in entry['tags']])
                        st.markdown(f"**標籤：** {tags_str}")

                with col2:
                    # 刪除按鈕
                    if st.button('🗑️ 刪除', key=f"delete_{entry['id']}"):
                        journal_data['entries'] = [e for e in journal_data['entries'] if e['id'] != entry['id']]
                        save_journal(journal_data)
                        st.rerun()

                st.markdown('---')

                # 交易原因
                if entry.get('reason'):
                    st.markdown('**交易原因：**')
                    st.markdown(entry['reason'])

                # 詳細內容
                if entry.get('content'):
                    st.markdown('**詳細內容：**')
                    st.markdown(entry['content'])

                # 經驗教訓
                if entry.get('lesson'):
                    st.markdown('**經驗教訓：**')
                    st.info(entry['lesson'])

    else:
        show_empty_state('沒有符合條件的日誌', icon='📝', suggestion='請嘗試調整篩選條件，或新增您的第一筆交易日誌')

# ========== 統計分析 ==========
with tab3:
    st.markdown('### 統計分析')

    if entries:
        # 交易類型統計
        type_counts = {}
        tag_counts = {}
        monthly_counts = {}

        for entry in entries:
            # 類型統計
            entry_type = entry.get('type', '其他')
            type_counts[entry_type] = type_counts.get(entry_type, 0) + 1

            # 標籤統計
            for tag in entry.get('tags', []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

            # 月份統計
            entry_date = entry.get('date', '')[:7]  # YYYY-MM
            monthly_counts[entry_date] = monthly_counts.get(entry_date, 0) + 1

        col1, col2 = st.columns(2)

        with col1:
            st.markdown('#### 交易類型分布')
            type_df = pd.DataFrame({
                '類型': list(type_counts.keys()),
                '次數': list(type_counts.values())
            })
            st.bar_chart(type_df.set_index('類型'))

        with col2:
            st.markdown('#### 標籤使用頻率')
            if tag_counts:
                tag_df = pd.DataFrame({
                    '標籤': list(tag_counts.keys()),
                    '次數': list(tag_counts.values())
                }).sort_values('次數', ascending=False)
                st.bar_chart(tag_df.set_index('標籤'))

        # 月度趨勢
        st.markdown('#### 月度日誌數量')
        if monthly_counts:
            monthly_df = pd.DataFrame({
                '月份': list(monthly_counts.keys()),
                '日誌數': list(monthly_counts.values())
            }).sort_values('月份')
            st.line_chart(monthly_df.set_index('月份'))

        # 統計摘要
        st.markdown('#### 統計摘要')

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric('總日誌數', len(entries))

        with col2:
            buy_count = type_counts.get('買入', 0) + type_counts.get('加碼', 0)
            st.metric('買入/加碼次數', buy_count)

        with col3:
            sell_count = type_counts.get('賣出', 0) + type_counts.get('減碼', 0)
            st.metric('賣出/減碼次數', sell_count)

        with col4:
            lesson_count = sum(1 for e in entries if e.get('lesson'))
            st.metric('有記錄教訓', lesson_count)

    else:
        show_empty_state('尚無日誌數據', icon='📝', suggestion='開始記錄您的交易，累積寶貴的交易經驗')

# ========== 匯出功能 ==========
st.markdown('---')
st.markdown('### 📤 匯出日誌')

col1, col2 = st.columns(2)

with col1:
    if entries:
        export_df = pd.DataFrame([
            {
                '日期': e.get('date'),
                '類型': e.get('type'),
                '標題': e.get('title'),
                '股票': e.get('stock'),
                '價格': e.get('price'),
                '股數': e.get('shares'),
                '原因': e.get('reason'),
                '內容': e.get('content'),
                '教訓': e.get('lesson'),
                '標籤': ', '.join(e.get('tags', [])),
            }
            for e in entries
        ])

        csv = export_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            '📥 下載 CSV',
            csv,
            f'trading_journal_{datetime.now().strftime("%Y%m%d")}.csv',
            'text/csv',
            use_container_width=True
        )

with col2:
    if entries:
        json_str = json.dumps(journal_data, ensure_ascii=False, indent=2)
        st.download_button(
            '📥 下載 JSON 備份',
            json_str,
            f'trading_journal_backup_{datetime.now().strftime("%Y%m%d")}.json',
            'application/json',
            use_container_width=True
        )

# ========== 說明 ==========
with st.expander('📖 使用說明'):
    st.markdown('''
    ### 為什麼要記錄交易日誌？

    1. **追蹤決策過程**：記錄買賣原因，避免事後忘記
    2. **情緒管理**：記錄交易時的心理狀態
    3. **經驗累積**：從成功和失敗中學習
    4. **改進策略**：發現交易模式的優缺點

    ### 建議記錄內容

    - **交易原因**：為什麼做這筆交易？技術面、基本面還是消息？
    - **預期目標**：預期的獲利目標和停損點
    - **實際結果**：最終結果是否符合預期
    - **經驗教訓**：學到了什麼？下次如何改進？

    ### 標籤使用建議

    - `技術分析`：基於圖表、指標的交易
    - `基本面`：基於財報、估值的交易
    - `消息面`：基於新聞、公告的交易
    - `情緒`：記錄交易時的心理狀態
    - `風控`：與風險控制相關
    - `檢討`：交易後的反思
    ''')

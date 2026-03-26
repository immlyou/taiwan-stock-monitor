"""
自選股清單管理
"""
import streamlit as st
import pandas as pd
import json
import sys
from pathlib import Path
from datetime import datetime
import io


from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.session_manager import (
    init_session_state, get_state, set_state, StateKeys,
    navigate_to_stock_analysis
)
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error

st.set_page_config(page_title='自選股', page_icon='⭐', layout='wide')

# 檢查登入狀態
if not st.session_state.get("authenticated", False):
    st.warning("⚠️ 請先登入")
    st.markdown("[👉 點此前往登入頁面](../)")
    st.stop()

# 初始化 Session State
init_session_state()

# 渲染側邊欄
render_sidebar_mini(current_page='watchlist')

render_page_header('自選股', icon='⭐')

# 自選股檔案路徑
WATCHLIST_FILE = Path(__file__).parent.parent.parent / 'data' / 'watchlists.json'
WATCHLIST_FILE.parent.mkdir(exist_ok=True)

def load_watchlists():
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_watchlists(watchlists):
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(watchlists, f, ensure_ascii=False, indent=2, default=str)

# 載入數據
@st.cache_data(ttl=CACHE_TTL['daily'], show_spinner='載入數據中...')
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'volume': loader.get('volume'),
        'stock_info': loader.get_stock_info(),
    }

try:
    data = load_data()
    close = data['close']
    volume = data['volume']
    stock_info = data['stock_info']
    active_stocks = get_active_stocks()
except Exception as e:
    show_error(e, title='載入數據失敗', suggestion='請檢查資料來源是否正常，或嘗試重新整理頁面')
    st.stop()

# 股票選項
stock_options = {f"{row['stock_id']} {row['name']}": row['stock_id']
                 for _, row in stock_info.iterrows()
                 if row['stock_id'] in active_stocks}

# 載入自選股
watchlists = load_watchlists()

# ========== 側邊欄 - 清單管理 ==========
with st.sidebar:
    st.markdown('### 📁 清單管理')

    # 選擇清單
    watchlist_names = list(watchlists.keys())

    if watchlist_names:
        selected_watchlist = st.selectbox(
            '選擇清單',
            ['-- 新建清單 --'] + watchlist_names,
        )
    else:
        selected_watchlist = '-- 新建清單 --'

    # 新建清單
    if selected_watchlist == '-- 新建清單 --':
        new_name = st.text_input('清單名稱', placeholder='例如：觀察中', key='new_watchlist_name')

        if st.button('➕ 建立清單', use_container_width=True, key='create_watchlist_btn'):
            if new_name and new_name not in watchlists:
                watchlists[new_name] = {
                    'created_at': datetime.now().isoformat(),
                    'stocks': [],
                    'notes': {},
                }
                save_watchlists(watchlists)
                st.success(f'已建立清單: {new_name}')
                st.rerun()
            elif new_name in watchlists:
                st.error('此名稱已存在')
            else:
                st.error('請輸入名稱')

    # 清單操作
    if selected_watchlist != '-- 新建清單 --':
        st.markdown('---')

        # 重新命名
        new_list_name = st.text_input('重新命名', value=selected_watchlist, key='rename_watchlist')
        if new_list_name != selected_watchlist and st.button('✏️ 確認重新命名', key='rename_btn'):
            if new_list_name and new_list_name not in watchlists:
                watchlists[new_list_name] = watchlists.pop(selected_watchlist)
                save_watchlists(watchlists)
                st.rerun()

        st.markdown('---')

        # 刪除清單
        if st.button('🗑️ 刪除此清單', use_container_width=True):
            del watchlists[selected_watchlist]
            save_watchlists(watchlists)
            st.success('已刪除')
            st.rerun()

# ========== 主內容區 ==========
if selected_watchlist != '-- 新建清單 --' and selected_watchlist in watchlists:
    watchlist = watchlists[selected_watchlist]
    stocks = watchlist.get('stocks', [])
    notes = watchlist.get('notes', {})

    st.subheader(f'⭐ {selected_watchlist}')
    st.caption(f"建立於: {watchlist.get('created_at', '未知')[:10]} | 共 {len(stocks)} 檔股票")

    # ========== 新增股票 ==========
    st.markdown('### ➕ 新增股票')

    col1, col2 = st.columns([4, 1])

    with col1:
        # 搜尋股票
        search_stock = st.selectbox(
            '搜尋股票',
            list(stock_options.keys()),
            key='add_stock_search'
        )

    with col2:
        st.markdown('<br>', unsafe_allow_html=True)
        if st.button('➕ 新增', use_container_width=True):
            stock_id = stock_options[search_stock]
            if stock_id not in stocks:
                watchlists[selected_watchlist]['stocks'].append(stock_id)
                save_watchlists(watchlists)
                st.success(f'已新增 {stock_id}')
                st.rerun()
            else:
                st.warning('此股票已在清單中')

    st.markdown('---')

    # ========== 股票列表 ==========
    if stocks:
        st.markdown('### 📋 自選股列表')

        # 顯示模式選擇
        view_mode = st.radio('顯示模式', ['表格', '卡片'], horizontal=True)

        # 取得股票資訊
        watchlist_data = []

        for stock_id in stocks:
            info = stock_info[stock_info['stock_id'] == stock_id]
            name = info['name'].values[0] if len(info) > 0 else ''
            category = info['category'].values[0] if len(info) > 0 else ''

            # 取得價格資訊
            if stock_id in close.columns:
                stock_close = close[stock_id].dropna()
                latest_price = stock_close.iloc[-1]
                prev_price = stock_close.iloc[-2] if len(stock_close) > 1 else latest_price
                daily_change = (latest_price / prev_price - 1) * 100

                week_ago = stock_close.iloc[-5] if len(stock_close) > 5 else latest_price
                week_change = (latest_price / week_ago - 1) * 100

                month_ago = stock_close.iloc[-20] if len(stock_close) > 20 else latest_price
                month_change = (latest_price / month_ago - 1) * 100
            else:
                latest_price = 0
                daily_change = 0
                week_change = 0
                month_change = 0

            # 取得成交量
            if stock_id in volume.columns:
                stock_volume = volume[stock_id].dropna()
                latest_volume = stock_volume.iloc[-1] if len(stock_volume) > 0 else 0
            else:
                latest_volume = 0

            watchlist_data.append({
                'stock_id': stock_id,
                '代號': stock_id,
                '名稱': name,
                '產業': category,
                '現價': latest_price,
                '日漲跌': daily_change,
                '週漲跌': week_change,
                '月漲跌': month_change,
                '成交量': latest_volume,
                '備註': notes.get(stock_id, ''),
            })

        watchlist_df = pd.DataFrame(watchlist_data)

        if view_mode == '表格':
            # 表格顯示
            display_df = watchlist_df[['代號', '名稱', '產業', '現價', '日漲跌', '週漲跌', '月漲跌']].copy()
            display_df['現價'] = display_df['現價'].apply(lambda x: f'{x:.2f}')
            display_df['日漲跌'] = display_df['日漲跌'].apply(lambda x: f'{x:+.2f}%')
            display_df['週漲跌'] = display_df['週漲跌'].apply(lambda x: f'{x:+.2f}%')
            display_df['月漲跌'] = display_df['月漲跌'].apply(lambda x: f'{x:+.2f}%')

            st.dataframe(display_df, use_container_width=True, hide_index=True)

        else:
            # 卡片顯示
            cols = st.columns(3)

            for i, row in watchlist_df.iterrows():
                with cols[i % 3]:
                    color = '🟢' if row['日漲跌'] >= 0 else '🔴'

                    st.markdown(f'''
                    <div style="border: 1px solid #ddd; border-radius: 10px; padding: 15px; margin-bottom: 10px;">
                        <h4>{row['代號']} {row['名稱']}</h4>
                        <p style="color: gray; font-size: 0.9em;">{row['產業']}</p>
                        <p style="font-size: 1.5em; font-weight: bold;">{row['現價']:.2f}</p>
                        <p>{color} 日: {row['日漲跌']:+.2f}% | 週: {row['週漲跌']:+.2f}%</p>
                    </div>
                    ''', unsafe_allow_html=True)

        st.markdown('---')

        # ========== 備註管理 ==========
        st.markdown('### 📝 備註管理')

        note_stock = st.selectbox('選擇股票', [f"{s} - {stock_info[stock_info['stock_id']==s]['name'].values[0] if len(stock_info[stock_info['stock_id']==s]) > 0 else ''}" for s in stocks])

        if note_stock:
            note_stock_id = note_stock.split(' - ')[0]
            current_note = notes.get(note_stock_id, '')

            new_note = st.text_area('備註內容', value=current_note, placeholder='例如：等待回檔到 500 元')

            if st.button('💾 儲存備註'):
                if 'notes' not in watchlists[selected_watchlist]:
                    watchlists[selected_watchlist]['notes'] = {}
                watchlists[selected_watchlist]['notes'][note_stock_id] = new_note
                save_watchlists(watchlists)
                st.success('備註已儲存')

        st.markdown('---')

        # ========== 股票操作 ==========
        st.markdown('### ⚙️ 股票操作')

        col1, col2 = st.columns(2)

        with col1:
            remove_stock = st.selectbox(
                '移除股票',
                [f"{s} - {stock_info[stock_info['stock_id']==s]['name'].values[0] if len(stock_info[stock_info['stock_id']==s]) > 0 else ''}" for s in stocks],
                key='remove_stock'
            )

            if st.button('🗑️ 移除選中股票'):
                stock_id_to_remove = remove_stock.split(' - ')[0]
                watchlists[selected_watchlist]['stocks'].remove(stock_id_to_remove)
                if stock_id_to_remove in watchlists[selected_watchlist].get('notes', {}):
                    del watchlists[selected_watchlist]['notes'][stock_id_to_remove]
                save_watchlists(watchlists)
                st.rerun()

        with col2:
            st.markdown('**快速操作**')

            if st.button('📊 分析選中股票'):
                stock_id_to_analyze = remove_stock.split(' - ')[0]
                navigate_to_stock_analysis(stock_id_to_analyze)
                st.switch_page('pages/3_個股分析.py')

        st.markdown('---')

        # ========== 匯出/匯入 ==========
        st.markdown('### 📤 匯出/匯入')

        col1, col2 = st.columns(2)

        with col1:
            st.markdown('**匯出清單**')

            export_df = watchlist_df[['代號', '名稱', '產業', '現價', '備註']]
            csv = export_df.to_csv(index=False).encode('utf-8-sig')

            st.download_button(
                label='📥 下載 CSV',
                data=csv,
                file_name=f'watchlist_{selected_watchlist}_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv',
                use_container_width=True
            )

        with col2:
            st.markdown('**匯入清單**')

            uploaded_file = st.file_uploader('上傳 CSV', type=['csv'])

            if uploaded_file is not None:
                try:
                    import_df = pd.read_csv(uploaded_file)

                    if '代號' in import_df.columns:
                        import_stocks = import_df['代號'].astype(str).tolist()
                        valid_stocks = [s for s in import_stocks if s in active_stocks]

                        if valid_stocks:
                            if st.button('✅ 確認匯入'):
                                for stock_id in valid_stocks:
                                    if stock_id not in stocks:
                                        watchlists[selected_watchlist]['stocks'].append(stock_id)
                                save_watchlists(watchlists)
                                st.success(f'已匯入 {len(valid_stocks)} 檔股票')
                                st.rerun()
                        else:
                            st.warning('找不到有效的股票代號')
                    else:
                        st.error('CSV 必須包含「代號」欄位')
                except Exception as e:
                    show_error(e, title='匯入失敗', suggestion='請確認 CSV 檔案格式是否正確')

    else:
        show_empty_state('此清單尚無股票', icon='⭐', suggestion='請在上方搜尋並新增股票')

else:
    show_empty_state('尚未選擇自選股清單', icon='⭐', suggestion='請在側邊欄選擇或建立自選股清單')

# ========== 說明 ==========
with st.expander('📖 使用說明'):
    st.markdown('''
    ### 如何使用自選股清單

    1. **建立清單**：在側邊欄輸入名稱並點擊建立
    2. **新增股票**：搜尋股票後點擊新增
    3. **添加備註**：為每檔股票記錄觀察重點
    4. **追蹤行情**：查看即時漲跌、週/月報酬
    5. **匯出/匯入**：備份或分享您的自選股清單

    ### 功能特色

    - 支援多個清單（如：短線觀察、長期持有）
    - 卡片/表格兩種顯示模式
    - 可匯出 CSV 備份
    - 可添加個股備註
    ''')

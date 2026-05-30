# -*- coding: utf-8 -*-
"""
頁首元件 - 統一的頁面標題列（含重新整理按鈕與資料日期）
"""
import streamlit as st
from datetime import datetime
from app.components.theme import COLORS


def _is_market_open() -> bool:
    """是否為台股盤中時段（平日 09:00–13:30）"""
    now = datetime.now()
    return (now.weekday() < 5
            and datetime.strptime('09:00', '%H:%M').time() <= now.time()
            <= datetime.strptime('13:30', '%H:%M').time())


def render_global_ticker_bar(active_stock: str = None):
    """全域行情列 + 命令列搜尋（置於各頁標題上方，提供全站市場脈絡與快速切換）。

    顯示：加權指數＋漲跌、盤中/盤後 badge、資料日期、股票數，
    右側輸入股票代號 Enter 即跳轉個股分析（取代逐頁 selectbox 挑選）。
    """
    # 取大盤摘要（沿用既有快取，不額外加重）
    taiex = taiex_chg = None
    latest_date = '-'
    total_stocks = None
    try:
        from core.data_loader import get_data_summary
        summary = get_data_summary()
        if 'error' not in summary:
            taiex = summary.get('taiex_index')
            taiex_chg = summary.get('taiex_change')
            latest_date = summary.get('latest_date', '-')
            total_stocks = summary.get('total_stocks')
    except Exception:
        pass

    is_open = _is_market_open()
    session_badge = ('🟢 盤中', COLORS['down_strong']) if is_open else ('🌙 盤後', COLORS['text_muted'])

    if taiex:
        up = taiex_chg is not None and taiex_chg >= 0
        chg_color = COLORS['up'] if up else COLORS['down']
        arrow = '▲' if up else '▼'
        taiex_html = (f'<span style="color:{COLORS["text_muted"]};font-size:0.72rem">加權</span> '
                      f'<span class="num-mono" style="color:{COLORS["text_primary"]};font-weight:700;font-size:1.05rem">{taiex:,.0f}</span> '
                      f'<span class="num-mono" style="color:{chg_color};font-weight:600;font-size:0.85rem">{arrow} {abs(taiex_chg or 0):.2f}%</span>')
    else:
        taiex_html = f'<span style="color:{COLORS["text_muted"]};font-size:0.8rem">加權指數載入中…</span>'

    stocks_html = (f'<span style="color:{COLORS["text_muted"]};font-size:0.72rem">上市 {total_stocks:,} 檔</span>'
                   if total_stocks else '')
    active_html = (f'<span style="color:{COLORS["accent"]};font-size:0.78rem;font-weight:600">● {active_stock}</span>'
                   if active_stock else '')

    bar_col, search_col = st.columns([3.2, 1])
    with bar_col:
        st.markdown(f'''
        <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;
                    background:{COLORS['secondary']};border:1px solid {COLORS['border']};
                    border-radius:10px;padding:8px 16px;margin-bottom:10px">
            {taiex_html}
            <span style="color:{session_badge[1]};font-size:0.78rem;font-weight:600">{session_badge[0]}</span>
            <span style="color:{COLORS['text_muted']};font-size:0.72rem">📅 {latest_date}</span>
            {stocks_html}
            {active_html}
        </div>
        ''', unsafe_allow_html=True)

    with search_col:
        with st.form(key='_global_stock_search', clear_on_submit=True, border=False):
            c1, c2 = st.columns([3, 1])
            with c1:
                code = st.text_input('搜尋', placeholder='代號 ↵', label_visibility='collapsed',
                                     key='_global_search_input')
            with c2:
                submitted = st.form_submit_button('🔍', use_container_width=True)
        if submitted and code and code.strip():
            from app.components.session_manager import navigate_to_stock_analysis
            navigate_to_stock_analysis(code.strip())
            try:
                st.switch_page('pages/3_個股分析.py')
            except Exception:
                st.rerun()


def _get_latest_data_date() -> str:
    """嘗試從 DataLoader 取最新資料日期，失敗時 fallback 到 now()"""
    try:
        from core.data_loader import get_data_summary
        summary = get_data_summary()
        date_range = summary.get('date_range', '')
        if '~' in date_range:
            return date_range.split(' ~ ')[1].strip()
    except Exception:
        pass
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def render_page_header(title: str, icon: str = "", show_refresh: bool = True, show_date: bool = True):
    """
    渲染統一頁首

    Parameters:
    -----------
    title : str
        頁面標題
    icon : str
        標題前圖示
    show_refresh : bool
        是否顯示重新整理按鈕
    show_date : bool
        是否顯示資料日期
    """
    cols = st.columns([6, 2, 1] if show_refresh else [8, 2])

    with cols[0]:
        display_title = f"{icon} {title}" if icon else title
        st.markdown(f'''
        <h1 style="
            color:{COLORS['text_primary']};
            font-size:1.8rem;
            font-weight:700;
            margin:0;
            padding-bottom:0.5rem;
            border-bottom:3px solid {COLORS['accent']};
        ">{display_title}</h1>
        ''', unsafe_allow_html=True)

    with cols[1]:
        if show_date:
            display_date = _get_latest_data_date()
            st.markdown(f'''
            <div style="
                text-align:right;
                padding-top:0.8rem;
                color:{COLORS['text_muted']};
                font-size:0.8rem;
            ">{display_date}</div>
            ''', unsafe_allow_html=True)

    if show_refresh and len(cols) > 2:
        with cols[2]:
            if st.button("🔄", help="重新整理", key=f"refresh_{title}"):
                st.cache_data.clear()
                st.rerun()

    st.markdown("<div style='margin-bottom:1rem;'></div>", unsafe_allow_html=True)

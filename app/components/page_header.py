# -*- coding: utf-8 -*-
"""
頁首元件 - 統一的頁面標題列（含重新整理按鈕與資料日期）
"""
import streamlit as st
from datetime import datetime
from app.components.theme import COLORS


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

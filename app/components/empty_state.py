# -*- coding: utf-8 -*-
"""
空狀態元件 - 統一的無資料/空白頁面展示
"""
import streamlit as st
from app.components.theme import COLORS


def show_empty_state(message: str, icon: str = "📭", suggestion: str = None,
                     action_label: str = None, action_page: str = None,
                     action_key: str = None):
    """
    顯示統一風格的空狀態提示（可選 CTA 按鈕，引導使用者下一步）

    Parameters:
    -----------
    message : str
        主要提示訊息
    icon : str
        顯示的圖示
    suggestion : str, optional
        建議操作說明
    action_label : str, optional
        CTA 按鈕文字（提供時顯示按鈕）
    action_page : str, optional
        點擊 CTA 要切換的頁面路徑（如 'pages/1_選股篩選.py'）
    action_key : str, optional
        按鈕 key（同頁多個空狀態時避免衝突）
    """
    suggestion_html = ''
    if suggestion:
        suggestion_html = f'<p style="color:{COLORS["text_muted"]};font-size:0.85rem;margin-top:8px;">{suggestion}</p>'

    st.markdown(f'''
    <div style="
        text-align:center;
        padding:3rem 2rem;
        background:{COLORS['secondary']};
        border:1px solid {COLORS['border']};
        border-radius:12px;
        margin:1rem 0;
    ">
        <div style="font-size:2.5rem;margin-bottom:0.5rem;">{icon}</div>
        <p style="color:{COLORS['text_secondary']};font-size:1rem;margin:0;">{message}</p>
        {suggestion_html}
    </div>
    ''', unsafe_allow_html=True)

    # 置中 CTA 按鈕
    if action_label:
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            clicked = st.button(action_label, use_container_width=True, type='primary',
                                key=action_key or f'empty_cta_{action_label}')
            if clicked and action_page:
                st.switch_page(action_page)
            return clicked
    return False


def show_skeleton(rows: int = 3, height: int = 28):
    """顯示骨架載入佔位（資料載入中時取代空白，降低跳動感）。"""
    bars = ''.join(
        f'<div style="height:{height}px;background:linear-gradient(90deg,'
        f'{COLORS["secondary"]} 25%, {COLORS["border"]} 50%, {COLORS["secondary"]} 75%);'
        f'background-size:200% 100%;border-radius:8px;margin-bottom:10px;'
        f'animation:skeleton-shimmer 1.4s ease-in-out infinite"></div>'
        for _ in range(max(1, rows))
    )
    st.markdown(f'''
    <style>
    @keyframes skeleton-shimmer {{
        0% {{ background-position: 200% 0; }}
        100% {{ background-position: -200% 0; }}
    }}
    </style>
    <div>{bars}</div>
    ''', unsafe_allow_html=True)

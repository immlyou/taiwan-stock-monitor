# -*- coding: utf-8 -*-
"""
空狀態元件 - 統一的無資料/空白頁面展示
"""
import streamlit as st
from app.components.theme import COLORS


def show_empty_state(message: str, icon: str = "📭", suggestion: str = None):
    """
    顯示統一風格的空狀態提示

    Parameters:
    -----------
    message : str
        主要提示訊息
    icon : str
        顯示的圖示
    suggestion : str, optional
        建議操作說明
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

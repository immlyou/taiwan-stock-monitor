# -*- coding: utf-8 -*-
"""
AI 異常警報 - 自動偵測股票異常訊號並提供 AI 解讀
"""
import streamlit as st

from config import STREAMLIT_CONFIG, CACHE_TTL
from core.data_loader import get_loader
from core.ai_models import AnomalyDetector
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_page_header, render_global_ticker_bar
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error
from app.components.theme import (
    COLORS,
    create_page_title,
    create_section_header,
    render_kpi_row,
    format_number,
)

st.set_page_config(
    page_title=f"{STREAMLIT_CONFIG['page_title']} - AI 異常警報",
    page_icon='⚠️',
    layout='wide',
)

render_sidebar_mini(current_page='ai_anomaly')
render_global_ticker_bar()
st.markdown(
    create_page_title('AI 異常警報', subtitle='自動偵測爆量、跳空、法人轉向、連續漲跌停等異常訊號', icon='⚠️'),
    unsafe_allow_html=True,
)

# 資料載入
@st.cache_data(ttl=CACHE_TTL['intraday'])
def load_data():
    loader = get_loader()
    return loader

# 掃描設定
st.markdown(create_section_header('掃描設定', icon='⚙️'), unsafe_allow_html=True)

col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    scan_scope = st.selectbox('掃描範圍', ['自選股', '全市場（前 500 大）'], index=0)
with col_cfg2:
    enable_ai = st.checkbox('啟用 AI 解讀', value=True)

# 載入自選股
watchlist_ids = []
if scan_scope == '自選股':
    try:
        from app.components.watchlist_utils import load_watchlists
        watchlists = load_watchlists()
        for wl in watchlists.values():
            for s in wl.get('stocks', []):
                sid = s if isinstance(s, str) else s.get('stock_id', '')
                if sid and sid not in watchlist_ids:
                    watchlist_ids.append(sid)
    except Exception:
        pass

    # 也加入持倉的股票
    try:
        from app.components.portfolio_utils import load_portfolios
        portfolios = load_portfolios()
        for p in portfolios.values():
            for h in p.get('holdings', []):
                sid = h.get('stock_id', '')
                if sid and sid not in watchlist_ids:
                    watchlist_ids.append(sid)
    except Exception:
        pass

if st.button('🔍 開始掃描異常', type='primary', use_container_width=True):
    with st.spinner('正在掃描異常訊號...'):
        try:
            loader = load_data()
            detector = AnomalyDetector()

            stock_ids = watchlist_ids if scan_scope == '自選股' and watchlist_ids else None
            anomalies = detector.detect(loader, stock_ids)

            st.session_state['anomalies'] = anomalies

            # AI 解讀
            if enable_ai and anomalies:
                with st.spinner('AI 正在解讀異常訊號...'):
                    explanation = detector.explain(anomalies)
                    st.session_state['anomaly_explanation'] = explanation
        except Exception as e:
            show_error(e, title='掃描失敗')


# ===== 視覺輔助 =====
# 嚴重度視覺對應（顏色 / 底色 / 圖示 / 中文標籤）
_SEVERITY_META = {
    'high': {'icon': '🔴', 'label': '高', 'color': COLORS['up'], 'bg': COLORS['up_bg']},
    'medium': {'icon': '🟡', 'label': '中', 'color': COLORS['warning'], 'bg': 'rgba(245, 158, 11, 0.12)'},
    'low': {'icon': '🟢', 'label': '低', 'color': COLORS['down'], 'bg': COLORS['down_bg']},
}
_SEVERITY_ORDER = ['high', 'medium', 'low']

_TYPE_ICONS = {
    '爆量': '📊', '跳空上漲': '⬆️', '跳空下跌': '⬇️',
    '外資轉賣': '🏦', '外資轉買': '🏦',
    '連續漲停': '🚀', '連續跌停': '💥',
}


def _anomaly_card(a):
    """單筆異常卡片（紅/黃/綠底依嚴重度，深色 token，無硬編 hex）。"""
    meta = _SEVERITY_META.get(a.get('severity'), _SEVERITY_META['medium'])
    icon = _TYPE_ICONS.get(a.get('anomaly_type'), '⚡')
    stock_id = a.get('stock_id', '')
    name = a.get('name', '') or ''
    return f'''
    <div style="
        background:{meta['bg']};
        border:1px solid {COLORS['border']};
        border-left:4px solid {meta['color']};
        border-radius:8px;
        padding:0.85rem 1rem;
        margin-bottom:8px;
    ">
        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px">
            <div>
                <span style="color:{COLORS['text_primary']};font-weight:700;font-size:1rem">{icon} {stock_id}</span>
                <span style="color:{COLORS['text_secondary']};font-size:0.85rem;margin-left:6px">{name}</span>
            </div>
            <span style="
                background:{meta['color']};
                color:{COLORS['primary']};
                padding:2px 10px;
                border-radius:12px;
                font-size:0.72rem;
                font-weight:700;
            ">{a.get('anomaly_type', '')}</span>
        </div>
        <div style="color:{COLORS['text_secondary']};font-size:0.85rem;margin-top:6px">{a.get('description', '')}</div>
    </div>
    '''


# 顯示結果
if 'anomalies' in st.session_state:
    anomalies = st.session_state['anomalies']

    high_count = sum(1 for a in anomalies if a['severity'] == 'high')
    medium_count = sum(1 for a in anomalies if a['severity'] == 'medium')
    low_count = sum(1 for a in anomalies if a['severity'] == 'low')

    # KPI 概覽
    st.markdown(create_section_header('異常概覽', icon='📈'), unsafe_allow_html=True)
    render_kpi_row([
        {'label': '異常總數', 'value': format_number(len(anomalies), kind='int')},
        {'label': '🔴 高度異常', 'value': format_number(high_count, kind='int'),
         'delta': '需立即關注' if high_count else None, 'delta_color': 'up' if high_count else 'flat'},
        {'label': '🟡 中度異常', 'value': format_number(medium_count, kind='int')},
        {'label': '🟢 低度異常', 'value': format_number(low_count, kind='int')},
    ])

    # AI 解讀
    if 'anomaly_explanation' in st.session_state and st.session_state['anomaly_explanation']:
        st.markdown(create_section_header('AI 解讀', icon='🤖'), unsafe_allow_html=True)
        st.info(st.session_state['anomaly_explanation'])

    # 異常列表
    st.markdown(create_section_header('異常訊號明細', icon='📋'), unsafe_allow_html=True)

    if anomalies:
        # 篩選 / 排序 / 匯出 工具列
        all_types = sorted({a.get('anomaly_type', '') for a in anomalies if a.get('anomaly_type')})
        f1, f2, f3 = st.columns([2, 1.4, 1])
        with f1:
            type_filter = st.multiselect('類型篩選', all_types, default=all_types,
                                         placeholder='全部類型')
        with f2:
            sort_mode = st.selectbox('排序', ['嚴重度', '股票代號', '異常類型'], index=0)
        with f3:
            import pandas as pd
            export_df = pd.DataFrame([
                {
                    '股票代號': a.get('stock_id', ''),
                    '名稱': a.get('name', ''),
                    '異常類型': a.get('anomaly_type', ''),
                    '嚴重度': _SEVERITY_META.get(a.get('severity'), {}).get('label', ''),
                    '說明': a.get('description', ''),
                }
                for a in anomalies
            ])
            st.markdown('<div style="height:1.85rem"></div>', unsafe_allow_html=True)
            st.download_button(
                '📥 匯出 CSV',
                data=export_df.to_csv(index=False).encode('utf-8-sig'),
                file_name='anomalies.csv',
                mime='text/csv',
                use_container_width=True,
            )

        # 套用篩選
        selected_types = set(type_filter) if type_filter else set(all_types)
        filtered = [a for a in anomalies if a.get('anomaly_type', '') in selected_types]

        # 套用排序
        if sort_mode == '股票代號':
            filtered = sorted(filtered, key=lambda a: a.get('stock_id', ''))
        elif sort_mode == '異常類型':
            filtered = sorted(filtered, key=lambda a: a.get('anomaly_type', ''))
        else:  # 嚴重度
            _ord = {'high': 0, 'medium': 1, 'low': 2}
            filtered = sorted(filtered, key=lambda a: _ord.get(a.get('severity'), 2))

        if not filtered:
            show_empty_state('沒有符合篩選條件的異常訊號', icon='🔍', suggestion='調整上方類型篩選')
        else:
            # 按嚴重度分組摺疊
            for sev in _SEVERITY_ORDER:
                group = [a for a in filtered if a.get('severity') == sev]
                if not group:
                    continue
                meta = _SEVERITY_META[sev]
                with st.expander(f"{meta['icon']} {meta['label']}度異常 ({len(group)})", expanded=(sev == 'high')):
                    for a in group:
                        st.markdown(_anomaly_card(a), unsafe_allow_html=True)
    else:
        show_empty_state('目前沒有偵測到異常訊號', icon='✅', suggestion='市場正常運作中')

st.caption('偵測邏輯：爆量(>3x均量)、跳空(>3%)、法人轉向、連續漲跌停')

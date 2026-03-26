"""
共用側邊欄元件 - 專業金融風格
"""
import streamlit as st
from core.data_loader import get_loader, get_data_summary
from core.cache_warmer import get_cache_warmer, is_cache_warm, get_warmup_status_summary


def check_authentication():
    """
    全域認證檢查（免登入模式 - 自動通過）
    """
    if not st.session_state.get("authenticated", False):
        st.session_state["authenticated"] = True
        st.session_state["current_user"] = "user"


# 專業配色 (與 theme.py 一致)
SIDEBAR_COLORS = {
    'bg_primary': '#0f172a',
    'bg_secondary': '#1e293b',
    'accent': '#3b82f6',
    'accent_gradient': 'linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)',
    'text_primary': '#f1f5f9',
    'text_secondary': '#94a3b8',
    'text_muted': '#64748b',
    'border': '#334155',
    'success': '#22c55e',
    'danger': '#ef4444',
}


def apply_sidebar_style():
    """套用專業側邊欄樣式"""
    st.markdown(f"""
    <style>
        /* 隱藏 Streamlit 原生頁面導航 */
        [data-testid="stSidebarNav"] {{
            display: none !important;
        }}

        /* 側邊欄整體樣式 */
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {SIDEBAR_COLORS['bg_primary']} 0%, #020617 100%);
        }}

        [data-testid="stSidebar"] > div:first-child {{
            padding-top: 0;
        }}

        /* 側邊欄文字 */
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
            color: {SIDEBAR_COLORS['text_secondary']};
        }}

        /* 指標卡片 */
        [data-testid="stSidebar"] .stMetric {{
            background: {SIDEBAR_COLORS['bg_secondary']};
            padding: 12px;
            border-radius: 10px;
            border: 1px solid {SIDEBAR_COLORS['border']};
        }}

        [data-testid="stSidebar"] [data-testid="stMetricValue"] {{
            color: {SIDEBAR_COLORS['accent']} !important;
            font-size: 1.1rem !important;
        }}

        [data-testid="stSidebar"] [data-testid="stMetricLabel"] {{
            color: {SIDEBAR_COLORS['text_secondary']} !important;
            font-size: 0.75rem !important;
        }}

        /* 側邊欄按鈕 */
        [data-testid="stSidebar"] .stButton > button {{
            background: {SIDEBAR_COLORS['bg_secondary']};
            color: {SIDEBAR_COLORS['text_primary']};
            border: 1px solid {SIDEBAR_COLORS['border']};
            border-radius: 8px;
            transition: all 0.2s ease;
        }}

        [data-testid="stSidebar"] .stButton > button:hover {{
            background: rgba(59, 130, 246, 0.15);
            border-color: {SIDEBAR_COLORS['accent']};
            color: {SIDEBAR_COLORS['accent']};
        }}

        [data-testid="stSidebar"] .stButton > button[kind="primary"] {{
            background: {SIDEBAR_COLORS['accent_gradient']};
            border: none;
            color: white;
        }}

        /* Expander 樣式 */
        [data-testid="stSidebar"] .stExpander {{
            background: transparent;
            border: none;
        }}

        [data-testid="stSidebar"] .stExpander > div:first-child {{
            background: {SIDEBAR_COLORS['bg_secondary']};
            border-radius: 8px;
            border: 1px solid {SIDEBAR_COLORS['border']};
        }}

        [data-testid="stSidebar"] .streamlit-expanderHeader {{
            color: {SIDEBAR_COLORS['text_primary']} !important;
            font-weight: 500;
        }}

        [data-testid="stSidebar"] .streamlit-expanderContent {{
            background: {SIDEBAR_COLORS['bg_secondary']};
            border: 1px solid {SIDEBAR_COLORS['border']};
            border-top: none;
            border-radius: 0 0 8px 8px;
        }}

        /* 側邊欄 Logo 區塊 */
        .sidebar-logo {{
            text-align: center;
            padding: 1.5rem 1rem;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);
            border-bottom: 1px solid {SIDEBAR_COLORS['border']};
            margin: -1rem -1rem 1rem -1rem;
        }}

        .sidebar-logo-icon {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }}

        .sidebar-logo-title {{
            color: {SIDEBAR_COLORS['text_primary']};
            font-size: 1.3rem;
            font-weight: 700;
            margin: 0;
        }}

        .sidebar-logo-subtitle {{
            color: {SIDEBAR_COLORS['text_muted']};
            font-size: 0.75rem;
            margin: 0;
            letter-spacing: 1px;
        }}

        /* 狀態指示器 */
        .status-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
        }}

        .status-online {{
            background: rgba(34, 197, 94, 0.15);
            color: {SIDEBAR_COLORS['success']};
        }}

        .status-offline {{
            background: rgba(239, 68, 68, 0.15);
            color: {SIDEBAR_COLORS['danger']};
        }}

        .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }}

        .status-dot-online {{ background: {SIDEBAR_COLORS['success']}; }}
        .status-dot-offline {{ background: {SIDEBAR_COLORS['danger']}; }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}

        /* 導航分組標題 */
        .nav-group-title {{
            color: {SIDEBAR_COLORS['text_muted']};
            font-size: 0.65rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin: 1rem 0 0.5rem 0;
            padding-left: 4px;
        }}

        /* 分隔線 */
        .sidebar-divider {{
            height: 1px;
            background: linear-gradient(90deg, transparent, {SIDEBAR_COLORS['border']}, transparent);
            margin: 1rem 0;
        }}

        /* 區塊標題 */
        .sidebar-section {{
            margin-bottom: 1rem;
        }}

        .sidebar-section-title {{
            color: {SIDEBAR_COLORS['text_primary']};
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: 0.75rem;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        /* 數據卡片 */
        .data-card {{
            background: {SIDEBAR_COLORS['bg_secondary']};
            border: 1px solid {SIDEBAR_COLORS['border']};
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 8px;
        }}

        .data-card-label {{
            color: {SIDEBAR_COLORS['text_muted']};
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .data-card-value {{
            color: {SIDEBAR_COLORS['text_primary']};
            font-size: 1.25rem;
            font-weight: 700;
            margin-top: 4px;
        }}

        .data-card-delta {{
            font-size: 0.8rem;
            font-weight: 600;
            margin-top: 2px;
        }}

        .delta-up {{ color: #ef4444; }}
        .delta-down {{ color: #22c55e; }}

        /* 頁面標籤 */
        .page-tag {{
            display: inline-block;
            background: {SIDEBAR_COLORS['accent_gradient']};
            color: white;
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.75rem;
            font-weight: 500;
        }}

        /* 版本資訊 */
        .version-info {{
            text-align: center;
            padding: 1rem;
            color: {SIDEBAR_COLORS['text_muted']};
            font-size: 0.7rem;
        }}

        .version-info a {{
            color: {SIDEBAR_COLORS['accent']};
            text-decoration: none;
        }}

        /* 快取預熱狀態 */
        .cache-status {{
            background: {SIDEBAR_COLORS['bg_secondary']};
            border: 1px solid {SIDEBAR_COLORS['border']};
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 12px;
        }}

        .cache-status-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;
        }}

        .cache-status-title {{
            color: {SIDEBAR_COLORS['text_secondary']};
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .cache-status-badge {{
            font-size: 0.65rem;
            padding: 2px 8px;
            border-radius: 10px;
            font-weight: 500;
        }}

        .cache-status-ready {{
            background: rgba(34, 197, 94, 0.15);
            color: {SIDEBAR_COLORS['success']};
        }}

        .cache-status-warming {{
            background: rgba(251, 191, 36, 0.15);
            color: #fbbf24;
        }}

        .cache-status-idle {{
            background: rgba(100, 116, 139, 0.15);
            color: {SIDEBAR_COLORS['text_muted']};
        }}

        .cache-progress {{
            height: 4px;
            background: {SIDEBAR_COLORS['border']};
            border-radius: 2px;
            overflow: hidden;
            margin-top: 8px;
        }}

        .cache-progress-bar {{
            height: 100%;
            background: {SIDEBAR_COLORS['accent_gradient']};
            border-radius: 2px;
            transition: width 0.3s ease;
        }}

        .cache-task-info {{
            color: {SIDEBAR_COLORS['text_muted']};
            font-size: 0.7rem;
            margin-top: 6px;
        }}

        .cache-stats {{
            display: flex;
            gap: 12px;
            margin-top: 8px;
        }}

        .cache-stat {{
            flex: 1;
            text-align: center;
        }}

        .cache-stat-value {{
            color: {SIDEBAR_COLORS['text_primary']};
            font-size: 0.85rem;
            font-weight: 600;
        }}

        .cache-stat-label {{
            color: {SIDEBAR_COLORS['text_muted']};
            font-size: 0.65rem;
        }}
    </style>
    """, unsafe_allow_html=True)


# 頁面分組定義 — 5 組投資工作流程
PAGE_GROUPS = {
    'market': {
        'title': '市場動態',
        'icon': '📡',
        'pages': [
            {'id': 'dashboard', 'icon': '📊', 'title': '儀表板', 'page': 'pages/0_儀表板.py'},
            {'id': 'realtime_quote', 'icon': '💹', 'title': '即時報價', 'page': 'pages/17_即時報價.py'},
            {'id': 'morning_report', 'icon': '📰', 'title': '每日晨報', 'page': 'pages/16_每日晨報.py'},
            {'id': 'heatmap', 'icon': '🗺️', 'title': '市場熱力圖', 'page': 'pages/18_市場熱力圖.py'},
            {'id': 'money_flow', 'icon': '💸', 'title': '資金流向', 'page': 'pages/19_資金流向.py'},
            {'id': 'after_hours', 'icon': '📋', 'title': '盤後總覽', 'page': 'pages/20_盤後總覽.py'},
        ]
    },
    'research': {
        'title': '研究分析',
        'icon': '🔬',
        'pages': [
            {'id': 'stock', 'icon': '📈', 'title': '個股分析', 'page': 'pages/3_個股分析.py'},
            {'id': 'technical', 'icon': '📉', 'title': '技術分析', 'page': 'pages/22_技術分析.py'},
            {'id': 'compare', 'icon': '⚖️', 'title': '比較分析', 'page': 'pages/12_比較分析.py'},
            {'id': 'industry', 'icon': '🏭', 'title': '產業分析', 'page': 'pages/7_產業分析.py'},
            {'id': 'margin', 'icon': '💰', 'title': '籌碼分析', 'page': 'pages/13_籌碼分析.py'},
            {'id': 'financial', 'icon': '📑', 'title': '財報分析', 'page': 'pages/14_財報分析.py'},
            {'id': 'risk', 'icon': '⚠️', 'title': '風險分析', 'page': 'pages/6_風險分析.py'},
        ]
    },
    'strategy': {
        'title': '選股策略',
        'icon': '🎯',
        'pages': [
            {'id': 'screening', 'icon': '🔍', 'title': '選股篩選', 'page': 'pages/1_選股篩選.py'},
            {'id': 'ai_stock', 'icon': '🤖', 'title': 'AI 智慧選股', 'page': 'pages/23_AI智慧選股.py'},
            {'id': 'backtest', 'icon': '📊', 'title': '回測分析', 'page': 'pages/2_回測分析.py'},
            {'id': 'strategy', 'icon': '📋', 'title': '策略管理', 'page': 'pages/4_策略管理.py'},
            {'id': 'optimizer', 'icon': '🎯', 'title': '參數優化', 'page': 'pages/5_參數優化.py'},
            {'id': 'prediction', 'icon': '🔮', 'title': '預測驗證', 'page': 'pages/21_預測驗證.py'},
        ]
    },
    'portfolio': {
        'title': '投資管理',
        'icon': '💼',
        'pages': [
            {'id': 'portfolio', 'icon': '💼', 'title': '投資組合', 'page': 'pages/8_投資組合.py'},
            {'id': 'watchlist', 'icon': '⭐', 'title': '自選股', 'page': 'pages/10_自選股.py'},
            {'id': 'journal', 'icon': '📝', 'title': '交易日誌', 'page': 'pages/15_交易日誌.py'},
            {'id': 'alerts', 'icon': '🔔', 'title': '警報設定', 'page': 'pages/11_警報設定.py'},
        ]
    },
    'system': {
        'title': '系統',
        'icon': '⚙️',
        'pages': [
            {'id': 'settings', 'icon': '⚙️', 'title': '系統設定', 'page': 'pages/9_系統設定.py'},
        ]
    },
}


def get_page_display_name(page_id: str) -> str:
    """取得頁面顯示名稱"""
    for group in PAGE_GROUPS.values():
        for page in group['pages']:
            if page['id'] == page_id:
                return f"{page['icon']} {page['title']}"
    return page_id


def render_cache_status(compact: bool = False):
    """
    渲染快取預熱狀態

    Parameters:
    -----------
    compact : bool
        是否使用緊湊模式 (用於 mini sidebar)
    """
    summary = get_warmup_status_summary()

    status = summary['status']
    progress = summary['progress']
    current_task = summary['current_task']
    loaded_count = summary['loaded_count']
    total_count = summary['total_count']
    failed_count = summary['failed_count']
    total_time = summary['total_time']

    # 決定狀態顯示
    if status == 'warming':
        badge_class = 'cache-status-warming'
        badge_text = '載入中'
        status_icon = '🔄'
    elif status == 'ready':
        badge_class = 'cache-status-ready'
        badge_text = '已就緒'
        status_icon = '✅'
    else:
        badge_class = 'cache-status-idle'
        badge_text = '未預熱'
        status_icon = '⏸️'

    if compact:
        # 緊湊模式 - 只顯示一行狀態
        progress_html = ''
        if status == 'warming':
            progress_html = f'<div class="cache-progress"><div class="cache-progress-bar" style="width:{progress:.0f}%"></div></div>'

        st.markdown(f'''
        <div class="cache-status" style="padding:8px 10px">
            <div style="display:flex;align-items:center;justify-content:space-between">
                <span style="color:{SIDEBAR_COLORS['text_muted']};font-size:0.7rem">{status_icon} 快取</span>
                <span class="cache-status-badge {badge_class}">{badge_text}</span>
            </div>
            {progress_html}
        </div>
        ''', unsafe_allow_html=True)
    else:
        # 完整模式
        st.markdown(f'''
        <div class="cache-status">
            <div class="cache-status-header">
                <span class="cache-status-title">{status_icon} 快取狀態</span>
                <span class="cache-status-badge {badge_class}">{badge_text}</span>
            </div>
        ''', unsafe_allow_html=True)

        if status == 'warming':
            # 顯示進度條和當前任務
            st.markdown(f'''
            <div class="cache-progress">
                <div class="cache-progress-bar" style="width:{progress:.0f}%"></div>
            </div>
            <div class="cache-task-info">正在載入: {current_task}</div>
            ''', unsafe_allow_html=True)
        elif status == 'ready':
            # 顯示統計資訊
            st.markdown(f'''
            <div class="cache-stats">
                <div class="cache-stat">
                    <div class="cache-stat-value">{loaded_count}/{total_count}</div>
                    <div class="cache-stat-label">已載入</div>
                </div>
                <div class="cache-stat">
                    <div class="cache-stat-value" style="color:{SIDEBAR_COLORS['danger'] if failed_count > 0 else SIDEBAR_COLORS['success']}">{failed_count}</div>
                    <div class="cache-stat-label">失敗</div>
                </div>
                <div class="cache-stat">
                    <div class="cache-stat-value">{total_time:.1f}s</div>
                    <div class="cache-stat-label">耗時</div>
                </div>
            </div>
            ''', unsafe_allow_html=True)
        else:
            # 未預熱
            st.markdown(f'''
            <div class="cache-task-info">首頁載入時將自動預熱</div>
            ''', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


def render_sidebar(current_page: str = None):
    """
    渲染側邊欄

    Parameters:
    -----------
    current_page : str
        當前頁面名稱，用於高亮導航
    """
    check_authentication()
    apply_sidebar_style()

    with st.sidebar:
        # Logo 與標題
        st.markdown(f'''
        <div class="sidebar-logo">
            <div class="sidebar-logo-icon">📊</div>
            <h1 class="sidebar-logo-title">台股分析系統</h1>
            <p class="sidebar-logo-subtitle">TAIWAN STOCK ANALYTICS</p>
        </div>
        ''', unsafe_allow_html=True)

        # 用戶資訊與登出
        current_user = st.session_state.get("current_user", "")
        if current_user:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f'''
                <div style="background:{SIDEBAR_COLORS['bg_secondary']};border-radius:8px;padding:8px 12px;margin-bottom:1rem">
                    <div style="display:flex;align-items:center;gap:8px">
                        <span style="font-size:1.2rem">👤</span>
                        <div>
                            <div style="color:{SIDEBAR_COLORS['text_primary']};font-size:0.85rem;font-weight:600">{current_user}</div>
                            <div style="color:{SIDEBAR_COLORS['text_muted']};font-size:0.7rem">管理員</div>
                        </div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            with col2:
                if st.button('🚪', key='logout_btn', help='登出'):
                    st.session_state["authenticated"] = False
                    st.session_state["current_user"] = None
                    st.rerun()

        # 系統狀態
        summary = get_data_summary()
        if 'error' not in summary:
            st.markdown('''
            <div style="text-align: center; margin-bottom: 1rem;">
                <span class="status-badge status-online">
                    <span class="status-dot status-dot-online"></span>
                    系統運行中
                </span>
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.markdown('''
            <div style="text-align: center; margin-bottom: 1rem;">
                <span class="status-badge status-offline">
                    <span class="status-dot status-dot-offline"></span>
                    系統異常
                </span>
            </div>
            ''', unsafe_allow_html=True)

        # 數據摘要區塊
        st.markdown('<div class="nav-group-title">數據概覽</div>', unsafe_allow_html=True)

        if 'error' not in summary:
            # 使用自訂卡片顯示數據
            taiex = summary.get('taiex_index')
            taiex_chg = summary.get('taiex_change')

            if taiex:
                delta_class = 'delta-up' if taiex_chg and taiex_chg >= 0 else 'delta-down'
                delta_arrow = '▲' if taiex_chg and taiex_chg >= 0 else '▼'
                st.markdown(f'''
                <div class="data-card">
                    <div class="data-card-label">加權指數</div>
                    <div class="data-card-value">{taiex:,.0f}</div>
                    <div class="data-card-delta {delta_class}">{delta_arrow} {abs(taiex_chg or 0):.2f}%</div>
                </div>
                ''', unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.metric('股票', f"{summary['total_stocks']:,}")
            with col2:
                st.metric('交易日', f"{summary['total_days']:,}")

            st.markdown(f'''
            <div style="text-align:center;color:{SIDEBAR_COLORS['text_muted']};font-size:0.75rem;margin-top:8px">
                📅 資料日期: {summary['latest_date']}
            </div>
            ''', unsafe_allow_html=True)
        else:
            st.error(f"數據載入錯誤")

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

        # 功能導覽 - 分組顯示
        st.markdown('<div class="nav-group-title">功能導覽</div>', unsafe_allow_html=True)

        for group_key, group in PAGE_GROUPS.items():
            with st.expander(f"{group['icon']} {group['title']}", expanded=(group_key in ['market', 'research'])):
                for page in group['pages']:
                    is_active = current_page == page['id']
                    btn_type = 'primary' if is_active else 'secondary'

                    if st.button(
                        f"{page['icon']} {page['title']}",
                        key=f"nav_{page['id']}",
                        use_container_width=True,
                        type=btn_type
                    ):
                        st.switch_page(page['page'])

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

        # 快取預熱狀態
        st.markdown('<div class="nav-group-title">系統狀態</div>', unsafe_allow_html=True)
        render_cache_status(compact=False)

        # 快速操作
        st.markdown('<div class="nav-group-title">快速操作</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            if st.button('🔄 更新', use_container_width=True, help='重新載入數據'):
                st.cache_data.clear()
                st.rerun()
        with col2:
            if st.button('📋 清除', use_container_width=True, help='清除快取'):
                get_loader().clear_cache()
                # 重置快取預熱狀態
                warmer = get_cache_warmer()
                warmer.reset()
                st.toast('快取已清除！', icon='✅')

        # 版本資訊
        st.markdown(f'''
        <div class="version-info">
            <div>v2.4.0 | 2026</div>
            <div>Powered by <a href="#">FinLab</a></div>
        </div>
        ''', unsafe_allow_html=True)


def render_sidebar_mini(current_page: str = None):
    """
    渲染簡化版側邊欄 (用於子頁面)

    Parameters:
    -----------
    current_page : str
        當前頁面名稱
    """
    check_authentication()
    apply_sidebar_style()

    with st.sidebar:
        # Logo 與標題
        st.markdown(f'''
        <div class="sidebar-logo">
            <div class="sidebar-logo-icon">📊</div>
            <h1 class="sidebar-logo-title">台股分析系統</h1>
            <p class="sidebar-logo-subtitle">TAIWAN STOCK ANALYTICS</p>
        </div>
        ''', unsafe_allow_html=True)

        # 用戶資訊與登出
        current_user = st.session_state.get("current_user", "")
        if current_user:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f'''
                <div style="background:{SIDEBAR_COLORS['bg_secondary']};border-radius:8px;padding:6px 10px;margin-bottom:0.5rem">
                    <div style="display:flex;align-items:center;gap:6px">
                        <span>👤</span>
                        <span style="color:{SIDEBAR_COLORS['text_primary']};font-size:0.8rem">{current_user}</span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            with col2:
                if st.button('🚪', key='mini_logout_btn', help='登出'):
                    st.session_state["authenticated"] = False
                    st.session_state["current_user"] = None
                    st.rerun()

        # 當前頁面標籤
        if current_page:
            page_display = get_page_display_name(current_page)
            st.markdown(f'<div style="text-align: center;"><span class="page-tag">{page_display}</span></div>',
                        unsafe_allow_html=True)

        # 系統狀態
        summary = get_data_summary()
        if 'error' not in summary:
            st.markdown('''
            <div style="text-align: center; padding: 10px;">
                <span class="status-badge status-online">
                    <span class="status-dot status-dot-online"></span>
                    系統正常
                </span>
            </div>
            ''', unsafe_allow_html=True)

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

        # 數據摘要
        st.markdown('<div class="nav-group-title">數據資訊</div>', unsafe_allow_html=True)

        if 'error' not in summary:
            st.metric('📅 資料日期', summary['latest_date'])
            st.metric('📊 上市股票', f"{summary['total_stocks']:,}",
                      help=f"排除 {summary.get('delisted_stocks', 0)} 檔已下市股票")

            # 顯示加權指數
            if summary.get('taiex_index'):
                st.metric('📊 加權指數', f"{summary['taiex_index']:,.0f}",
                          help='發行量加權股價指數 (TAIEX)')

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

        # 頁面導航 - 分組可摺疊
        st.markdown('<div class="nav-group-title">快速導覽</div>', unsafe_allow_html=True)

        # 找出當前頁面所屬的分組
        current_group = None
        for group_key, group in PAGE_GROUPS.items():
            for page in group['pages']:
                if page['id'] == current_page:
                    current_group = group_key
                    break

        for group_key, group in PAGE_GROUPS.items():
            # 當前分組預設展開
            is_expanded = (group_key == current_group)

            with st.expander(f"{group['icon']} {group['title']}", expanded=is_expanded):
                for page in group['pages']:
                    is_active = current_page == page['id']
                    btn_type = 'primary' if is_active else 'secondary'

                    if st.button(
                        f"{page['icon']} {page['title']}",
                        key=f"mini_nav_{page['id']}",
                        use_container_width=True,
                        type=btn_type,
                        disabled=is_active
                    ):
                        st.switch_page(page['page'])

        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)

        # 快取預熱狀態 (緊湊模式)
        render_cache_status(compact=True)

        # 快速操作
        col1, col2 = st.columns(2)
        with col1:
            if st.button('🔄 更新', use_container_width=True, key='mini_refresh'):
                st.cache_data.clear()
                get_loader().clear_cache()
                # 重置快取預熱狀態
                warmer = get_cache_warmer()
                warmer.reset()
                st.rerun()
        with col2:
            if st.button('🏠 首頁', use_container_width=True, key='mini_home'):
                st.switch_page("pages/0_儀表板.py")

        # 版本資訊
        st.markdown(f'''
        <div class="version-info">
            <div>v2.4.0</div>
        </div>
        ''', unsafe_allow_html=True)

"""
財報分析頁面 - 進階基本面分析工具
6 個分頁：財報總覽、獲利能力、估值分析、營收分析、現金流分析、價值篩選
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.charts import apply_dark_theme
from app.components.theme import DEFAULT_PLOTLY_LAYOUT, COLORS, CHART_PALETTE

st.set_page_config(page_title='財報分析', page_icon='📑', layout='wide')

render_sidebar_mini(current_page='financial')
render_page_header('財報分析', icon='📋')

# ========== FinLab 資料存取 ==========
try:
    from finlab import data as finlab_data
    FINLAB_AVAILABLE = True
except ImportError:
    FINLAB_AVAILABLE = False
    finlab_data = None

@st.cache_data(ttl=CACHE_TTL['daily'], show_spinner=False)
def load_finlab(data_key: str):
    """快取 FinLab 資料"""
    if FINLAB_AVAILABLE and finlab_data:
        try:
            return finlab_data.get(data_key)
        except Exception:
            return None
    return None


# ========== 基礎資料載入 ==========
@st.cache_data(ttl=CACHE_TTL['daily'])
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'pe_ratio': loader.get('pe_ratio'),
        'pb_ratio': loader.get('pb_ratio'),
        'dividend_yield': loader.get('dividend_yield'),
        'monthly_revenue': loader.get('monthly_revenue'),
        'revenue_yoy': loader.get('revenue_yoy'),
        'revenue_mom': loader.get('revenue_mom'),
        'stock_info': loader.get_stock_info(),
    }


try:
    data = load_data()
    close = data['close']
    pe_ratio = data['pe_ratio']
    pb_ratio = data['pb_ratio']
    dividend_yield = data['dividend_yield']
    monthly_revenue = data['monthly_revenue']
    revenue_yoy = data['revenue_yoy']
    revenue_mom = data['revenue_mom']
    stock_info = data['stock_info']
    active_stocks = get_active_stocks()
except Exception as e:
    show_error(e, title='載入數據失敗', suggestion='請檢查資料來源是否正常')
    st.stop()

stock_options = [f"{row['stock_id']} {row['name']}"
                 for _, row in stock_info.iterrows()
                 if row['stock_id'] in active_stocks]


# ========== 工具函式 ==========
def _latest(df, stock_id):
    """安全取得最新值"""
    if df is not None and stock_id in df.columns:
        s = df[stock_id].dropna()
        if len(s) > 0:
            return s.iloc[-1]
    return None


def _tail(df, stock_id, n=20):
    """安全取得尾端 n 筆"""
    if df is not None and stock_id in df.columns:
        s = df[stock_id].dropna()
        if len(s) > 0:
            return s.tail(n)
    return None


def _metric_display(label, value, fmt='{:.2f}', suffix=''):
    """顯示 metric，處理 None"""
    if value is not None and not (isinstance(value, float) and (np.isnan(value) or np.isinf(value))):
        st.metric(label, f'{fmt.format(value)}{suffix}')
    else:
        st.metric(label, 'N/A')


def _valuation_position(current, mean, std):
    """判斷估值位置"""
    if current < mean - std:
        return '偏低'
    elif current > mean + std:
        return '偏高'
    return '合理'


# ========== 全域股票選擇器（所有分頁共用） ==========
st.markdown('### 選擇分析股票')
selected_stock = st.selectbox(
    '選擇股票', stock_options,
    index=0 if stock_options else None,
    key='fin_global_stock'
)

if selected_stock:
    sid = selected_stock.split(' ')[0]
    sname = ' '.join(selected_stock.split(' ')[1:])
    st.markdown(f'#### {sid} {sname}')
else:
    sid = None
    sname = ''

st.markdown('---')

# ========== 6 個分頁 ==========
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    '📋 財報總覽', '💰 獲利能力', '📊 估值分析',
    '📈 營收分析', '💵 現金流分析', '🎯 價值篩選'
])


# ==================== Tab 1: 財報總覽 ====================
with tab1:
    st.markdown('### 財報總覽')

    if selected_stock:
        # KPI 卡片列
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            _metric_display('收盤價', _latest(close, sid))
        with c2:
            _metric_display('本益比', _latest(pe_ratio, sid))
        with c3:
            _metric_display('股價淨值比', _latest(pb_ratio, sid))
        with c4:
            _metric_display('殖利率', _latest(dividend_yield, sid), suffix='%')
        with c5:
            eps_data = load_finlab('financial_statement:每股盈餘')
            _metric_display('EPS', _latest(eps_data, sid))
        with c6:
            roe_data = load_finlab('fundamental_features:ROE稅後')
            _metric_display('ROE', _latest(roe_data, sid), suffix='%')

        st.markdown('---')

        # 趨勢圖：EPS + ROE
        col1, col2 = st.columns(2)

        with col1:
            eps_series = _tail(eps_data, sid, 20)
            if eps_series is not None and len(eps_series) > 0:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=eps_series.index, y=eps_series.values,
                    name='EPS',
                    marker_color=[COLORS['up'] if v >= 0 else COLORS['down'] for v in eps_series.values]
                ))
                apply_dark_theme(fig, height=320, title='每股盈餘 (EPS) 趨勢')
                st.plotly_chart(fig, use_container_width=True)
            else:
                show_empty_state('EPS 資料不可用', icon='📊')

        with col2:
            roe_series = _tail(roe_data, sid, 20)
            roa_data = load_finlab('fundamental_features:ROA稅後息前')
            roa_series = _tail(roa_data, sid, 20)

            if roe_series is not None and len(roe_series) > 0:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=roe_series.index, y=roe_series.values,
                    name='ROE', mode='lines+markers',
                    line=dict(color=CHART_PALETTE[0], width=2)
                ))
                if roa_series is not None and len(roa_series) > 0:
                    fig.add_trace(go.Scatter(
                        x=roa_series.index, y=roa_series.values,
                        name='ROA', mode='lines+markers',
                        line=dict(color=CHART_PALETTE[1], width=2)
                    ))
                apply_dark_theme(fig, height=320, title='ROE / ROA 趨勢')
                st.plotly_chart(fig, use_container_width=True)
            else:
                show_empty_state('ROE 資料不可用', icon='📊')

        # 利潤率摘要
        gm = load_finlab('fundamental_features:營業毛利率')
        om = load_finlab('fundamental_features:營業利益率')
        nm = load_finlab('fundamental_features:稅後淨利率')

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _metric_display('毛利率', _latest(gm, sid), suffix='%')
        with c2:
            _metric_display('營益率', _latest(om, sid), suffix='%')
        with c3:
            _metric_display('淨利率', _latest(nm, sid), suffix='%')
        with c4:
            dr = load_finlab('fundamental_features:負債比率')
            _metric_display('負債比率', _latest(dr, sid), suffix='%')


# ==================== Tab 2: 獲利能力 ====================
with tab2:
    st.markdown('### 獲利能力分析')

    if selected_stock:

        gm_data = load_finlab('fundamental_features:營業毛利率')
        om_data = load_finlab('fundamental_features:營業利益率')
        nm_data = load_finlab('fundamental_features:稅後淨利率')

        gm_s = _tail(gm_data, sid, 20)
        om_s = _tail(om_data, sid, 20)
        nm_s = _tail(nm_data, sid, 20)

        has_data = any(s is not None and len(s) > 0 for s in [gm_s, om_s, nm_s])

        if has_data:
            # 利潤率趨勢圖
            fig = go.Figure()
            traces = [
                (gm_s, '毛利率', CHART_PALETTE[0]),
                (om_s, '營益率', CHART_PALETTE[1]),
                (nm_s, '淨利率', CHART_PALETTE[2]),
            ]
            for series, name, color in traces:
                if series is not None and len(series) > 0:
                    fig.add_trace(go.Scatter(
                        x=series.index, y=series.values,
                        name=name, mode='lines+markers',
                        line=dict(color=color, width=2)
                    ))
            apply_dark_theme(fig, height=400, title='利潤率趨勢')
            fig.update_layout(yaxis_title='%')
            st.plotly_chart(fig, use_container_width=True)

            # 統計摘要
            st.markdown('##### 利潤率統計')
            summary_data = []
            for series, name in [(gm_s, '毛利率'), (om_s, '營益率'), (nm_s, '淨利率')]:
                if series is not None and len(series) > 0:
                    summary_data.append({
                        '指標': name,
                        '最新': f'{series.iloc[-1]:.2f}%',
                        '平均': f'{series.mean():.2f}%',
                        '最高': f'{series.max():.2f}%',
                        '最低': f'{series.min():.2f}%',
                        '趨勢': '上升' if len(series) >= 2 and series.iloc[-1] > series.iloc[-2] else '下降',
                    })
            if summary_data:
                st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)

            # ROE 拆解 (杜邦分析)
            st.markdown('##### ROE 與 ROA')
            roe_s = _tail(load_finlab('fundamental_features:ROE稅後'), sid, 20)
            roa_s = _tail(load_finlab('fundamental_features:ROA稅後息前'), sid, 20)

            if roe_s is not None and len(roe_s) > 0:
                fig2 = go.Figure()
                fig2.add_trace(go.Bar(
                    x=roe_s.index, y=roe_s.values,
                    name='ROE', marker_color=CHART_PALETTE[0], opacity=0.8
                ))
                if roa_s is not None and len(roa_s) > 0:
                    fig2.add_trace(go.Scatter(
                        x=roa_s.index, y=roa_s.values,
                        name='ROA', mode='lines+markers',
                        line=dict(color=CHART_PALETTE[1], width=2)
                    ))
                apply_dark_theme(fig2, height=350, title='ROE / ROA 趨勢')
                fig2.update_layout(yaxis_title='%')
                st.plotly_chart(fig2, use_container_width=True)
        else:
            show_empty_state('此功能需要 FinLab 進階財務數據', icon='💰',
                             suggestion='請確認 FinLab API 可用且已登入')


# ==================== Tab 3: 估值分析 ====================
with tab3:
    st.markdown('### 估值分析')

    if selected_stock:

        # 估值 KPI
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            _metric_display('本益比', _latest(pe_ratio, sid))
        with c2:
            _metric_display('股價淨值比', _latest(pb_ratio, sid))
        with c3:
            _metric_display('殖利率', _latest(dividend_yield, sid), suffix='%')
        with c4:
            _metric_display('收盤價', _latest(close, sid))

        # PE / PB 歷史走勢 + 河流圖
        period_years = st.selectbox('分析期間', ['1年', '2年', '3年', '5年'], index=1, key='val_period')
        period_map = {'1年': 252, '2年': 504, '3年': 756, '5年': 1260}
        n_days = period_map[period_years]

        col1, col2 = st.columns(2)

        with col1:
            pe_s = _tail(pe_ratio, sid, n_days)
            if pe_s is not None and len(pe_s) > 10:
                pe_mean = pe_s.mean()
                pe_std = pe_s.std()

                fig = go.Figure()
                # 河流圖帶
                fig.add_trace(go.Scatter(
                    x=pe_s.index, y=[pe_mean + 2 * pe_std] * len(pe_s),
                    name='+2σ', line=dict(width=0), showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=pe_s.index, y=[pe_mean - 2 * pe_std] * len(pe_s),
                    name='-2σ', line=dict(width=0), fill='tonexty',
                    fillcolor='rgba(59, 130, 246, 0.1)', showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=pe_s.index, y=[pe_mean + pe_std] * len(pe_s),
                    name='+1σ', line=dict(width=0), showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=pe_s.index, y=[pe_mean - pe_std] * len(pe_s),
                    name='-1σ', line=dict(width=0), fill='tonexty',
                    fillcolor='rgba(59, 130, 246, 0.15)', showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=pe_s.index, y=[pe_mean] * len(pe_s),
                    name='平均', line=dict(color=COLORS['text_muted'], dash='dash', width=1)
                ))
                fig.add_trace(go.Scatter(
                    x=pe_s.index, y=pe_s.values,
                    name='本益比', line=dict(color=CHART_PALETTE[0], width=2)
                ))
                apply_dark_theme(fig, height=350, title='本益比河流圖')
                st.plotly_chart(fig, use_container_width=True)

                # 百分位
                percentile = (pe_s < pe_s.iloc[-1]).sum() / len(pe_s) * 100
                c_a, c_b, c_c = st.columns(3)
                c_a.metric('目前位置', _valuation_position(pe_s.iloc[-1], pe_mean, pe_std))
                c_b.metric('歷史百分位', f'{percentile:.0f}%')
                c_c.metric('平均±σ', f'{pe_mean:.1f} ± {pe_std:.1f}')

        with col2:
            pb_s = _tail(pb_ratio, sid, n_days)
            if pb_s is not None and len(pb_s) > 10:
                pb_mean = pb_s.mean()
                pb_std = pb_s.std()

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=pb_s.index, y=[pb_mean + 2 * pb_std] * len(pb_s),
                    name='+2σ', line=dict(width=0), showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=pb_s.index, y=[pb_mean - 2 * pb_std] * len(pb_s),
                    name='-2σ', line=dict(width=0), fill='tonexty',
                    fillcolor='rgba(139, 92, 246, 0.1)', showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=pb_s.index, y=[pb_mean + pb_std] * len(pb_s),
                    name='+1σ', line=dict(width=0), showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=pb_s.index, y=[pb_mean - pb_std] * len(pb_s),
                    name='-1σ', line=dict(width=0), fill='tonexty',
                    fillcolor='rgba(139, 92, 246, 0.15)', showlegend=False
                ))
                fig.add_trace(go.Scatter(
                    x=pb_s.index, y=[pb_mean] * len(pb_s),
                    name='平均', line=dict(color=COLORS['text_muted'], dash='dash', width=1)
                ))
                fig.add_trace(go.Scatter(
                    x=pb_s.index, y=pb_s.values,
                    name='股價淨值比', line=dict(color=CHART_PALETTE[2], width=2)
                ))
                apply_dark_theme(fig, height=350, title='股價淨值比河流圖')
                st.plotly_chart(fig, use_container_width=True)

                percentile = (pb_s < pb_s.iloc[-1]).sum() / len(pb_s) * 100
                c_a, c_b, c_c = st.columns(3)
                c_a.metric('目前位置', _valuation_position(pb_s.iloc[-1], pb_mean, pb_std))
                c_b.metric('歷史百分位', f'{percentile:.0f}%')
                c_c.metric('平均±σ', f'{pb_mean:.2f} ± {pb_std:.2f}')

        # 多股估值比較
        st.markdown('---')
        st.markdown('##### 多股估值比較')
        compare_stocks = st.multiselect(
            '選擇比較股票 (最多 10 檔)', stock_options,
            max_selections=10, key='val_compare'
        )
        if compare_stocks:
            compare_ids = [s.split(' ')[0] for s in compare_stocks]
            val_data = []
            for cid in compare_ids:
                info = stock_info[stock_info['stock_id'] == cid]
                name = info['name'].values[0] if len(info) > 0 else ''
                val_data.append({
                    '代碼': cid, '名稱': name,
                    '本益比': _latest(pe_ratio, cid),
                    '股價淨值比': _latest(pb_ratio, cid),
                    '殖利率(%)': _latest(dividend_yield, cid),
                    '營收YoY(%)': _latest(revenue_yoy, cid),
                })
            df = pd.DataFrame(val_data)
            st.dataframe(
                df.style.format({
                    '本益比': '{:.2f}', '股價淨值比': '{:.2f}',
                    '殖利率(%)': '{:.2f}', '營收YoY(%)': '{:+.2f}',
                }, na_rep='N/A'),
                use_container_width=True, hide_index=True
            )


# ==================== Tab 4: 營收分析 ====================
with tab4:
    st.markdown('### 營收分析')

    if selected_stock:
        st.markdown(f'#### {sid} {sname} 營收分析')

        if monthly_revenue is not None and sid in monthly_revenue.columns:
            rev_data = monthly_revenue[sid].dropna()

            if len(rev_data) > 0:
                period = st.selectbox(
                    '分析期間',
                    ['近12個月', '近24個月', '近36個月', '全部'],
                    index=1, key='rev_period'
                )
                period_map = {'近12個月': 12, '近24個月': 24, '近36個月': 36}
                if period in period_map:
                    rev_data = rev_data.tail(period_map[period])

                # 月營收走勢 (Plotly)
                rev_billion = rev_data / 1e8
                yoy_s = _tail(revenue_yoy, sid, len(rev_data))

                fig = make_subplots(specs=[[{"secondary_y": True}]])
                fig.add_trace(go.Bar(
                    x=rev_data.index, y=rev_billion.values,
                    name='月營收(億)', marker_color=CHART_PALETTE[0], opacity=0.8
                ), secondary_y=False)
                if yoy_s is not None and len(yoy_s) > 0:
                    # align yoy to rev_data index
                    yoy_aligned = yoy_s.reindex(rev_data.index)
                    fig.add_trace(go.Scatter(
                        x=rev_data.index, y=yoy_aligned.values,
                        name='年增率(%)', mode='lines+markers',
                        line=dict(color=COLORS['up'], width=2)
                    ), secondary_y=True)
                    fig.update_yaxes(title_text='年增率(%)', secondary_y=True)

                fig.update_yaxes(title_text='營收(億)', secondary_y=False)
                apply_dark_theme(fig, height=400, title='月營收走勢')
                st.plotly_chart(fig, use_container_width=True)

                # KPI
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric('最新月營收', f'{rev_billion.iloc[-1]:.2f} 億')
                with c2:
                    yoy_val = _latest(revenue_yoy, sid)
                    _metric_display('年增率 (YoY)', yoy_val, fmt='{:+.2f}', suffix='%')
                with c3:
                    mom_val = _latest(revenue_mom, sid)
                    _metric_display('月增率 (MoM)', mom_val, fmt='{:+.2f}', suffix='%')
                with c4:
                    current_year = datetime.now().year
                    ytd_rev = rev_data[rev_data.index.year == current_year].sum() / 1e8
                    st.metric('本年累計營收', f'{ytd_rev:.2f} 億')

                # 累積 YTD 比較
                st.markdown('##### 累積 YTD 營收比較')
                years = sorted(rev_data.index.year.unique())[-3:]
                if len(years) >= 2:
                    fig_ytd = go.Figure()
                    for i, yr in enumerate(years):
                        yr_data = rev_data[rev_data.index.year == yr]
                        cumsum = yr_data.cumsum() / 1e8
                        fig_ytd.add_trace(go.Scatter(
                            x=list(range(1, len(cumsum) + 1)),
                            y=cumsum.values,
                            name=str(yr), mode='lines+markers',
                            line=dict(color=CHART_PALETTE[i % len(CHART_PALETTE)], width=2)
                        ))
                    apply_dark_theme(fig_ytd, height=350, title='累積 YTD 營收比較 (億)')
                    fig_ytd.update_layout(xaxis_title='月份')
                    st.plotly_chart(fig_ytd, use_container_width=True)

                # 年度比較
                st.markdown('##### 年度營收比較')
                yearly_rev = rev_data.groupby(rev_data.index.year).sum() / 1e8
                yearly_growth = yearly_rev.pct_change() * 100

                col1, col2 = st.columns(2)
                with col1:
                    fig_yr = go.Figure()
                    fig_yr.add_trace(go.Bar(
                        x=[str(y) for y in yearly_rev.index], y=yearly_rev.values,
                        marker_color=CHART_PALETTE[0], opacity=0.8
                    ))
                    apply_dark_theme(fig_yr, height=300, title='年度營收(億)')
                    st.plotly_chart(fig_yr, use_container_width=True)
                with col2:
                    growth_df = pd.DataFrame({
                        '年度': [str(y) for y in yearly_growth.index],
                        '營收(億)': yearly_rev.values,
                        '年增率(%)': yearly_growth.values,
                    })
                    st.dataframe(growth_df.style.format({
                        '營收(億)': '{:.2f}', '年增率(%)': '{:+.2f}'
                    }, na_rep='-'), hide_index=True, use_container_width=True)

                # 季節性分析
                st.markdown('##### 季節性分析')
                monthly_avg = rev_data.groupby(rev_data.index.month).mean() / 1e8
                months = ['1月', '2月', '3月', '4月', '5月', '6月',
                          '7月', '8月', '9月', '10月', '11月', '12月']
                fig_season = go.Figure()
                fig_season.add_trace(go.Bar(
                    x=months, y=[monthly_avg.get(i, 0) for i in range(1, 13)],
                    marker_color=CHART_PALETTE[1], opacity=0.8
                ))
                apply_dark_theme(fig_season, height=300, title='平均月營收分布(億)')
                st.plotly_chart(fig_season, use_container_width=True)
        else:
            show_empty_state('無月營收資料', icon='📈')


# ==================== Tab 5: 現金流分析 ====================
with tab5:
    st.markdown('### 現金流分析')

    if selected_stock:

        operating_cf = load_finlab('fundamental_features:營運現金流')
        fcf_data = load_finlab('fundamental_features:自由現金流量')
        cf_ratio = load_finlab('fundamental_features:現金流量比率')
        per_share_cf = load_finlab('fundamental_features:每股現金流量')

        ocf_s = _tail(operating_cf, sid, 20)
        fcf_s = _tail(fcf_data, sid, 20)

        has_cf = any(s is not None and len(s) > 0 for s in [ocf_s, fcf_s])

        if has_cf:
            # KPI
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                _metric_display('營運現金流', _latest(operating_cf, sid), fmt='{:.0f}')
            with c2:
                _metric_display('自由現金流', _latest(fcf_data, sid), fmt='{:.0f}')
            with c3:
                _metric_display('現金流量比率', _latest(cf_ratio, sid), suffix='%')
            with c4:
                _metric_display('每股現金流量', _latest(per_share_cf, sid))

            # 現金流趨勢圖
            fig = go.Figure()
            if ocf_s is not None and len(ocf_s) > 0:
                fig.add_trace(go.Bar(
                    x=ocf_s.index, y=ocf_s.values,
                    name='營運現金流', marker_color=CHART_PALETTE[0], opacity=0.8
                ))
            if fcf_s is not None and len(fcf_s) > 0:
                fig.add_trace(go.Scatter(
                    x=fcf_s.index, y=fcf_s.values,
                    name='自由現金流', mode='lines+markers',
                    line=dict(color=CHART_PALETTE[2], width=2)
                ))
            apply_dark_theme(fig, height=400, title='現金流趨勢')
            st.plotly_chart(fig, use_container_width=True)

            # FCF 殖利率
            if fcf_s is not None and len(fcf_s) > 0:
                mv_data = load_finlab('etl:market_value')
                mv_s = _tail(mv_data, sid, len(fcf_s))
                if mv_s is not None and len(mv_s) > 0:
                    # Align by common index
                    common_idx = fcf_s.index.intersection(mv_s.index)
                    if len(common_idx) > 0:
                        fcf_yield = (fcf_s.loc[common_idx] / mv_s.loc[common_idx] * 100).dropna()
                        if len(fcf_yield) > 0:
                            st.markdown('##### 自由現金流殖利率')
                            fig_fy = go.Figure()
                            fig_fy.add_trace(go.Scatter(
                                x=fcf_yield.index, y=fcf_yield.values,
                                name='FCF 殖利率(%)', mode='lines+markers',
                                line=dict(color=CHART_PALETTE[3], width=2),
                                fill='tozeroy', fillcolor='rgba(6, 182, 212, 0.1)'
                            ))
                            apply_dark_theme(fig_fy, height=300, title='自由現金流殖利率 (%)')
                            st.plotly_chart(fig_fy, use_container_width=True)

            # 現金流品質
            st.markdown('##### 現金流品質指標')
            eps_d = load_finlab('financial_statement:每股盈餘')
            eps_s = _tail(eps_d, sid, 20)
            pcf_s = _tail(per_share_cf, sid, 20)

            if eps_s is not None and pcf_s is not None and len(eps_s) > 0 and len(pcf_s) > 0:
                fig_q = go.Figure()
                fig_q.add_trace(go.Bar(
                    x=eps_s.index, y=eps_s.values,
                    name='EPS', marker_color=CHART_PALETTE[0], opacity=0.7
                ))
                fig_q.add_trace(go.Bar(
                    x=pcf_s.index, y=pcf_s.values,
                    name='每股現金流', marker_color=CHART_PALETTE[2], opacity=0.7
                ))
                apply_dark_theme(fig_q, height=350, title='EPS vs 每股現金流')
                fig_q.update_layout(barmode='group')
                st.plotly_chart(fig_q, use_container_width=True)
        else:
            show_empty_state('此功能需要 FinLab 進階財務數據', icon='💵',
                             suggestion='請確認 FinLab API 可用且已登入')


# ==================== Tab 6: 價值篩選 ====================
with tab6:
    st.markdown('### 價值篩選')
    st.markdown('根據基本面指標篩選價值股')

    col1, col2, col3 = st.columns(3)

    with col1:
        max_pe = st.number_input('本益比上限', 1.0, 100.0, 15.0, key='vs_pe')
        max_pb = st.number_input('股價淨值比上限', 0.1, 10.0, 1.5, key='vs_pb')

    with col2:
        min_yield = st.number_input('殖利率下限 (%)', 0.0, 20.0, 4.0, key='vs_dy')
        min_yoy = st.number_input('營收年增率下限 (%)', -50.0, 100.0, 0.0, key='vs_yoy')

    with col3:
        min_roe = st.number_input('ROE 下限 (%)', -50.0, 100.0, 0.0, key='vs_roe')
        min_gm = st.number_input('毛利率下限 (%)', -50.0, 100.0, 0.0, key='vs_gm')

    if st.button('執行選股', type='primary', key='value_screening'):
        with st.spinner('選股中...'):
            try:
                roe_all = load_finlab('fundamental_features:ROE稅後')
                gm_all = load_finlab('fundamental_features:營業毛利率')

                selected_stocks = []
                for stock_id in active_stocks:
                    # PE
                    pe = _latest(pe_ratio, stock_id)
                    if pe is None or pe > max_pe or pe <= 0:
                        continue
                    # PB
                    pb = _latest(pb_ratio, stock_id)
                    if pb is None or pb > max_pb or pb <= 0:
                        continue
                    # Dividend yield
                    dy = _latest(dividend_yield, stock_id)
                    if dy is None or dy < min_yield:
                        continue
                    # YoY
                    yoy = _latest(revenue_yoy, stock_id)
                    if yoy is not None and yoy < min_yoy:
                        continue
                    # ROE
                    roe = _latest(roe_all, stock_id)
                    if roe is not None and roe < min_roe:
                        continue
                    # Gross margin
                    gm = _latest(gm_all, stock_id)
                    if gm is not None and gm < min_gm:
                        continue

                    price = _latest(close, stock_id)
                    info = stock_info[stock_info['stock_id'] == stock_id]
                    name = info['name'].values[0] if len(info) > 0 else ''

                    selected_stocks.append({
                        '代碼': stock_id, '名稱': name,
                        '收盤價': price, '本益比': pe, '股價淨值比': pb,
                        '殖利率(%)': dy, '營收YoY(%)': yoy,
                        'ROE(%)': roe, '毛利率(%)': gm,
                    })
            except Exception as e:
                show_error(e, title='價值選股失敗')
                selected_stocks = []

            if selected_stocks:
                df = pd.DataFrame(selected_stocks)
                df['價值評分'] = (
                    (1 - df['本益比'] / max_pe) * 25 +
                    (1 - df['股價淨值比'] / max_pb) * 25 +
                    (df['殖利率(%)'] / 10) * 25 +
                    (df['ROE(%)'].fillna(0) / 30) * 25
                ).clip(0, 100)
                df = df.sort_values('價值評分', ascending=False)

                st.success(f'找到 {len(df)} 檔價值股')
                st.dataframe(
                    df.style.format({
                        '收盤價': '{:.2f}', '本益比': '{:.2f}', '股價淨值比': '{:.2f}',
                        '殖利率(%)': '{:.2f}', '營收YoY(%)': '{:+.2f}',
                        'ROE(%)': '{:.2f}', '毛利率(%)': '{:.2f}',
                        '價值評分': '{:.1f}',
                    }, na_rep='N/A'),
                    use_container_width=True, hide_index=True
                )

                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    '📥 下載選股結果', csv,
                    f'value_stocks_{datetime.now().strftime("%Y%m%d")}.csv',
                    'text/csv',
                )
            else:
                show_empty_state('沒有符合條件的股票', icon='🔍',
                                 suggestion='請嘗試放寬篩選條件')


# ========== 說明 ==========
with st.expander('📖 財報分析說明'):
    st.markdown('''
    ### 估值指標說明

    #### 本益比 (P/E Ratio)
    - 公式: 股價 / 每股盈餘
    - 一般標準: 10-20 倍為合理區間

    #### 股價淨值比 (P/B Ratio)
    - 公式: 股價 / 每股淨值
    - 一般標準: < 1 可能被低估

    #### ROE (股東權益報酬率)
    - 公式: 淨利 / 股東權益
    - 衡量公司為股東創造利潤的效率

    #### 利潤率 (毛利率/營益率/淨利率)
    - 毛利率 = 毛利 / 營收
    - 營益率 = 營業利益 / 營收
    - 淨利率 = 淨利 / 營收

    ### 現金流分析重點
    - **營運現金流 > 0**: 本業能產生現金
    - **自由現金流 > 0**: 公司有餘裕的現金
    - **每股現金流 > EPS**: 獲利品質佳
    - **FCF 殖利率**: 自由現金流 / 市值，越高越有價值
    ''')

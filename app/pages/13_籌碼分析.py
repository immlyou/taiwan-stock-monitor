"""
籌碼分析頁面 - 融資融券、法人買賣超分析
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.error_handler import show_error
from app.components.page_header import render_page_header, render_global_ticker_bar
from app.components.empty_state import show_empty_state
from app.components.theme import (
    COLORS, create_page_title, create_section_header,
    render_kpi_row, format_number,
)
from app.components.charts import apply_dark_theme, CHART_CONFIG

st.set_page_config(page_title='籌碼分析', page_icon='💰', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='margin')

# 載入數據
@st.cache_data(ttl=CACHE_TTL['daily'])
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

# 股票選擇
stock_options = [f"{row['stock_id']} {row['name']}"
                 for _, row in stock_info.iterrows()
                 if row['stock_id'] in active_stocks]

# 全域行情列（帶入目前選取的個股代號）+ 頁面標題
_selected_label = st.session_state.get('margin_selected_stock')
if _selected_label not in stock_options:
    _selected_label = stock_options[0] if stock_options else None
_active_code = _selected_label.split(' ')[0] if _selected_label else None
render_global_ticker_bar(active_stock=_active_code)
st.markdown(
    create_page_title('籌碼分析', subtitle='融資融券 · 法人買賣超 · 量價籌碼', icon='🏦'),
    unsafe_allow_html=True,
)

# Tab 選擇
tab1, tab2, tab3, tab4 = st.tabs(['🔍 個股籌碼', '📊 籌碼指標', '🏆 籌碼排行', '📈 策略選股'])

# ========== 個股籌碼分析 ==========
with tab1:
    st.markdown('### 個股籌碼分析')

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_stock = st.selectbox(
            '選擇股票',
            stock_options,
            index=0 if stock_options else None,
            key='margin_selected_stock'
        )

    with col2:
        analysis_days = st.selectbox(
            '分析天數',
            [20, 40, 60, 120, 252],
            index=2
        )

    if selected_stock:
        stock_id = selected_stock.split(' ')[0]
        stock_name = selected_stock.split(' ')[1] if len(selected_stock.split(' ')) > 1 else ''

        if stock_id in close.columns:
            stock_close = close[stock_id].dropna().tail(analysis_days)
            stock_volume = volume[stock_id].dropna().tail(analysis_days) if stock_id in volume.columns else None

            # 預先載入籌碼資料（融資融券 + 法人）供後續四段使用
            margin_balance = None
            short_balance = None
            inst_frames = {}
            institutional_df = None
            try:
                loader = get_loader()
                margin_buy = loader.get('margin_buy')
                short_sell = loader.get('short_sell')
                has_margin = (margin_buy is not None and stock_id in margin_buy.columns)
                if has_margin:
                    margin_balance = margin_buy[stock_id].dropna().tail(analysis_days)
                    short_balance = short_sell[stock_id].dropna().tail(analysis_days) if (short_sell is not None and stock_id in short_sell.columns) else None
            except Exception:
                margin_balance = None
                short_balance = None

            try:
                loader = get_loader()
                foreign_inv = loader.get('foreign_investors')
                trust_inv = loader.get('investment_trust')
                dealer_inv = loader.get('dealer')
                if foreign_inv is not None and stock_id in foreign_inv.columns:
                    inst_frames['外資'] = foreign_inv[stock_id].dropna().tail(analysis_days)
                if trust_inv is not None and stock_id in trust_inv.columns:
                    inst_frames['投信'] = trust_inv[stock_id].dropna().tail(analysis_days)
                if dealer_inv is not None and stock_id in dealer_inv.columns:
                    inst_frames['自營商'] = dealer_inv[stock_id].dropna().tail(analysis_days)
                if inst_frames:
                    institutional_df = pd.DataFrame(inst_frames)
                    institutional_df['合計'] = institutional_df.sum(axis=1)
            except Exception:
                inst_frames = {}
                institutional_df = None

            # 法人色票對應
            _inst_colors = {
                '外資': COLORS['flow_foreign'],
                '投信': COLORS['flow_trust'],
                '自營商': COLORS['flow_dealer'],
            }

            # ===== 第一段：關鍵 KPI 卡 =====
            st.markdown(
                create_section_header(f'{stock_id} {stock_name} 關鍵指標', icon='📌'),
                unsafe_allow_html=True,
            )

            current_price = stock_close.iloc[-1]
            price_change = (stock_close.iloc[-1] / stock_close.iloc[0] - 1) * 100

            kpi_items = [
                {
                    'label': '收盤價',
                    'value': format_number(current_price, kind='price'),
                    'delta': format_number(price_change, kind='pct', signed=True),
                    'delta_color': 'up' if price_change > 0 else ('down' if price_change < 0 else 'flat'),
                    'sparkline': list(stock_close.values[-30:]),
                },
            ]

            if stock_volume is not None and len(stock_volume) > 0:
                avg_volume = stock_volume.mean() / 1000  # 轉換為張
                kpi_items.append({
                    'label': '平均成交量',
                    'value': f'{format_number(avg_volume, kind="int")} 張',
                })
            else:
                kpi_items.append({'label': '平均成交量', 'value': '-'})

            volatility = stock_close.pct_change().std() * np.sqrt(252) * 100
            kpi_items.append({
                'label': '年化波動率',
                'value': format_number(volatility, kind='pct'),
            })

            # RSI
            delta = stock_close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 0
            kpi_items.append({
                'label': 'RSI(14)',
                'value': format_number(current_rsi, kind='pct').replace('%', ''),
            })

            # 融資/融券/券資比 KPI（若有資料）
            if margin_balance is not None and len(margin_balance) >= 2:
                latest_margin = margin_balance.iloc[-1]
                margin_change = margin_balance.iloc[-1] - margin_balance.iloc[-2]
                kpi_items.append({
                    'label': '融資餘額(張)',
                    'value': format_number(latest_margin, kind='int'),
                    'delta': format_number(margin_change, kind='int', signed=True),
                    # 融資增加偏空（綠）、減少偏多（紅）
                    'delta_color': 'down' if margin_change > 0 else ('up' if margin_change < 0 else 'flat'),
                })
            if short_balance is not None and len(short_balance) >= 2:
                latest_short = short_balance.iloc[-1]
                short_change = short_balance.iloc[-1] - short_balance.iloc[-2]
                kpi_items.append({
                    'label': '融券餘額(張)',
                    'value': format_number(latest_short, kind='int'),
                    'delta': format_number(short_change, kind='int', signed=True),
                    'delta_color': 'up' if short_change > 0 else ('down' if short_change < 0 else 'flat'),
                })
            if (short_balance is not None and len(short_balance) > 0
                    and margin_balance is not None and len(margin_balance) > 0):
                latest_margin_val = margin_balance.iloc[-1]
                latest_short_val = short_balance.iloc[-1]
                ratio = (latest_short_val / latest_margin_val * 100) if latest_margin_val > 0 else 0
                kpi_items.append({
                    'label': '券資比',
                    'value': format_number(ratio, kind='pct'),
                })

            render_kpi_row(kpi_items)

            if margin_balance is None:
                st.caption('💡 融資融券數據不可用，請確認 FinLab API 資料已載入')

            # ===== 第二段：法人買賣超分組長條 =====
            st.markdown(
                create_section_header('法人買賣超（近期分組）', icon='🏦'),
                unsafe_allow_html=True,
            )

            if inst_frames:
                grouped_df = pd.DataFrame(inst_frames).tail(min(analysis_days, 20))
                bar_fig = go.Figure()
                for name in inst_frames.keys():
                    bar_fig.add_trace(go.Bar(
                        x=grouped_df.index,
                        y=grouped_df[name],
                        name=name,
                        marker_color=_inst_colors.get(name, COLORS['accent']),
                    ))
                bar_fig.update_layout(barmode='group')
                bar_fig.update_yaxes(title_text='買賣超（張/股）')
                apply_dark_theme(bar_fig, height=CHART_CONFIG['height_md'], unified_hover=True)
                st.plotly_chart(bar_fig, use_container_width=True)
            else:
                st.caption('💡 法人買賣超數據不可用，請確認 FinLab API 資料已載入')

            # ===== 第三段：多日趨勢折線（價格 + 量 + 法人累計）=====
            st.markdown(
                create_section_header('多日趨勢', icon='📈'),
                unsafe_allow_html=True,
            )

            has_volume = stock_volume is not None and len(stock_volume) > 0
            trend_fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                vertical_spacing=0.06, row_heights=[0.62, 0.38],
                subplot_titles=('價格走勢', '成交量（張）' if has_volume else '成交量'),
            )

            _price_color = COLORS['up'] if price_change >= 0 else COLORS['down']
            trend_fig.add_trace(
                go.Scatter(
                    x=stock_close.index, y=stock_close.values,
                    name='收盤價', mode='lines',
                    line=dict(color=_price_color, width=2),
                ),
                row=1, col=1,
            )

            if has_volume:
                vol_in_lots = stock_volume / 1000
                # 量柱依當日漲跌上色
                close_aligned = stock_close.reindex(vol_in_lots.index)
                vol_colors = []
                prev = None
                for idx in vol_in_lots.index:
                    cur = close_aligned.get(idx)
                    if prev is None or cur is None or (isinstance(cur, float) and cur != cur):
                        vol_colors.append(COLORS['flat'])
                    else:
                        vol_colors.append(COLORS['up'] if cur >= prev else COLORS['down'])
                    if cur is not None and not (isinstance(cur, float) and cur != cur):
                        prev = cur
                trend_fig.add_trace(
                    go.Bar(
                        x=vol_in_lots.index, y=vol_in_lots.values,
                        name='成交量', marker_color=vol_colors, opacity=0.7,
                    ),
                    row=2, col=1,
                )

            apply_dark_theme(trend_fig, height=CHART_CONFIG['height_lg'], unified_hover=True)
            trend_fig.update_layout(xaxis_rangeslider_visible=False)
            st.plotly_chart(trend_fig, use_container_width=True)

            # 法人多日累計趨勢
            if institutional_df is not None and inst_frames:
                cum_fig = go.Figure()
                cum_df = pd.DataFrame(inst_frames).cumsum()
                for name in inst_frames.keys():
                    cum_fig.add_trace(go.Scatter(
                        x=cum_df.index, y=cum_df[name],
                        name=f'{name}(累計)', mode='lines',
                        line=dict(color=_inst_colors.get(name, COLORS['accent']), width=2),
                    ))
                cum_fig.update_yaxes(title_text='累計買賣超')
                apply_dark_theme(cum_fig, height=CHART_CONFIG['height_md'], unified_hover=True)
                st.plotly_chart(cum_fig, use_container_width=True)

            # ===== 第四段：可展開逐日明細 =====
            if institutional_df is not None:
                with st.expander('📋 法人買賣超逐日明細'):
                    st.dataframe(
                        institutional_df.tail(10),
                        use_container_width=True,
                    )

        else:
            st.warning(f'找不到股票 {stock_id} 的數據')

# ========== 籌碼指標 ==========
with tab2:
    st.markdown(create_section_header('籌碼指標計算器', icon='🧮'), unsafe_allow_html=True)

    with st.expander('📖 籌碼指標說明'):
        st.markdown('''
        #### 融資融券指標

        | 指標 | 說明 | 多頭訊號 | 空頭訊號 |
        |------|------|----------|----------|
        | 融資餘額 | 投資人借錢買股票的金額 | 減少 | 增加 |
        | 融券餘額 | 投資人借股票賣出的數量 | 增加 | 減少 |
        | 券資比 | 融券/融資 | > 30% | < 10% |
        | 融資使用率 | 融資餘額/融資限額 | < 20% | > 40% |

        #### 法人買賣超指標

        | 法人 | 特性 | 參考價值 |
        |------|------|----------|
        | 外資 | 資金充沛，中長期布局 | 高 |
        | 投信 | 追蹤績效，波段操作 | 中 |
        | 自營商 | 短線交易，避險為主 | 低 |

        #### 籌碼分析原則

        1. **量價配合**: 上漲放量、下跌縮量為健康型態
        2. **主力動向**: 觀察大戶與散戶籌碼變化
        3. **融資減碼**: 融資大減通常是築底訊號
        4. **法人連買**: 三大法人連續買超為正向訊號
        ''')

    col1, col2 = st.columns(2)

    with col1:
        margin_balance = st.number_input('融資餘額 (張)', 0, 1000000, 10000)
        margin_limit = st.number_input('融資限額 (張)', 0, 1000000, 50000)

    with col2:
        short_balance = st.number_input('融券餘額 (張)', 0, 1000000, 2000)
        volume_input = st.number_input('今日成交量 (張)', 0, 10000000, 5000)

    if margin_limit > 0:
        usage_rate = margin_balance / margin_limit * 100
        st.markdown(f'**融資使用率**: {usage_rate:.2f}%')

    if margin_balance > 0:
        ratio = short_balance / margin_balance * 100
        st.markdown(f'**券資比**: {ratio:.2f}%')

# ========== 籌碼排行 ==========
with tab3:
    st.markdown(create_section_header('籌碼排行榜', icon='🏆'), unsafe_allow_html=True)

    ranking_type = st.selectbox(
        '排行類型',
        ['成交量排行', '漲幅排行', '跌幅排行', '波動率排行', '量能變化排行']
    )

    ranking_days = st.selectbox(
        '統計天數',
        [1, 5, 20, 60],
        index=1
    )

    if st.button('計算排行', type='primary'):
        with st.spinner('計算中...'):
            try:
                # 取得最近數據
                recent_close = close[active_stocks].tail(ranking_days + 1)
                recent_volume = volume[active_stocks].tail(ranking_days)

                results = []

                for stock_id in active_stocks:
                    if stock_id not in recent_close.columns:
                        continue

                    stock_data = recent_close[stock_id].dropna()
                    if len(stock_data) < 2:
                        continue

                    # 計算指標
                    price_change = (stock_data.iloc[-1] / stock_data.iloc[0] - 1) * 100
                    volatility = stock_data.pct_change().std() * 100

                    # 成交量
                    if stock_id in recent_volume.columns:
                        vol_data = recent_volume[stock_id].dropna()
                        avg_volume = vol_data.mean() / 1000 if len(vol_data) > 0 else 0
                        # 量能變化 (最近5日 vs 前5日)
                        if len(vol_data) >= 10:
                            recent_vol = vol_data.tail(5).mean()
                            prev_vol = vol_data.head(5).mean()
                            vol_change = (recent_vol / prev_vol - 1) * 100 if prev_vol > 0 else 0
                        else:
                            vol_change = 0
                    else:
                        avg_volume = 0
                        vol_change = 0

                    # 股票名稱
                    info = stock_info[stock_info['stock_id'] == stock_id]
                    name = info['name'].values[0] if len(info) > 0 else ''

                    results.append({
                        '股票代碼': stock_id,
                        '股票名稱': name,
                        '收盤價': stock_data.iloc[-1],
                        '漲跌幅(%)': price_change,
                        '波動率(%)': volatility,
                        '平均成交量(張)': avg_volume,
                        '量能變化(%)': vol_change,
                    })

                df = pd.DataFrame(results)
            except Exception as e:
                show_error(e, title='計算排行失敗', suggestion='請檢查資料是否完整')
                df = pd.DataFrame()

            if len(df) > 0:
                # 根據排行類型排序
                if ranking_type == '成交量排行':
                    df = df.sort_values('平均成交量(張)', ascending=False)
                elif ranking_type == '漲幅排行':
                    df = df.sort_values('漲跌幅(%)', ascending=False)
                elif ranking_type == '跌幅排行':
                    df = df.sort_values('漲跌幅(%)', ascending=True)
                elif ranking_type == '波動率排行':
                    df = df.sort_values('波動率(%)', ascending=False)
                elif ranking_type == '量能變化排行':
                    df = df.sort_values('量能變化(%)', ascending=False)

                # 顯示前 30 名
                st.dataframe(
                    df.head(30).style.format({
                        '收盤價': '{:.2f}',
                        '漲跌幅(%)': '{:+.2f}',
                        '波動率(%)': '{:.2f}',
                        '平均成交量(張)': '{:,.0f}',
                        '量能變化(%)': '{:+.2f}',
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning('沒有符合條件的數據')

# ========== 策略選股 ==========
with tab4:
    st.markdown(create_section_header('籌碼策略選股', icon='📈'), unsafe_allow_html=True)

    with st.expander('📖 策略說明'):
        st.markdown('''
        基於籌碼指標的選股策略：

        1. **量增價漲**: 成交量放大且價格上漲
        2. **量縮價穩**: 成交量萎縮但價格持穩
        3. **突破均量**: 成交量突破近期均量
        ''')

    strategy = st.selectbox(
        '選擇策略',
        ['量增價漲', '量縮價穩', '突破均量', '爆量長紅']
    )

    col1, col2 = st.columns(2)

    with col1:
        lookback = st.number_input('回看天數', 5, 60, 20)

    with col2:
        volume_threshold = st.number_input('量能倍數', 1.0, 5.0, 1.5)

    if st.button('執行選股', type='primary', key='margin_screening'):
        with st.spinner('選股中...'):
            try:
                selected_stocks = []

                for stock_id in active_stocks:
                    if stock_id not in close.columns or stock_id not in volume.columns:
                        continue

                    stock_close = close[stock_id].dropna().tail(lookback + 1)
                    stock_volume = volume[stock_id].dropna().tail(lookback + 1)

                    if len(stock_close) < lookback or len(stock_volume) < lookback:
                        continue

                    # 計算指標
                    price_change = (stock_close.iloc[-1] / stock_close.iloc[-2] - 1) * 100
                    period_change = (stock_close.iloc[-1] / stock_close.iloc[0] - 1) * 100
                    avg_volume = stock_volume.iloc[:-1].mean()
                    today_volume = stock_volume.iloc[-1]
                    volume_ratio = today_volume / avg_volume if avg_volume > 0 else 0

                    # 策略判斷
                    selected = False

                    if strategy == '量增價漲':
                        # 今日上漲且量能放大
                        selected = price_change > 0 and volume_ratio > volume_threshold

                    elif strategy == '量縮價穩':
                        # 價格波動小且量能萎縮
                        volatility = stock_close.pct_change().std()
                        selected = abs(price_change) < 1 and volume_ratio < 0.7 and volatility < 0.02

                    elif strategy == '突破均量':
                        # 成交量突破均量
                        selected = volume_ratio > volume_threshold

                    elif strategy == '爆量長紅':
                        # 大漲且爆量
                        selected = price_change > 3 and volume_ratio > 2

                    if selected:
                        info = stock_info[stock_info['stock_id'] == stock_id]
                        name = info['name'].values[0] if len(info) > 0 else ''

                        selected_stocks.append({
                            '股票代碼': stock_id,
                            '股票名稱': name,
                            '收盤價': stock_close.iloc[-1],
                            '今日漲跌(%)': price_change,
                            '區間漲跌(%)': period_change,
                            '量能倍數': volume_ratio,
                        })
            except Exception as e:
                show_error(e, title='選股執行失敗', suggestion='請檢查選股條件或資料是否完整')
                selected_stocks = []

            if selected_stocks:
                df = pd.DataFrame(selected_stocks)
                df = df.sort_values('量能倍數', ascending=False)

                st.success(f'找到 {len(df)} 檔符合條件的股票')

                st.dataframe(
                    df.style.format({
                        '收盤價': '{:.2f}',
                        '今日漲跌(%)': '{:+.2f}',
                        '區間漲跌(%)': '{:+.2f}',
                        '量能倍數': '{:.2f}',
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                show_empty_state('沒有符合條件的股票', icon='🔍', suggestion='請嘗試調整篩選條件')

# ========== 說明 ==========
with st.expander('📖 籌碼分析說明'):
    st.markdown('''
    ### 籌碼分析的重要性

    籌碼分析是技術分析的重要組成部分，透過觀察市場參與者的行為來預測價格走勢。

    ### 主要觀察指標

    1. **融資融券**
       - 融資增加：散戶看多
       - 融券增加：市場看空
       - 券資比上升：軋空機會

    2. **法人買賣超**
       - 外資：國際資金動向
       - 投信：國內基金動向
       - 自營商：短線交易參考

    3. **量能分析**
       - 量價配合是趨勢延續的重要指標
       - 量能萎縮可能是變盤前兆

    ### 注意事項

    - 籌碼分析需要配合其他分析方法
    - 單一指標可能產生誤導
    - 建議結合基本面和技術面分析
    ''')

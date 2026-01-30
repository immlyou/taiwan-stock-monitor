"""
投資組合追蹤頁面 - 追蹤持股績效
"""
import streamlit as st
import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.data_loader import get_loader, get_active_stocks
from core.risk import RiskAnalyzer
from app.components.sidebar import render_sidebar_mini

st.set_page_config(page_title='投資組合', page_icon='💼', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='portfolio')

st.title('💼 投資組合追蹤')
st.markdown('建立並追蹤您的投資組合績效')
st.markdown('---')

# 儲存投資組合的檔案路徑
PORTFOLIO_FILE = Path(__file__).parent.parent.parent / 'data' / 'portfolios.json'
PORTFOLIO_FILE.parent.mkdir(exist_ok=True)

# 載入/儲存投資組合
def load_portfolios():
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_portfolios(portfolios):
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(portfolios, f, ensure_ascii=False, indent=2, default=str)

# 載入數據
@st.cache_data(ttl=3600, show_spinner='載入數據中...')
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'stock_info': loader.get_stock_info(),
        'benchmark': loader.get_benchmark(),
    }

try:
    data = load_data()
except Exception as e:
    st.error(f'載入數據失敗: {e}')
    st.stop()

close = data['close']
stock_info = data['stock_info']
benchmark = data['benchmark']
active_stocks = get_active_stocks()

# 股票選項
stock_options = {f"{row['stock_id']} {row['name']}": row['stock_id']
                 for _, row in stock_info.iterrows()
                 if row['stock_id'] in active_stocks}

# 載入已儲存的投資組合
portfolios = load_portfolios()

# ========== 側邊欄 - 投資組合管理 ==========
with st.sidebar:
    st.markdown('### 📁 投資組合管理')

    # 選擇現有投資組合
    portfolio_names = list(portfolios.keys())

    if portfolio_names:
        selected_portfolio = st.selectbox(
            '選擇投資組合',
            ['-- 新建投資組合 --'] + portfolio_names,
        )
    else:
        selected_portfolio = '-- 新建投資組合 --'

    # 新建投資組合
    if selected_portfolio == '-- 新建投資組合 --':
        new_name = st.text_input('投資組合名稱', placeholder='例如：我的價值組合')

        if st.button('➕ 建立投資組合', use_container_width=True):
            if new_name and new_name not in portfolios:
                portfolios[new_name] = {
                    'created_at': datetime.now().isoformat(),
                    'holdings': [],
                }
                save_portfolios(portfolios)
                st.success(f'已建立投資組合: {new_name}')
                st.rerun()
            elif new_name in portfolios:
                st.error('此名稱已存在')
            else:
                st.error('請輸入名稱')

    # 刪除投資組合
    if selected_portfolio != '-- 新建投資組合 --':
        if st.button('🗑️ 刪除此投資組合', use_container_width=True):
            del portfolios[selected_portfolio]
            save_portfolios(portfolios)
            st.success('已刪除')
            st.rerun()

# ========== 主內容區 ==========
if selected_portfolio != '-- 新建投資組合 --' and selected_portfolio in portfolios:
    portfolio = portfolios[selected_portfolio]
    holdings = portfolio.get('holdings', [])

    st.subheader(f'📊 {selected_portfolio}')
    st.caption(f"建立於: {portfolio.get('created_at', '未知')[:10]}")

    # ========== 新增持股 ==========
    st.markdown('### ➕ 新增持股')

    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

    with col1:
        add_stock_option = st.selectbox('選擇股票', list(stock_options.keys()))

    with col2:
        add_shares = st.number_input('股數', 1, 100000, 1000, 100)

    with col3:
        add_cost = st.number_input('成本價', 1.0, 10000.0, 100.0, 1.0)

    with col4:
        add_date = st.date_input('買入日期', value=date.today())

    if st.button('新增持股', use_container_width=True):
        stock_id = stock_options[add_stock_option]

        new_holding = {
            'stock_id': stock_id,
            'shares': add_shares,
            'cost_price': add_cost,
            'buy_date': add_date.isoformat(),
        }

        portfolios[selected_portfolio]['holdings'].append(new_holding)
        save_portfolios(portfolios)
        st.success(f'已新增 {stock_id}')
        st.rerun()

    st.markdown('---')

    # ========== 持股列表 ==========
    if holdings:
        st.markdown('### 📋 持股明細')

        holdings_data = []
        total_cost = 0
        total_value = 0

        for i, holding in enumerate(holdings):
            stock_id = holding['stock_id']
            shares = holding['shares']
            cost_price = holding['cost_price']
            buy_date = holding.get('buy_date', '')

            # 取得股票名稱
            info = stock_info[stock_info['stock_id'] == stock_id]
            name = info['name'].values[0] if len(info) > 0 else ''

            # 取得最新股價
            if stock_id in close.columns:
                latest_price = close[stock_id].dropna().iloc[-1]
            else:
                latest_price = cost_price

            # 計算損益
            cost_total = shares * cost_price
            value_total = shares * latest_price
            pnl = value_total - cost_total
            pnl_pct = (latest_price / cost_price - 1) * 100

            total_cost += cost_total
            total_value += value_total

            holdings_data.append({
                '序號': i + 1,
                '代號': stock_id,
                '名稱': name,
                '股數': shares,
                '成本價': cost_price,
                '現價': latest_price,
                '成本': cost_total,
                '市值': value_total,
                '損益': pnl,
                '報酬率': pnl_pct,
                '買入日期': buy_date,
            })

        holdings_df = pd.DataFrame(holdings_data)

        # 格式化顯示
        display_holdings = holdings_df[['代號', '名稱', '股數', '成本價', '現價', '損益', '報酬率']].copy()
        display_holdings['成本價'] = display_holdings['成本價'].apply(lambda x: f'{x:.2f}')
        display_holdings['現價'] = display_holdings['現價'].apply(lambda x: f'{x:.2f}')
        display_holdings['損益'] = display_holdings['損益'].apply(lambda x: f'{x:+,.0f}')
        display_holdings['報酬率'] = display_holdings['報酬率'].apply(lambda x: f'{x:+.2f}%')

        st.dataframe(display_holdings, use_container_width=True, hide_index=True)

        # 刪除持股
        delete_idx = st.selectbox(
            '選擇要刪除的持股',
            [None] + [f"{h['stock_id']} - {h['shares']}股" for h in holdings],
        )

        if delete_idx and st.button('🗑️ 刪除選中的持股'):
            idx = [f"{h['stock_id']} - {h['shares']}股" for h in holdings].index(delete_idx)
            portfolios[selected_portfolio]['holdings'].pop(idx)
            save_portfolios(portfolios)
            st.rerun()

        st.markdown('---')

        # ========== 投資組合摘要 ==========
        st.markdown('### 📊 投資組合摘要')

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric('總成本', f'{total_cost:,.0f}')

        with col2:
            st.metric('總市值', f'{total_value:,.0f}')

        with col3:
            st.metric('總損益', f'{total_pnl:+,.0f}',
                      delta=f'{total_pnl_pct:+.2f}%')

        with col4:
            st.metric('持股數', f'{len(holdings)} 檔')

        # ========== 匯出報告 ==========
        export_col1, export_col2, export_col3 = st.columns([2, 1, 1])

        with export_col2:
            if st.button('📄 匯出 PDF 報告', use_container_width=True, key='export_portfolio_pdf'):
                from core.report_generator import ReportGenerator

                generator = ReportGenerator()
                html_report = generator.generate_portfolio_html(
                    portfolio_name=selected_portfolio,
                    holdings=holdings,
                    stock_info=stock_info,
                    close=close,
                    benchmark=benchmark,
                )

                st.download_button(
                    label='下載報告 (HTML)',
                    data=html_report.encode('utf-8'),
                    file_name=f'投資組合報告_{selected_portfolio}_{datetime.now().strftime("%Y%m%d")}.html',
                    mime='text/html',
                    use_container_width=True,
                    help='下載 HTML 報告，可在瀏覽器開啟並列印為 PDF',
                    key='download_portfolio_html'
                )

        with export_col3:
            # Excel 匯出
            from core.report_generator import ReportGenerator as RG
            rg = RG()
            excel_data = rg.generate_portfolio_excel(
                holdings=holdings,
                stock_info=stock_info,
                close=close,
                portfolio_name=selected_portfolio,
            )
            st.download_button(
                label='📊 匯出 Excel',
                data=excel_data,
                file_name=f'投資組合_{selected_portfolio}_{datetime.now().strftime("%Y%m%d")}.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True,
                key='download_portfolio_excel'
            )

        st.markdown('---')

        # ========== 持股佔比 ==========
        st.markdown('### 🥧 持股佔比')

        import plotly.express as px

        holdings_df['佔比'] = holdings_df['市值'] / total_value * 100

        fig_pie = px.pie(
            holdings_df,
            values='市值',
            names='名稱',
            title='持股市值佔比',
        )

        fig_pie.update_traces(textposition='inside', textinfo='percent+label')

        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown('---')

        # ========== 績效追蹤 ==========
        st.markdown('### 📈 績效追蹤')

        # 計算投資組合歷史績效
        weights = {}
        for holding in holdings:
            stock_id = holding['stock_id']
            value = holding['shares'] * close[stock_id].dropna().iloc[-1] if stock_id in close.columns else 0
            weights[stock_id] = value

        total_weight = sum(weights.values())
        weights = {k: v / total_weight for k, v in weights.items() if total_weight > 0}

        available_stocks = [s for s in weights.keys() if s in close.columns]

        if available_stocks:
            close_period = close[available_stocks].tail(252)
            weight_series = pd.Series({s: weights[s] for s in available_stocks})

            portfolio_returns = (close_period.pct_change() * weight_series).sum(axis=1).dropna()
            portfolio_value = (1 + portfolio_returns).cumprod()

            # 與大盤比較
            benchmark_period = benchmark.tail(252)
            benchmark_normalized = benchmark_period / benchmark_period.iloc[0]

            import plotly.graph_objects as go

            fig_perf = go.Figure()

            fig_perf.add_trace(go.Scatter(
                x=portfolio_value.index,
                y=(portfolio_value - 1) * 100,
                name='投資組合',
                line=dict(color='blue', width=2),
            ))

            fig_perf.add_trace(go.Scatter(
                x=benchmark_normalized.index,
                y=(benchmark_normalized - 1) * 100,
                name='大盤',
                line=dict(color='gray', width=1, dash='dash'),
            ))

            fig_perf.update_layout(
                title='近一年累積報酬',
                xaxis_title='日期',
                yaxis_title='累積報酬 (%)',
                hovermode='x unified',
                height=400,
            )

            st.plotly_chart(fig_perf, use_container_width=True)

            # 績效統計
            col1, col2, col3, col4 = st.columns(4)

            analyzer = RiskAnalyzer()
            benchmark_returns = benchmark_period.pct_change().dropna()

            vol = analyzer.calculate_volatility(portfolio_returns)
            max_dd, _, _ = analyzer.calculate_max_drawdown(portfolio_value)
            beta = analyzer.calculate_beta(portfolio_returns, benchmark_returns)

            with col1:
                annual_return = portfolio_returns.mean() * 252
                st.metric('年化報酬', f'{annual_return * 100:.2f}%')

            with col2:
                st.metric('年化波動率', f'{vol * 100:.2f}%')

            with col3:
                st.metric('最大回撤', f'{max_dd * 100:.2f}%')

            with col4:
                sharpe = annual_return / vol if vol > 0 else 0
                st.metric('Sharpe Ratio', f'{sharpe:.2f}')

    else:
        st.info('此投資組合尚無持股，請在上方新增持股。')

else:
    st.info('請在側邊欄選擇或建立投資組合')

# ========== 說明 ==========
with st.expander('📖 使用說明'):
    st.markdown('''
    ### 如何使用投資組合追蹤

    1. **建立投資組合**：在側邊欄輸入名稱並點擊建立
    2. **新增持股**：選擇股票、輸入股數、成本價和買入日期
    3. **追蹤績效**：系統會自動計算損益、報酬率、與大盤比較

    ### 注意事項

    - 投資組合資料儲存在本地，換電腦不會同步
    - 成本價應輸入您實際的買入價格（含手續費攤提後）
    - 績效計算使用當日收盤價

    ### 指標說明

    | 指標 | 說明 |
    |------|------|
    | 年化報酬 | 換算成一年的報酬率 |
    | 年化波動率 | 報酬率的標準差（風險指標）|
    | 最大回撤 | 歷史最大跌幅 |
    | Sharpe Ratio | 風險調整後報酬，越高越好 |
    ''')

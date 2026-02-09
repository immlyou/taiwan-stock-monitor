"""
圖表元件模組 - 使用 Plotly 建立各種視覺化圖表
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any

from app.components.theme import DEFAULT_PLOTLY_LAYOUT, COLORS, CHART_PALETTE


def apply_dark_theme(fig, height=400, **kwargs):
    """套用統一深色主題到任何 Plotly 圖表"""
    layout_args = {**DEFAULT_PLOTLY_LAYOUT, 'height': height, **kwargs}
    fig.update_layout(**layout_args)
    return fig


def render_chart(fig, title: Optional[str] = None, use_container_width: bool = True):
    """在深色容器中渲染 Plotly 圖表"""
    apply_dark_theme(fig)
    html_parts = []
    if title:
        html_parts.append(f'<div class="chart-title">{title}</div>')
    if html_parts:
        st.markdown(f'<div class="chart-container">{"".join(html_parts)}</div>', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=use_container_width)


def create_price_chart(df: pd.DataFrame,
                       stock_id: str,
                       show_volume: bool = True,
                       show_ma: List[int] = [5, 20, 60],
                       show_bollinger: bool = False,
                       title: Optional[str] = None) -> go.Figure:
    """
    建立股價走勢圖

    Parameters:
    -----------
    df : pd.DataFrame
        價格數據，需包含 OHLCV 欄位
    stock_id : str
        股票代號
    show_volume : bool
        是否顯示成交量
    show_ma : list
        要顯示的移動平均線週期
    title : str
        圖表標題
    """
    if show_volume:
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                           vertical_spacing=0.03,
                           row_heights=[0.7, 0.3])
    else:
        fig = go.Figure()

    # K 線圖
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['open'] if 'open' in df.columns else df['close'],
            high=df['high'] if 'high' in df.columns else df['close'],
            low=df['low'] if 'low' in df.columns else df['close'],
            close=df['close'],
            name='K線',
            increasing_line_color=COLORS['up'],
            decreasing_line_color=COLORS['down'],
        ),
        row=1 if show_volume else None,
        col=1 if show_volume else None
    )

    # 移動平均線
    for i, period in enumerate(show_ma):
        ma = df['close'].rolling(window=period).mean()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=ma,
                name=f'MA{period}',
                line=dict(color=CHART_PALETTE[i % len(CHART_PALETTE)], width=1),
            ),
            row=1 if show_volume else None,
            col=1 if show_volume else None
        )

    # 布林通道
    if show_bollinger:
        period = 20
        std_dev = 2
        middle = df['close'].rolling(window=period).mean()
        rolling_std = df['close'].rolling(window=period).std()
        upper = middle + (rolling_std * std_dev)
        lower = middle - (rolling_std * std_dev)

        # 上軌
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=upper,
                name='布林上軌',
                line=dict(color='rgba(128, 128, 128, 0.5)', width=1, dash='dash'),
            ),
            row=1 if show_volume else None,
            col=1 if show_volume else None
        )

        # 中軌
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=middle,
                name='布林中軌',
                line=dict(color='rgba(128, 128, 128, 0.7)', width=1),
            ),
            row=1 if show_volume else None,
            col=1 if show_volume else None
        )

        # 下軌
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=lower,
                name='布林下軌',
                line=dict(color='rgba(128, 128, 128, 0.5)', width=1, dash='dash'),
                fill='tonexty',
                fillcolor='rgba(128, 128, 128, 0.1)',
            ),
            row=1 if show_volume else None,
            col=1 if show_volume else None
        )

    # 成交量
    if show_volume and 'volume' in df.columns:
        colors_vol = [COLORS['down'] if df['close'].iloc[i] < df['close'].iloc[i-1]
                      else COLORS['up'] for i in range(1, len(df))]
        colors_vol.insert(0, COLORS['up'])

        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['volume'],
                name='成交量',
                marker_color=colors_vol,
                opacity=0.7,
            ),
            row=2, col=1
        )

    # 設定
    apply_dark_theme(fig,
        height=600 if show_volume else 400,
        title=title or f'{stock_id} 股價走勢',
        xaxis_rangeslider_visible=False,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )

    # 根據是否有 subplots 來設定軸標題
    if show_volume:
        fig.update_xaxes(title_text='日期', row=2, col=1)
        fig.update_yaxes(title_text='價格', row=1, col=1)
        fig.update_yaxes(title_text='成交量', row=2, col=1)
    else:
        fig.update_xaxes(title_text='日期')
        fig.update_yaxes(title_text='價格')

    return fig


def create_portfolio_chart(portfolio_values: pd.Series,
                           benchmark: Optional[pd.Series] = None,
                           title: str = '投資組合淨值走勢') -> go.Figure:
    """
    建立投資組合淨值走勢圖

    Parameters:
    -----------
    portfolio_values : pd.Series
        投資組合淨值
    benchmark : pd.Series, optional
        大盤指數
    title : str
        圖表標題
    """
    fig = go.Figure()

    # 投資組合曲線
    portfolio_normalized = portfolio_values / portfolio_values.iloc[0] * 100
    fig.add_trace(
        go.Scatter(
            x=portfolio_values.index,
            y=portfolio_normalized,
            name='投資組合',
            line=dict(color=CHART_PALETTE[0], width=2),
            fill='tozeroy',
            fillcolor='rgba(59, 130, 246, 0.1)',
        )
    )

    # 大盤曲線
    if benchmark is not None:
        # 對齊日期
        common_dates = portfolio_values.index.intersection(benchmark.index)
        benchmark_aligned = benchmark.loc[common_dates]
        benchmark_normalized = benchmark_aligned / benchmark_aligned.iloc[0] * 100

        fig.add_trace(
            go.Scatter(
                x=benchmark_normalized.index,
                y=benchmark_normalized,
                name='大盤指數',
                line=dict(color=COLORS['up'], width=2, dash='dash'),
            )
        )

    apply_dark_theme(fig,
        height=400,
        title=title,
        xaxis_title='日期',
        yaxis_title='淨值 (基期=100)',
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
        hovermode='x unified',
    )

    return fig


def create_drawdown_chart(portfolio_values: pd.Series,
                          title: str = '回撤分析') -> go.Figure:
    """建立回撤圖"""
    rolling_max = portfolio_values.cummax()
    drawdown = (portfolio_values - rolling_max) / rolling_max * 100

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=drawdown.index,
            y=drawdown,
            name='回撤',
            fill='tozeroy',
            fillcolor='rgba(239, 68, 68, 0.3)',
            line=dict(color=COLORS['up'], width=1),
        )
    )

    # 標記最大回撤點
    max_dd_idx = drawdown.idxmin()
    max_dd_value = drawdown.min()

    fig.add_annotation(
        x=max_dd_idx,
        y=max_dd_value,
        text=f'最大回撤: {max_dd_value:.2f}%',
        showarrow=True,
        arrowhead=2,
        font=dict(color=COLORS['text_primary']),
        arrowcolor=COLORS['text_secondary'],
    )

    apply_dark_theme(fig,
        height=300,
        title=title,
        xaxis_title='日期',
        yaxis_title='回撤 (%)',
    )

    return fig


def create_metrics_gauge(value: float,
                         title: str,
                         min_val: float = 0,
                         max_val: float = 100,
                         thresholds: Optional[Dict[str, float]] = None) -> go.Figure:
    """
    建立指標儀表板
    """
    if thresholds is None:
        thresholds = {'poor': 25, 'fair': 50, 'good': 75}

    fig = go.Figure(go.Indicator(
        mode='gauge+number',
        value=value,
        title={'text': title},
        gauge={
            'axis': {'range': [min_val, max_val]},
            'bar': {'color': CHART_PALETTE[0]},
            'steps': [
                {'range': [min_val, thresholds['poor']], 'color': '#FF6B6B'},
                {'range': [thresholds['poor'], thresholds['fair']], 'color': '#FFD93D'},
                {'range': [thresholds['fair'], thresholds['good']], 'color': '#6BCB77'},
                {'range': [thresholds['good'], max_val], 'color': '#4D96FF'},
            ],
        }
    ))

    apply_dark_theme(fig, height=250)

    return fig


def create_pie_chart(labels: List[str],
                     values: List[float],
                     title: str = '持股分佈') -> go.Figure:
    """建立圓餅圖"""
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        textinfo='label+percent',
    )])

    apply_dark_theme(fig, height=400, title=title)

    return fig


def create_bar_chart(df: pd.DataFrame,
                     x: str,
                     y: str,
                     title: str,
                     color: Optional[str] = None,
                     orientation: str = 'v') -> go.Figure:
    """建立長條圖"""
    fig = px.bar(
        df,
        x=x if orientation == 'v' else y,
        y=y if orientation == 'v' else x,
        color=color,
        title=title,
        orientation=orientation,
    )

    apply_dark_theme(fig, height=400)

    return fig


def create_heatmap(df: pd.DataFrame,
                   title: str = '相關性矩陣') -> go.Figure:
    """建立熱力圖"""
    fig = go.Figure(data=go.Heatmap(
        z=df.values,
        x=df.columns,
        y=df.index,
        colorscale='RdYlGn',
        zmid=0,
    ))

    apply_dark_theme(fig, height=500, title=title)

    return fig


def create_monthly_returns_heatmap(returns: pd.Series,
                                   title: str = '月報酬率熱力圖') -> go.Figure:
    """建立月報酬率熱力圖"""
    # 轉換為月報酬
    monthly = returns.resample('M').apply(lambda x: (1 + x).prod() - 1) * 100

    # 建立年-月矩陣
    df = pd.DataFrame({
        'year': monthly.index.year,
        'month': monthly.index.month,
        'return': monthly.values
    })

    pivot = df.pivot(index='year', columns='month', values='return')
    pivot.columns = ['一月', '二月', '三月', '四月', '五月', '六月',
                     '七月', '八月', '九月', '十月', '十一月', '十二月']

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale='RdYlGn',
        zmid=0,
        text=np.round(pivot.values, 1),
        texttemplate='%{text}%',
        textfont={'size': 10},
    ))

    apply_dark_theme(fig, height=400, title=title)

    return fig


def create_scatter_plot(df: pd.DataFrame,
                        x: str,
                        y: str,
                        title: str,
                        color: Optional[str] = None,
                        size: Optional[str] = None,
                        hover_data: Optional[List[str]] = None) -> go.Figure:
    """建立散點圖"""
    fig = px.scatter(
        df,
        x=x,
        y=y,
        color=color,
        size=size,
        hover_data=hover_data,
        title=title,
    )

    apply_dark_theme(fig, height=500)

    return fig


def create_technical_chart(close: pd.Series,
                           indicators: Dict[str, pd.Series],
                           title: str = '技術分析圖') -> go.Figure:
    """
    建立技術分析圖

    Parameters:
    -----------
    close : pd.Series
        收盤價
    indicators : dict
        指標字典，如 {'RSI': rsi_series, 'MACD': macd_series}
    title : str
        圖表標題
    """
    n_indicators = len(indicators)
    heights = [0.5] + [0.5 / n_indicators] * n_indicators

    fig = make_subplots(
        rows=1 + n_indicators,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=heights,
    )

    # 價格
    fig.add_trace(
        go.Scatter(x=close.index, y=close, name='收盤價', line=dict(width=1)),
        row=1, col=1
    )

    # 各指標
    for i, (name, series) in enumerate(indicators.items(), start=2):
        fig.add_trace(
            go.Scatter(x=series.index, y=series, name=name, line=dict(width=1)),
            row=i, col=1
        )
        fig.update_yaxes(title_text=name, row=i, col=1)

    apply_dark_theme(fig,
        height=200 + 150 * n_indicators,
        title=title,
        legend=dict(orientation='h', yanchor='bottom', y=1.02),
    )

    return fig

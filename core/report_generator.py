"""
報告生成模組 - 產生 PDF、HTML 和 Excel 報告
支援：
- 個股分析報告（基本面 + 技術面）
- 選股結果報告
- 投資組合績效報告
"""
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import io
import base64
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


class PDFReportGenerator:
    """
    PDF/HTML 報告生成器

    使用 HTML 格式生成報告，可直接在瀏覽器中列印成 PDF。
    """

    # 報告樣式模板
    CSS_TEMPLATE = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap');

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Noto Sans TC', 'Microsoft JhengHei', sans-serif;
            font-size: 12px;
            line-height: 1.6;
            color: #333;
            background: #fff;
        }

        .report-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }

        .report-header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #1e3a5f;
        }

        .report-title {
            font-size: 28px;
            font-weight: 700;
            color: #1e3a5f;
            margin-bottom: 10px;
        }

        .report-subtitle {
            font-size: 14px;
            color: #666;
        }

        .report-date {
            font-size: 12px;
            color: #888;
            margin-top: 5px;
        }

        .section {
            margin-bottom: 25px;
            page-break-inside: avoid;
        }

        .section-title {
            font-size: 16px;
            font-weight: 700;
            color: #1e3a5f;
            margin-bottom: 15px;
            padding-bottom: 5px;
            border-bottom: 2px solid #e0e0e0;
        }

        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 20px;
        }

        .metric-card {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #dee2e6;
        }

        .metric-label {
            font-size: 11px;
            color: #666;
            margin-bottom: 5px;
        }

        .metric-value {
            font-size: 18px;
            font-weight: 700;
            color: #1e3a5f;
        }

        .metric-value.positive {
            color: #28a745;
        }

        .metric-value.negative {
            color: #dc3545;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
            font-size: 11px;
        }

        th, td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }

        th {
            background: #1e3a5f;
            color: #fff;
            font-weight: 500;
            text-transform: uppercase;
            font-size: 10px;
            letter-spacing: 0.5px;
        }

        tr:nth-child(even) {
            background: #f8f9fa;
        }

        tr:hover {
            background: #e9ecef;
        }

        .text-right {
            text-align: right;
        }

        .text-center {
            text-align: center;
        }

        .positive {
            color: #28a745;
        }

        .negative {
            color: #dc3545;
        }

        .chart-container {
            margin: 20px 0;
            text-align: center;
        }

        .chart-container img {
            max-width: 100%;
            height: auto;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
        }

        .summary-box {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }

        .summary-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
        }

        .summary-row:last-child {
            border-bottom: none;
        }

        .summary-label {
            color: #666;
        }

        .summary-value {
            font-weight: 600;
        }

        .footer {
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #888;
            font-size: 10px;
        }

        .page-break {
            page-break-before: always;
        }

        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 500;
        }

        .badge-success {
            background: #d4edda;
            color: #155724;
        }

        .badge-danger {
            background: #f8d7da;
            color: #721c24;
        }

        .badge-warning {
            background: #fff3cd;
            color: #856404;
        }

        .badge-info {
            background: #cce5ff;
            color: #004085;
        }

        .analysis-text {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin-top: 10px;
            font-size: 12px;
            line-height: 1.8;
        }

        .indicator-row {
            display: flex;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }

        .indicator-name {
            width: 120px;
            font-weight: 500;
        }

        .indicator-value {
            width: 80px;
            text-align: right;
            font-weight: 600;
        }

        .indicator-signal {
            flex: 1;
            text-align: right;
        }

        @media print {
            body {
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }

            .report-container {
                padding: 0;
            }

            .page-break {
                page-break-before: always;
            }
        }
    </style>
    """

    def __init__(self):
        """初始化報告生成器"""
        pass

    def _get_value_class(self, value: float) -> str:
        """根據數值正負返回 CSS 類別"""
        if value > 0:
            return 'positive'
        elif value < 0:
            return 'negative'
        return ''

    def _format_number(self, value: float, decimals: int = 2, prefix: str = '', suffix: str = '') -> str:
        """格式化數字"""
        if pd.isna(value):
            return '-'
        if abs(value) >= 1e8:
            return f'{prefix}{value/1e8:.{decimals}f}億{suffix}'
        if abs(value) >= 1e4:
            return f'{prefix}{value/1e4:.{decimals}f}萬{suffix}'
        return f'{prefix}{value:,.{decimals}f}{suffix}'

    def _format_percent(self, value: float, decimals: int = 2) -> str:
        """格式化百分比"""
        if pd.isna(value):
            return '-'
        sign = '+' if value > 0 else ''
        return f'{sign}{value:.{decimals}f}%'

    def generate_stock_analysis_html(
        self,
        stock_id: str,
        stock_name: str,
        category: str,
        market: str,
        close: pd.Series,
        volume: pd.Series,
        fundamental_data: Dict[str, Any],
        technical_data: Dict[str, Any],
        chart_base64: Optional[str] = None,
    ) -> str:
        """
        生成個股分析報告 HTML

        Parameters:
        -----------
        stock_id : str
            股票代號
        stock_name : str
            股票名稱
        category : str
            產業類別
        market : str
            市場
        close : pd.Series
            收盤價
        volume : pd.Series
            成交量
        fundamental_data : dict
            基本面資料 (pe, pb, dividend_yield, eps, revenue_yoy 等)
        technical_data : dict
            技術面資料 (rsi, macd, ma 等)
        chart_base64 : str, optional
            圖表的 base64 編碼圖片

        Returns:
        --------
        str
            HTML 報告內容
        """
        now = datetime.now()
        latest_price = close.iloc[-1] if len(close) > 0 else 0
        prev_price = close.iloc[-2] if len(close) > 1 else latest_price
        change = latest_price - prev_price
        change_pct = (change / prev_price * 100) if prev_price != 0 else 0

        # 計算區間報酬
        week_return = ((close.iloc[-1] / close.iloc[-5] - 1) * 100) if len(close) >= 5 else 0
        month_return = ((close.iloc[-1] / close.iloc[-20] - 1) * 100) if len(close) >= 20 else 0
        quarter_return = ((close.iloc[-1] / close.iloc[-60] - 1) * 100) if len(close) >= 60 else 0
        year_return = ((close.iloc[-1] / close.iloc[-252] - 1) * 100) if len(close) >= 252 else 0

        # 計算統計數據
        high_52w = close.tail(252).max() if len(close) >= 252 else close.max()
        low_52w = close.tail(252).min() if len(close) >= 252 else close.min()
        avg_volume = volume.tail(20).mean() if volume is not None and len(volume) >= 20 else 0

        # 技術指標信號判斷
        def get_signal(indicator: str, value: float) -> Tuple[str, str]:
            """返回技術指標信號和樣式"""
            if indicator == 'rsi':
                if value > 70:
                    return '超買', 'badge-danger'
                elif value < 30:
                    return '超賣', 'badge-success'
                else:
                    return '中性', 'badge-info'
            elif indicator == 'macd':
                if value > 0:
                    return '多頭', 'badge-success'
                else:
                    return '空頭', 'badge-danger'
            elif indicator == 'ma':
                if value > 0:
                    return '站上均線', 'badge-success'
                else:
                    return '跌破均線', 'badge-warning'
            return '中性', 'badge-info'

        rsi_val = technical_data.get('rsi', 50)
        macd_val = technical_data.get('macd', 0)
        ma20_diff = technical_data.get('ma20_diff', 0)

        rsi_signal, rsi_badge = get_signal('rsi', rsi_val)
        macd_signal, macd_badge = get_signal('macd', macd_val)
        ma_signal, ma_badge = get_signal('ma', ma20_diff)

        # 生成 HTML
        html = f"""
        <!DOCTYPE html>
        <html lang="zh-TW">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{stock_id} {stock_name} 分析報告</title>
            {self.CSS_TEMPLATE}
        </head>
        <body>
            <div class="report-container">
                <div class="report-header">
                    <div class="report-title">{stock_id} {stock_name}</div>
                    <div class="report-subtitle">{category} | {market}</div>
                    <div class="report-date">報告生成時間：{now.strftime('%Y-%m-%d %H:%M')}</div>
                </div>

                <!-- 股價概況 -->
                <div class="section">
                    <div class="section-title">股價概況</div>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-label">最新股價</div>
                            <div class="metric-value">{latest_price:.2f}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">漲跌幅</div>
                            <div class="metric-value {self._get_value_class(change_pct)}">{self._format_percent(change_pct)}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">52週高點</div>
                            <div class="metric-value">{high_52w:.2f}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">52週低點</div>
                            <div class="metric-value">{low_52w:.2f}</div>
                        </div>
                    </div>

                    <div class="summary-box">
                        <div class="summary-row">
                            <span class="summary-label">近一週報酬</span>
                            <span class="summary-value {self._get_value_class(week_return)}">{self._format_percent(week_return)}</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">近一月報酬</span>
                            <span class="summary-value {self._get_value_class(month_return)}">{self._format_percent(month_return)}</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">近一季報酬</span>
                            <span class="summary-value {self._get_value_class(quarter_return)}">{self._format_percent(quarter_return)}</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">近一年報酬</span>
                            <span class="summary-value {self._get_value_class(year_return)}">{self._format_percent(year_return)}</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">20日均量</span>
                            <span class="summary-value">{self._format_number(avg_volume, 0)}</span>
                        </div>
                    </div>
                </div>
        """

        # 圖表區（如果有的話）
        if chart_base64:
            html += f"""
                <div class="section">
                    <div class="section-title">走勢圖</div>
                    <div class="chart-container">
                        <img src="data:image/png;base64,{chart_base64}" alt="股價走勢圖" />
                    </div>
                </div>
            """

        # 基本面分析
        pe = fundamental_data.get('pe', None)
        pb = fundamental_data.get('pb', None)
        dividend_yield = fundamental_data.get('dividend_yield', None)
        eps = fundamental_data.get('eps', None)
        revenue_yoy = fundamental_data.get('revenue_yoy', None)
        revenue_mom = fundamental_data.get('revenue_mom', None)
        market_value = fundamental_data.get('market_value', None)

        html += f"""
                <!-- 基本面分析 -->
                <div class="section">
                    <div class="section-title">基本面分析</div>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-label">本益比 (PE)</div>
                            <div class="metric-value">{f'{pe:.2f}' if pe else '-'}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">股價淨值比 (PB)</div>
                            <div class="metric-value">{f'{pb:.2f}' if pb else '-'}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">殖利率</div>
                            <div class="metric-value">{f'{dividend_yield:.2f}%' if dividend_yield else '-'}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">每股盈餘</div>
                            <div class="metric-value">{f'{eps:.2f}' if eps else '-'}</div>
                        </div>
                    </div>

                    <table>
                        <thead>
                            <tr>
                                <th>指標</th>
                                <th class="text-right">數值</th>
                                <th class="text-right">說明</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>營收年增率</td>
                                <td class="text-right {self._get_value_class(revenue_yoy) if revenue_yoy else ''}">{self._format_percent(revenue_yoy) if revenue_yoy else '-'}</td>
                                <td class="text-right">與去年同期比較</td>
                            </tr>
                            <tr>
                                <td>營收月增率</td>
                                <td class="text-right {self._get_value_class(revenue_mom) if revenue_mom else ''}">{self._format_percent(revenue_mom) if revenue_mom else '-'}</td>
                                <td class="text-right">與上個月比較</td>
                            </tr>
                            <tr>
                                <td>市值</td>
                                <td class="text-right">{self._format_number(market_value, 0) if market_value else '-'}</td>
                                <td class="text-right">股價 x 流通股數</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <!-- 技術面分析 -->
                <div class="section">
                    <div class="section-title">技術面分析</div>
                    <div class="summary-box">
                        <div class="indicator-row">
                            <div class="indicator-name">RSI (14日)</div>
                            <div class="indicator-value">{rsi_val:.1f}</div>
                            <div class="indicator-signal"><span class="badge {rsi_badge}">{rsi_signal}</span></div>
                        </div>
                        <div class="indicator-row">
                            <div class="indicator-name">MACD</div>
                            <div class="indicator-value">{macd_val:.2f}</div>
                            <div class="indicator-signal"><span class="badge {macd_badge}">{macd_signal}</span></div>
                        </div>
                        <div class="indicator-row">
                            <div class="indicator-name">20日均線</div>
                            <div class="indicator-value">{technical_data.get('ma20', 0):.2f}</div>
                            <div class="indicator-signal"><span class="badge {ma_badge}">{ma_signal}</span></div>
                        </div>
                        <div class="indicator-row">
                            <div class="indicator-name">60日均線</div>
                            <div class="indicator-value">{technical_data.get('ma60', 0):.2f}</div>
                            <div class="indicator-signal">-</div>
                        </div>
                        <div class="indicator-row">
                            <div class="indicator-name">布林通道上軌</div>
                            <div class="indicator-value">{technical_data.get('bb_upper', 0):.2f}</div>
                            <div class="indicator-signal">-</div>
                        </div>
                        <div class="indicator-row">
                            <div class="indicator-name">布林通道下軌</div>
                            <div class="indicator-value">{technical_data.get('bb_lower', 0):.2f}</div>
                            <div class="indicator-signal">-</div>
                        </div>
                    </div>
                </div>

                <div class="footer">
                    <p>本報告由 FinLab DB 系統自動產生，僅供參考，不構成投資建議。</p>
                    <p>投資有風險，入市需謹慎。</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def generate_screening_html(
        self,
        strategy_name: str,
        params: Dict[str, Any],
        stocks: List[str],
        scores: Optional[pd.Series],
        stock_info: pd.DataFrame,
        close: pd.DataFrame,
    ) -> str:
        """
        生成選股結果報告 HTML

        Parameters:
        -----------
        strategy_name : str
            策略名稱
        params : dict
            策略參數
        stocks : list
            選股結果
        scores : pd.Series
            評分
        stock_info : pd.DataFrame
            股票資訊
        close : pd.DataFrame
            收盤價

        Returns:
        --------
        str
            HTML 報告內容
        """
        now = datetime.now()

        # 準備股票資料
        stock_data = []
        for stock_id in stocks:
            info = stock_info[stock_info['stock_id'] == stock_id]
            name = info['name'].values[0] if len(info) > 0 else ''
            category = info['category'].values[0] if len(info) > 0 else ''

            if stock_id in close.columns:
                stock_close = close[stock_id].dropna()
                latest_price = stock_close.iloc[-1] if len(stock_close) > 0 else None
                week_return = ((stock_close.iloc[-1] / stock_close.iloc[-5] - 1) * 100) if len(stock_close) >= 5 else None
                month_return = ((stock_close.iloc[-1] / stock_close.iloc[-20] - 1) * 100) if len(stock_close) >= 20 else None
            else:
                latest_price = None
                week_return = None
                month_return = None

            score = scores.get(stock_id, 0) if scores is not None and stock_id in scores.index else 0

            stock_data.append({
                'stock_id': stock_id,
                'name': name,
                'category': category,
                'price': latest_price,
                'score': score,
                'week_return': week_return,
                'month_return': month_return,
            })

        # 產業分布統計
        industry_counts = {}
        for s in stock_data:
            cat = s['category'] or '未分類'
            industry_counts[cat] = industry_counts.get(cat, 0) + 1

        # 參數說明
        params_html = ""
        for k, v in params.items():
            params_html += f"<div class='summary-row'><span class='summary-label'>{k}</span><span class='summary-value'>{v}</span></div>"

        # 股票列表
        stocks_html = ""
        for i, s in enumerate(stock_data, 1):
            week_class = self._get_value_class(s['week_return']) if s['week_return'] else ''
            month_class = self._get_value_class(s['month_return']) if s['month_return'] else ''

            stocks_html += f"""
            <tr>
                <td class="text-center">{i}</td>
                <td>{s['stock_id']}</td>
                <td>{s['name']}</td>
                <td>{s['category']}</td>
                <td class="text-right">{f"{s['price']:.2f}" if s['price'] else '-'}</td>
                <td class="text-right">{f"{s['score']:.1f}" if s['score'] else '-'}</td>
                <td class="text-right {week_class}">{self._format_percent(s['week_return']) if s['week_return'] else '-'}</td>
                <td class="text-right {month_class}">{self._format_percent(s['month_return']) if s['month_return'] else '-'}</td>
            </tr>
            """

        # 產業分布
        industry_html = ""
        for cat, count in sorted(industry_counts.items(), key=lambda x: x[1], reverse=True):
            pct = count / len(stock_data) * 100
            industry_html += f"""
            <tr>
                <td>{cat}</td>
                <td class="text-right">{count}</td>
                <td class="text-right">{pct:.1f}%</td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html lang="zh-TW">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{strategy_name} 選股報告</title>
            {self.CSS_TEMPLATE}
        </head>
        <body>
            <div class="report-container">
                <div class="report-header">
                    <div class="report-title">{strategy_name} 選股報告</div>
                    <div class="report-subtitle">共篩選出 {len(stocks)} 檔股票</div>
                    <div class="report-date">報告生成時間：{now.strftime('%Y-%m-%d %H:%M')}</div>
                </div>

                <!-- 策略參數 -->
                <div class="section">
                    <div class="section-title">策略參數</div>
                    <div class="summary-box">
                        {params_html}
                    </div>
                </div>

                <!-- 選股統計 -->
                <div class="section">
                    <div class="section-title">選股統計</div>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-label">選股數量</div>
                            <div class="metric-value">{len(stocks)}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">平均評分</div>
                            <div class="metric-value">{np.mean([s['score'] for s in stock_data if s['score']]):.1f}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">涵蓋產業數</div>
                            <div class="metric-value">{len(industry_counts)}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">最高評分</div>
                            <div class="metric-value">{max([s['score'] for s in stock_data if s['score']], default=0):.1f}</div>
                        </div>
                    </div>
                </div>

                <!-- 選股結果 -->
                <div class="section">
                    <div class="section-title">選股結果</div>
                    <table>
                        <thead>
                            <tr>
                                <th class="text-center">#</th>
                                <th>代號</th>
                                <th>名稱</th>
                                <th>產業</th>
                                <th class="text-right">股價</th>
                                <th class="text-right">評分</th>
                                <th class="text-right">週報酬</th>
                                <th class="text-right">月報酬</th>
                            </tr>
                        </thead>
                        <tbody>
                            {stocks_html}
                        </tbody>
                    </table>
                </div>

                <!-- 產業分布 -->
                <div class="section page-break">
                    <div class="section-title">產業分布</div>
                    <table>
                        <thead>
                            <tr>
                                <th>產業</th>
                                <th class="text-right">股票數</th>
                                <th class="text-right">佔比</th>
                            </tr>
                        </thead>
                        <tbody>
                            {industry_html}
                        </tbody>
                    </table>
                </div>

                <div class="footer">
                    <p>本報告由 FinLab DB 系統自動產生，僅供參考，不構成投資建議。</p>
                    <p>投資有風險，入市需謹慎。</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def generate_portfolio_html(
        self,
        portfolio_name: str,
        holdings: List[Dict],
        stock_info: pd.DataFrame,
        close: pd.DataFrame,
        benchmark: Optional[pd.Series] = None,
    ) -> str:
        """
        生成投資組合績效報告 HTML

        Parameters:
        -----------
        portfolio_name : str
            投資組合名稱
        holdings : list
            持股列表
        stock_info : pd.DataFrame
            股票資訊
        close : pd.DataFrame
            收盤價
        benchmark : pd.Series, optional
            大盤指數

        Returns:
        --------
        str
            HTML 報告內容
        """
        now = datetime.now()

        # 計算持股資料
        holdings_data = []
        total_cost = 0
        total_value = 0

        for holding in holdings:
            stock_id = holding['stock_id']
            shares = holding['shares']
            cost_price = holding['cost_price']
            buy_date = holding.get('buy_date', '')

            info = stock_info[stock_info['stock_id'] == stock_id]
            name = info['name'].values[0] if len(info) > 0 else ''
            category = info['category'].values[0] if len(info) > 0 else ''

            if stock_id in close.columns:
                latest_price = close[stock_id].dropna().iloc[-1]
            else:
                latest_price = cost_price

            cost_total = shares * cost_price
            value_total = shares * latest_price
            pnl = value_total - cost_total
            pnl_pct = (latest_price / cost_price - 1) * 100

            total_cost += cost_total
            total_value += value_total

            holdings_data.append({
                'stock_id': stock_id,
                'name': name,
                'category': category,
                'shares': shares,
                'cost_price': cost_price,
                'latest_price': latest_price,
                'cost_total': cost_total,
                'value_total': value_total,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'buy_date': buy_date,
            })

        total_pnl = total_value - total_cost
        total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0

        # 持股明細
        holdings_html = ""
        for h in holdings_data:
            pnl_class = self._get_value_class(h['pnl'])
            weight = h['value_total'] / total_value * 100 if total_value > 0 else 0

            holdings_html += f"""
            <tr>
                <td>{h['stock_id']}</td>
                <td>{h['name']}</td>
                <td class="text-right">{h['shares']:,}</td>
                <td class="text-right">{h['cost_price']:.2f}</td>
                <td class="text-right">{h['latest_price']:.2f}</td>
                <td class="text-right">{self._format_number(h['value_total'], 0)}</td>
                <td class="text-right {pnl_class}">{self._format_number(h['pnl'], 0, prefix='+' if h['pnl'] > 0 else '')}</td>
                <td class="text-right {pnl_class}">{self._format_percent(h['pnl_pct'])}</td>
                <td class="text-right">{weight:.1f}%</td>
            </tr>
            """

        # 產業配置
        industry_allocation = {}
        for h in holdings_data:
            cat = h['category'] or '未分類'
            industry_allocation[cat] = industry_allocation.get(cat, 0) + h['value_total']

        industry_html = ""
        for cat, value in sorted(industry_allocation.items(), key=lambda x: x[1], reverse=True):
            pct = value / total_value * 100 if total_value > 0 else 0
            industry_html += f"""
            <tr>
                <td>{cat}</td>
                <td class="text-right">{self._format_number(value, 0)}</td>
                <td class="text-right">{pct:.1f}%</td>
            </tr>
            """

        # 績效統計 (簡化版，假設沒有歷史數據)
        html = f"""
        <!DOCTYPE html>
        <html lang="zh-TW">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{portfolio_name} 投資組合報告</title>
            {self.CSS_TEMPLATE}
        </head>
        <body>
            <div class="report-container">
                <div class="report-header">
                    <div class="report-title">{portfolio_name}</div>
                    <div class="report-subtitle">投資組合績效報告</div>
                    <div class="report-date">報告生成時間：{now.strftime('%Y-%m-%d %H:%M')}</div>
                </div>

                <!-- 投資組合摘要 -->
                <div class="section">
                    <div class="section-title">投資組合摘要</div>
                    <div class="metrics-grid">
                        <div class="metric-card">
                            <div class="metric-label">總成本</div>
                            <div class="metric-value">{self._format_number(total_cost, 0)}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">總市值</div>
                            <div class="metric-value">{self._format_number(total_value, 0)}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">總損益</div>
                            <div class="metric-value {self._get_value_class(total_pnl)}">{self._format_number(total_pnl, 0, prefix='+' if total_pnl > 0 else '')}</div>
                        </div>
                        <div class="metric-card">
                            <div class="metric-label">總報酬率</div>
                            <div class="metric-value {self._get_value_class(total_pnl_pct)}">{self._format_percent(total_pnl_pct)}</div>
                        </div>
                    </div>

                    <div class="summary-box">
                        <div class="summary-row">
                            <span class="summary-label">持股檔數</span>
                            <span class="summary-value">{len(holdings)} 檔</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">獲利股票數</span>
                            <span class="summary-value positive">{len([h for h in holdings_data if h['pnl'] > 0])} 檔</span>
                        </div>
                        <div class="summary-row">
                            <span class="summary-label">虧損股票數</span>
                            <span class="summary-value negative">{len([h for h in holdings_data if h['pnl'] < 0])} 檔</span>
                        </div>
                    </div>
                </div>

                <!-- 持股明細 -->
                <div class="section">
                    <div class="section-title">持股明細</div>
                    <table>
                        <thead>
                            <tr>
                                <th>代號</th>
                                <th>名稱</th>
                                <th class="text-right">股數</th>
                                <th class="text-right">成本價</th>
                                <th class="text-right">現價</th>
                                <th class="text-right">市值</th>
                                <th class="text-right">損益</th>
                                <th class="text-right">報酬率</th>
                                <th class="text-right">佔比</th>
                            </tr>
                        </thead>
                        <tbody>
                            {holdings_html}
                        </tbody>
                    </table>
                </div>

                <!-- 產業配置 -->
                <div class="section page-break">
                    <div class="section-title">產業配置</div>
                    <table>
                        <thead>
                            <tr>
                                <th>產業</th>
                                <th class="text-right">市值</th>
                                <th class="text-right">佔比</th>
                            </tr>
                        </thead>
                        <tbody>
                            {industry_html}
                        </tbody>
                    </table>
                </div>

                <div class="footer">
                    <p>本報告由 FinLab DB 系統自動產生，僅供參考，不構成投資建議。</p>
                    <p>投資有風險，入市需謹慎。</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html


class ReportGenerator:
    """
    報告生成器

    支援格式:
    - PDF (透過 HTML)
    - HTML
    - Excel (xlsx)
    - CSV
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """
        初始化報告生成器

        Parameters:
        -----------
        output_dir : Path, optional
            報告輸出目錄
        """
        self.output_dir = output_dir or Path(__file__).parent.parent / 'reports'
        self.output_dir.mkdir(exist_ok=True)
        self.pdf_generator = PDFReportGenerator()

    def generate_backtest_excel(self, backtest_result, filename: Optional[str] = None) -> bytes:
        """
        產生回測報告 Excel

        Parameters:
        -----------
        backtest_result : BacktestResult
            回測結果
        filename : str, optional
            輸出檔名

        Returns:
        --------
        bytes
            Excel 檔案內容
        """
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 績效摘要
            metrics = backtest_result.metrics
            summary_data = {
                '指標': [
                    '總報酬率 (%)',
                    '年化報酬率 (%)',
                    '年化波動率 (%)',
                    'Sharpe Ratio',
                    'Sortino Ratio',
                    '最大回撤 (%)',
                    '勝率 (%)',
                    '總交易次數',
                ],
                '數值': [
                    f'{metrics.total_return:.2f}',
                    f'{metrics.annual_return:.2f}',
                    f'{metrics.volatility:.2f}',
                    f'{metrics.sharpe_ratio:.2f}',
                    f'{metrics.sortino_ratio:.2f}',
                    f'{metrics.max_drawdown:.2f}',
                    f'{metrics.win_rate:.2f}',
                    f'{metrics.total_trades}',
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='績效摘要', index=False)

            # 與大盤比較
            if backtest_result.benchmark_comparison:
                benchmark_data = {
                    '指標': list(backtest_result.benchmark_comparison.keys()),
                    '數值': [f'{v:.4f}' if isinstance(v, float) else str(v)
                            for v in backtest_result.benchmark_comparison.values()]
                }
                benchmark_df = pd.DataFrame(benchmark_data)
                benchmark_df.to_excel(writer, sheet_name='與大盤比較', index=False)

            # 交易記錄
            if not backtest_result.trades.empty:
                trades_df = backtest_result.trades.copy()
                trades_df.to_excel(writer, sheet_name='交易記錄', index=False)

            # 淨值走勢
            portfolio_df = pd.DataFrame({
                '日期': backtest_result.portfolio_values.index,
                '淨值': backtest_result.portfolio_values.values
            })
            portfolio_df.to_excel(writer, sheet_name='淨值走勢', index=False)

            # 回測設定
            config_data = {
                '設定項': list(backtest_result.config.keys()),
                '設定值': [str(v) for v in backtest_result.config.values()]
            }
            config_df = pd.DataFrame(config_data)
            config_df.to_excel(writer, sheet_name='回測設定', index=False)

        output.seek(0)
        return output.getvalue()

    def generate_screening_excel(self,
                                  stocks: List[str],
                                  scores: Optional[pd.Series],
                                  stock_info: pd.DataFrame,
                                  close: pd.DataFrame,
                                  strategy_name: str) -> bytes:
        """
        產生選股報告 Excel

        Parameters:
        -----------
        stocks : list
            選股結果股票列表
        scores : pd.Series
            股票評分
        stock_info : pd.DataFrame
            股票資訊
        close : pd.DataFrame
            收盤價數據
        strategy_name : str
            策略名稱

        Returns:
        --------
        bytes
            Excel 檔案內容
        """
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 選股結果
            result_data = []

            for stock_id in stocks:
                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''
                category = info['category'].values[0] if len(info) > 0 else ''

                # 取得股價
                if stock_id in close.columns:
                    stock_close = close[stock_id].dropna()
                    latest_price = stock_close.iloc[-1] if len(stock_close) > 0 else None

                    # 計算報酬
                    if len(stock_close) > 5:
                        week_return = (stock_close.iloc[-1] / stock_close.iloc[-5] - 1) * 100
                    else:
                        week_return = None

                    if len(stock_close) > 20:
                        month_return = (stock_close.iloc[-1] / stock_close.iloc[-20] - 1) * 100
                    else:
                        month_return = None
                else:
                    latest_price = None
                    week_return = None
                    month_return = None

                score = scores.get(stock_id, 0) if scores is not None and stock_id in scores.index else 0

                result_data.append({
                    '代號': stock_id,
                    '名稱': name,
                    '產業': category,
                    '現價': latest_price,
                    '評分': score,
                    '週報酬%': week_return,
                    '月報酬%': month_return,
                })

            result_df = pd.DataFrame(result_data)
            result_df.to_excel(writer, sheet_name='選股結果', index=False)

            # 報告資訊
            info_data = {
                '項目': ['策略名稱', '選股數量', '報告日期'],
                '內容': [strategy_name, len(stocks), datetime.now().strftime('%Y-%m-%d %H:%M')]
            }
            info_df = pd.DataFrame(info_data)
            info_df.to_excel(writer, sheet_name='報告資訊', index=False)

            # 產業分布
            if len(result_df) > 0:
                industry_counts = result_df['產業'].value_counts().reset_index()
                industry_counts.columns = ['產業', '數量']
                industry_counts.to_excel(writer, sheet_name='產業分布', index=False)

        output.seek(0)
        return output.getvalue()

    def generate_portfolio_excel(self,
                                  holdings: List[Dict],
                                  stock_info: pd.DataFrame,
                                  close: pd.DataFrame,
                                  portfolio_name: str) -> bytes:
        """
        產生投資組合報告 Excel

        Parameters:
        -----------
        holdings : list
            持股列表
        stock_info : pd.DataFrame
            股票資訊
        close : pd.DataFrame
            收盤價數據
        portfolio_name : str
            投資組合名稱

        Returns:
        --------
        bytes
            Excel 檔案內容
        """
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # 持股明細
            holdings_data = []
            total_cost = 0
            total_value = 0

            for holding in holdings:
                stock_id = holding['stock_id']
                shares = holding['shares']
                cost_price = holding['cost_price']
                buy_date = holding.get('buy_date', '')

                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''
                category = info['category'].values[0] if len(info) > 0 else ''

                if stock_id in close.columns:
                    latest_price = close[stock_id].dropna().iloc[-1]
                else:
                    latest_price = cost_price

                cost_total = shares * cost_price
                value_total = shares * latest_price
                pnl = value_total - cost_total
                pnl_pct = (latest_price / cost_price - 1) * 100

                total_cost += cost_total
                total_value += value_total

                holdings_data.append({
                    '代號': stock_id,
                    '名稱': name,
                    '產業': category,
                    '股數': shares,
                    '成本價': cost_price,
                    '現價': latest_price,
                    '成本': cost_total,
                    '市值': value_total,
                    '損益': pnl,
                    '報酬率%': pnl_pct,
                    '買入日期': buy_date,
                })

            holdings_df = pd.DataFrame(holdings_data)
            holdings_df.to_excel(writer, sheet_name='持股明細', index=False)

            # 投資組合摘要
            total_pnl = total_value - total_cost
            total_pnl_pct = (total_value / total_cost - 1) * 100 if total_cost > 0 else 0

            summary_data = {
                '項目': ['投資組合名稱', '總成本', '總市值', '總損益', '總報酬率%', '持股檔數', '報告日期'],
                '數值': [
                    portfolio_name,
                    f'{total_cost:,.0f}',
                    f'{total_value:,.0f}',
                    f'{total_pnl:+,.0f}',
                    f'{total_pnl_pct:+.2f}',
                    str(len(holdings)),
                    datetime.now().strftime('%Y-%m-%d %H:%M'),
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='投資組合摘要', index=False)

        output.seek(0)
        return output.getvalue()

    # PDF/HTML 報告生成方法
    def generate_stock_analysis_html(self, **kwargs) -> str:
        """生成個股分析報告 HTML"""
        return self.pdf_generator.generate_stock_analysis_html(**kwargs)

    def generate_screening_html(self, **kwargs) -> str:
        """生成選股結果報告 HTML"""
        return self.pdf_generator.generate_screening_html(**kwargs)

    def generate_portfolio_html(self, **kwargs) -> str:
        """生成投資組合績效報告 HTML"""
        return self.pdf_generator.generate_portfolio_html(**kwargs)


def generate_backtest_report(backtest_result, format: str = 'excel') -> bytes:
    """
    快速產生回測報告

    Parameters:
    -----------
    backtest_result : BacktestResult
        回測結果
    format : str
        輸出格式 ('excel' 或 'csv')

    Returns:
    --------
    bytes
        報告檔案內容
    """
    generator = ReportGenerator()

    if format == 'excel':
        return generator.generate_backtest_excel(backtest_result)
    else:
        # CSV 格式
        output = io.StringIO()
        backtest_result.trades.to_csv(output, index=False)
        return output.getvalue().encode('utf-8-sig')


# Streamlit 輔助函數
def create_pdf_download_button(html_content: str, filename: str, button_text: str = "匯出 PDF 報告"):
    """
    建立 PDF 下載按鈕 (透過 HTML)

    在 Streamlit 中使用此函數來提供 PDF 下載功能。
    由於直接生成 PDF 需要額外依賴，這裡提供 HTML 下載，
    用戶可以在瀏覽器中開啟並列印為 PDF。

    Parameters:
    -----------
    html_content : str
        HTML 報告內容
    filename : str
        下載的檔案名稱
    button_text : str
        按鈕文字

    Returns:
    --------
    使用 st.download_button 的返回值
    """
    import streamlit as st

    return st.download_button(
        label=button_text,
        data=html_content.encode('utf-8'),
        file_name=filename,
        mime='text/html',
        help='下載 HTML 報告，可在瀏覽器中開啟並列印為 PDF'
    )

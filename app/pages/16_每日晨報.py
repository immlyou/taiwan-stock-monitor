# -*- coding: utf-8 -*-
"""
每日晨報頁面 - 新聞掃描與開盤提醒 (優化版)

整合新聞 RSS、社群討論，提供精準的市場情報
增加：新聞 + 成交量 + 價格動能 交叉分析
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta


from config import STREAMLIT_CONFIG, CACHE_TTL
from core.data_loader import get_loader
from core.news_scanner import NewsScanner, RSS_FEEDS
from core.ai_models import ClaudeNewsSentimentAnalyzer
from core.hot_stocks import HotStockAnalyzer
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_global_ticker_bar
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error
from app.components.session_manager import set_state, StateKeys
from app.components.theme import (
    COLORS,
    create_page_title,
    create_section_header,
    render_kpi_row,
    render_data_table,
    format_number,
)

st.set_page_config(
    page_title=f"{STREAMLIT_CONFIG['page_title']} - 每日晨報",
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout='wide',
)

# 渲染側邊欄
render_sidebar_mini(current_page='morning_report')

# 全域報價跑馬燈（sidebar 後、標題前呼叫一次）
render_global_ticker_bar()


# ========== 資料載入 ==========
@st.cache_data(ttl=CACHE_TTL['daily'])
def load_stock_info():
    loader = get_loader()
    return loader.get_stock_info()


from app.components.watchlist_utils import load_watchlists as load_watchlist


try:
    stock_info = load_stock_info()
except Exception as e:
    show_error(e, title='載入股票資訊失敗', suggestion='請確認 FinLab API 設定是否正確')
    stock_info = None


def get_stock_name(stock_id):
    """取得股票名稱"""
    if stock_info is None:
        return ''
    info = stock_info[stock_info['stock_id'] == stock_id]
    return info['name'].values[0] if len(info) > 0 else ''


# 初始化新聞掃描器
def get_scanner():
    return NewsScanner(stock_info)


# 每次都重新建立 scanner 以確保使用最新的 stock_patterns
# 但仍保留快取的新聞資料
scanner = get_scanner()
scanner.load_cache()

# 同步到 session_state (給其他需要的地方使用)
set_state(StateKeys.NEWS_SCANNER, scanner)


# ========== 頁面標題 ==========
st.markdown(
    create_page_title('每日晨報', subtitle='新聞掃描 · 開盤提醒 · 整合熱度分析', icon='🌅'),
    unsafe_allow_html=True,
)

if st.button('🔄 更新新聞', type='primary'):
    with st.spinner('正在抓取新聞...'):
        try:
            news_list = scanner.fetch_all_feeds()
            st.success(f'已更新 {len(news_list)} 則新聞')
            st.rerun()
        except Exception as e:
            show_error(e, title='抓取新聞失敗', suggestion='請檢查網路連線狀態')

# ========== 主要內容 ==========
if not scanner.news_cache:
    show_empty_state('尚無新聞資料', icon='📰', suggestion='點擊「更新新聞」開始抓取最新新聞')

    if st.button('🚀 立即抓取', use_container_width=True):
        with st.spinner('正在抓取新聞...'):
            scanner.fetch_all_feeds()
            st.success('抓取完成！')
            st.rerun()
    st.stop()

# 產生晨報
report = scanner.generate_morning_report(refresh=False)

# ========== 區塊 1：總覽 KPI ==========
st.markdown(create_section_header('市場總覽', icon='📊'), unsafe_allow_html=True)

_pos = report['summary']['positive_count']
_neg = report['summary']['negative_count']
if _pos + _neg > 0:
    _ratio = _pos / (_pos + _neg) * 100
    _ratio_delta_color = 'up' if _ratio >= 50 else 'down'
else:
    _ratio = 50
    _ratio_delta_color = 'flat'

render_kpi_row([
    {'label': '📰 新聞總數', 'value': format_number(report['summary']['total_news'], kind='int')},
    {'label': '📈 利多', 'value': format_number(_pos, kind='int'), 'delta_color': 'up'},
    {'label': '📉 利空', 'value': format_number(_neg, kind='int'), 'delta_color': 'down'},
    {'label': '🎯 多空比', 'value': f'{_ratio:.0f}%', 'delta_color': _ratio_delta_color},
    {'label': '🔥 熱門股', 'value': format_number(len(report['hot_stocks']), kind='int')},
    {'label': '📊 涉及標的', 'value': format_number(report['summary'].get('unique_stocks', 0), kind='int')},
])

# ========== 區塊 2：新聞（利多 / 利空，上下堆疊避免高度不齊） ==========
st.markdown(create_section_header('新聞快訊', icon='📰'), unsafe_allow_html=True)


def _render_news_block(news_items, empty_msg, empty_icon):
    """以固定高度容器渲染新聞清單，避免利多/利空兩欄高度不齊。"""
    if not news_items:
        show_empty_state(empty_msg, icon=empty_icon)
        return
    for news in news_items[:4]:
        with st.container():
            title = news['title'][:50] + '...' if len(news['title']) > 50 else news['title']
            st.markdown(f"**{title}**")
            if news.get('summary'):
                summary = news['summary'][:80] + '...' if len(news['summary']) > 80 else news['summary']
                st.caption(summary)
            tag_col1, tag_col2 = st.columns([3, 1])
            with tag_col1:
                if news['stocks']:
                    stock_tags = ' '.join([f"`{s}`" for s in news['stocks'][:3]])
                    st.markdown(stock_tags)
            with tag_col2:
                st.caption(f"📡{news['source'][:6]}")
            st.markdown(f"[閱讀全文]({news['link']})")
            st.markdown('---')


news_tab_pos, news_tab_neg = st.tabs(['📈 利多消息', '📉 利空消息'])
with news_tab_pos:
    with st.container(height=180):
        _render_news_block(report['positive_news'], '目前無利多新聞', '📈')
with news_tab_neg:
    with st.container(height=180):
        _render_news_block(report['negative_news'], '目前無利空新聞', '📉')

# ========== 區塊 3：熱門股票 ==========
st.markdown(create_section_header('熱門股票 Top 10', icon='🔥'), unsafe_allow_html=True)

if report['hot_stocks']:
    for stock in report['hot_stocks'][:10]:
        stock_id = stock['stock_id']
        name = get_stock_name(stock_id)
        trend = stock.get('trend', 'neutral')

        # 趨勢圖示
        trend_icon = {'bullish': '🟢', 'bearish': '🔴', 'neutral': '⚪'}.get(trend, '⚪')

        # 情緒分數（紅漲綠跌 → 利多紅、利空綠）
        pos = stock.get('positive', 0)
        neg = stock.get('negative', 0)

        st.markdown(
            f"<div style='display:flex;justify-content:space-between;align-items:center;"
            f"padding:6px 0;border-bottom:1px solid {COLORS['border']}'>"
            f"<div>"
            f"<span style='font-weight:bold;color:{COLORS['text_primary']}'>{stock_id}</span> "
            f"<span style='color:{COLORS['text_secondary']};font-size:12px'>{name[:4]}</span>"
            f"</div>"
            f"<div style='font-size:12px'>"
            f"{trend_icon} "
            f"<span style='color:{COLORS['up']}'>📈{pos}</span>/"
            f"<span style='color:{COLORS['down']}'>📉{neg}</span>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    # 查看詳情
    st.markdown('')
    selected_hot = st.selectbox(
        '選擇查看詳情',
        [f"{s['stock_id']} {get_stock_name(s['stock_id'])}" for s in report['hot_stocks'][:10]],
        key='hot_stock_select',
        label_visibility='collapsed',
    )

    if selected_hot:
        sel_stock_id = selected_hot.split(' ')[0]
        stock_news = scanner.get_stock_news(sel_stock_id, 48)

        if stock_news:
            st.markdown(f'**{selected_hot} 近期新聞**')
            for news in stock_news[:3]:
                icon = {'positive': '📈', 'negative': '📉', 'neutral': '➖'}.get(news.sentiment, '➖')
                st.markdown(f"{icon} [{news.title[:30]}...]({news.link})")
else:
    show_empty_state('暫無熱門股票', icon='🔥', suggestion='請先更新新聞資料')

# ========== 區塊 4：AI 新聞情緒分析 ==========
st.markdown(create_section_header('AI 新聞情緒分析', icon='🤖'), unsafe_allow_html=True)

if st.button('🔍 啟動 AI 情緒分析', key='ai_sentiment_btn'):
    with st.spinner('AI 正在分析新聞情緒...'):
        analyzer = ClaudeNewsSentimentAnalyzer()
        # 從 report 中收集新聞
        all_news = []
        for news in report.get('positive_news', []) + report.get('negative_news', []) + report.get('neutral_news', []):
            all_news.append({
                'title': news.get('title', ''),
                'summary': news.get('summary', ''),
                'link': news.get('link', ''),
                'source': news.get('source', ''),
            })

        if all_news:
            ai_results = analyzer.analyze_batch(all_news)
            if ai_results and not ai_results[0].get('error'):
                st.session_state['ai_sentiment_results'] = ai_results
            else:
                error_msg = ai_results[0].get('error', '未知錯誤') if ai_results else '無結果'
                st.warning(f'AI 分析失敗：{error_msg}')
        else:
            st.info('目前沒有新聞可供分析')

if 'ai_sentiment_results' in st.session_state:
    results = st.session_state['ai_sentiment_results']

    # 統計
    pos_count = sum(1 for r in results if r.get('sentiment') == 'positive')
    neg_count = sum(1 for r in results if r.get('sentiment') == 'negative')
    avg_score = sum(r.get('score', 0) for r in results) / len(results) if results else 0

    render_kpi_row([
        {'label': 'AI 判定利多', 'value': format_number(pos_count, kind='int'), 'delta_color': 'up'},
        {'label': 'AI 判定利空', 'value': format_number(neg_count, kind='int'), 'delta_color': 'down'},
        {'label': '情緒分數', 'value': f'{avg_score:+.2f}',
         'delta_color': 'up' if avg_score >= 0 else 'down'},
    ])

    # 詳細結果（🟢=正面紅、🔴=負面綠 由 icon 表達；分數正負保留符號）
    for r in results:
        sentiment_icon = '🟢' if r.get('sentiment') == 'positive' else ('🔴' if r.get('sentiment') == 'negative' else '⚪')
        score = r.get('score', 0)
        title = r.get('title', '')[:50]
        impact = r.get('impact', '')
        stocks = ', '.join(r.get('related_stocks', []))

        st.markdown(
            f"{sentiment_icon} **{title}** `{score:+.1f}` {impact}"
            + (f" | 相關：{stocks}" if stocks else ""),
        )

# ========== 整合分析：新聞+成交量+動能 ==========
st.markdown(create_section_header('需要關注股票（整合分析）', icon='🎯'), unsafe_allow_html=True)
st.caption('結合新聞熱度、成交量異常、價格動能三大面向')

try:
    # 從新聞取得熱門股票資料
    # get_hot_stocks 回傳 Dict[str, float] (stock_id -> score)
    news_hot_dict = scanner.get_hot_stocks(hours=48) if scanner.news_cache else {}

    # 轉換格式並取得更多資訊
    news_hot_stocks = None
    if news_hot_dict:
        news_hot_stocks = {}
        for stock_id, score in list(news_hot_dict.items())[:50]:
            # 取得情緒摘要
            sentiment_summary = scanner.get_stock_sentiment_summary(stock_id, hours=48)
            news_hot_stocks[stock_id] = {
                'count': sentiment_summary.get('mention_count', 1),
                'sentiment': sentiment_summary.get('avg_sentiment', 0),
                'score': min(100, score * 20),  # 正規化分數
            }

    # 整合分析
    analyzer = HotStockAnalyzer(
        news_weight=0.4,
        volume_weight=0.3,
        momentum_weight=0.3,
    )
    integrated_hot_stocks = analyzer.analyze_hot_stocks(news_hot_stocks, top_n=15, min_score=35)

    if integrated_hot_stocks:
        # 顯示統計
        high_vol_count = sum(1 for s in integrated_hot_stocks if s.is_high_volume)
        pos_news_count = sum(1 for s in integrated_hot_stocks if s.is_positive_news)
        strong_count = sum(1 for s in integrated_hot_stocks if s.price_change_5d >= 5)
        render_kpi_row([
            {'label': '分析股票數', 'value': format_number(len(integrated_hot_stocks), kind='int')},
            {'label': '爆量股', 'value': format_number(high_vol_count, kind='int')},
            {'label': '正面新聞', 'value': format_number(pos_news_count, kind='int'), 'delta_color': 'up'},
            {'label': '短線強勢', 'value': format_number(strong_count, kind='int'), 'delta_color': 'up'},
        ])

        st.markdown('')

        # 表格顯示
        data_rows = []
        for stock in integrated_hot_stocks:
            # 綜合分數顏色
            if stock.total_score >= 70:
                score_color = '🔴'
            elif stock.total_score >= 55:
                score_color = '🟠'
            else:
                score_color = '🟡'

            # 趨勢方向
            if stock.price_change_5d >= 5:
                trend = '📈強'
            elif stock.price_change_5d >= 0:
                trend = '📈'
            elif stock.price_change_5d >= -5:
                trend = '📉'
            else:
                trend = '📉弱'

            # 量比顯示
            vol_str = f'{stock.volume_ratio:.1f}x'
            if stock.is_high_volume:
                vol_str = f'**{vol_str}**'

            data_rows.append({
                '代號': stock.stock_id,
                '名稱': stock.name[:4] if stock.name else '',
                '綜合分': f'{score_color} {stock.total_score:.0f}',
                '新聞': f'{stock.news_score:.0f}' if stock.news_score > 0 else '-',
                '量比': vol_str,
                '5日%': f'{stock.price_change_5d:+.1f}%',
                '趨勢': trend,
                '標籤': ', '.join(stock.tags[:2]) if stock.tags else '',
            })

        df_hot = pd.DataFrame(data_rows)
        render_data_table(df_hot, freeze_cols=2, dense=True)

        # 詳細資訊展開
        with st.expander('📊 詳細分數說明'):
            detail_cols = st.columns(3)

            with detail_cols[0]:
                st.markdown('**新聞分數 (40%)**')
                st.caption('基於新聞提及次數與情緒分析')
                for stock in integrated_hot_stocks[:5]:
                    if stock.news_score > 0:
                        sentiment_icon = '📈' if stock.news_sentiment > 0 else ('📉' if stock.news_sentiment < 0 else '➖')
                        st.markdown(f"{stock.stock_id}: {stock.news_score:.0f}分 ({stock.news_count}則 {sentiment_icon})")

            with detail_cols[1]:
                st.markdown('**成交量分數 (30%)**')
                st.caption('近5日均量 vs 20日均量')
                for stock in integrated_hot_stocks[:5]:
                    vol_icon = '🔥' if stock.volume_ratio >= 2 else ('⬆️' if stock.volume_ratio >= 1.2 else '➖')
                    st.markdown(f"{stock.stock_id}: {stock.volume_score:.0f}分 ({stock.volume_ratio:.1f}x {vol_icon})")

            with detail_cols[2]:
                st.markdown('**動能分數 (30%)**')
                st.caption('5日與20日價格變動')
                for stock in integrated_hot_stocks[:5]:
                    trend_icon = '📈' if stock.price_change_5d > 0 else '📉'
                    st.markdown(f"{stock.stock_id}: {stock.momentum_score:.0f}分 (5日:{stock.price_change_5d:+.1f}% {trend_icon})")

    else:
        show_empty_state('目前無符合條件的熱門股票', icon='🎯', suggestion='請先更新新聞資料以取得整合分析結果')

except Exception as e:
    st.warning(f'整合分析暫時無法使用: {e}')

# ========== 自選股警示 ==========
st.markdown(create_section_header('自選股新聞警示', icon='⭐'), unsafe_allow_html=True)

watchlists = load_watchlist()

if watchlists:

    # 取得所有自選股
    all_watchlist_stocks = []
    for stocks in watchlists.values():
        all_watchlist_stocks.extend(stocks)
    all_watchlist_stocks = list(set(all_watchlist_stocks))

    if all_watchlist_stocks:
        alerts = scanner.get_watchlist_alerts(all_watchlist_stocks, hours=24)

        if alerts:
            alert_cols = st.columns(min(len(alerts), 4))
            for i, alert in enumerate(alerts[:4]):
                with alert_cols[i % 4]:
                    stock_id = alert['stock_id']
                    name = get_stock_name(stock_id)

                    if alert['type'] == 'negative':
                        st.warning(f"⚠️ **{stock_id} {name}**\n\n{alert['message']}")
                    elif alert['type'] == 'positive':
                        st.success(f"📈 **{stock_id} {name}**\n\n{alert['message']}")
                    else:
                        st.info(f"📊 **{stock_id} {name}**\n\n{alert['message']}")

            if len(alerts) > 4:
                with st.expander(f'查看更多警示 ({len(alerts) - 4} 則)'):
                    for alert in alerts[4:]:
                        st.markdown(f"- {alert['stock_id']} {get_stock_name(alert['stock_id'])}: {alert['message']}")
        else:
            st.caption('自選股近期無重要新聞')

        # 自選股新聞列表
        with st.expander('📋 自選股完整新聞'):
            watchlist_news = scanner.get_watchlist_news(all_watchlist_stocks, hours=48)

            if watchlist_news:
                for news in watchlist_news[:15]:
                    icon = {'positive': '📈', 'negative': '📉', 'neutral': '➖'}.get(news.sentiment, '➖')
                    stocks_str = ', '.join(news.stocks[:3])
                    st.markdown(f"{icon} **{news.title[:60]}** `{stocks_str}` [連結]({news.link})")
            else:
                show_empty_state('自選股近期無相關新聞', icon='⭐')
else:
    st.caption('💡 建立自選股清單可追蹤關注標的的新聞')

# ========== 市場要聞 ==========
st.markdown(create_section_header('市場要聞 / 進階工具', icon='🗞️'), unsafe_allow_html=True)

with st.expander('📋 市場最新要聞', expanded=False):
    for news in report['market_news'][:12]:
        sentiment_icon = {'positive': '📈', 'negative': '📉', 'neutral': '➖'}.get(news['sentiment'], '➖')

        col1, col2, col3 = st.columns([0.5, 5, 1])
        with col1:
            st.write(sentiment_icon)
        with col2:
            title = news['title'][:60] + '...' if len(news['title']) > 60 else news['title']
            st.markdown(f"**{title}** [↗]({news['link']})")
            if news.get('summary'):
                st.caption(news['summary'][:100] + '...' if len(news['summary']) > 100 else news['summary'])
        with col3:
            st.caption(f"{news['source'][:6]}\n{news['published']}")

# ========== 新聞篩選器 ==========
with st.expander('🔍 進階新聞篩選'):
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

    with filter_col1:
        sentiment_filter = st.selectbox('情緒', ['全部', '利多', '利空', '中性'], key='filter_sentiment')

    with filter_col2:
        sources = list(set(n.source for n in scanner.news_cache))
        source_filter = st.selectbox('來源', ['全部'] + sources, key='filter_source')

    with filter_col3:
        hours_filter = st.selectbox(
            '時間',
            [('全部', 0), ('6小時', 6), ('12小時', 12), ('24小時', 24), ('48小時', 48)],
            format_func=lambda x: x[0],
            key='filter_hours'
        )

    with filter_col4:
        stock_filter = st.text_input('股票代號', placeholder='例: 2330', key='filter_stock')

    # 篩選結果
    filtered_news = list(scanner.news_cache)

    if hours_filter[1] > 0:
        cutoff = datetime.now() - timedelta(hours=hours_filter[1])
        filtered_news = [n for n in filtered_news if n.published >= cutoff]

    if sentiment_filter == '利多':
        filtered_news = [n for n in filtered_news if n.sentiment == 'positive']
    elif sentiment_filter == '利空':
        filtered_news = [n for n in filtered_news if n.sentiment == 'negative']
    elif sentiment_filter == '中性':
        filtered_news = [n for n in filtered_news if n.sentiment == 'neutral']

    if source_filter != '全部':
        filtered_news = [n for n in filtered_news if n.source == source_filter]

    if stock_filter:
        filtered_news = [n for n in filtered_news if stock_filter in n.stocks]

    st.caption(f'篩選結果: {len(filtered_news)} 則')

    # 顯示篩選結果
    for news in filtered_news[:20]:
        sentiment_color = {'positive': '🟢', 'negative': '🔴', 'neutral': '⚪'}.get(news.sentiment, '⚪')

        with st.container():
            st.markdown(f"{sentiment_color} **{news.title}**")
            if news.summary:
                st.caption(news.summary[:150] + '...' if len(news.summary) > 150 else news.summary)

            info_col1, info_col2 = st.columns([3, 1])
            with info_col1:
                if news.stocks:
                    st.caption(f"📌 {', '.join(news.stocks[:5])}")
                st.caption(f"📡 {news.source} | 🕐 {news.published.strftime('%m/%d %H:%M')}")
            with info_col2:
                st.markdown(f"[閱讀全文]({news.link})")

            st.markdown('---')

# ========== 設定與說明 ==========
with st.expander('⚙️ RSS 來源設定'):
    st.markdown('#### 可用的新聞來源')

    # 分類顯示
    categories = {}
    for key, config in RSS_FEEDS.items():
        cat = config.get('category', 'other')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(config)

    cat_names = {
        'news': '📰 綜合新聞',
        'market': '📊 台股市場',
        'regulation': '🏛️ 官方公告',
        'us_stock': '🇺🇸 美股新聞',
        'international': '🌍 國際財經',
        'column': '📝 專欄評論',
    }

    for cat, sources in categories.items():
        st.markdown(f"**{cat_names.get(cat, cat)}**")
        for source in sources:
            weight = source.get('weight', 1.0)
            weight_str = '⭐' * min(int(weight * 2), 3)
            st.caption(f"- {source['name']} {weight_str}")

with st.expander('📖 使用說明'):
    st.markdown('''
    ### 每日晨報功能說明

    #### 智慧功能
    - **精準股票識別**: 使用正則邊界匹配，減少誤判
    - **加權情緒分析**: 考慮否定詞、關鍵字強度
    - **智慧熱門排名**: 同事件去重、時間衰減、來源權重
    - **自選股警示**: 自動追蹤關注標的的重要新聞

    #### 情緒分析說明
    - **利多關鍵字**: 漲停、創高、成長、獲利、買進等
    - **利空關鍵字**: 跌停、衰退、虧損、砍單、賣出等
    - 系統會考慮否定詞 (如「不看好」會反轉情緒)

    #### 建議使用方式
    1. 每日開盤前查看晨報總覽
    2. 關注「自選股警示」了解持股動態
    3. 追蹤「熱門股票」的多空變化
    4. 使用篩選器深入分析特定股票

    #### 注意事項
    - 新聞情緒分析僅供參考
    - 資料通常有數分鐘延遲
    - 官方來源 (金管會等) 權重較高
    ''')

st.caption('資料來源: Yahoo、中央社、自由時報、金管會、鉅亨網等')

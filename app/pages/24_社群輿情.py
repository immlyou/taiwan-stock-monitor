# -*- coding: utf-8 -*-
"""
社群輿情頁面 — PTT Stock 版 / X (Twitter) 股票討論熱度追蹤
抓取社群平台的台股討論，分析熱門個股與市場情緒。
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import re
import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_page_header
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error
from app.components.theme import COLORS, create_kpi_card, DEFAULT_PLOTLY_LAYOUT

st.set_page_config(page_title='社群輿情', page_icon='🗣️', layout='wide')
render_sidebar_mini(current_page='sentiment')
render_page_header('社群輿情', icon='🗣️')

# ─── PTT 爬取 ─────────────────────────────────────────
PTT_STOCK_URL = 'https://www.ptt.cc/bbs/Stock/index.html'
HEADERS = {'Cookie': 'over18=1', 'User-Agent': 'Mozilla/5.0'}

# 台股股票代碼正則 (4 碼數字)
STOCK_RE = re.compile(r'\b(\d{4})\b')


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_ptt_stock_titles(pages: int = 5):
    """
    爬取 PTT Stock 版最新文章標題
    Returns list of dicts: [{'title': ..., 'date': ..., 'author': ...}, ...]
    """
    articles = []
    url = PTT_STOCK_URL
    try:
        for _ in range(pages):
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            html = resp.text

            # 簡易解析
            # 每篇文章在 <div class="r-ent">
            blocks = html.split('<div class="r-ent">')
            for block in blocks[1:]:
                title_match = re.search(r'<a href="[^"]*">(.+?)</a>', block)
                date_match = re.search(r'<div class="date">\s*(\S+)\s*</div>', block)
                author_match = re.search(r'<div class="author">(.+?)</div>', block)
                if title_match:
                    articles.append({
                        'title': title_match.group(1).strip(),
                        'date': date_match.group(1).strip() if date_match else '',
                        'author': author_match.group(1).strip() if author_match else '',
                    })

            # 取得上一頁連結
            prev_match = re.search(r'<a class="btn wide" href="([^"]+)">‹ 上頁</a>', html)
            if prev_match:
                url = 'https://www.ptt.cc' + prev_match.group(1)
            else:
                break
    except Exception:
        pass

    return articles


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_x_stock_posts(bearer_token: str, query: str = '台股 OR 加權指數', max_results: int = 50):
    """
    使用 X (Twitter) API v2 搜尋最近推文
    """
    if not bearer_token:
        return []

    url = 'https://api.twitter.com/2/tweets/search/recent'
    headers = {'Authorization': f'Bearer {bearer_token}'}
    params = {
        'query': f'{query} lang:zh',
        'max_results': min(max_results, 100),
        'tweet.fields': 'created_at,public_metrics,author_id',
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data.get('data', [])
    except Exception:
        pass

    return []


# ─── 資料分析 ─────────────────────────────────────────
active = get_active_stocks()
active_ids = set(active) if active else set()


def extract_stock_mentions(texts, stock_ids):
    """從文字列表中提取被提及的股票代碼及頻次"""
    counter = Counter()
    for text in texts:
        found = STOCK_RE.findall(text)
        for code in found:
            if code in stock_ids:
                counter[code] += 1
    return counter


# ─── 主面板 ───────────────────────────────────────────

tab_ptt, tab_x = st.tabs(['💬 PTT Stock 版', '🐦 X (Twitter)'])

# ─── PTT Tab ──────────────────────────────────────────
with tab_ptt:
    ptt_pages = st.slider('爬取頁數', 2, 15, 5, key='ptt_pages')

    with st.spinner('正在抓取 PTT Stock 版文章...'):
        articles = fetch_ptt_stock_titles(pages=ptt_pages)

    if not articles:
        show_empty_state(
            '無法取得 PTT 資料',
            icon='📭',
            suggestion='可能是網路問題或 PTT 暫時無法連線，請稍後再試',
        )
    else:
        titles = [a['title'] for a in articles]

        # 股票提及統計
        mentions = extract_stock_mentions(titles, active_ids)
        total_articles = len(articles)
        unique_stocks = len(mentions)

        # 文章分類統計
        tag_counter = Counter()
        for t in titles:
            tag_match = re.match(r'\[(.+?)\]', t)
            if tag_match:
                tag_counter[tag_match.group(1)] += 1

        # KPI
        kpi_cols = st.columns(4)
        with kpi_cols[0]:
            st.markdown(create_kpi_card('📝', '文章總數', str(total_articles), f'最近 {ptt_pages} 頁'), unsafe_allow_html=True)
        with kpi_cols[1]:
            st.markdown(create_kpi_card('📊', '被提及個股', str(unique_stocks), '不重複股票代碼'), unsafe_allow_html=True)
        with kpi_cols[2]:
            top_tag = tag_counter.most_common(1)[0] if tag_counter else ('—', 0)
            st.markdown(create_kpi_card('🏷️', '最熱分類', f'[{top_tag[0]}]', f'{top_tag[1]} 篇'), unsafe_allow_html=True)
        with kpi_cols[3]:
            pct_has_stock = sum(1 for t in titles if STOCK_RE.search(t)) / total_articles * 100
            st.markdown(create_kpi_card('🎯', '含股票代碼', f'{pct_has_stock:.0f}%', '提及個股比例'), unsafe_allow_html=True)

        col_left, col_right = st.columns([3, 2])

        with col_left:
            st.markdown('#### 🔥 熱門討論個股')
            if mentions:
                top_mentions = mentions.most_common(20)
                mention_df = pd.DataFrame(top_mentions, columns=['股票代碼', '被提及次數'])

                import plotly.express as px
                fig = px.bar(mention_df, x='被提及次數', y='股票代碼', orientation='h',
                             color='被提及次數', color_continuous_scale=['#1e40af', '#3b82f6', '#ef4444'],
                             text='被提及次數')
                fig.update_layout(**DEFAULT_PLOTLY_LAYOUT, height=450, showlegend=False,
                                  coloraxis_showscale=False, yaxis=dict(autorange='reversed'))
                fig.update_traces(textposition='outside')
                st.plotly_chart(fig, use_container_width=True)
            else:
                show_empty_state('未偵測到股票代碼', suggestion='文章標題中未包含 4 碼股票代碼')

        with col_right:
            st.markdown('#### 🏷️ 文章分類分佈')
            if tag_counter:
                tag_df = pd.DataFrame(tag_counter.most_common(10), columns=['分類', '數量'])
                import plotly.express as px
                fig_pie = px.pie(tag_df, values='數量', names='分類', hole=0.4,
                                 color_discrete_sequence=['#3b82f6', '#8b5cf6', '#ef4444', '#f59e0b',
                                                          '#22c55e', '#06b6d4', '#ec4899', '#64748b',
                                                          '#f97316', '#14b8a6'])
                fig_pie.update_layout(**DEFAULT_PLOTLY_LAYOUT, height=450, showlegend=True,
                                      legend=dict(font=dict(size=11)))
                st.plotly_chart(fig_pie, use_container_width=True)

        # 最新文章列表
        with st.expander(f'📋 最新文章列表（共 {total_articles} 篇）', expanded=False):
            art_df = pd.DataFrame(articles)
            art_df.columns = ['標題', '日期', '作者']
            st.dataframe(art_df, use_container_width=True, height=400)

# ─── X (Twitter) Tab ──────────────────────────────────
with tab_x:
    bearer_token = os.environ.get('X_BEARER_TOKEN', '')

    if not bearer_token:
        # 嘗試從 streamlit secrets 取得
        try:
            bearer_token = st.secrets.get('X_BEARER_TOKEN', '')
        except Exception:
            pass

    if not bearer_token:
        st.info('💡 需要設定 `X_BEARER_TOKEN` 環境變數才能使用 X (Twitter) 輿情分析。')
        st.markdown(f'''
        <div style="background:{COLORS["card_bg"]};border:1px solid {COLORS["border"]};border-radius:10px;padding:1rem 1.25rem">
            <h5 style="color:{COLORS["text_primary"]};margin-bottom:0.5rem">如何設定？</h5>
            <ol style="color:{COLORS["text_secondary"]};font-size:0.85rem">
                <li>前往 <a href="https://developer.twitter.com/" target="_blank" style="color:{COLORS["accent"]}">X Developer Portal</a> 申請 API 存取權限</li>
                <li>取得 Bearer Token</li>
                <li>在 Streamlit Cloud 的 Settings → Secrets 加入 <code>X_BEARER_TOKEN = "your_token"</code></li>
            </ol>
        </div>
        ''', unsafe_allow_html=True)
    else:
        search_query = st.text_input('搜尋關鍵字', value='台股 OR 加權指數 OR 台積電', key='x_query')
        max_results = st.slider('最大推文數', 10, 100, 50, 10, key='x_max')

        if st.button('🔍 搜尋', key='x_search'):
            with st.spinner('正在搜尋 X 上的推文...'):
                tweets = fetch_x_stock_posts(bearer_token, query=search_query, max_results=max_results)

            if not tweets:
                show_empty_state('未搜尋到相關推文', suggestion='請嘗試調整關鍵字或確認 API Token 是否有效')
            else:
                st.success(f'找到 {len(tweets)} 則相關推文')

                # 提取股票代碼
                tweet_texts = [t.get('text', '') for t in tweets]
                x_mentions = extract_stock_mentions(tweet_texts, active_ids)

                if x_mentions:
                    st.markdown('#### 🔥 X 上的熱門個股')
                    xm_df = pd.DataFrame(x_mentions.most_common(15), columns=['股票代碼', '提及次數'])
                    st.dataframe(xm_df, use_container_width=True)

                # 推文列表
                with st.expander(f'📋 推文列表（{len(tweets)} 則）', expanded=True):
                    for tweet in tweets[:30]:
                        text = tweet.get('text', '')
                        created = tweet.get('created_at', '')[:10]
                        metrics = tweet.get('public_metrics', {})
                        likes = metrics.get('like_count', 0)
                        retweets = metrics.get('retweet_count', 0)

                        st.markdown(f'''
                        <div style="background:{COLORS["card_bg"]};border:1px solid {COLORS["border"]};
                                    border-radius:8px;padding:0.75rem 1rem;margin-bottom:0.5rem">
                            <p style="color:{COLORS["text_primary"]};font-size:0.85rem;margin:0 0 0.5rem 0">{text}</p>
                            <div style="display:flex;gap:1rem;color:{COLORS["text_muted"]};font-size:0.75rem">
                                <span>📅 {created}</span>
                                <span>❤️ {likes}</span>
                                <span>🔁 {retweets}</span>
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)

# ─── 免責聲明 ──────────────────────────────────────────
st.markdown(f'''
<div style="background:{COLORS["card_bg"]};border:1px solid {COLORS["border"]};border-radius:8px;padding:0.75rem 1rem;margin-top:1rem">
    <p style="color:{COLORS["text_muted"]};font-size:0.75rem;margin:0">
        ⚠️ <b>免責聲明</b>：社群輿情資料僅供參考，不代表投資建議。
        文章來源為公開論壇與社群平台，內容不代表本系統立場。
    </p>
</div>
''', unsafe_allow_html=True)

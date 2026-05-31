"""
預測驗證頁面
功能：新增預測、查看驗證結果、統計報表
"""
import streamlit as st
import pandas as pd
from datetime import datetime


from config import CACHE_TTL
from core.data_loader import get_loader, get_active_stocks
from core.prediction_tracker import (
    get_tracker, PredictionType, PredictionStatus
)
from app.components.sidebar import render_sidebar_mini
from app.components.page_header import render_global_ticker_bar
from app.components.empty_state import show_empty_state
from app.components.error_handler import show_error
from app.components.theme import (
    COLORS,
    create_page_title,
    create_section_header,
    render_kpi_row,
    render_data_table,
    format_number,
    inject_professional_theme,
)

st.set_page_config(page_title='預測驗證', page_icon='🎯', layout='wide')

# 注入專業主題
inject_professional_theme()

render_sidebar_mini(current_page='prediction')

# 全域報價列（sidebar 後、標題前呼叫一次）
render_global_ticker_bar()

# ==================== 標題 ====================
st.markdown(
    create_page_title('預測驗證', subtitle='追蹤預測、自動驗證與勝率統計', icon='🎯'),
    unsafe_allow_html=True,
)

# ==================== 資料載入 ====================
@st.cache_data(ttl=CACHE_TTL['daily'])
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'stock_info': loader.get_stock_info(),
    }

try:
    data = load_data()
    close = data['close']
    stock_info = data['stock_info']
except Exception as e:
    show_error(e, title='載入資料失敗', suggestion='請確認 FinLab API 設定是否正確')
    st.stop()

tracker = get_tracker()

# ==================== 頁籤 ====================
tab1, tab2, tab3, tab4 = st.tabs(['📊 統計總覽', '➕ 新增預測', '📋 預測記錄', '🔍 執行驗證'])

# ==================== Tab 1: 統計總覽 ====================
with tab1:
    col1, col2 = st.columns([1, 3])

    with col1:
        stats_days = st.selectbox('統計期間', [7, 14, 30, 60, 90], index=2, format_func=lambda x: f'最近 {x} 天')

    stats = tracker.get_statistics(days=stats_days)

    # KPI 卡片
    st.markdown(create_section_header('整體表現', icon='📈'), unsafe_allow_html=True)
    verified = stats['success'] + stats['failed']
    avg_return = stats['avg_return']
    render_kpi_row([
        {'label': '總預測數', 'value': format_number(stats['total'], kind='int')},
        {'label': '已驗證', 'value': format_number(verified, kind='int'),
         'delta': f"待驗證 {stats['pending']}", 'delta_color': 'flat'},
        {'label': '勝率', 'value': format_number(stats['success_rate'], kind='pct'),
         'delta': f"✅{stats['success']} / ❌{stats['failed']}", 'delta_color': 'flat'},
        {'label': '平均報酬', 'value': format_number(avg_return, kind='pct', signed=True),
         'delta_color': 'up' if avg_return >= 0 else 'down'},
    ])

    # 依類型統計
    if stats['by_type']:
        st.markdown(create_section_header('依預測類型', icon='📋'), unsafe_allow_html=True)
        type_names = {
            'target_price': '🎯 目標價達成',
            'direction': '📈 漲跌方向',
            'stock_pick': '📊 選股勝率'
        }

        cols = st.columns(3)
        for i, (ptype, type_data) in enumerate(stats['by_type'].items()):
            with cols[i]:
                if type_data['total'] > 0:
                    st.markdown(f"**{type_names.get(ptype, ptype)}**")
                    st.write(f"總數: {type_data['total']}")
                    st.write(f"已驗證: {type_data['verified']}")
                    st.write(f"勝率: **{type_data['success_rate']:.1f}%**")
                else:
                    st.markdown(f"**{type_names.get(ptype, ptype)}**")
                    st.write("尚無資料")

    # 依來源統計
    if stats['by_source']:
        st.markdown(create_section_header('依策略來源', icon='🏷️'), unsafe_allow_html=True)
        source_df = pd.DataFrame([
            {
                '策略': source,
                '預測數': src_data['total'],
                '已驗證': src_data['verified'],
                '成功': src_data['success'],
                '勝率': f"{src_data['success_rate']:.1f}%",
                '平均報酬': format_number(src_data['avg_return'], kind='pct', signed=True)
            }
            for source, src_data in stats['by_source'].items()
        ])
        render_data_table(source_df, freeze_cols=1,
                          numeric_cols=['預測數', '已驗證', '成功'])

# ==================== Tab 2: 新增預測 ====================
with tab2:
    st.markdown(create_section_header('新增預測', icon='➕'), unsafe_allow_html=True)

    pred_type = st.radio(
        '預測類型',
        ['🎯 目標價達成', '📈 漲跌方向', '📊 選股追蹤'],
        horizontal=True
    )

    # 股票選擇
    active_stocks = get_active_stocks()
    stock_options = []
    stock_map = {}
    for _, row in stock_info.iterrows():
        if row['stock_id'] in active_stocks:
            label = f"{row['stock_id']} {row['name']}"
            stock_options.append(label)
            stock_map[label] = {'id': row['stock_id'], 'name': row['name']}

    col1, col2 = st.columns([2, 1])

    with col1:
        selected_stock = st.selectbox(
            '選擇股票',
            options=stock_options,
            placeholder='輸入股票代號或名稱搜尋...'
        )

    # 取得目前股價
    current_price = None
    if selected_stock:
        stock_id = stock_map[selected_stock]['id']
        if stock_id in close.columns:
            current_price = float(close[stock_id].dropna().iloc[-1])

    with col2:
        if current_price:
            st.metric('目前股價', f'{current_price:.2f}')
        else:
            st.warning('無法取得股價')

    # 根據預測類型顯示不同表單
    if pred_type == '🎯 目標價達成':
        col1, col2, col3 = st.columns(3)
        with col1:
            target_price = st.number_input(
                '目標價',
                min_value=0.01,
                value=current_price * 1.1 if current_price else 100.0,
                step=0.5,
                format='%.2f'
            )
        with col2:
            verify_days = st.number_input('驗證天數', min_value=1, max_value=90, value=20)
        with col3:
            source = st.text_input('來源/策略', placeholder='例如: 技術分析')

        notes = st.text_area('備註', placeholder='預測理由或觀察...')

        if current_price and target_price:
            expected_return = (target_price - current_price) / current_price * 100
            st.info(f'預期報酬: {expected_return:+.2f}% (目標價 {target_price:.2f} vs 現價 {current_price:.2f})')

        if st.button('新增目標價預測', type='primary', use_container_width=True):
            if selected_stock and current_price:
                stock = stock_map[selected_stock]
                tracker.add_target_price_prediction(
                    stock_id=stock['id'],
                    stock_name=stock['name'],
                    current_price=current_price,
                    target_price=target_price,
                    verify_days=verify_days,
                    source=source or None,
                    notes=notes or None
                )
                st.success(f'✅ 已新增預測: {stock["id"]} {stock["name"]} 目標價 {target_price}')
                st.rerun()

    elif pred_type == '📈 漲跌方向':
        col1, col2, col3 = st.columns(3)
        with col1:
            direction = st.radio('預測方向', ['看漲 📈', '看跌 📉'], horizontal=True)
        with col2:
            verify_days = st.number_input('幾天後驗證', min_value=1, max_value=30, value=1)
        with col3:
            source = st.text_input('來源/策略', placeholder='例如: K線型態', key='dir_source')

        notes = st.text_area('備註', placeholder='預測理由...', key='dir_notes')

        if st.button('新增方向預測', type='primary', use_container_width=True):
            if selected_stock and current_price:
                stock = stock_map[selected_stock]
                tracker.add_direction_prediction(
                    stock_id=stock['id'],
                    stock_name=stock['name'],
                    current_price=current_price,
                    direction='up' if '漲' in direction else 'down',
                    verify_days=verify_days,
                    source=source or None,
                    notes=notes or None
                )
                st.success(f'✅ 已新增預測: {stock["id"]} {stock["name"]} {direction}')
                st.rerun()

    else:  # 選股追蹤
        col1, col2 = st.columns(2)
        with col1:
            verify_days = st.number_input('驗證天數', min_value=1, max_value=60, value=5, key='pick_days')
        with col2:
            source = st.text_input('策略名稱', placeholder='例如: 價值選股', key='pick_source')

        notes = st.text_area('備註', placeholder='選股理由...', key='pick_notes')

        if st.button('新增選股追蹤', type='primary', use_container_width=True):
            if selected_stock and current_price:
                stock = stock_map[selected_stock]
                tracker.add_stock_pick_prediction(
                    stock_id=stock['id'],
                    stock_name=stock['name'],
                    current_price=current_price,
                    verify_days=verify_days,
                    source=source or None,
                    notes=notes or None
                )
                st.success(f'✅ 已新增選股追蹤: {stock["id"]} {stock["name"]}')
                st.rerun()

# ==================== Tab 3: 預測記錄 ====================
with tab3:
    st.markdown(create_section_header('預測記錄', icon='📋'), unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_days = st.selectbox('顯示期間', [7, 14, 30, 60, 90], index=2,
                                    format_func=lambda x: f'最近 {x} 天', key='record_days')
    with col2:
        filter_status = st.selectbox('狀態篩選', ['全部', '待驗證', '成功', '失敗', '過期'],
                                      key='record_status')
    with col3:
        filter_type = st.selectbox('類型篩選', ['全部', '目標價', '漲跌方向', '選股'],
                                    key='record_type')

    # 取得記錄
    status_map = {
        '全部': None,
        '待驗證': PredictionStatus.PENDING.value,
        '成功': PredictionStatus.SUCCESS.value,
        '失敗': PredictionStatus.FAILED.value,
        '過期': PredictionStatus.EXPIRED.value
    }
    records = tracker.get_recent_predictions(days=filter_days, status=status_map[filter_status])

    # 類型篩選
    type_map = {
        '全部': None,
        '目標價': PredictionType.TARGET_PRICE.value,
        '漲跌方向': PredictionType.DIRECTION.value,
        '選股': PredictionType.STOCK_PICK.value
    }
    if type_map[filter_type]:
        records = [r for r in records if r.type == type_map[filter_type]]

    if not records:
        show_empty_state('沒有符合條件的記錄', icon='📋', suggestion='嘗試調整篩選條件，或新增您的第一筆預測')
    else:
        # 轉換為 DataFrame 顯示
        display_data = []
        for r in records:
            status_icon = {
                'pending': '⏳',
                'success': '✅',
                'failed': '❌',
                'expired': '⏰',
                'cancelled': '🚫'
            }.get(r.status, '❓')

            type_name = {
                'target_price': '目標價',
                'direction': '方向',
                'stock_pick': '選股'
            }.get(r.type, r.type)

            # 預測內容
            if r.type == PredictionType.TARGET_PRICE.value:
                pred_content = f'目標: {r.target_price:.2f}'
            elif r.type == PredictionType.DIRECTION.value:
                pred_content = '看漲' if r.predicted_direction == 'up' else '看跌'
            else:
                pred_content = '追蹤報酬'

            display_data.append({
                'ID': r.id,
                '狀態': status_icon,
                '股票': f'{r.stock_id} {r.stock_name}',
                '類型': type_name,
                '預測': pred_content,
                '建立價': format_number(r.created_price, kind='price'),
                '驗證價': format_number(r.verified_price, kind='price') if r.verified_price else '-',
                '報酬': format_number(r.actual_return, kind='pct', signed=True) if r.actual_return else '-',
                '建立日': r.created_at[:10],
                '到期日': r.expire_date,
                '來源': r.source or '-'
            })

        df = pd.DataFrame(display_data)
        render_data_table(df, freeze_cols=1)

        # 匯出功能
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            '📥 匯出 CSV',
            csv,
            f'predictions_{datetime.now().strftime("%Y%m%d")}.csv',
            'text/csv'
        )

# ==================== Tab 4: 執行驗證 ====================
with tab4:
    st.markdown(create_section_header('執行驗證', icon='🔍'), unsafe_allow_html=True)

    pending = tracker.get_pending_predictions()
    st.info(f'目前有 **{len(pending)}** 筆待驗證的預測')

    if pending:
        st.markdown(create_section_header('待驗證清單', icon='📝'), unsafe_allow_html=True)

        # 清單可能過長 → 分頁顯示，避免一次渲染數百張卡片
        PAGE_SIZE = 20
        total_pages = (len(pending) + PAGE_SIZE - 1) // PAGE_SIZE
        page_idx = 0
        if total_pages > 1:
            page_idx = st.selectbox(
                '頁次', list(range(total_pages)),
                format_func=lambda i: f'第 {i + 1} / {total_pages} 頁'
                                      f'（{i * PAGE_SIZE + 1}-{min((i + 1) * PAGE_SIZE, len(pending))}）',
                key='pending_page',
            )
        start = page_idx * PAGE_SIZE
        page_items = pending[start:start + PAGE_SIZE]

        type_name_map = {'target_price': '目標價', 'direction': '方向', 'stock_pick': '選股'}
        # 可摺疊卡片組：每筆預測一張卡片，預設展開首筆
        for offset, p in enumerate(page_items):
            type_name = type_name_map.get(p.type, p.type)
            with st.expander(f'{p.stock_id} {p.stock_name}　·　{type_name}',
                             expanded=(offset == 0)):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.caption(f'建立: {p.created_at[:10]} | 到期: {p.expire_date}')
                    if p.type == PredictionType.TARGET_PRICE.value:
                        st.write(f'目標: {format_number(p.target_price, kind="price")} '
                                 f'(現價: {format_number(p.created_price, kind="price")})')
                    elif p.type == PredictionType.DIRECTION.value:
                        if p.predicted_direction == 'up':
                            st.markdown(
                                f'<span style="color:{COLORS["up"]};font-weight:600">▲ 看漲 📈</span>',
                                unsafe_allow_html=True)
                        else:
                            st.markdown(
                                f'<span style="color:{COLORS["down"]};font-weight:600">▼ 看跌 📉</span>',
                                unsafe_allow_html=True)
                    else:
                        st.write(f'追蹤 {p.verify_days} 天報酬')
                with col2:
                    if st.button('取消', key=f'cancel_{p.id}', use_container_width=True):
                        tracker.cancel_prediction(p.id)
                        st.rerun()

    st.markdown(create_section_header('驗證操作', icon='🔄'), unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        if st.button('🔄 執行驗證', type='primary', use_container_width=True):
            with st.spinner('驗證中...'):
                results = tracker.verify_predictions(close)

            if results['verified_count'] > 0:
                st.success(f"""
                驗證完成！
                - 驗證筆數: {results['verified_count']}
                - ✅ 成功: {results['success_count']}
                - ❌ 失敗: {results['failed_count']}
                - ⏰ 過期: {results['expired_count']}
                """)

                if results['details']:
                    st.markdown('**詳細結果:**')
                    for d in results['details']:
                        icon = '✅' if d['status'] == 'success' else '❌'
                        ret = format_number(d['return'], kind='pct', signed=True) if d['return'] else 'N/A'
                        st.write(f"{icon} {d['stock']} - 報酬: {ret}")
            else:
                show_empty_state('沒有需要驗證的預測', icon='🔍', suggestion='可能尚未到驗證日期，請稍後再試')

    with col2:
        st.markdown('''
        **驗證說明：**
        - 目標價：檢查期間內最高價是否達到目標
        - 漲跌方向：檢查驗證日收盤價與預測方向
        - 選股勝率：檢查驗證日收盤價是否高於買入價
        ''')

    st.markdown(create_section_header('自動化排程', icon='⏰'), unsafe_allow_html=True)
    st.code('''
# 加入 crontab 每日收盤後執行 (例如每天 15:30)
30 15 * * 1-5 cd /path/to/finlab_db && python scripts/daily_verify.py

# 或使用 launchd (macOS)
# 建立 ~/Library/LaunchAgents/com.finlab.verify.plist
    ''', language='bash')

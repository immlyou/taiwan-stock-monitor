"""
警報設定頁面 - 價格與指標警報
"""
import streamlit as st
import pandas as pd
import json
import uuid
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.data_loader import get_loader, get_active_stocks
from core.indicators import rsi, macd
from app.components.sidebar import render_sidebar_mini

st.set_page_config(page_title='警報設定', page_icon='🔔', layout='wide')

# 渲染側邊欄
render_sidebar_mini(current_page='alerts')

st.title('🔔 警報設定')
st.markdown('設定價格與技術指標警報，條件觸發時通知您')
st.markdown('---')

# 警報檔案路徑
ALERTS_FILE = Path(__file__).parent.parent.parent / 'data' / 'alerts.json'
ALERTS_FILE.parent.mkdir(exist_ok=True)

def load_alerts():
    if ALERTS_FILE.exists():
        with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'alerts': []}

def save_alerts(alerts_data):
    with open(ALERTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(alerts_data, f, ensure_ascii=False, indent=2, default=str)

# 載入數據
@st.cache_data(ttl=3600, show_spinner='載入數據中...')
def load_data():
    loader = get_loader()
    return {
        'close': loader.get('close'),
        'high': loader.get('high'),
        'low': loader.get('low'),
        'volume': loader.get('volume'),
        'stock_info': loader.get_stock_info(),
    }

try:
    data = load_data()
    close = data['close']
    high = data['high']
    low = data['low']
    volume = data['volume']
    stock_info = data['stock_info']
    active_stocks = get_active_stocks()
except Exception as e:
    st.error(f'載入數據失敗: {e}')
    st.stop()

# 股票選項
stock_options = {f"{row['stock_id']} {row['name']}": row['stock_id']
                 for _, row in stock_info.iterrows()
                 if row['stock_id'] in active_stocks}

# 載入警報
alerts_data = load_alerts()
alerts = alerts_data.get('alerts', [])

# 警報類型定義
ALERT_TYPES = {
    'price_above': {'name': '價格突破上方', 'icon': '📈', 'description': '當股價高於設定價格時觸發'},
    'price_below': {'name': '價格跌破下方', 'icon': '📉', 'description': '當股價低於設定價格時觸發'},
    'rsi_above': {'name': 'RSI 超買', 'icon': '🔥', 'description': '當 RSI 高於設定值時觸發（預設 70）'},
    'rsi_below': {'name': 'RSI 超賣', 'icon': '❄️', 'description': '當 RSI 低於設定值時觸發（預設 30）'},
    'volume_spike': {'name': '成交量爆量', 'icon': '💥', 'description': '當成交量超過 N 日平均的倍數時觸發'},
    'ma_cross_up': {'name': '均線黃金交叉', 'icon': '✨', 'description': '當短期均線向上穿越長期均線時觸發'},
    'ma_cross_down': {'name': '均線死亡交叉', 'icon': '💀', 'description': '當短期均線向下穿越長期均線時觸發'},
    'new_high': {'name': '創新高', 'icon': '🏆', 'description': '當股價創 N 日新高時觸發'},
    'new_low': {'name': '創新低', 'icon': '📊', 'description': '當股價創 N 日新低時觸發'},
}

# ========== 建立新警報 ==========
st.markdown('### ➕ 建立新警報')

col1, col2 = st.columns(2)

with col1:
    alert_stock = st.selectbox('選擇股票', list(stock_options.keys()))
    alert_stock_id = stock_options[alert_stock]

    alert_type = st.selectbox(
        '警報類型',
        list(ALERT_TYPES.keys()),
        format_func=lambda x: f"{ALERT_TYPES[x]['icon']} {ALERT_TYPES[x]['name']}"
    )

    st.caption(ALERT_TYPES[alert_type]['description'])

with col2:
    # 根據警報類型顯示不同的參數設定
    if alert_type in ['price_above', 'price_below']:
        # 取得當前股價作為參考
        if alert_stock_id in close.columns:
            current_price = close[alert_stock_id].dropna().iloc[-1]
        else:
            current_price = 100

        alert_value = st.number_input(
            '目標價格',
            min_value=1.0,
            max_value=10000.0,
            value=float(current_price),
            step=1.0,
            help=f'當前股價: {current_price:.2f}'
        )

    elif alert_type in ['rsi_above', 'rsi_below']:
        default_rsi = 70 if alert_type == 'rsi_above' else 30
        alert_value = st.number_input(
            'RSI 門檻值',
            min_value=0,
            max_value=100,
            value=default_rsi,
            step=5
        )

    elif alert_type == 'volume_spike':
        alert_value = st.number_input(
            '量能倍數',
            min_value=1.0,
            max_value=10.0,
            value=2.0,
            step=0.5,
            help='成交量超過 N 日平均的倍數'
        )

    elif alert_type in ['ma_cross_up', 'ma_cross_down']:
        col_a, col_b = st.columns(2)
        with col_a:
            short_ma = st.number_input('短期均線', 5, 50, 5)
        with col_b:
            long_ma = st.number_input('長期均線', 10, 200, 20)
        alert_value = f'{short_ma},{long_ma}'

    elif alert_type in ['new_high', 'new_low']:
        alert_value = st.number_input(
            '天數範圍',
            min_value=5,
            max_value=252,
            value=20,
            step=5,
            help='創 N 日新高/新低'
        )

    else:
        alert_value = st.number_input('設定值', value=0.0)

    # 通知設定
    alert_note = st.text_input('備註 (選填)', placeholder='例如：突破前高')

if st.button('🔔 建立警報', type='primary', use_container_width=True):
    new_alert = {
        'id': str(uuid.uuid4())[:8],
        'stock_id': alert_stock_id,
        'type': alert_type,
        'value': alert_value,
        'note': alert_note,
        'enabled': True,
        'triggered': False,
        'created_at': datetime.now().isoformat(),
        'triggered_at': None,
    }

    alerts_data['alerts'].append(new_alert)
    save_alerts(alerts_data)
    st.success(f'警報已建立！當 {alert_stock_id} {ALERT_TYPES[alert_type]["name"]} {alert_value} 時通知您')
    st.rerun()

st.markdown('---')

# ========== 警報列表 ==========
st.markdown('### 📋 警報列表')

if alerts:
    # 分類顯示
    tab1, tab2, tab3 = st.tabs(['🟢 啟用中', '🔴 已觸發', '⚪ 已停用'])

    with tab1:
        active_alerts = [a for a in alerts if a.get('enabled') and not a.get('triggered')]

        if active_alerts:
            for alert in active_alerts:
                stock_id = alert['stock_id']
                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''

                alert_type_info = ALERT_TYPES.get(alert['type'], {})

                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    st.markdown(f'''
                    **{stock_id} {name}**
                    {alert_type_info.get('icon', '')} {alert_type_info.get('name', alert['type'])} `{alert['value']}`
                    ''')
                    if alert.get('note'):
                        st.caption(f"備註: {alert['note']}")

                with col2:
                    # 檢查當前狀態
                    if stock_id in close.columns:
                        current_price = close[stock_id].dropna().iloc[-1]
                        st.metric('當前價', f'{current_price:.2f}')

                with col3:
                    if st.button('停用', key=f"disable_{alert['id']}"):
                        for a in alerts_data['alerts']:
                            if a['id'] == alert['id']:
                                a['enabled'] = False
                        save_alerts(alerts_data)
                        st.rerun()

                    if st.button('刪除', key=f"delete_{alert['id']}"):
                        alerts_data['alerts'] = [a for a in alerts_data['alerts'] if a['id'] != alert['id']]
                        save_alerts(alerts_data)
                        st.rerun()

                st.markdown('---')
        else:
            st.info('目前沒有啟用中的警報')

    with tab2:
        triggered_alerts = [a for a in alerts if a.get('triggered')]

        if triggered_alerts:
            for alert in triggered_alerts:
                stock_id = alert['stock_id']
                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''

                alert_type_info = ALERT_TYPES.get(alert['type'], {})

                col1, col2 = st.columns([4, 1])

                with col1:
                    st.markdown(f'''
                    **{stock_id} {name}** - 已觸發
                    {alert_type_info.get('icon', '')} {alert_type_info.get('name', alert['type'])} `{alert['value']}`
                    觸發時間: {alert.get('triggered_at', '未知')[:19] if alert.get('triggered_at') else '未知'}
                    ''')

                with col2:
                    if st.button('重新啟用', key=f"reset_{alert['id']}"):
                        for a in alerts_data['alerts']:
                            if a['id'] == alert['id']:
                                a['triggered'] = False
                                a['triggered_at'] = None
                        save_alerts(alerts_data)
                        st.rerun()

                st.markdown('---')
        else:
            st.info('目前沒有已觸發的警報')

    with tab3:
        disabled_alerts = [a for a in alerts if not a.get('enabled')]

        if disabled_alerts:
            for alert in disabled_alerts:
                stock_id = alert['stock_id']
                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''

                alert_type_info = ALERT_TYPES.get(alert['type'], {})

                col1, col2 = st.columns([4, 1])

                with col1:
                    st.markdown(f'''
                    **{stock_id} {name}** - 已停用
                    {alert_type_info.get('icon', '')} {alert_type_info.get('name', alert['type'])} `{alert['value']}`
                    ''')

                with col2:
                    if st.button('啟用', key=f"enable_{alert['id']}"):
                        for a in alerts_data['alerts']:
                            if a['id'] == alert['id']:
                                a['enabled'] = True
                        save_alerts(alerts_data)
                        st.rerun()

                st.markdown('---')
        else:
            st.info('目前沒有已停用的警報')

else:
    st.info('尚未建立任何警報')

st.markdown('---')

# ========== 立即檢查警報 ==========
st.markdown('### 🔍 立即檢查警報')

if st.button('檢查所有警報', use_container_width=True):
    with st.spinner('檢查中...'):
        triggered_count = 0

        for alert in alerts_data['alerts']:
            if not alert.get('enabled') or alert.get('triggered'):
                continue

            stock_id = alert['stock_id']
            alert_type = alert['type']
            alert_value = alert['value']

            if stock_id not in close.columns:
                continue

            stock_close = close[stock_id].dropna()
            current_price = stock_close.iloc[-1]
            is_triggered = False

            # 檢查各種警報條件
            if alert_type == 'price_above' and current_price > alert_value:
                is_triggered = True

            elif alert_type == 'price_below' and current_price < alert_value:
                is_triggered = True

            elif alert_type == 'rsi_above':
                rsi = rsi(stock_close, period=14)
                if rsi.iloc[-1] > alert_value:
                    is_triggered = True

            elif alert_type == 'rsi_below':
                rsi = rsi(stock_close, period=14)
                if rsi.iloc[-1] < alert_value:
                    is_triggered = True

            elif alert_type == 'volume_spike':
                if stock_id in volume.columns:
                    stock_volume = volume[stock_id].dropna()
                    avg_volume = stock_volume.tail(20).mean()
                    if stock_volume.iloc[-1] > avg_volume * alert_value:
                        is_triggered = True

            elif alert_type == 'new_high':
                lookback = int(alert_value)
                if current_price >= stock_close.tail(lookback).max():
                    is_triggered = True

            elif alert_type == 'new_low':
                lookback = int(alert_value)
                if current_price <= stock_close.tail(lookback).min():
                    is_triggered = True

            if is_triggered:
                alert['triggered'] = True
                alert['triggered_at'] = datetime.now().isoformat()
                triggered_count += 1

                info = stock_info[stock_info['stock_id'] == stock_id]
                name = info['name'].values[0] if len(info) > 0 else ''
                st.warning(f"🔔 觸發: {stock_id} {name} - {ALERT_TYPES[alert_type]['name']} {alert_value}")

        save_alerts(alerts_data)

        if triggered_count == 0:
            st.success('所有警報條件均未達成')
        else:
            st.info(f'共觸發 {triggered_count} 個警報')

# ========== 說明 ==========
with st.expander('📖 使用說明'):
    st.markdown('''
    ### 警報類型說明

    | 類型 | 說明 | 適用場景 |
    |------|------|----------|
    | 價格突破上方 | 股價 > 設定值 | 突破壓力位 |
    | 價格跌破下方 | 股價 < 設定值 | 跌破支撐位 |
    | RSI 超買 | RSI > 設定值 | 短線過熱 |
    | RSI 超賣 | RSI < 設定值 | 短線超跌 |
    | 成交量爆量 | 成交量 > N倍均量 | 主力進場 |
    | 創新高/新低 | N日內最高/最低價 | 趨勢確認 |

    ### 使用建議

    1. **價格警報**：設定在重要支撐/壓力位
    2. **RSI 警報**：超買設 70-80，超賣設 20-30
    3. **成交量警報**：爆量設定建議 1.5-2 倍
    4. **定期檢查**：可設定排程自動檢查警報

    ### 自動檢查

    如需自動檢查警報，可在「系統設定」頁面設定排程任務。
    ''')

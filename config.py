"""
系統設定檔
"""
from pathlib import Path

# 資料夾路徑
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR  # pickle 檔案在根目錄

# 數據檔案對應
DATA_FILES = {
    # 價格數據
    'close': 'price#收盤價.pickle',
    'open': 'price#開盤價.pickle',
    'high': 'price#最高價.pickle',
    'low': 'price#最低價.pickle',
    'volume': 'price#成交股數.pickle',

    # ETL 處理後數據
    'adj_close': 'etl#adj_close.pickle',
    'market_value': 'etl#market_value.pickle',
    'is_flagged': 'etl#is_flagged_stock.pickle',

    # 本益比相關
    'pe_ratio': 'price_earning_ratio#本益比.pickle',
    'pb_ratio': 'price_earning_ratio#股價淨值比.pickle',
    'dividend_yield': 'price_earning_ratio#殖利率(%).pickle',

    # 月營收
    'monthly_revenue': 'monthly_revenue#當月營收.pickle',
    'revenue_yoy': 'monthly_revenue#去年同月增減(%).pickle',
    'revenue_mom': 'monthly_revenue#上月比較增減(%).pickle',

    # 其他
    'benchmark': 'benchmark_return#發行量加權股價報酬指數.pickle',
    'categories': 'security_categories.pickle',

    # 三大法人買賣超
    'foreign_investors': 'institutional_investors_trading_summary#外陸資買賣超股數(不含外資自營商).pickle',
    'investment_trust': 'institutional_investors_trading_summary#投信買賣超股數.pickle',
    'dealer': 'institutional_investors_trading_summary#自營商買賣超股數(自行買賣).pickle',

    # 外資持股
    'foreign_holding': 'foreign_investors_shareholding#全體外資及陸資持股比率.pickle',

    # 融資融券
    'margin_buy': 'margin_transactions#融資今日餘額.pickle',
    'margin_sell': 'margin_transactions#融券今日餘額.pickle',
}

# 交易成本設定
TRADING_COSTS = {
    'commission_rate': 0.001425,  # 手續費 0.1425%
    'tax_rate': 0.003,            # 交易稅 0.3%
    'discount': 0.6,              # 券商手續費折扣 (預設6折)
}

# 台股漲跌幅限制設定
PRICE_LIMITS = {
    'up_limit': 0.10,      # 漲停 +10%
    'down_limit': -0.10,   # 跌停 -10%
    'enabled': True,       # 是否啟用漲跌幅限制
}

# 流動性篩選門檻
LIQUIDITY_FILTERS = {
    'min_daily_volume': 500,        # 最低日成交量 (張)
    'min_daily_turnover': 5000000,  # 最低日成交金額 (元)
    'avg_period': 20,               # 平均計算天數
    'enabled': True,                # 是否啟用流動性檢查
}

# 回測預設設定
BACKTEST_DEFAULTS = {
    'initial_capital': 1_000_000,  # 初始資金 100萬
    'rebalance_freq': 'M',          # 換股頻率: M=月, Q=季
    'max_stocks': 10,               # 最大持股數
    'weight_method': 'equal',       # equal=等權重, market_cap=市值加權
}

# 策略預設參數
STRATEGY_PARAMS = {
    'value': {
        'pe_max': 15,
        'pb_max': 1.5,
        'dividend_yield_min': 4.0,
    },
    'growth': {
        'revenue_yoy_min': 20,
        'revenue_mom_min': 10,
        'consecutive_months': 3,
    },
    'momentum': {
        'breakout_days': 20,
        'volume_ratio': 1.5,
        'rsi_min': 50,
        'rsi_max': 80,
    },
}

# 策略預設組合 (保守/標準/激進)
STRATEGY_PRESETS = {
    'value': {
        'conservative': {
            'name': '保守型',
            'description': '低風險，注重安全邊際',
            'params': {
                'pe_max': 12.0,
                'pb_max': 1.0,
                'dividend_yield_min': 5.0,
                'use_pe': True,
                'use_pb': True,
                'use_dividend': True,
            },
        },
        'standard': {
            'name': '標準型',
            'description': '平衡風險與收益',
            'params': {
                'pe_max': 20.0,
                'pb_max': 1.5,
                'dividend_yield_min': 4.0,
                'use_pe': True,
                'use_pb': True,
                'use_dividend': True,
            },
        },
        'aggressive': {
            'name': '積極型',
            'description': '追求較高報酬，容忍較高估值',
            'params': {
                'pe_max': 30.0,
                'pb_max': 2.5,
                'dividend_yield_min': 2.5,
                'use_pe': True,
                'use_pb': True,
                'use_dividend': True,
            },
        },
    },
    'growth': {
        'conservative': {
            'name': '保守型',
            'description': '要求穩定高成長',
            'params': {
                'revenue_yoy_min': 10.0,
                'revenue_mom_min': 5.0,
                'consecutive_months': 6,
                'use_yoy': True,
                'use_mom': True,
            },
        },
        'standard': {
            'name': '標準型',
            'description': '平衡成長要求',
            'params': {
                'revenue_yoy_min': 20.0,
                'revenue_mom_min': 10.0,
                'consecutive_months': 3,
                'use_yoy': True,
                'use_mom': True,
            },
        },
        'aggressive': {
            'name': '積極型',
            'description': '追求爆發性成長',
            'params': {
                'revenue_yoy_min': 40.0,
                'revenue_mom_min': 20.0,
                'consecutive_months': 2,
                'use_yoy': True,
                'use_mom': True,
            },
        },
    },
    'momentum': {
        'conservative': {
            'name': '保守型',
            'description': '長週期突破，穩健動能',
            'params': {
                'breakout_days': 60,
                'volume_ratio': 1.2,
                'rsi_min': 40,
                'rsi_max': 70,
                'use_breakout': True,
                'use_volume': True,
                'use_rsi': True,
            },
        },
        'standard': {
            'name': '標準型',
            'description': '中週期動能策略',
            'params': {
                'breakout_days': 20,
                'volume_ratio': 1.5,
                'rsi_min': 50,
                'rsi_max': 80,
                'use_breakout': True,
                'use_volume': True,
                'use_rsi': True,
            },
        },
        'aggressive': {
            'name': '積極型',
            'description': '短週期高動能',
            'params': {
                'breakout_days': 10,
                'volume_ratio': 2.0,
                'rsi_min': 60,
                'rsi_max': 90,
                'use_breakout': True,
                'use_volume': True,
                'use_rsi': True,
            },
        },
    },
}

# 通知設定
NOTIFICATION_CONFIG = {
    'line_notify': {
        'enabled': False,
        'token': '',  # LINE Notify Token
    },
    'telegram': {
        'enabled': False,
        'token': '',     # Telegram Bot Token (從 @BotFather 取得)
        'chat_id': '',   # 目標 Chat ID (從 @userinfobot 取得)
    },
    'email': {
        'enabled': False,
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'sender': '',
        'password': '',
        'recipients': [],
    },
}

# Streamlit 設定
STREAMLIT_CONFIG = {
    'page_title': '台股分析系統',
    'page_icon': '📈',
    'layout': 'wide',
}

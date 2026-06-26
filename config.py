"""
系統設定檔
"""
import os
from pathlib import Path

# 資料夾路徑
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR  # pickle 檔案在根目錄

# 統一數據登錄表 - 單一來源，同時描述本地 pickle 檔名與 FinLab API 鍵名
# 所有數據映射都應從此處衍生，不應在其他模組重複定義
DATA_REGISTRY = {
    # 價格數據
    'close':          {'file': 'price#收盤價.pickle',                                                                'finlab_key': 'price:收盤價'},
    'open':           {'file': 'price#開盤價.pickle',                                                                'finlab_key': 'price:開盤價'},
    'high':           {'file': 'price#最高價.pickle',                                                                'finlab_key': 'price:最高價'},
    'low':            {'file': 'price#最低價.pickle',                                                                'finlab_key': 'price:最低價'},
    'volume':         {'file': 'price#成交股數.pickle',                                                              'finlab_key': 'price:成交股數'},

    # ETL 處理後數據
    'adj_close':      {'file': 'etl#adj_close.pickle',                                                              'finlab_key': 'etl:adj_close'},
    'market_value':   {'file': 'etl#market_value.pickle',                                                           'finlab_key': 'etl:market_value'},
    'is_flagged':     {'file': 'etl#is_flagged_stock.pickle',                                                       'finlab_key': 'etl:is_flagged_stock'},

    # 本益比相關
    'pe_ratio':       {'file': 'price_earning_ratio#本益比.pickle',                                                 'finlab_key': 'price_earning_ratio:本益比'},
    'pb_ratio':       {'file': 'price_earning_ratio#股價淨值比.pickle',                                             'finlab_key': 'price_earning_ratio:股價淨值比'},
    'dividend_yield': {'file': 'price_earning_ratio#殖利率(%).pickle',                                              'finlab_key': 'price_earning_ratio:殖利率(%)'},

    # 月營收
    'monthly_revenue':   {'file': 'monthly_revenue#當月營收.pickle',                                                'finlab_key': 'monthly_revenue:當月營收'},
    'revenue_yoy':       {'file': 'monthly_revenue#去年同月增減(%).pickle',                                        'finlab_key': 'monthly_revenue:去年同月增減(%)'},
    'revenue_mom':       {'file': 'monthly_revenue#上月比較增減(%).pickle',                                        'finlab_key': 'monthly_revenue:上月比較增減(%)'},

    # 其他
    'benchmark':      {'file': 'benchmark_return#發行量加權股價報酬指數.pickle',                                    'finlab_key': 'benchmark_return:發行量加權股價報酬指數'},
    'taiex_price':    {'file': 'stock_index_price#收盤指數.pickle',                                                  'finlab_key': 'stock_index_price:收盤指數'},
    'categories':     {'file': 'security_categories.pickle',                                                         'finlab_key': 'security_categories'},

    # 三大法人買賣超
    'foreign_investors': {'file': 'institutional_investors_trading_summary#外陸資買賣超股數(不含外資自營商).pickle', 'finlab_key': 'institutional_investors_trading_summary:外陸資買賣超股數(不含外資自營商)'},
    'investment_trust':  {'file': 'institutional_investors_trading_summary#投信買賣超股數.pickle',                   'finlab_key': 'institutional_investors_trading_summary:投信買賣超股數'},
    'dealer':            {'file': 'institutional_investors_trading_summary#自營商買賣超股數(自行買賣).pickle',       'finlab_key': 'institutional_investors_trading_summary:自營商買賣超股數(自行買賣)'},

    # 外資持股
    'foreign_holding':   {'file': 'foreign_investors_shareholding#全體外資及陸資持股比率.pickle',                   'finlab_key': 'foreign_investors_shareholding:全體外資及陸資持股比率'},

    # 融資融券
    'margin_buy':        {'file': 'margin_transactions#融資今日餘額.pickle',                                        'finlab_key': 'margin_transactions:融資今日餘額'},
    'margin_sell':       {'file': 'margin_transactions#融券今日餘額.pickle',                                        'finlab_key': 'margin_transactions:融券今日餘額'},

    # 大戶持股分布（籌碼分析用）
    'inventory_total_holders':   {'file': 'etl#inventory#全部人數.pickle',          'finlab_key': 'etl:inventory:全部人數'},
    'inventory_over_1000_ratio': {'file': 'etl#inventory#大於一千張佔比.pickle',    'finlab_key': 'etl:inventory:大於一千張佔比'},
    'inventory_over_1000_shares':{'file': 'etl#inventory#大於一千張股數.pickle',    'finlab_key': 'etl:inventory:大於一千張股數'},
    'inventory_over_100_ratio':  {'file': 'etl#inventory#大於一百張佔比.pickle',    'finlab_key': 'etl:inventory:大於一百張佔比'},
    'inventory_over_400_holders':{'file': 'etl#inventory#大於四百張人數.pickle',    'finlab_key': 'etl:inventory:大於四百張人數'},
    'inventory_over_400_ratio':  {'file': 'etl#inventory#大於四百張佔比.pickle',    'finlab_key': 'etl:inventory:大於四百張佔比'},
    'inventory_over_400_shares': {'file': 'etl#inventory#大於四百張股數.pickle',    'finlab_key': 'etl:inventory:大於四百張股數'},
    'inventory_under_10_holders':{'file': 'etl#inventory#小於十張人數.pickle',      'finlab_key': 'etl:inventory:小於十張人數'},
    'inventory_under_10_ratio':  {'file': 'etl#inventory#小於十張佔比.pickle',      'finlab_key': 'etl:inventory:小於十張佔比'},
    'inventory_under_10_shares': {'file': 'etl#inventory#小於十張股數.pickle',      'finlab_key': 'etl:inventory:小於十張股數'},
}

# 向後相容：從 DATA_REGISTRY 自動衍生的 DATA_FILES 字典（維持舊介面）
DATA_FILES = {key: entry['file'] for key, entry in DATA_REGISTRY.items()}

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
    'rebalance_freq': 'ME',         # 換股頻率: ME=月底, QE=季底 (pandas 2.2+ 格式)
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
                'use_consecutive': False,
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
                'use_consecutive': True,
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
                'use_consecutive': True,
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

# 通知設定 — 敏感憑證從環境變數讀取
NOTIFICATION_CONFIG = {
    'line_notify': {
        'enabled': False,
        'token': os.getenv('LINE_NOTIFY_TOKEN', ''),  # LINE Notify Token
    },
    'telegram': {
        'enabled': False,
        'token': os.getenv('TELEGRAM_BOT_TOKEN', ''),     # Telegram Bot Token (從 @BotFather 取得)
        'chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),     # 目標 Chat ID (從 @userinfobot 取得)
    },
    'email': {
        'enabled': False,
        'smtp_server': os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com'),
        'smtp_port': int(os.getenv('EMAIL_SMTP_PORT', '587')),
        'sender': os.getenv('EMAIL_SENDER', ''),
        'password': os.getenv('EMAIL_PASSWORD', ''),
        'recipients': os.getenv('EMAIL_RECIPIENTS', '').split(',') if os.getenv('EMAIL_RECIPIENTS') else [],
    },
}

# Cache TTL 設定 (秒)
CACHE_TTL = {
    'realtime': 60,       # 即時資料 (報價、當前市場)
    'intraday': 300,      # 盤中資料 (市場總覽、熱力圖)
    'daily': 3600,        # 日頻資料 (分析、回測)
    'static': 86400,      # 靜態資料 (股票資訊、產業分類)
}

# Streamlit 設定
STREAMLIT_CONFIG = {
    'page_title': '台股分析系統',
    'page_icon': '📈',
    'layout': 'wide',
}

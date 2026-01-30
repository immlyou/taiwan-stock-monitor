"""
Pytest 共用 fixtures 和設定
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 設定路徑
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope='session')
def sample_dates():
    """生成測試用日期索引"""
    start = datetime(2023, 1, 1)
    dates = pd.date_range(start, periods=252, freq='B')  # 一年交易日
    return dates


@pytest.fixture(scope='session')
def sample_stocks():
    """測試用股票代碼"""
    return ['2330', '2317', '2454', '2412', '2308']


@pytest.fixture(scope='session')
def sample_close(sample_dates, sample_stocks):
    """生成模擬收盤價數據"""
    np.random.seed(42)
    n_days = len(sample_dates)
    n_stocks = len(sample_stocks)

    # 生成隨機價格走勢
    returns = np.random.normal(0.0005, 0.02, (n_days, n_stocks))
    prices = 100 * np.exp(np.cumsum(returns, axis=0))

    df = pd.DataFrame(prices, index=sample_dates, columns=sample_stocks)
    return df


@pytest.fixture(scope='session')
def sample_volume(sample_dates, sample_stocks):
    """生成模擬成交量數據"""
    np.random.seed(42)
    n_days = len(sample_dates)
    n_stocks = len(sample_stocks)

    volume = np.random.randint(1000, 50000, (n_days, n_stocks)) * 1000
    df = pd.DataFrame(volume, index=sample_dates, columns=sample_stocks)
    return df


@pytest.fixture(scope='session')
def sample_returns(sample_close):
    """計算日報酬率"""
    return sample_close.pct_change().dropna()


@pytest.fixture(scope='session')
def sample_stock_info(sample_stocks):
    """生成測試用股票資訊"""
    names = ['台積電', '鴻海', '聯發科', '中華電', '台達電']
    industries = ['半導體', '電子', '半導體', '電信', '電子']

    df = pd.DataFrame({
        'stock_id': sample_stocks,
        'name': names,
        'industry': industries,
    })
    return df


@pytest.fixture
def temp_data_dir(tmp_path):
    """建立臨時數據目錄"""
    data_dir = tmp_path / 'data'
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_loader(sample_close, sample_volume):
    """模擬 DataLoader"""
    class MockLoader:
        def get(self, key):
            if key == 'close':
                return sample_close
            elif key == 'volume':
                return sample_volume
            return None

        def get_stock_info(self):
            return pd.DataFrame({
                'stock_id': sample_close.columns,
                'name': ['Stock_' + s for s in sample_close.columns],
            })

    return MockLoader()

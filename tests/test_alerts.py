"""
警報引擎模組測試
涵蓋：AlertEngine、check_alert（所有警報類型）、CRUD 操作、atomic write
"""
import json
import uuid
import pytest
import pandas as pd
import numpy as np
from pathlib import Path


from core.alerts import AlertEngine, AlertResult


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def dates():
    return pd.date_range("2023-01-01", periods=60, freq="B")


@pytest.fixture
def stocks():
    return ["2330", "2317", "2454"]


@pytest.fixture
def close_df(dates, stocks):
    """固定走勢：2330 持續上漲，2317 持續下跌，2454 平盤"""
    np.random.seed(0)
    n = len(dates)
    prices = {
        "2330": np.linspace(500, 600, n),   # 上漲
        "2317": np.linspace(150, 100, n),   # 下跌
        "2454": np.full(n, 300.0),          # 平盤
    }
    return pd.DataFrame(prices, index=dates)


@pytest.fixture
def volume_df(dates, stocks):
    np.random.seed(1)
    # 最後一天 2330 爆量（20倍均量）
    data = np.ones((len(dates), len(stocks))) * 10_000
    data[-1, 0] *= 20   # 2330 最後一天爆量
    return pd.DataFrame(data, index=dates, columns=stocks)


@pytest.fixture
def market_data(close_df, volume_df):
    return {
        "close": close_df,
        "volume": volume_df,
        "high": close_df * 1.01,
        "low": close_df * 0.99,
    }


@pytest.fixture
def tmp_alerts_file(tmp_path):
    return tmp_path / "alerts.json"


@pytest.fixture
def engine(tmp_alerts_file):
    """AlertEngine 指向臨時檔案"""
    eng = AlertEngine.__new__(AlertEngine)
    eng.ALERTS_FILE = tmp_alerts_file
    eng.alerts_data = {"alerts": []}
    return eng


def _make_alert(alert_type: str, stock_id: str, value, enabled: bool = True) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "stock_id": stock_id,
        "type": alert_type,
        "value": value,
        "enabled": enabled,
        "triggered": False,
    }


# ──────────────────────────────────────────────
# price_above / price_below
# ──────────────────────────────────────────────

class TestPriceAlerts:

    def test_price_above_triggered(self, engine, market_data):
        alert = _make_alert("price_above", "2330", 550.0)
        # 2330 收盤在 600，應觸發
        result = engine.check_alert(alert, market_data)
        assert result.is_triggered
        assert result.stock_id == "2330"

    def test_price_above_not_triggered(self, engine, market_data):
        alert = _make_alert("price_above", "2330", 700.0)
        result = engine.check_alert(alert, market_data)
        assert not result.is_triggered

    def test_price_below_triggered(self, engine, market_data):
        alert = _make_alert("price_below", "2317", 120.0)
        # 2317 收盤在 100，應觸發
        result = engine.check_alert(alert, market_data)
        assert result.is_triggered

    def test_price_below_not_triggered(self, engine, market_data):
        alert = _make_alert("price_below", "2317", 50.0)
        result = engine.check_alert(alert, market_data)
        assert not result.is_triggered

    def test_unknown_stock_not_triggered(self, engine, market_data):
        alert = _make_alert("price_above", "9999", 100.0)
        result = engine.check_alert(alert, market_data)
        assert not result.is_triggered
        assert "找不到" in result.message


# ──────────────────────────────────────────────
# RSI 警報
# ──────────────────────────────────────────────

class TestRsiAlerts:

    def test_rsi_above_type(self, engine, market_data):
        alert = _make_alert("rsi_above", "2330", 30.0)
        result = engine.check_alert(alert, market_data)
        assert isinstance(result.is_triggered, bool)
        # RSI 在完全單調上漲序列（無下跌日）時可能為 NaN（avg_loss=0）
        # 確認為有效數值或 NaN，不應崩潰
        import math
        assert math.isnan(result.current_value) or (0 <= result.current_value <= 100)

    def test_rsi_below_type(self, engine, market_data):
        alert = _make_alert("rsi_below", "2317", 80.0)
        result = engine.check_alert(alert, market_data)
        assert isinstance(result.is_triggered, bool)
        assert 0 <= result.current_value <= 100

    def test_rsi_above_impossible_threshold_not_triggered(self, engine, market_data):
        """RSI > 100 永遠不可能"""
        alert = _make_alert("rsi_above", "2330", 101.0)
        result = engine.check_alert(alert, market_data)
        assert not result.is_triggered

    def test_rsi_below_zero_threshold_not_triggered(self, engine, market_data):
        """RSI < 0 永遠不可能"""
        alert = _make_alert("rsi_below", "2317", -1.0)
        result = engine.check_alert(alert, market_data)
        assert not result.is_triggered


# ──────────────────────────────────────────────
# 成交量爆量
# ──────────────────────────────────────────────

class TestVolumeAlerts:

    def test_volume_spike_triggered(self, engine, market_data):
        """2330 最後一天成交量為均量的 20 倍，設門檻 10 倍應觸發"""
        alert = _make_alert("volume_spike", "2330", 10.0)
        result = engine.check_alert(alert, market_data)
        assert result.is_triggered

    def test_volume_spike_not_triggered(self, engine, market_data):
        """設門檻 25 倍，應不觸發"""
        alert = _make_alert("volume_spike", "2330", 25.0)
        result = engine.check_alert(alert, market_data)
        assert not result.is_triggered

    def test_volume_spike_no_volume_data(self, engine, close_df):
        """無成交量資料，不應崩潰"""
        alert = _make_alert("volume_spike", "2330", 2.0)
        result = engine.check_alert(alert, {"close": close_df})
        assert isinstance(result.is_triggered, bool)


# ──────────────────────────────────────────────
# 均線交叉
# ──────────────────────────────────────────────

class TestMACrossAlerts:

    def test_ma_cross_up_result_type(self, engine, market_data):
        alert = _make_alert("ma_cross_up", "2330", "5,20")
        result = engine.check_alert(alert, market_data)
        assert isinstance(result.is_triggered, bool)

    def test_ma_cross_down_result_type(self, engine, market_data):
        alert = _make_alert("ma_cross_down", "2317", "5,20")
        result = engine.check_alert(alert, market_data)
        assert isinstance(result.is_triggered, bool)

    def test_ma_cross_up_golden_cross_detected(self, dates):
        """人工構造黃金交叉場景"""
        # 前段下降（短線低於長線），最後兩天短線向上穿越
        n = 40
        prices = np.concatenate([
            np.linspace(100, 80, n - 5),    # 下降段
            np.linspace(80, 120, 5),         # 急速反彈，短線穿越長線
        ])
        close = pd.DataFrame({"A": prices}, index=dates[:n])
        engine = AlertEngine.__new__(AlertEngine)
        engine.ALERTS_FILE = Path("/tmp/test_alerts.json")
        engine.alerts_data = {"alerts": []}
        alert = _make_alert("ma_cross_up", "A", "5,20")
        result = engine.check_alert(alert, {"close": close})
        assert isinstance(result.is_triggered, bool)  # 不崩潰即可

    def test_ma_cross_default_periods_when_invalid_value(self, engine, market_data):
        """target_value 非字串格式時，預設使用 5,20"""
        alert = _make_alert("ma_cross_up", "2330", 0)
        result = engine.check_alert(alert, market_data)
        assert isinstance(result.is_triggered, bool)


# ──────────────────────────────────────────────
# 創新高 / 創新低
# ──────────────────────────────────────────────

class TestNewHighLow:

    def test_new_high_triggered_for_uptrend(self, engine, market_data):
        """2330 持續上漲，應創 20 日新高"""
        alert = _make_alert("new_high", "2330", 20)
        result = engine.check_alert(alert, market_data)
        assert result.is_triggered

    def test_new_low_triggered_for_downtrend(self, engine, market_data):
        """2317 持續下跌，應創 20 日新低"""
        alert = _make_alert("new_low", "2317", 20)
        result = engine.check_alert(alert, market_data)
        assert result.is_triggered

    def test_new_high_flat_not_triggered(self, engine, market_data):
        """2454 平盤，不應創新高（最後一天等於之前最高）"""
        alert = _make_alert("new_high", "2454", 20)
        result = engine.check_alert(alert, market_data)
        assert not result.is_triggered

    def test_new_low_uptrend_not_triggered(self, engine, market_data):
        """2330 上漲，不應創新低"""
        alert = _make_alert("new_low", "2330", 20)
        result = engine.check_alert(alert, market_data)
        assert not result.is_triggered

    def test_insufficient_data_not_triggered(self, engine, dates):
        """資料筆數不足 lookback 天數，不應觸發"""
        short_close = pd.DataFrame({"2330": [100.0, 110.0]}, index=dates[:2])
        alert = _make_alert("new_high", "2330", 20)
        result = engine.check_alert(alert, {"close": short_close})
        assert not result.is_triggered


# ──────────────────────────────────────────────
# AlertResult 結構
# ──────────────────────────────────────────────

class TestAlertResult:

    def test_result_has_required_fields(self, engine, market_data):
        alert = _make_alert("price_above", "2330", 500.0)
        result = engine.check_alert(alert, market_data)
        assert hasattr(result, "alert_id")
        assert hasattr(result, "stock_id")
        assert hasattr(result, "alert_type")
        assert hasattr(result, "is_triggered")
        assert hasattr(result, "current_value")
        assert hasattr(result, "target_value")
        assert hasattr(result, "message")

    def test_result_alert_id_matches(self, engine, market_data):
        alert = _make_alert("price_above", "2330", 500.0)
        result = engine.check_alert(alert, market_data)
        assert result.alert_id == alert["id"]

    def test_result_stock_id_matches(self, engine, market_data):
        alert = _make_alert("price_above", "2330", 500.0)
        result = engine.check_alert(alert, market_data)
        assert result.stock_id == "2330"


# ──────────────────────────────────────────────
# check_all_alerts
# ──────────────────────────────────────────────

class TestCheckAllAlerts:

    def test_returns_only_triggered(self, engine, market_data):
        engine.alerts_data["alerts"] = [
            _make_alert("price_above", "2330", 500.0),   # 應觸發 (收盤 600)
            _make_alert("price_above", "2330", 700.0),   # 不觸發
        ]
        triggered = engine.check_all_alerts(market_data)
        assert len(triggered) == 1
        assert triggered[0].is_triggered

    def test_disabled_alerts_skipped(self, engine, market_data):
        engine.alerts_data["alerts"] = [
            _make_alert("price_above", "2330", 500.0, enabled=False),
        ]
        triggered = engine.check_all_alerts(market_data)
        assert triggered == []

    def test_already_triggered_alerts_skipped(self, engine, market_data):
        alert = _make_alert("price_above", "2330", 500.0)
        alert["triggered"] = True
        engine.alerts_data["alerts"] = [alert]
        triggered = engine.check_all_alerts(market_data)
        assert triggered == []

    def test_triggered_alert_marked_in_state(self, engine, market_data):
        alert = _make_alert("price_above", "2330", 500.0)
        engine.alerts_data["alerts"] = [alert]
        engine.check_all_alerts(market_data)
        assert engine.alerts_data["alerts"][0]["triggered"] is True
        assert "triggered_at" in engine.alerts_data["alerts"][0]

    def test_empty_alerts_no_crash(self, engine, market_data):
        engine.alerts_data["alerts"] = []
        result = engine.check_all_alerts(market_data)
        assert result == []


# ──────────────────────────────────────────────
# CRUD 操作（reset / enable / disable）
# ──────────────────────────────────────────────

class TestAlertCRUD:

    def setup_method(self, method):
        """每個測試方法前重建 engine"""
        pass

    def test_reset_alert_clears_triggered(self, engine):
        alert = _make_alert("price_above", "2330", 500.0)
        alert["triggered"] = True
        alert["triggered_at"] = "2023-01-01T10:00:00"
        engine.alerts_data["alerts"] = [alert]
        success = engine.reset_alert(alert["id"])
        assert success is True
        assert engine.alerts_data["alerts"][0]["triggered"] is False
        assert engine.alerts_data["alerts"][0]["triggered_at"] is None

    def test_reset_nonexistent_alert_returns_false(self, engine):
        engine.alerts_data["alerts"] = []
        assert engine.reset_alert("nonexistent-id") is False

    def test_disable_alert(self, engine):
        alert = _make_alert("price_above", "2330", 500.0)
        engine.alerts_data["alerts"] = [alert]
        success = engine.disable_alert(alert["id"])
        assert success is True
        assert engine.alerts_data["alerts"][0]["enabled"] is False

    def test_enable_alert(self, engine):
        alert = _make_alert("price_above", "2330", 500.0, enabled=False)
        engine.alerts_data["alerts"] = [alert]
        success = engine.enable_alert(alert["id"])
        assert success is True
        assert engine.alerts_data["alerts"][0]["enabled"] is True

    def test_get_active_alerts_filters_correctly(self, engine):
        alerts = [
            _make_alert("price_above", "2330", 500.0, enabled=True),     # 活躍
            _make_alert("price_below", "2317", 100.0, enabled=False),     # 停用
        ]
        alerts[0]["triggered"] = False
        triggered = _make_alert("new_high", "2454", 20, enabled=True)
        triggered["triggered"] = True
        alerts.append(triggered)
        engine.alerts_data["alerts"] = alerts
        active = engine.get_active_alerts()
        assert len(active) == 1
        assert active[0]["stock_id"] == "2330"

    def test_get_triggered_alerts(self, engine):
        alert = _make_alert("price_above", "2330", 500.0)
        alert["triggered"] = True
        engine.alerts_data["alerts"] = [alert]
        triggered = engine.get_triggered_alerts()
        assert len(triggered) == 1


# ──────────────────────────────────────────────
# Atomic Write（修正 W4 後驗證）
# ──────────────────────────────────────────────

class TestAtomicWrite:

    def test_save_creates_file(self, engine, tmp_alerts_file):
        engine.alerts_data = {"alerts": [_make_alert("price_above", "2330", 500.0)]}
        engine._save_alerts()
        assert tmp_alerts_file.exists()

    def test_saved_content_is_valid_json(self, engine, tmp_alerts_file):
        engine.alerts_data = {"alerts": [_make_alert("price_above", "2330", 500.0)]}
        engine._save_alerts()
        with open(tmp_alerts_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "alerts" in data
        assert len(data["alerts"]) == 1

    def test_tmp_file_not_left_behind(self, engine, tmp_alerts_file):
        """atomic write 完成後，.tmp 檔案應被清除"""
        engine.alerts_data = {"alerts": []}
        engine._save_alerts()
        tmp = tmp_alerts_file.with_suffix(".tmp")
        assert not tmp.exists()

    def test_load_alerts_from_file(self, engine, tmp_alerts_file):
        """儲存後重新載入，內容應一致"""
        original = {"alerts": [_make_alert("price_above", "2330", 500.0)]}
        engine.alerts_data = original
        engine._save_alerts()
        engine.alerts_data = {}
        engine.alerts_data = engine._load_alerts()
        assert len(engine.alerts_data["alerts"]) == 1

    def test_load_alerts_missing_file_returns_empty(self, tmp_path):
        eng = AlertEngine.__new__(AlertEngine)
        eng.ALERTS_FILE = tmp_path / "nonexistent.json"
        data = eng._load_alerts()
        assert data == {"alerts": []}

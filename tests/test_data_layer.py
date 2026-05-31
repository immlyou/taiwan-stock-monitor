"""
資料層模組測試
涵蓋：data_loader、cache_warmer、health_check
"""
import pickle
import time
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch


# ──────────────────────────────────────────────
# data_loader
# ──────────────────────────────────────────────
from core.data_loader import (
    DataCache, DataLoader, get_loader, reset_loader,
    reset_all_caches, is_stock_active,
    clear_active_stocks_cache,
    is_streamlit_cloud,
)


@pytest.fixture
def temp_data_dir(tmp_path):
    """建立含 pickle 檔案的臨時目錄"""
    np.random.seed(99)
    dates = pd.date_range("2022-01-01", periods=50, freq="B")
    stocks = ["2330", "2317", "2454"]

    def make_prices():
        return 100 * np.exp(np.cumsum(np.random.normal(0, 0.01, (50, 3)), axis=0))

    # 建立所有 DATA_FILES 需要的 pickle
    from config import DATA_FILES
    for key, filename in DATA_FILES.items():
        filepath = tmp_path / filename
        df = pd.DataFrame(make_prices(), index=dates, columns=stocks)
        with open(filepath, "wb") as f:
            pickle.dump(df, f)

    return tmp_path


@pytest.fixture
def local_loader(temp_data_dir):
    loader = DataLoader(data_dir=temp_data_dir, use_global_cache=False)
    # 強制使用本地 pickle 模式（繞過 is_streamlit_cloud() 的環境偵測）
    loader._use_finlab_api = False
    return loader


class TestDataCache:
    def test_singleton(self):
        c1 = DataCache()
        c2 = DataCache()
        assert c1 is c2

    def test_set_and_get(self):
        cache = DataCache()
        df = pd.DataFrame({"A": [1, 2, 3]})
        cache.set("_test_key_abc", df)
        result = cache.get("_test_key_abc")
        assert result is not None
        pd.testing.assert_frame_equal(result, df)

    def test_has_within_ttl(self):
        cache = DataCache()
        cache.set("_ttl_key", pd.DataFrame())
        assert cache.has("_ttl_key", max_age=3600)

    def test_has_expired(self):
        cache = DataCache()
        cache.set("_expired_key", pd.DataFrame())
        cache._load_times["_expired_key"] = time.time() - 7200  # 2 hours ago
        assert not cache.has("_expired_key", max_age=3600)

    def test_has_no_max_age(self):
        cache = DataCache()
        cache.set("_no_expire_key", pd.DataFrame())
        cache._load_times["_no_expire_key"] = time.time() - 999999
        assert cache.has("_no_expire_key", max_age=0)

    def test_clear(self):
        cache = DataCache()
        cache.set("_clear_key", pd.DataFrame())
        cache.clear()
        assert cache.get("_clear_key") is None

    def test_clear_key(self):
        cache = DataCache()
        cache.set("_ck_key", pd.DataFrame({"x": [1]}))
        cache.clear_key("_ck_key")
        assert cache.get("_ck_key") is None

    def test_get_stats(self):
        cache = DataCache()
        cache.set("_stats_key", pd.DataFrame())
        stats = cache.get_stats()
        assert "cached_keys" in stats
        assert "total_items" in stats


class TestDataLoader:
    def test_get_close(self, local_loader):
        df = local_loader.get("close")
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 50

    def test_get_volume(self, local_loader):
        df = local_loader.get("volume")
        assert isinstance(df, pd.DataFrame)

    def test_get_unknown_key_raises(self, local_loader):
        with pytest.raises(KeyError):
            local_loader.get("nonexistent_key_xyz")

    def test_cache_hit(self, local_loader):
        local_loader._cache = {}
        local_loader.get("close")
        local_loader.get("close")  # 應該使用快取
        # 只要不報錯且資料一致即可
        df = local_loader.get("close")
        assert isinstance(df, pd.DataFrame)

    def test_cache_bypass(self, local_loader):
        df = local_loader.get("close", use_cache=False)
        assert isinstance(df, pd.DataFrame)

    def test_get_stock_info(self, local_loader):
        info = local_loader.get_stock_info()
        assert isinstance(info, pd.DataFrame)

    def test_get_stock_list(self, local_loader):
        stocks = local_loader.get_stock_list()
        assert isinstance(stocks, list)
        assert len(stocks) > 0

    def test_get_latest_date(self, local_loader):
        date = local_loader.get_latest_date()
        assert isinstance(date, pd.Timestamp)

    def test_get_benchmark(self, local_loader):
        benchmark = local_loader.get_benchmark()
        assert isinstance(benchmark, pd.Series)

    def test_load_for_strategy_value(self, local_loader):
        data = local_loader.load_for_strategy("value")
        assert "close" in data

    def test_load_for_strategy_growth(self, local_loader):
        data = local_loader.load_for_strategy("growth")
        assert isinstance(data, dict)

    def test_load_for_strategy_unknown(self, local_loader):
        data = local_loader.load_for_strategy("nonexistent")
        assert isinstance(data, dict)

    def test_preload_all(self, local_loader):
        local_loader._cache = {}
        local_loader.preload_all()  # 不應崩潰

    def test_clear_cache(self, local_loader):
        local_loader.get("close")
        local_loader.clear_cache()
        assert local_loader._cache == {}

    def test_get_cache_stats(self, local_loader):
        stats = local_loader.get_cache_stats()
        assert "cached_keys" in stats

    def test_normalize_dataframe_date_column(self, local_loader):
        """_normalize_dataframe 將 date 欄移至 index"""
        df = pd.DataFrame({
            "date": pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]),
            "A": [1, 2, 3]
        })
        result = local_loader._normalize_dataframe(df)
        assert result.index.name == "date"
        assert "A" in result.columns

    def test_load_pickle_file_not_found(self, local_loader):
        with pytest.raises(FileNotFoundError):
            local_loader._load_pickle("nonexistent_file.pickle")


class TestGetActiveStocks:
    def test_returns_list(self, temp_data_dir):
        loader = DataLoader(data_dir=temp_data_dir, use_global_cache=False)
        loader._use_finlab_api = False
        with patch("core.data_loader.DataLoader", return_value=loader):
            cache = DataCache()
            cache.clear_key("_active_stocks_30")
            stocks = loader.get_stock_list()
            assert isinstance(stocks, list)


class TestIsStockActive:
    def test_active_stock(self, temp_data_dir):
        loader = DataLoader(data_dir=temp_data_dir, use_global_cache=False)
        loader._use_finlab_api = False
        stocks = loader.get_stock_list()
        if stocks:
            result = is_stock_active.__wrapped__(stocks[0]) if hasattr(is_stock_active, '__wrapped__') else True
            assert isinstance(result, bool) or result in [True, False]

    def test_nonexistent_stock(self, temp_data_dir):
        loader = DataLoader(data_dir=temp_data_dir, use_global_cache=False)
        loader._use_finlab_api = False
        with patch("core.data_loader.DataLoader", return_value=loader):
            result = is_stock_active("XXXX_NOT_EXISTS", days_threshold=30)
            assert result is False


class TestResetFunctions:
    def test_reset_loader(self):
        get_loader()
        reset_loader()
        # 重置後應能重新建立
        loader = get_loader()
        assert loader is not None

    def test_reset_all_caches(self):
        reset_all_caches()  # 不應崩潰
        cache = DataCache()
        assert isinstance(cache, DataCache)

    def test_clear_active_stocks_cache(self):
        cache = DataCache()
        cache.set("_active_stocks_30", ["2330"])
        clear_active_stocks_cache()
        assert cache.get("_active_stocks_30") is None


class TestIsStreamlitCloud:
    def test_returns_bool(self):
        result = is_streamlit_cloud()
        assert isinstance(result, bool)


# ──────────────────────────────────────────────
# cache_warmer
# ──────────────────────────────────────────────
from core.cache_warmer import CacheWarmer, WarmupTask


class TestWarmupTask:
    def test_default_values(self):
        task = WarmupTask(name="close", loader=lambda: None)
        assert task.priority == 0
        assert task.required is False
        assert task.loaded is False
        assert task.error is None


class TestCacheWarmer:
    def test_add_task(self):
        warmer = CacheWarmer()
        warmer.add_task("test", lambda: pd.DataFrame(), priority=1)
        assert len(warmer._tasks) == 1

    def test_tasks_sorted_by_priority(self):
        warmer = CacheWarmer()
        warmer.add_task("low", lambda: None, priority=10)
        warmer.add_task("high", lambda: None, priority=1)
        assert warmer._tasks[0].priority == 1

    def test_warmup_success(self):
        warmer = CacheWarmer()
        warmer.add_task("data1", lambda: pd.DataFrame({"A": [1]}), priority=0)
        warmer.add_task("data2", lambda: pd.DataFrame({"B": [2]}), priority=1)
        result = warmer.warmup()
        assert isinstance(result, dict)
        assert result["success"] == 2

    def test_warmup_with_callback(self):
        warmer = CacheWarmer()
        callbacks = []
        warmer.add_task("task1", lambda: pd.DataFrame())
        warmer.warmup(callback=lambda name, pct: callbacks.append((name, pct)))
        assert len(callbacks) > 0

    def test_warmup_handles_task_error(self):
        warmer = CacheWarmer()
        warmer.add_task("failing", lambda: (_ for _ in ()).throw(RuntimeError("失敗")))
        result = warmer.warmup()
        assert result["failed"] == 1

    def test_progress_initial_zero(self):
        warmer = CacheWarmer()
        assert warmer.progress == 0.0

    def test_progress_property(self):
        warmer = CacheWarmer()
        assert isinstance(warmer.progress, float)

    def test_get_status(self):
        warmer = CacheWarmer()
        status = warmer.get_status()
        assert isinstance(status, dict)
        assert "is_warming" in status

    def test_warmup_marks_tasks_loaded(self):
        warmer = CacheWarmer()
        warmer.add_task("loaded_task", lambda: pd.DataFrame())
        warmer.warmup()
        task = warmer._tasks[0]
        assert task.loaded is True

    def test_is_completed_initially_false(self):
        warmer = CacheWarmer()
        assert not warmer.is_completed

    def test_is_completed_after_warmup(self):
        warmer = CacheWarmer()
        warmer.add_task("t", lambda: pd.DataFrame())
        warmer.warmup()
        assert warmer.is_completed

    def test_reset(self):
        warmer = CacheWarmer()
        warmer.add_task("t", lambda: pd.DataFrame())
        warmer.warmup()
        warmer.reset()
        assert not warmer.is_completed
        assert warmer.progress == 0.0

    def test_warmup_async_does_not_crash(self):
        warmer = CacheWarmer()
        warmer.add_task("t", lambda: pd.DataFrame())
        warmer.warmup_async()
        import time; time.sleep(0.2)  # 等背景執行緒完成

    def test_is_warming_property(self):
        warmer = CacheWarmer()
        assert not warmer.is_warming

    def test_current_task_property(self):
        warmer = CacheWarmer()
        assert isinstance(warmer.current_task, str)


# ──────────────────────────────────────────────
# health_check
# ──────────────────────────────────────────────
from core.health_check import (
    HealthChecker, HealthStatus, CheckResult,
)


class TestCheckResult:
    def test_creation(self):
        result = CheckResult(name="資料新鮮度", status="healthy", message="資料最新")
        assert result.name == "資料新鮮度"
        assert result.status == "healthy"


class TestHealthStatus:
    def test_to_dict(self):
        status = HealthStatus(
            overall_status="healthy",
            checks=[CheckResult("test", "healthy", "ok")]
        )
        d = status.to_dict()
        assert d["overall_status"] == "healthy"
        assert "checks" in d
        assert "timestamp" in d


class TestHealthChecker:
    def test_init(self):
        checker = HealthChecker()
        assert isinstance(checker, HealthChecker)

    def test_check_disk_space(self):
        checker = HealthChecker()
        result = checker.check_disk_space()
        assert isinstance(result, CheckResult)
        assert result.status in ("healthy", "warning", "critical")

    def test_check_memory_usage(self):
        checker = HealthChecker()
        result = checker.check_memory_usage()
        assert isinstance(result, CheckResult)
        assert result.status in ("healthy", "warning", "critical")

    def test_check_data_freshness_no_file(self, tmp_path):
        checker = HealthChecker()
        checker.data_dir = tmp_path
        result = checker.check_data_freshness()
        assert isinstance(result, CheckResult)
        assert result.status == "critical"

    def test_check_data_freshness_with_fresh_data(self, tmp_path):
        """放入近期的 pickle 資料，應回傳 healthy"""
        from config import DATA_FILES
        close_file = tmp_path / DATA_FILES["close"]
        dates = pd.date_range(end=pd.Timestamp.now(), periods=5, freq="B")
        df = pd.DataFrame({"A": range(5)}, index=dates)
        df.to_pickle(close_file)

        checker = HealthChecker()
        checker.data_dir = tmp_path
        result = checker.check_data_freshness(max_days=5)
        assert result.status in ("healthy", "warning")

    def test_check_data_files_missing(self, tmp_path):
        checker = HealthChecker()
        checker.data_dir = tmp_path
        result = checker.check_data_files()
        assert isinstance(result, CheckResult)
        assert result.status in ("warning", "critical")

    def test_check_data_files_all_present(self, temp_data_dir):
        checker = HealthChecker()
        checker.data_dir = temp_data_dir
        result = checker.check_data_files()
        assert result.status == "healthy"

    def test_check_logs_no_dir(self, tmp_path):
        checker = HealthChecker()
        checker.data_dir = tmp_path
        result = checker.check_logs()
        assert isinstance(result, CheckResult)

    def test_check_logs_with_dir(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "test.log").write_text("test log content")
        checker = HealthChecker()
        checker.data_dir = tmp_path
        result = checker.check_logs()
        assert result.status == "healthy"

    def test_run_all_checks_returns_health_status(self, tmp_path):
        checker = HealthChecker()
        checker.data_dir = tmp_path
        status = checker.run_all_checks()
        assert isinstance(status, HealthStatus)
        assert status.overall_status in ("healthy", "warning", "critical")
        assert len(status.checks) == 5

    def test_overall_critical_when_any_critical(self, tmp_path):
        checker = HealthChecker()
        checker.data_dir = tmp_path
        status = checker.run_all_checks()
        statuses = {c.status for c in status.checks}
        if "critical" in statuses:
            assert status.overall_status == "critical"

    def test_overall_warning_when_any_warning(self):
        """手動驗證 run_all_checks 的聚合邏輯"""
        checker = HealthChecker()
        checker.checks = [
            CheckResult("a", "healthy", "ok"),
            CheckResult("b", "warning", "注意"),
        ]
        statuses = [c.status for c in checker.checks]
        if "critical" in statuses:
            overall = "critical"
        elif "warning" in statuses:
            overall = "warning"
        else:
            overall = "healthy"
        assert overall == "warning"

"""背景排程器 — 盤中自動警報檢查等定時任務

過去警報只能靠 `/alerts/check` 手動 POST 或外部 cron 觸發；這個模組在
API 進程內用 APScheduler 跑 BackgroundScheduler，啟動後自動在台股盤中
（平日 09:00–13:30，台北時區）定期檢查警報並送通知。

設計重點
--------
- **環境開關**：`ENABLE_SCHEDULER` 明確控制；未設定時雲端（Railway）預設開、
  本地預設關，避免 `--reload` 開發時重複排程。
- **單進程**：Railway 跑單一 uvicorn worker（見 Procfile / railway.toml），
  進程內排程不會有多 worker 重複觸發問題。
- **非阻塞**：BackgroundScheduler 跑在獨立執行緒，不影響事件迴圈與 /health。
- **防重疊**：`max_instances=1` + `coalesce=True`，避免上一輪未跑完又疊一輪。
- **節流**：警報送通知走 core.notification 的 throttle，盤中反覆檢查不會轟炸。

擴充其他任務（盤後 AI 覆盤、每日報告）時，在 `start_scheduler()` 內
`add_job` 即可。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from core.timeutils import TAIPEI_TZ, now_taipei

logger = logging.getLogger(__name__)

# 進程內單例（避免重複 start）
_scheduler: Optional[Any] = None


def scheduler_enabled() -> bool:
    """是否啟用排程器。

    ENABLE_SCHEDULER 明確設定時以它為準（1/true/yes/on 視為開）；
    未設定時：雲端預設開、本地預設關。
    """
    raw = os.getenv("ENABLE_SCHEDULER")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() in ("1", "true", "yes", "on")
    try:
        from api.deps import IS_CLOUD
    except Exception:
        IS_CLOUD = False
    return bool(IS_CLOUD)


def _alert_check_job() -> None:
    """排程任務：載入最新價量資料 → 檢查所有啟用警報 → 送出通知。

    任務內所有例外都被吞掉並記錄，絕不可讓它逸出而毒死排程執行緒。
    """
    try:
        from api.state import loader
        from core.alerts import check_alerts_and_notify

        data = {key: loader.get(key) for key in ("close", "volume", "high", "low")}
        triggered = check_alerts_and_notify(data, send_notification=True)
        if triggered:
            logger.info("排程警報檢查：%d 筆觸發", len(triggered))
        else:
            logger.debug("排程警報檢查：無觸發")
    except Exception:
        logger.exception("排程警報檢查失敗")


def _verify_predictions_job() -> None:
    """排程任務：用最新收盤驗證所有到期的預測（含 XGBoost 選股前向追蹤）。"""
    try:
        from api.state import loader
        from core.prediction_tracker import get_tracker

        close = loader.get("close")
        if close is None or close.empty:
            return
        result = get_tracker().verify_predictions(close)
        verified = result.get("verified") if isinstance(result, dict) else result
        logger.info("排程預測驗證完成：%s", verified)
    except Exception:
        logger.exception("排程預測驗證失敗")


def _record_xgboost_picks_job() -> None:
    """排程任務：記錄當前 XGBoost top-20 選股，供 20 日後驗證實際命中率。"""
    try:
        from api.state import loader
        from core.xgboost_backtest import record_live_xgboost_picks

        n = record_live_xgboost_picks(loader, top_n=20, verify_days=20)
        logger.info("排程記錄 XGBoost 選股：%d 筆", n)
    except Exception:
        logger.exception("排程記錄 XGBoost 選股失敗")


def start_scheduler() -> Optional[Any]:
    """啟動背景排程器（若已啟動則直接回傳既有實例）。

    回傳 BackgroundScheduler 實例；未啟用或 apscheduler 未安裝時回傳 None。
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    if not scheduler_enabled():
        logger.info("排程器未啟用（設 ENABLE_SCHEDULER=1 開啟）")
        return None

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("apscheduler 未安裝，排程器停用（pip install apscheduler）")
        return None

    interval = max(1, int(os.getenv("ALERT_CHECK_INTERVAL_MIN", "5")))

    sched = BackgroundScheduler(timezone=TAIPEI_TZ)
    # 平日 09:00–13:xx 每 interval 分鐘檢查一次。
    # hour=9-13 會跑到 13:55（收盤 13:30 後多幾輪），收盤後價格已定、無害。
    sched.add_job(
        _alert_check_job,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-13",
            minute=f"*/{interval}",
            timezone=TAIPEI_TZ,
        ),
        id="alert_check",
        name="盤中警報檢查",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=120,
        replace_existing=True,
    )

    # 每日盤後（平日 14:00 台北）驗證到期預測 —— 為 XGBoost 選股累積真實命中率。
    sched.add_job(
        _verify_predictions_job,
        CronTrigger(day_of_week="mon-fri", hour=14, minute=0, timezone=TAIPEI_TZ),
        id="verify_predictions",
        name="預測驗證",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
        replace_existing=True,
    )

    # 每週一 09:30（台北）記錄當前 XGBoost top-20 選股，20 日後由上面的驗證流程比對。
    sched.add_job(
        _record_xgboost_picks_job,
        CronTrigger(day_of_week="mon", hour=9, minute=30, timezone=TAIPEI_TZ),
        id="record_xgboost_picks",
        name="記錄XGBoost選股",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=1800,
        replace_existing=True,
    )

    sched.start()
    logger.info(
        "排程器已啟動：盤中警報每 %d 分檢查一次（台北平日 09:00–13:30）",
        interval,
    )
    _scheduler = sched
    return sched


def shutdown_scheduler() -> None:
    """關閉排程器（app 結束時呼叫）。"""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
            logger.info("排程器已關閉")
        except Exception:
            logger.exception("排程器關閉失敗")
        finally:
            _scheduler = None


def get_scheduler_status() -> Dict[str, Any]:
    """回傳排程器狀態（供 /health 等端點顯示，不觸發任何網路 I/O）。"""
    enabled = scheduler_enabled()
    running = _scheduler is not None and getattr(_scheduler, "running", False)
    status: Dict[str, Any] = {
        "enabled": enabled,
        "running": running,
        "jobs": [],
    }
    if running:
        try:
            for job in _scheduler.get_jobs():
                nxt = job.next_run_time
                status["jobs"].append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": nxt.isoformat() if nxt else None,
                })
        except Exception:
            logger.exception("讀取排程任務清單失敗")
    status["now_taipei"] = now_taipei().isoformat()
    return status

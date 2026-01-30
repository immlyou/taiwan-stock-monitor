# -*- coding: utf-8 -*-
"""
快取預熱模組

在首頁載入時預先載入常用資料，提升後續頁面的載入速度
"""
import threading
import time
from typing import List, Dict, Callable, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger('finlab_app.cache_warmer')


@dataclass
class WarmupTask:
    """預熱任務"""
    name: str
    loader: Callable
    priority: int = 0  # 數字越小優先級越高
    required: bool = False  # 是否為必要資料
    loaded: bool = False
    load_time: float = 0.0
    error: Optional[str] = None


class CacheWarmer:
    """
    快取預熱器

    在背景執行緒中預先載入資料，提升使用者體驗
    """

    def __init__(self):
        self._tasks: List[WarmupTask] = []
        self._is_warming = False
        self._progress = 0.0
        self._current_task = ""
        self._lock = threading.Lock()
        self._completed_at: Optional[datetime] = None

    def add_task(
        self,
        name: str,
        loader: Callable,
        priority: int = 0,
        required: bool = False
    ):
        """
        新增預熱任務

        Parameters:
        -----------
        name : str
            任務名稱
        loader : Callable
            載入函數 (無參數)
        priority : int
            優先級 (數字越小越優先)
        required : bool
            是否為必要資料
        """
        task = WarmupTask(
            name=name,
            loader=loader,
            priority=priority,
            required=required
        )
        self._tasks.append(task)
        # 按優先級排序
        self._tasks.sort(key=lambda t: t.priority)

    def warmup(self, callback: Callable[[str, float], None] = None) -> Dict:
        """
        執行預熱

        Parameters:
        -----------
        callback : Callable
            進度回呼函數，接收 (task_name, progress) 參數

        Returns:
        --------
        Dict
            預熱結果統計
        """
        if self._is_warming:
            logger.warning("預熱已在進行中")
            return {}

        with self._lock:
            self._is_warming = True
            self._progress = 0.0

        results = {
            'total': len(self._tasks),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'total_time': 0.0,
            'tasks': []
        }

        start_time = time.time()

        for i, task in enumerate(self._tasks):
            self._current_task = task.name
            self._progress = i / len(self._tasks)

            if callback:
                callback(task.name, self._progress)

            task_start = time.time()

            try:
                logger.info(f"預熱: {task.name}")
                task.loader()
                task.loaded = True
                task.load_time = time.time() - task_start
                results['success'] += 1
                logger.info(f"預熱完成: {task.name} ({task.load_time:.2f}s)")

            except Exception as e:
                task.error = str(e)
                task.load_time = time.time() - task_start
                results['failed'] += 1
                logger.error(f"預熱失敗: {task.name} - {e}")

            results['tasks'].append({
                'name': task.name,
                'success': task.loaded,
                'time': task.load_time,
                'error': task.error
            })

        results['total_time'] = time.time() - start_time
        self._progress = 1.0
        self._is_warming = False
        self._completed_at = datetime.now()

        if callback:
            callback("完成", 1.0)

        return results

    def warmup_async(self, callback: Callable[[str, float], None] = None):
        """
        在背景執行緒中執行預熱

        Parameters:
        -----------
        callback : Callable
            進度回呼函數
        """
        thread = threading.Thread(target=self.warmup, args=(callback,))
        thread.daemon = True
        thread.start()

    @property
    def is_warming(self) -> bool:
        """是否正在預熱"""
        return self._is_warming

    @property
    def progress(self) -> float:
        """預熱進度 (0.0 ~ 1.0)"""
        return self._progress

    @property
    def current_task(self) -> str:
        """當前正在執行的任務"""
        return self._current_task

    @property
    def is_completed(self) -> bool:
        """預熱是否已完成"""
        return self._completed_at is not None

    def get_status(self) -> Dict:
        """取得預熱狀態"""
        return {
            'is_warming': self._is_warming,
            'progress': self._progress,
            'current_task': self._current_task,
            'completed_at': self._completed_at.isoformat() if self._completed_at else None,
            'tasks': [
                {
                    'name': t.name,
                    'loaded': t.loaded,
                    'load_time': t.load_time,
                    'error': t.error
                }
                for t in self._tasks
            ]
        }

    def reset(self):
        """重置預熱狀態"""
        self._is_warming = False
        self._progress = 0.0
        self._current_task = ""
        self._completed_at = None
        for task in self._tasks:
            task.loaded = False
            task.load_time = 0.0
            task.error = None


# 全域預熱器實例
_warmer: Optional[CacheWarmer] = None


def get_cache_warmer() -> CacheWarmer:
    """取得全域預熱器實例"""
    global _warmer
    if _warmer is None:
        _warmer = CacheWarmer()
        _setup_default_tasks(_warmer)
    return _warmer


def _setup_default_tasks(warmer: CacheWarmer):
    """設定預設預熱任務"""
    from core.data_loader import get_loader

    loader = get_loader()

    # 必要資料 (優先級 0)
    warmer.add_task(
        name="股票收盤價",
        loader=lambda: loader.get('close'),
        priority=0,
        required=True
    )

    warmer.add_task(
        name="股票資訊",
        loader=lambda: loader.get_stock_info(),
        priority=0,
        required=True
    )

    # 常用資料 (優先級 1)
    warmer.add_task(
        name="成交量",
        loader=lambda: loader.get('volume'),
        priority=1
    )

    warmer.add_task(
        name="本益比",
        loader=lambda: loader.get('pe_ratio'),
        priority=1
    )

    warmer.add_task(
        name="股價淨值比",
        loader=lambda: loader.get('pb_ratio'),
        priority=1
    )

    # 次要資料 (優先級 2)
    warmer.add_task(
        name="殖利率",
        loader=lambda: loader.get('dividend_yield'),
        priority=2
    )

    warmer.add_task(
        name="營收成長",
        loader=lambda: loader.get('revenue_yoy'),
        priority=2
    )

    warmer.add_task(
        name="大盤指數",
        loader=lambda: loader.get_benchmark(),
        priority=2
    )


def warmup_on_startup(show_progress: bool = True) -> Dict:
    """
    啟動時預熱 (供 Streamlit 使用)

    Parameters:
    -----------
    show_progress : bool
        是否顯示進度條

    Returns:
    --------
    Dict
        預熱結果
    """
    import streamlit as st

    warmer = get_cache_warmer()

    # 如果已經預熱過，直接返回
    if warmer.is_completed:
        return warmer.get_status()

    # 如果正在預熱，等待完成
    if warmer.is_warming:
        if show_progress:
            progress_bar = st.progress(0, text="資料載入中...")
            while warmer.is_warming:
                progress_bar.progress(warmer.progress, text=f"載入中: {warmer.current_task}")
                time.sleep(0.1)
            progress_bar.empty()
        return warmer.get_status()

    # 執行預熱
    if show_progress:
        progress_bar = st.progress(0, text="初始化系統...")

        def update_progress(task_name: str, progress: float):
            progress_bar.progress(progress, text=f"載入中: {task_name}")

        results = warmer.warmup(callback=update_progress)
        progress_bar.empty()
    else:
        results = warmer.warmup()

    return results


def is_cache_warm() -> bool:
    """檢查快取是否已預熱"""
    warmer = get_cache_warmer()
    return warmer.is_completed


def get_warmup_status_summary() -> Dict:
    """
    取得快取預熱狀態摘要 (供 UI 顯示用)

    Returns:
    --------
    Dict
        包含以下欄位:
        - status: 'ready' | 'warming' | 'idle'
        - progress: 進度百分比 (0-100)
        - current_task: 當前任務名稱
        - loaded_count: 已載入任務數
        - total_count: 總任務數
        - failed_count: 失敗任務數
        - total_time: 總耗時 (秒)
        - message: 狀態訊息
    """
    warmer = get_cache_warmer()
    status_data = warmer.get_status()

    tasks = status_data['tasks']
    loaded_count = sum(1 for t in tasks if t['loaded'])
    failed_count = sum(1 for t in tasks if t['error'])
    total_count = len(tasks)
    total_time = sum(t['load_time'] for t in tasks)

    if status_data['is_warming']:
        status = 'warming'
        message = f"正在載入: {status_data['current_task']}"
    elif status_data['completed_at']:
        status = 'ready'
        if failed_count > 0:
            message = f"已完成 ({loaded_count}/{total_count}，{failed_count} 失敗)"
        else:
            message = f"已完成 ({loaded_count}/{total_count})"
    else:
        status = 'idle'
        message = "尚未預熱"

    return {
        'status': status,
        'progress': status_data['progress'] * 100,
        'current_task': status_data['current_task'],
        'loaded_count': loaded_count,
        'total_count': total_count,
        'failed_count': failed_count,
        'total_time': total_time,
        'message': message,
        'completed_at': status_data['completed_at'],
    }


def trigger_warmup_if_needed() -> bool:
    """
    檢查並觸發預熱 (如果尚未預熱)

    適合在非首頁的頁面使用，檢查快取狀態並在背景預熱

    Returns:
    --------
    bool
        True 如果已預熱完成，False 如果正在預熱中
    """
    warmer = get_cache_warmer()

    if warmer.is_completed:
        return True

    if warmer.is_warming:
        return False

    # 在背景觸發預熱
    warmer.warmup_async()
    return False

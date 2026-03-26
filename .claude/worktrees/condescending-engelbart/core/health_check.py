"""
系統健康檢查模組
"""
import os
import shutil
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR, DATA_FILES


@dataclass
class CheckResult:
    """單項檢查結果"""
    name: str
    status: str  # 'healthy', 'warning', 'critical'
    message: str
    details: Dict = field(default_factory=dict)


@dataclass
class HealthStatus:
    """系統健康狀態"""
    overall_status: str  # 'healthy', 'warning', 'critical'
    checks: List[CheckResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'overall_status': self.overall_status,
            'timestamp': self.timestamp.isoformat(),
            'checks': [
                {
                    'name': c.name,
                    'status': c.status,
                    'message': c.message,
                    'details': c.details,
                }
                for c in self.checks
            ]
        }


class HealthChecker:
    """
    系統健康檢查器

    檢查項目:
    - 數據新鮮度
    - 磁碟空間
    - 記憶體使用
    - 數據完整性
    - 日誌狀態
    """

    def __init__(self):
        self.data_dir = DATA_DIR
        self.checks: List[CheckResult] = []

    def check_data_freshness(self, max_days: int = 3) -> CheckResult:
        """
        檢查數據新鮮度

        Parameters:
        -----------
        max_days : int
            最大允許天數

        Returns:
        --------
        CheckResult
            檢查結果
        """
        try:
            # 嘗試載入收盤價數據
            close_file = self.data_dir / DATA_FILES.get('close', 'price#收盤價.pickle')

            if not close_file.exists():
                return CheckResult(
                    name='數據新鮮度',
                    status='critical',
                    message='找不到收盤價數據檔案',
                    details={'file': str(close_file)}
                )

            close = pd.read_pickle(close_file)
            latest_date = close.index.max()
            days_old = (datetime.now() - latest_date).days

            if days_old <= max_days:
                status = 'healthy'
                message = f'數據更新於 {days_old} 天前'
            elif days_old <= max_days * 2:
                status = 'warning'
                message = f'數據已 {days_old} 天未更新'
            else:
                status = 'critical'
                message = f'數據已過期 ({days_old} 天未更新)'

            return CheckResult(
                name='數據新鮮度',
                status=status,
                message=message,
                details={
                    'latest_date': latest_date.strftime('%Y-%m-%d'),
                    'days_old': days_old,
                }
            )

        except Exception as e:
            return CheckResult(
                name='數據新鮮度',
                status='critical',
                message=f'檢查失敗: {e}',
            )

    def check_disk_space(self, min_free_gb: float = 1.0) -> CheckResult:
        """
        檢查磁碟空間

        Parameters:
        -----------
        min_free_gb : float
            最小剩餘空間 (GB)

        Returns:
        --------
        CheckResult
            檢查結果
        """
        try:
            disk_usage = shutil.disk_usage(self.data_dir)
            free_gb = disk_usage.free / (1024 ** 3)
            total_gb = disk_usage.total / (1024 ** 3)
            used_pct = (disk_usage.used / disk_usage.total) * 100

            if free_gb >= min_free_gb * 2:
                status = 'healthy'
                message = f'剩餘空間 {free_gb:.1f} GB'
            elif free_gb >= min_free_gb:
                status = 'warning'
                message = f'剩餘空間不足 ({free_gb:.1f} GB)'
            else:
                status = 'critical'
                message = f'磁碟空間嚴重不足 ({free_gb:.1f} GB)'

            return CheckResult(
                name='磁碟空間',
                status=status,
                message=message,
                details={
                    'free_gb': round(free_gb, 2),
                    'total_gb': round(total_gb, 2),
                    'used_percent': round(used_pct, 1),
                }
            )

        except Exception as e:
            return CheckResult(
                name='磁碟空間',
                status='warning',
                message=f'檢查失敗: {e}',
            )

    def check_memory_usage(self, max_percent: float = 90.0) -> CheckResult:
        """
        檢查記憶體使用

        Parameters:
        -----------
        max_percent : float
            最大使用百分比

        Returns:
        --------
        CheckResult
            檢查結果
        """
        try:
            memory = psutil.virtual_memory()
            used_percent = memory.percent
            available_gb = memory.available / (1024 ** 3)

            if used_percent < max_percent * 0.7:
                status = 'healthy'
                message = f'記憶體使用 {used_percent:.1f}%'
            elif used_percent < max_percent:
                status = 'warning'
                message = f'記憶體使用偏高 ({used_percent:.1f}%)'
            else:
                status = 'critical'
                message = f'記憶體不足 ({used_percent:.1f}%)'

            return CheckResult(
                name='記憶體使用',
                status=status,
                message=message,
                details={
                    'used_percent': round(used_percent, 1),
                    'available_gb': round(available_gb, 2),
                }
            )

        except Exception as e:
            return CheckResult(
                name='記憶體使用',
                status='warning',
                message=f'檢查失敗: {e}',
            )

    def check_data_files(self) -> CheckResult:
        """
        檢查數據檔案完整性

        Returns:
        --------
        CheckResult
            檢查結果
        """
        try:
            missing_files = []
            existing_files = []

            for key, filename in DATA_FILES.items():
                file_path = self.data_dir / filename
                if file_path.exists():
                    existing_files.append(key)
                else:
                    missing_files.append(key)

            total = len(DATA_FILES)
            found = len(existing_files)

            if found == total:
                status = 'healthy'
                message = f'所有 {total} 個數據檔案正常'
            elif found >= total * 0.8:
                status = 'warning'
                message = f'{total - found} 個數據檔案遺失'
            else:
                status = 'critical'
                message = f'多數數據檔案遺失 ({total - found}/{total})'

            return CheckResult(
                name='數據檔案',
                status=status,
                message=message,
                details={
                    'total': total,
                    'found': found,
                    'missing': missing_files if missing_files else None,
                }
            )

        except Exception as e:
            return CheckResult(
                name='數據檔案',
                status='critical',
                message=f'檢查失敗: {e}',
            )

    def check_logs(self) -> CheckResult:
        """
        檢查日誌狀態

        Returns:
        --------
        CheckResult
            檢查結果
        """
        try:
            logs_dir = self.data_dir / 'logs'

            if not logs_dir.exists():
                return CheckResult(
                    name='日誌系統',
                    status='warning',
                    message='日誌目錄不存在',
                )

            log_files = list(logs_dir.glob('*.log'))
            total_size_mb = sum(f.stat().st_size for f in log_files) / (1024 ** 2)

            if total_size_mb < 100:
                status = 'healthy'
                message = f'{len(log_files)} 個日誌檔案 ({total_size_mb:.1f} MB)'
            elif total_size_mb < 500:
                status = 'warning'
                message = f'日誌檔案較大 ({total_size_mb:.1f} MB)'
            else:
                status = 'critical'
                message = f'日誌檔案過大 ({total_size_mb:.1f} MB)'

            return CheckResult(
                name='日誌系統',
                status=status,
                message=message,
                details={
                    'file_count': len(log_files),
                    'total_size_mb': round(total_size_mb, 2),
                }
            )

        except Exception as e:
            return CheckResult(
                name='日誌系統',
                status='warning',
                message=f'檢查失敗: {e}',
            )

    def run_all_checks(self) -> HealthStatus:
        """
        執行所有健康檢查

        Returns:
        --------
        HealthStatus
            系統健康狀態
        """
        self.checks = [
            self.check_data_freshness(),
            self.check_disk_space(),
            self.check_memory_usage(),
            self.check_data_files(),
            self.check_logs(),
        ]

        # 決定整體狀態
        statuses = [c.status for c in self.checks]

        if 'critical' in statuses:
            overall = 'critical'
        elif 'warning' in statuses:
            overall = 'warning'
        else:
            overall = 'healthy'

        return HealthStatus(
            overall_status=overall,
            checks=self.checks,
        )


def check_system_health() -> HealthStatus:
    """快速執行系統健康檢查"""
    checker = HealthChecker()
    return checker.run_all_checks()


def get_health_summary() -> Dict:
    """取得健康檢查摘要"""
    status = check_system_health()
    return status.to_dict()

"""
統一日誌配置模組
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


# 日誌格式
DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
SIMPLE_FORMAT = '%(levelname)s - %(message)s'


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    log_dir: Optional[Path] = None,
    format_style: str = 'default',
    name: Optional[str] = None,
) -> logging.Logger:
    """
    設定日誌配置

    Parameters:
    -----------
    level : int
        日誌等級 (logging.DEBUG, logging.INFO, etc.)
    log_file : str, optional
        日誌檔案名稱（不含路徑）
    log_dir : Path, optional
        日誌目錄，預設為專案根目錄下的 logs 資料夾
    format_style : str
        格式風格: 'default', 'detailed', 'simple'
    name : str, optional
        Logger 名稱，預設為 'finlab'

    Returns:
    --------
    logging.Logger
        配置好的 Logger 實例
    """
    # 選擇格式
    if format_style == 'detailed':
        log_format = DETAILED_FORMAT
    elif format_style == 'simple':
        log_format = SIMPLE_FORMAT
    else:
        log_format = DEFAULT_FORMAT

    # Logger 名稱
    logger_name = name or 'finlab'
    logger = logging.getLogger(logger_name)

    # 避免重複添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    # 檔案 handler (如果指定)
    if log_file or log_dir:
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / 'logs'

        log_dir.mkdir(exist_ok=True)

        if log_file is None:
            log_file = f"finlab_{datetime.now().strftime('%Y%m%d')}.log"

        file_handler = logging.FileHandler(log_dir / log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT))
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    取得 Logger 實例

    Parameters:
    -----------
    name : str, optional
        Logger 名稱，會自動加上 'finlab.' 前綴

    Returns:
    --------
    logging.Logger
        Logger 實例
    """
    if name:
        return logging.getLogger(f'finlab.{name}')
    return logging.getLogger('finlab')


class LogContext:
    """
    日誌上下文管理器

    用於追蹤操作的開始與結束

    Example:
    --------
    >>> with LogContext(logger, '選股執行'):
    ...     strategy.run(data)
    """

    def __init__(self, logger: logging.Logger, operation: str, level: int = logging.INFO):
        self.logger = logger
        self.operation = operation
        self.level = level
        self.start_time = None

    def __enter__(self):
        import time
        self.start_time = time.time()
        self.logger.log(self.level, f'開始: {self.operation}')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        elapsed = time.time() - self.start_time

        if exc_type is not None:
            self.logger.error(f'失敗: {self.operation} - {exc_val} (耗時 {elapsed:.2f}秒)')
            return False  # 重新拋出異常
        else:
            self.logger.log(self.level, f'完成: {self.operation} (耗時 {elapsed:.2f}秒)')
            return True


# 預設 Logger (模組載入時初始化)
_default_logger = None


def init_default_logger(log_to_file: bool = False) -> logging.Logger:
    """
    初始化預設 Logger

    Parameters:
    -----------
    log_to_file : bool
        是否記錄到檔案

    Returns:
    --------
    logging.Logger
        預設 Logger 實例
    """
    global _default_logger
    if _default_logger is None:
        log_dir = Path(__file__).parent.parent / 'logs' if log_to_file else None
        _default_logger = setup_logging(log_dir=log_dir)
    return _default_logger


def log_strategy_execution(strategy_name: str, params: dict, result_count: int):
    """記錄策略執行結果"""
    logger = get_logger('strategy')
    logger.info(f'策略執行: {strategy_name} | 參數: {params} | 結果數量: {result_count}')


def log_backtest_result(strategy_name: str, metrics: dict):
    """記錄回測結果"""
    logger = get_logger('backtest')
    logger.info(
        f'回測完成: {strategy_name} | '
        f'總報酬: {metrics.get("total_return", 0):.2f}% | '
        f'年化報酬: {metrics.get("annualized_return", 0):.2f}% | '
        f'夏普比率: {metrics.get("sharpe_ratio", 0):.2f}'
    )


def log_data_update(data_name: str, success: bool, error: str = None):
    """記錄數據更新結果"""
    logger = get_logger('data')
    if success:
        logger.info(f'數據更新成功: {data_name}')
    else:
        logger.error(f'數據更新失敗: {data_name} - {error}')

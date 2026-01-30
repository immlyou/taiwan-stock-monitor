#!/usr/bin/env python3
"""
數據備份腳本
"""
import shutil
import sys
from pathlib import Path
from datetime import datetime
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DATA_DIR, DATA_FILES
from core.logging_config import setup_logging, get_logger

# 設定日誌
setup_logging(log_file='backup.log')
logger = get_logger(__name__)


def backup_data(backup_dir: Path = None, keep_count: int = 7) -> bool:
    """
    備份數據檔案

    Parameters:
    -----------
    backup_dir : Path, optional
        備份目錄
    keep_count : int
        保留最近 N 份備份

    Returns:
    --------
    bool
        是否成功
    """
    if backup_dir is None:
        backup_dir = Path(__file__).parent.parent / 'backups'

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    target_dir = backup_dir / f'backup_{timestamp}'

    logger.info(f'開始備份至: {target_dir}')

    try:
        target_dir.mkdir(parents=True, exist_ok=True)

        # 備份 pickle 數據檔案
        backed_up = []
        for key, filename in DATA_FILES.items():
            src = DATA_DIR / filename
            if src.exists():
                dst = target_dir / filename
                shutil.copy2(src, dst)
                backed_up.append(filename)
                logger.debug(f'已備份: {filename}')

        # 備份 JSON 設定檔
        json_files = ['portfolios.json', 'watchlists.json', 'alerts.json',
                      'settings.json', 'saved_strategies.json']

        data_subdir = DATA_DIR / 'data'
        for json_file in json_files:
            # 檢查根目錄和 data 子目錄
            for check_dir in [DATA_DIR, data_subdir]:
                src = check_dir / json_file
                if src.exists():
                    dst = target_dir / json_file
                    shutil.copy2(src, dst)
                    backed_up.append(json_file)
                    logger.debug(f'已備份: {json_file}')
                    break

        # 記錄備份資訊
        backup_info = {
            'timestamp': timestamp,
            'files_count': len(backed_up),
            'files': backed_up,
        }

        with open(target_dir / 'backup_info.json', 'w', encoding='utf-8') as f:
            json.dump(backup_info, f, ensure_ascii=False, indent=2)

        logger.info(f'備份完成: {len(backed_up)} 個檔案')

        # 清理舊備份
        cleanup_old_backups(backup_dir, keep_count)

        return True

    except Exception as e:
        logger.error(f'備份失敗: {e}')
        return False


def cleanup_old_backups(backup_dir: Path, keep_count: int):
    """
    清理舊備份

    Parameters:
    -----------
    backup_dir : Path
        備份目錄
    keep_count : int
        保留最近 N 份
    """
    try:
        # 列出所有備份目錄
        backups = sorted(
            [d for d in backup_dir.iterdir() if d.is_dir() and d.name.startswith('backup_')],
            key=lambda x: x.name,
            reverse=True
        )

        # 刪除多餘的備份
        for old_backup in backups[keep_count:]:
            shutil.rmtree(old_backup)
            logger.info(f'已刪除舊備份: {old_backup.name}')

    except Exception as e:
        logger.warning(f'清理舊備份時發生錯誤: {e}')


def restore_backup(backup_path: Path, confirm: bool = False) -> bool:
    """
    還原備份

    Parameters:
    -----------
    backup_path : Path
        備份目錄路徑
    confirm : bool
        是否確認還原

    Returns:
    --------
    bool
        是否成功
    """
    if not backup_path.exists():
        logger.error(f'備份不存在: {backup_path}')
        return False

    if not confirm:
        logger.warning('還原需要確認，請設定 confirm=True')
        return False

    logger.info(f'開始還原備份: {backup_path}')

    try:
        # 還原檔案
        restored = []
        for file in backup_path.glob('*.pickle'):
            dst = DATA_DIR / file.name
            shutil.copy2(file, dst)
            restored.append(file.name)
            logger.debug(f'已還原: {file.name}')

        for file in backup_path.glob('*.json'):
            if file.name == 'backup_info.json':
                continue
            dst = DATA_DIR / 'data' / file.name
            dst.parent.mkdir(exist_ok=True)
            shutil.copy2(file, dst)
            restored.append(file.name)
            logger.debug(f'已還原: {file.name}')

        logger.info(f'還原完成: {len(restored)} 個檔案')
        return True

    except Exception as e:
        logger.error(f'還原失敗: {e}')
        return False


def list_backups(backup_dir: Path = None) -> list:
    """
    列出所有備份

    Returns:
    --------
    list
        備份資訊列表
    """
    if backup_dir is None:
        backup_dir = Path(__file__).parent.parent / 'backups'

    if not backup_dir.exists():
        return []

    backups = []
    for d in sorted(backup_dir.iterdir(), reverse=True):
        if d.is_dir() and d.name.startswith('backup_'):
            info_file = d / 'backup_info.json'
            if info_file.exists():
                with open(info_file, 'r', encoding='utf-8') as f:
                    info = json.load(f)
            else:
                info = {'timestamp': d.name.replace('backup_', '')}

            # 計算備份大小
            size_mb = sum(f.stat().st_size for f in d.glob('*')) / (1024 ** 2)
            info['size_mb'] = round(size_mb, 2)
            info['path'] = str(d)

            backups.append(info)

    return backups


def main():
    """主函數"""
    import argparse

    parser = argparse.ArgumentParser(description='數據備份工具')
    parser.add_argument('--backup', action='store_true', help='執行備份')
    parser.add_argument('--list', action='store_true', help='列出備份')
    parser.add_argument('--restore', type=str, help='還原指定備份')
    parser.add_argument('--keep', type=int, default=7, help='保留備份數量')

    args = parser.parse_args()

    if args.backup:
        success = backup_data(keep_count=args.keep)
        sys.exit(0 if success else 1)

    elif args.list:
        backups = list_backups()
        if backups:
            print(f'找到 {len(backups)} 份備份:')
            for b in backups:
                print(f"  - {b['timestamp']} ({b.get('files_count', '?')} 檔案, {b.get('size_mb', '?')} MB)")
        else:
            print('沒有找到備份')

    elif args.restore:
        backup_path = Path(args.restore)
        print(f'即將還原備份: {backup_path}')
        confirm = input('確定要還原嗎？這將覆蓋現有數據 (yes/no): ')
        if confirm.lower() == 'yes':
            success = restore_backup(backup_path, confirm=True)
            sys.exit(0 if success else 1)
        else:
            print('取消還原')

    else:
        parser.print_help()


if __name__ == '__main__':
    main()

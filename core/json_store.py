"""使用者資料 JSON 檔的共用持久化工具

Railway Volume 上的 watchlists / portfolios / alerts / predictions 等
使用者資料都是「整檔 load → 改 → 整檔 save」的 JSON 檔，需要兩層保護：

- save_json_atomic()：tmp + os.replace 原子寫入。
  進程在寫到一半被砍（redeploy / OOM）時不會留下截斷檔。
- file_lock()：以解析後路徑為 key 的 process-wide threading.Lock，
  讓 load-modify-save 序列互斥，避免兩個併發請求互相覆蓋。
  （Railway 跑單進程 monolith，process-level lock 即足夠。）

用法::

    from core.json_store import file_lock, save_json_atomic

    with file_lock(MY_FILE):
        data = load(...)
        data["x"] = 1
        save_json_atomic(MY_FILE, data)
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict

_locks: Dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


def file_lock(path: Path | str) -> threading.RLock:
    """取得對應檔案路徑的 process-wide lock（同一路徑永遠回傳同一把鎖）。

    使用 RLock：router 層與 util 層各自取鎖時（同一執行緒巢狀）不會 deadlock。
    """
    key = str(Path(path).resolve())
    with _locks_guard:
        lock = _locks.get(key)
        if lock is None:
            lock = threading.RLock()
            _locks[key] = lock
        return lock


def save_json_atomic(path: Path | str, data: Any) -> None:
    """原子寫入 JSON 檔：先寫 tmp 再 os.replace，中斷不會毀檔。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    tmp_path.replace(path)  # atomic rename

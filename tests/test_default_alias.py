"""resolve_default_id —「default」別名解析 contract test

前端對自選股 / 投資組合 / 雷達健檢固定打 id="default"，但 default 並非真實
名稱。此 helper 統一解析，讓這些端點不會對新使用者回 404：
  - 請求 id 存在        -> (id, False)
  - default 且有資料    -> (第一個既有 key, False)
  - default 且完全沒資料 -> (None, True)   呼叫端回空結構（200）
  - 其他不存在的明確 id  -> (None, False)  呼叫端維持 404
"""
from api.helpers import resolve_default_id


def test_existing_id_used_as_is():
    assert resolve_default_id({"demo": 1, "x": 2}, "demo") == ("demo", False)


def test_default_resolves_to_first_existing():
    # dict 保序：default 退回第一個既有項目，讓有資料的使用者仍看到內容
    assert resolve_default_id({"我的組合": 1, "x": 2}, "default") == ("我的組合", False)


def test_default_with_no_items_is_empty_default():
    # (None, True) -> 呼叫端應回空結構（200），而非 404
    assert resolve_default_id({}, "default") == (None, True)


def test_genuine_missing_named_id_is_404():
    # (None, False) -> 呼叫端維持 404
    assert resolve_default_id({"demo": 1}, "不存在") == (None, False)


def test_literal_default_name_takes_precedence():
    # 若真的有名為 default 的項目，直接用它（不走 fallback）
    assert resolve_default_id({"default": 1, "other": 2}, "default") == ("default", False)

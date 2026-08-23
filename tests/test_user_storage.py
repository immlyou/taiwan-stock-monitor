from pathlib import Path

import pytest

from core.user_storage import DEFAULT_USER_ID, iter_user_ids, user_data_path


def test_owner_keeps_legacy_data_path(tmp_path: Path):
    assert user_data_path("owner", "settings.json", tmp_path) == tmp_path / "settings.json"


def test_google_user_gets_an_isolated_data_directory(tmp_path: Path):
    assert user_data_path(
        "google_109876543210", "settings.json", tmp_path
    ) == tmp_path / "users" / "google_109876543210" / "settings.json"


@pytest.mark.parametrize("user_id", ["../owner", "a/b", "", ".."])
def test_unsafe_user_id_is_rejected(tmp_path: Path, user_id: str):
    with pytest.raises(ValueError, match="user id"):
        user_data_path(user_id, "settings.json", tmp_path)


def test_iter_user_ids_includes_legacy_owner_and_namespaced_users(tmp_path: Path):
    (tmp_path / "users" / "google_alice123").mkdir(parents=True)
    (tmp_path / "users" / "google_bob456").mkdir(parents=True)
    (tmp_path / "users" / "not valid").mkdir(parents=True)

    assert iter_user_ids(tmp_path) == [
        DEFAULT_USER_ID,
        "google_alice123",
        "google_bob456",
    ]

import sqlite3

import pytest

import config
from src import asset_service as assets
from src.database import backup_database, connect, initialize


def test_initialize_schema_and_reopen(db, form):
    with connect(db) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        indexes = {row["name"] for row in connection.execute("PRAGMA index_list(assets)")}
    assert {"assets_category_idx", "assets_status_idx", "assets_year_idx"} <= indexes
    asset_id = assets.add_asset(db, form)
    initialize(db)
    assert assets.get_asset(db, asset_id)["name"] == form["name"]


def test_sqlite_constraints_and_rollback(db, form):
    asset_id = assets.add_asset(db, form)
    with pytest.raises(sqlite3.IntegrityError), connect(db) as connection:
        connection.execute("UPDATE assets SET name = ? WHERE id = ?", ("Changed", asset_id))
        connection.execute("UPDATE assets SET status = ? WHERE id = ?", ("Unknown", asset_id))
    assert assets.get_asset(db, asset_id)["name"] == form["name"]


def test_foreign_file_is_preserved(tmp_path):
    path = tmp_path / "other.sqlite3"
    with connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER)")
    previous = path.read_bytes()
    with pytest.raises(sqlite3.DatabaseError, match="not a supported"):
        initialize(path)
    assert path.read_bytes() == previous


def test_backup_is_consistent_and_does_not_replace(db, form, tmp_path):
    target = tmp_path / "backup.sqlite3"
    asset_id = assets.add_asset(db, form)
    backup_database(db, target)
    assets.delete_asset(db, asset_id)
    assert assets.get_asset(target, asset_id)["serial"] == form["serial"]
    with pytest.raises(FileExistsError):
        backup_database(db, target)
    with pytest.raises(FileExistsError):
        backup_database(db, db)
    assert assets.get_asset(target, asset_id)["serial"] == form["serial"]


def test_data_path_linux(monkeypatch, tmp_path):
    monkeypatch.setattr(config.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert config.database_path() == tmp_path / config.DATA_FOLDER.lower() / "inventory.sqlite3"
    monkeypatch.setenv("XDG_DATA_HOME", "relative")
    monkeypatch.setattr(config.Path, "home", lambda: tmp_path)
    assert config.database_path().is_relative_to(tmp_path / ".local" / "share")


def test_data_path_windows(monkeypatch, tmp_path):
    monkeypatch.setattr(config.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert config.database_path() == tmp_path / config.DATA_FOLDER / "inventory.sqlite3"



def test_backup_missing_source_does_not_create_files(tmp_path):
    missing = tmp_path / "missing.sqlite3"
    destination = tmp_path / "backup.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        backup_database(missing, destination)
    assert not missing.exists() and not destination.exists()

"""Storage v2 acceptance: real legacy DDL, safe migration and shared lookups."""
import csv
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest

from config import CATEGORIES
from src import asset_service as assets
from src import database, reports
from src.csv_import import import_prepared, prepare_import
from src.database import backup_database, connect, initialize
from src.validation import ValidationError, validate_asset


@pytest.fixture
def legacy(tmp_path):
    path = tmp_path / "v1.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript((Path(__file__).parent / "fixtures/schema_v1.sql").read_text())
    return path


def old_insert(path, form, asset_id=1):
    values = {**validate_asset(form), "id": asset_id,
              "created_at": "2024-01-02 03:04:05", "updated_at": "2025-02-03 04:05:06"}
    # A genuine v1 database can contain whitespace/case variations in location.
    values["location"] = form.get("location", "")
    with sqlite3.connect(path) as connection:
        columns = tuple(values)
        connection.execute(f"INSERT INTO assets ({', '.join(columns)}) VALUES ({', '.join(':'+key for key in columns)})", values)


def tables(path):
    with connect(path, read_only=True) as connection:
        return {r[0] for r in connection.execute("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def test_three_strict_tables_seed_and_indexes(db):
    assert tables(db) == {"assets", "categories", "locations"}
    assert assets.category_names(db) == CATEGORIES
    assert assets.location_names(db) == ()
    with connect(db) as c:
        assert all(r[5] == 1 for r in c.execute("PRAGMA table_list") if r[1] in tables(db))
        assert {r[1] for r in c.execute("PRAGMA table_info(locations)")} == {"id", "name"}
        assert {r[1] for r in c.execute("PRAGMA table_info(categories)")} == {"id", "name"}
        assert {r[1] for r in c.execute("PRAGMA index_list(assets)")} >= {
            "assets_category_idx", "assets_location_idx", "assets_status_idx", "assets_year_idx"}
        assert not {"category", "location", "operational"} & {r[1] for r in c.execute("PRAGMA table_info(assets)")}


@pytest.mark.parametrize("read_only", [False, True])
def test_every_connection_enables_foreign_keys(db, read_only):
    with connect(db, read_only=read_only) as c:
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert not c.execute("PRAGMA foreign_key_check").fetchall()


@pytest.mark.parametrize("column", ["category_id", "location_id"])
def test_invalid_fk_rejected(db, form, column):
    asset_id = assets.add_asset(db, form)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"), connect(db) as c:
        c.execute(f"UPDATE assets SET {column} = 99999 WHERE id = ?", (asset_id,))
    assert assets.get_asset(db, asset_id)["category"] == "Laptop"


@pytest.mark.parametrize("table", ["categories", "locations"])
def test_referenced_lookup_delete_restricted(db, form, table):
    asset_id = assets.add_asset(db, form)
    column = "category_id" if table == "categories" else "location_id"
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"), connect(db) as c:
        lookup_id = c.execute(f"SELECT {column} FROM assets WHERE id = ?", (asset_id,)).fetchone()[0]
        c.execute(f"DELETE FROM {table} WHERE id = ?", (lookup_id,))


def test_share_normalized_location_and_category(db, form):
    first = assets.add_asset(db, {**form, "location": "  ÄREA Lab  "})
    second = assets.add_asset(db, {**form, "serial": "002", "location": "ärea lab"})
    assert assets.location_names(db) == ("ÄREA Lab",)
    with connect(db) as c:
        rows = c.execute("SELECT category_id, location_id FROM assets").fetchall()
        assert tuple(rows[0]) == tuple(rows[1])
    assert assets.get_asset(db, first)["location"] == assets.get_asset(db, second)["location"] == "ÄREA Lab"


def test_optional_location_and_edit_lookup(db, form):
    asset_id = assets.add_asset(db, {**form, "location": " \t"})
    assert assets.location_names(db) == ()
    with connect(db) as c:
        assert c.execute("SELECT location_id FROM assets").fetchone()[0] is None
    assets.update_asset(db, asset_id, {**form, "location": "New Room"})
    assert assets.get_asset(db, asset_id)["location"] == "New Room"
    assets.update_asset(db, asset_id, {**form, "location": ""})
    assert assets.get_asset(db, asset_id)["location"] == ""
    # Unused real locations remain selectable, not silently deleted.
    assert assets.location_names(db) == ("New Room",)


def test_failed_asset_write_does_not_leave_location(db, form):
    assets.add_asset(db, form)
    with pytest.raises(ValidationError, match="already registered"):
        assets.add_asset(db, {**form, "location": "Should roll back"})
    assert assets.location_names(db) == ("Library",)
    with pytest.raises(assets.AssetNotFound):
        assets.update_asset(db, 999, {**form, "serial": "other", "location": "Also roll back"})
    assert assets.location_names(db) == ("Library",)


def test_concurrent_location_resolution(db, form):
    def add(index):
        return assets.add_asset(db, {**form, "serial": str(index), "location": "ÄREA" if index % 2 else "ärea"})
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert len(set(pool.map(add, range(8)))) == 8
    assert len(assets.location_names(db)) == 1
    assert len(assets.list_assets(db)) == 8


def test_migration_preserves_fields_and_deleted_id_high_water(legacy, form):
    old_insert(legacy, {**form, "location": "  Library  ", "notes": "Line 1\nLine 2", "serial": "ÄBC-001"}, 7)
    old_insert(legacy, {**form, "location": "library", "serial": ""}, 12)
    old_insert(legacy, {**form, "location": "", "serial": "003", "purchase_price": "0"}, 20)
    old_insert(legacy, {**form, "serial": "deleted"}, 99)
    with connect(legacy) as c:
        c.execute("DELETE FROM assets WHERE id=99")
        before = [dict(r) for r in c.execute("SELECT * FROM assets ORDER BY id")]
    backup = initialize(legacy)
    assert backup.is_file()
    assert tables(backup) == {"assets"}
    with connect(backup, read_only=True) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 1
        assert [dict(r) for r in c.execute("SELECT * FROM assets ORDER BY id")] == before
    after = list(reversed(assets.list_assets(legacy)))
    for original, migrated in zip(before, after, strict=True):
        assert {k: v for k, v in original.items() if k != "location"} == {k: v for k, v in dict(migrated).items() if k != "location"}
    assert [r["location"] for r in after] == ["Library", "Library", ""]
    assert assets.add_asset(legacy, {**form, "serial": "new"}) == 100
    contents = legacy.read_bytes()
    assert initialize(legacy) is None
    assert legacy.read_bytes() == contents
    assert len(list(legacy.parent.glob("*.pre-v2-*.sqlite3"))) == 1


def test_fifty_demo_v1_migration(legacy):
    with (Path(__file__).parents[1] / "examples/sample_inventory_50.csv").open(encoding="utf-8-sig", newline="") as stream:
        for index, row in enumerate(csv.DictReader(stream), 1):
            old_insert(legacy, {key: row.get(header, "") for header, key in reports.ASSET_COLUMNS if key}, index)
    with connect(legacy) as c:
        before = [dict(r) for r in c.execute("SELECT * FROM assets ORDER BY id DESC")]
    summary = reports.inventory_summary(before, date.today().year)
    tables_before = [reports.report_table(before, name) for name in reports.REPORT_NAMES]
    initialize(legacy)
    after = assets.list_assets(legacy)
    assert len(after) == 50
    assert [dict(r) for r in after] == before
    assert reports.inventory_summary(after, date.today().year) == summary
    assert [reports.report_table(after, name) for name in reports.REPORT_NAMES] == tables_before
    with connect(legacy) as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_empty_v1_migration(legacy):
    initialize(legacy)
    assert assets.list_assets(legacy) == []
    assert assets.location_names(legacy) == ()


def test_mid_migration_failure_rolls_back_schema_data_version(legacy, form, monkeypatch):
    old_insert(legacy, form, 1)
    old_insert(legacy, {**form, "serial": "other", "location": "New lab"}, 2)
    previous = legacy.read_bytes()
    resolve = database.resolve_relationships
    calls = 0

    def fail(connection, values):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("Injected migration failure")
        return resolve(connection, values)

    monkeypatch.setattr(database, "resolve_relationships", fail)
    with pytest.raises(sqlite3.OperationalError, match="Injected"):
        initialize(legacy)
    assert legacy.read_bytes() == previous
    assert tables(legacy) == {"assets"}
    with connect(legacy) as c:
        assert c.execute("PRAGMA user_version").fetchone()[0] == 1
        assert c.execute("SELECT count(*) FROM assets").fetchone()[0] == 2
    backups = list(legacy.parent.glob("*.pre-v2-*.sqlite3"))
    assert len(backups) == 1
    with connect(backups[0]) as saved, connect(legacy) as original:
        assert list(saved.iterdump()) == list(original.iterdump())
        assert saved.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    monkeypatch.setattr(database, "resolve_relationships", resolve)
    initialize(legacy)
    assert len(assets.list_assets(legacy)) == 2


def test_backup_failure_prevents_ddl(legacy, form, monkeypatch):
    old_insert(legacy, form)
    previous = legacy.read_bytes()

    def fail(*_):
        raise OSError("Backup unavailable")

    monkeypatch.setattr(database, "backup_database", fail)
    with pytest.raises(OSError, match="Backup unavailable"):
        initialize(legacy)
    assert legacy.read_bytes() == previous


@pytest.mark.parametrize("version", [-1, 3, 99])
def test_unsupported_version_not_modified(db, version):
    with connect(db) as c:
        c.execute(f"PRAGMA user_version = {version}")
    previous = db.read_bytes()
    with pytest.raises(sqlite3.DatabaseError, match="not a supported"):
        initialize(db)
    assert db.read_bytes() == previous


def test_malformed_v2_and_orphan_rejected(db, form):
    assets.add_asset(db, form)
    with sqlite3.connect(db) as c:  # Simulate a careless external editor without FK enforcement.
        c.execute("UPDATE assets SET location_id = 999")
    previous = db.read_bytes()
    with pytest.raises(sqlite3.DatabaseError, match="foreign-key"):
        initialize(db)
    assert db.read_bytes() == previous


def test_external_unicode_duplicate_locations_rejected(db):
    with connect(db) as c:
        c.executemany("INSERT INTO locations(name) VALUES (?)", [("ÄREA",), ("ärea",)])
    with pytest.raises(sqlite3.DatabaseError, match="duplicate normalized"):
        initialize(db)


def test_backup_contains_committed_wal_and_is_v2(db, form, tmp_path):
    with sqlite3.connect(db) as writer:
        writer.execute("PRAGMA journal_mode = WAL")
        asset_id = assets.add_asset(db, form)
        backup = tmp_path / "wal-copy.sqlite3"
        backup_database(db, backup)
        assert assets.get_asset(backup, asset_id)["location"] == "Library"
        assert tables(backup) == {"assets", "categories", "locations"}
        with connect(backup) as c:
            assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_csv_lookup_roundtrip_and_rollback(db, form, tmp_path):
    source = tmp_path / "input.csv"
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Name", "Category", "Year", "Status", "Location", "Serial number"])
        writer.writerows([
            ["A", "Laptop", "2020", "Available", "Library", "1"],
            ["B", "Laptop", "2020", "Assigned", " library ", "2"],
            ["C", "Other", "2020", "Retired", "", "3"],
        ])
    preview = prepare_import(db, source)
    assert assets.location_names(db) == ()  # Preview never inserts lookups.
    with connect(db) as c:
        c.execute("CREATE TRIGGER abort_batch BEFORE INSERT ON assets WHEN NEW.serial = '2' BEGIN SELECT RAISE(ABORT, 'batch failed'); END")
    with pytest.raises(sqlite3.IntegrityError, match="batch failed"):
        import_prepared(db, preview)
    assert assets.location_names(db) == () and assets.list_assets(db) == []
    with connect(db) as c:
        c.execute("DROP TRIGGER abort_batch")
    assert import_prepared(db, preview).inserted == 3
    assert assets.location_names(db) == ("Library",)
    assert import_prepared(db, prepare_import(db, source)).inserted == 0
    exported = tmp_path / "export.csv"
    reports.export_inventory(exported, assets.list_assets(db))
    destination = tmp_path / "fresh.sqlite3"
    initialize(destination)
    assert import_prepared(destination, prepare_import(destination, exported)).inserted == 3
    assert reports.inventory_summary(assets.list_assets(destination), date.today().year) == reports.inventory_summary(assets.list_assets(db), date.today().year)
    assert assets.location_names(destination) == ("Library",)


def test_report_database_adapter_uses_readable_join(db, form):
    assets.add_asset(db, form)
    for report in reports.REPORT_NAMES:
        assert reports.report_from_database(db, report, 2026) == reports.report_table(assets.list_assets(db), report, 2026)


def test_v2_missing_mandatory_fk_constraint_rejected(tmp_path):
    path = tmp_path / "malformed.sqlite3"
    with connect(path) as c:
        c.execute(database.CATEGORY_SCHEMA)
        c.execute(database.LOCATION_SCHEMA)
        c.executemany("INSERT INTO categories(name) VALUES (?)", ((name,) for name in CATEGORIES))
        c.execute(database.SCHEMA.replace("category_id INTEGER NOT NULL", "category_id INTEGER"))
        c.execute("PRAGMA user_version = 2")
    previous = path.read_bytes()
    with pytest.raises(sqlite3.DatabaseError, match="not a supported"):
        initialize(path)
    assert path.read_bytes() == previous


def test_v2_malformed_lookup_schema_rejected(db):
    with connect(db) as c:
        c.execute("ALTER TABLE locations RENAME COLUMN id TO missing_id")
    with pytest.raises(sqlite3.DatabaseError, match="not a supported"):
        initialize(db)

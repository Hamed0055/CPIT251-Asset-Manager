import csv
import sqlite3
from dataclasses import replace

import pytest

from src import asset_service as assets
from src import csv_import as importer
from src import reports
from src.database import connect, initialize

HEADERS = reports.ASSET_HEADERS


def csv_file(tmp_path, forms, *, headers=HEADERS, encoding="utf-8", lineterminator="\n"):
    path = tmp_path / "input.csv"
    with path.open("w", encoding=encoding, newline="") as stream:
        writer = csv.writer(stream, lineterminator=lineterminator)
        writer.writerow(headers)
        for index, form in enumerate(forms):
            fields = {header: form.get(key, "") if key else f"IT-{index + 600:06d}" for header, key in reports.ASSET_COLUMNS}
            writer.writerow([fields.get(header, "") for header in headers])
    return path


def test_single_preview_is_read_only_and_ids_regenerated(db, form, tmp_path):
    path = csv_file(tmp_path, [form | {"serial": "0000123"}])
    before = db.read_bytes()
    preview = importer.prepare_import(db, path)
    assert db.read_bytes() == before
    assert (preview.total, preview.valid, preview.invalid, preview.duplicates) == (1, 1, 0, 0)
    result = importer.import_prepared(db, preview)
    record = assets.list_assets(db)[0]
    assert (result.inserted, result.skipped, record["id"], record["serial"]) == (1, 0, 1, "0000123")


@pytest.mark.parametrize("count", [2, 50, 1000])
def test_many(db, form, tmp_path, count):
    path = csv_file(tmp_path, [form | {"serial": f"00{index}"} for index in range(count)])
    preview = importer.prepare_import(db, path)
    assert len(preview.first_rows) == min(10, count)
    result = importer.import_prepared(db, preview)
    assert (result.total, result.inserted, result.skipped) == (count, count, 0)
    assert len(assets.list_assets(db)) == count


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_unicode_quotes_multiline_optional_and_line_endings(db, form, tmp_path, encoding, newline):
    data = form | {"name": 'جهاز, "Library"', "notes": "First, line\nSecond line", "serial": "", "purchase_price": ""}
    preview = importer.prepare_import(db, csv_file(tmp_path, [data], encoding=encoding, lineterminator=newline))
    importer.import_prepared(db, preview)
    record = assets.list_assets(db)[0]
    assert record["name"] == data["name"] and record["notes"] == data["notes"]
    assert record["serial"] is None and record["price_cents"] is None


def test_inventory_export_roundtrip(db, form, tmp_path):
    originals = [form | {"name": name, "serial": f"000{index}", "notes": "=not a formula", "assigned_to": "'@literal"}
                 for index, name in enumerate(["Normal, Laptop", "=1+1", "'@literal", "''two quotes", "'plain"])]
    for item in originals:
        assets.add_asset(db, item)
    destination = tmp_path / "full.csv"
    reports.export_inventory(destination, assets.list_assets(db))
    fresh = tmp_path / "fresh.sqlite3"
    initialize(fresh)
    result = importer.import_prepared(fresh, importer.prepare_import(fresh, destination))
    assert result.inserted == len(originals)
    keys = ("name", "category", "serial", "purchase_year", "price_cents", "status", "assigned_to", "location", "notes")
    expected = {row["serial"]: tuple(row[key] for key in keys) for row in assets.list_assets(db)}
    actual = {row["serial"]: tuple(row[key] for key in keys) for row in assets.list_assets(fresh)}
    assert actual == expected
    with pytest.raises(FileExistsError):
        reports.export_inventory(destination, [])


@pytest.mark.parametrize("report", reports.REPORT_NAMES[1:])
def test_existing_detail_report_accepted(db, form, tmp_path, report):
    assets.add_asset(db, form | {"purchase_year": "2000"})
    destination = tmp_path / "report.csv"
    reports.export_csv(destination, *reports.report_table(assets.list_assets(db), report))
    fresh = tmp_path / "fresh.sqlite3"
    initialize(fresh)
    preview = importer.prepare_import(fresh, destination)
    assert preview.valid == 1 and any("no serial" in warning for warning in preview.warnings)
    importer.import_prepared(fresh, preview)
    item = assets.list_assets(fresh)[0]
    assert item["name"] == form["name"] and item["serial"] is None


def test_summary_is_not_assets(db, tmp_path):
    path = tmp_path / "summary.csv"
    reports.export_csv(path, *reports.report_table([], reports.REPORT_NAMES[0]))
    with pytest.raises(importer.CSVImportError, match="aggregate summary"):
        importer.prepare_import(db, path)


@pytest.mark.parametrize("headers,match", [
    (("Name", "Category", "Status"), "Missing required columns: Year"),
    (("Name", "Category", "Year", "Status", "Name"), "Duplicate"),
    (("Name", "Category", "Year", "Status", "Surprise"), "Unexpected columns"),
    (("Name", "Category", "Year", "Status", ""), "nonempty"),
    (("name", "category", "year", "status"), "Missing required"),
    (("Name", "Category", "Year", "Status", " Name "), "Duplicate"),
])
def test_bad_headers(db, form, tmp_path, headers, match):
    path = csv_file(tmp_path, [form], headers=headers)
    before = db.read_bytes()
    with pytest.raises(importer.CSVImportError, match=match):
        importer.prepare_import(db, path)
    assert db.read_bytes() == before


def test_reordered_trimmed_minimum_headers(db, form, tmp_path):
    path = tmp_path / "minimal.csv"
    path.write_text("Status, Year ,Category,Name\nAvailable,2020,Laptop,Minimal\n", encoding="utf-8")
    preview = importer.prepare_import(db, path)
    assert preview.valid == 1
    importer.import_prepared(db, preview)
    assert assets.list_assets(db)[0]["price_cents"] is None


def test_empty_and_header_only(db, tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8-sig")
    with pytest.raises(importer.CSVImportError, match="empty"):
        importer.prepare_import(db, path)
    preview = importer.prepare_import(db, csv_file(tmp_path, []))
    assert (preview.total, preview.valid, preview.invalid, preview.duplicates) == (0, 0, 0, 0)
    assert importer.import_prepared(db, preview).inserted == 0


@pytest.mark.parametrize("change", [
    {"purchase_year": ""}, {"purchase_year": "20xx"}, {"purchase_year": "2020.0"},
    {"purchase_year": "1899"}, {"purchase_year": "9999"},
    {"purchase_price": "-1"}, {"purchase_price": "NaN"}, {"purchase_price": "1.234"},
    {"purchase_price": "1,500"}, {"purchase_price": "1000000000"},
    {"name": " "}, {"category": ""}, {"status": ""}, {"category": "Monitor"},
    {"status": "Operational"}, {"serial": "s" * 101}, {"notes": "n" * 4001},
    {"location": "\x00bad"},
])
def test_existing_validation_rules(db, form, tmp_path, change):
    before = db.read_bytes()
    preview = importer.prepare_import(db, csv_file(tmp_path, [form | change]))
    assert preview.valid == 0 and preview.invalid == 1
    assert preview.issues[0].row_number == 2 and preview.issues[0].message
    assert db.read_bytes() == before


def test_duplicates_and_counts_preserve_existing(db, form, tmp_path):
    original = assets.add_asset(db, form)
    before = dict(assets.get_asset(db, original))
    forms = [form | {"serial": "lt-001"}, form | {"serial": "NEW"}, form | {"serial": " new "},
             form | {"name": "", "serial": "bad"}, form | {"serial": ""}, form | {"serial": ""}]
    preview = importer.prepare_import(db, csv_file(tmp_path, forms))
    assert (preview.total, preview.valid, preview.invalid, preview.duplicates) == (6, 3, 1, 2)
    result = importer.import_prepared(db, preview)
    assert (result.total, result.inserted, result.invalid, result.duplicates, result.skipped) == (6, 3, 1, 2, 3)
    assert dict(assets.get_asset(db, original)) == before
    assert len(assets.list_assets(db)) == 4
    assert [issue.row_number for issue in result.issues] == [2, 4, 5]


def test_invalid_first_occurrence_does_not_claim_serial(db, form, tmp_path):
    preview = importer.prepare_import(db, csv_file(tmp_path, [form | {"name": ""}, form]))
    assert (preview.valid, preview.invalid, preview.duplicates) == (1, 1, 0)


def test_duplicate_inserted_after_preview_is_rechecked(db, form, tmp_path):
    preview = importer.prepare_import(db, csv_file(tmp_path, [form]))
    assets.add_asset(db, form)
    result = importer.import_prepared(db, preview)
    assert result.inserted == 0 and result.duplicates == 1
    assert "since preview" in result.issues[0].message


def test_file_snapshot_and_cancel_without_mutations(db, form, tmp_path):
    path = csv_file(tmp_path, [form])
    before = db.read_bytes()
    preview = importer.prepare_import(db, path)
    assert db.read_bytes() == before  # Cancelling here never calls insertion.
    path.write_text("replaced after preview", encoding="utf-8")
    result = importer.import_prepared(db, preview)
    assert result.inserted == 1 and assets.list_assets(db)[0]["name"] == form["name"]


def test_unexpected_insert_failure_rolls_back_entire_batch(db, form, tmp_path, monkeypatch):
    original = assets.add_asset(db, form | {"serial": "EXISTING"})
    original_row = dict(assets.get_asset(db, original))
    preview = importer.prepare_import(db, csv_file(tmp_path, [form | {"serial": "ONE"}, form | {"serial": "TWO"}]))
    real_insert = importer.insert_validated_asset
    count = 0

    def fail_second(connection, values):
        nonlocal count
        count += 1
        if count == 2:
            raise sqlite3.OperationalError("simulated disk failure")
        return real_insert(connection, values)

    monkeypatch.setattr(importer, "insert_validated_asset", fail_second)
    with pytest.raises(sqlite3.OperationalError, match="disk failure"):
        importer.import_prepared(db, preview)
    assert [dict(row) for row in assets.list_assets(db)] == [original_row]
    with connect(db) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_sqlite_constraint_failure_is_atomic(db, form, tmp_path):
    preview = importer.prepare_import(db, csv_file(tmp_path, [form | {"serial": "ONE"}, form | {"serial": "TWO"}]))
    with connect(db) as connection:
        connection.execute("CREATE TRIGGER reject_two BEFORE INSERT ON assets WHEN NEW.serial = 'TWO' BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        importer.import_prepared(db, preview)
    assert not assets.list_assets(db)


@pytest.mark.parametrize("contents,match", [
    (b'Name,Category,Year,Status\n"unterminated,Laptop,2020,Available', "Malformed CSV"),
    (b'Name,Category,Year,Status\n\xff,Laptop,2020,Available', "UTF-8"),
])
def test_fatal_file_errors_do_not_write(db, tmp_path, contents, match):
    path = tmp_path / "bad.csv"
    path.write_bytes(contents)
    before = db.read_bytes()
    with pytest.raises(importer.CSVImportError, match=match):
        importer.prepare_import(db, path)
    assert db.read_bytes() == before


def test_bad_field_count_and_multiline_row_numbers(db, tmp_path):
    path = tmp_path / "width.csv"
    path.write_text('Name,Category,Year,Status\n"Two\nlines",Laptop,2020,Available\nExtra,Laptop,2020,Available,oops\nMissing,Laptop\n\n', encoding="utf-8")
    preview = importer.prepare_import(db, path)
    assert (preview.total, preview.valid, preview.invalid) == (3, 1, 2)
    assert [row.row_number for row in preview.first_rows] == [2, 4, 5]
    assert [issue.row_number for issue in preview.issues] == [4, 5]


def test_no_database_creation_during_preview(db, form, tmp_path):
    missing = tmp_path / "missing.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        importer.prepare_import(missing, csv_file(tmp_path, [form]))
    assert not missing.exists()


def test_file_not_found_and_permission_error(db, tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError):
        importer.prepare_import(db, tmp_path / "missing.csv")
    original_open = type(tmp_path).open

    def denied(path, *args, **kwargs):
        if path.suffix == ".csv":
            raise PermissionError("test permission denied")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(type(tmp_path), "open", denied)
    with pytest.raises(PermissionError):
        importer.prepare_import(db, tmp_path / "denied.csv")


def test_wrong_database_rejected(db, form, tmp_path):
    preview = importer.prepare_import(db, csv_file(tmp_path, [form]))
    other = tmp_path / "other.sqlite3"
    initialize(other)
    with pytest.raises(importer.CSVImportError, match="different inventory"):
        importer.import_prepared(other, preview)
    assert not assets.list_assets(other)


def test_revalidate_during_commit(db, form, tmp_path):
    preview = importer.prepare_import(db, csv_file(tmp_path, [form]))
    invalid = replace(preview.records[0], fields=tuple((form | {"name": ""}).items()))
    with pytest.raises(ValueError):
        importer.import_prepared(db, replace(preview, records=(invalid,)))
    assert not assets.list_assets(db)


def test_shipped_demonstration_files(db):
    from pathlib import Path
    examples = Path(__file__).resolve().parents[1] / "examples"
    preview = importer.prepare_import(db, examples / "sample_inventory_50.csv")
    assert (preview.total, preview.valid, preview.invalid, preview.duplicates) == (50, 50, 0, 0)
    result = importer.import_prepared(db, preview)
    assert result.inserted == 50
    categories = {record["category"] for record in assets.list_assets(db)}
    assert categories == {"Desktop PC", "Laptop", "Router", "Switch", "Peripheral", "Other"}
    demo = importer.prepare_import(db, examples / "invalid_inventory.csv")
    assert (demo.total, demo.valid, demo.invalid, demo.duplicates) == (7, 0, 4, 3)

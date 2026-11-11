import csv

import pytest

from src import asset_service as assets
from src import reports


@pytest.mark.parametrize(("age", "label"), [
    (0, "New"), (2, "New"), (3, "Standard"), (4, "Standard"),
    (5, "Aging"), (6, "Aging"), (7, "Replacement recommended"), (30, "Replacement recommended"),
])
def test_age_boundaries(age, label):
    assert reports.age_classification(age) == label


@pytest.mark.parametrize("age", [0, 2, 5, 7, 10])
@pytest.mark.parametrize("status", ["Under Maintenance", "Retired"])
def test_repair_precedes_age(status, age):
    assert reports.maintenance_action(status, age) == "Repair priority"


def test_reports_and_priority_sort(db, form):
    for name, year, status in [
        ("New", "2026", "Available"),
        ("Needs repair", "2026", "Under Maintenance"),
        ("Old", "2018", "Assigned"),
        ("Aging", "2020", "Available"),
        ("Retired", "2018", "Retired"),
    ]:
        assets.add_asset(db, form | {"name": name, "purchase_year": year, "status": status, "serial": ""})
    records = assets.list_assets(db)
    summary = reports.inventory_summary(records, 2026)
    assert {key: summary[key] for key in (
        "total", "operational", "non_operational", "repair", "aging", "maintenance",
    )} == {"total": 5, "operational": 3, "non_operational": 2, "repair": 2, "aging": 3, "maintenance": 4}
    assert summary["categories"]["Laptop"] == 5 and summary["categories"]["Switch"] == 0
    assert summary["statuses"]["Assigned"] == 1
    _, aging = reports.report_table(records, reports.REPORT_NAMES[1], 2026)
    assert [row[1] for row in aging] == ["Retired", "Old", "Aging"]
    _, maintenance = reports.report_table(records, reports.REPORT_NAMES[2], 2026)
    assert [row[1] for row in maintenance] == ["Retired", "Needs repair", "Old", "Aging"]
    assert [row[-1] for row in maintenance] == [
        "Repair priority", "Repair priority", "Review for replacement", "Schedule maintenance review",
    ]


def test_empty_summary():
    headers, rows = reports.report_table([], reports.REPORT_NAMES[0], 2026)
    assert headers == reports.SUMMARY_HEADERS
    assert rows[0] == ("Overview", "Total assets", 0)
    assert all(row[2] == 0 for row in rows)


def test_csv_quoting_unicode_and_no_overwrite(tmp_path):
    path = tmp_path / "report.csv"
    reports.export_csv(path, ["Name", "Status"], [["Routeur, Étage", "Assigned"], [" =1+1", "Available"]])
    with path.open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.reader(stream)) == [
            ["Name", "Status"], ["Routeur, Étage", "Assigned"], ["' =1+1", "Available"],
        ]
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        reports.export_csv(path, ["other"], [])
    assert path.read_bytes() == before

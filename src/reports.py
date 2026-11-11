"""Turn an inventory snapshot into dashboard totals, reports, and CSV."""
import csv
from collections import Counter
from datetime import date
from pathlib import Path

from config import CATEGORIES, OPERATIONAL, STATUSES
from src.asset_service import asset_code, format_price

REPORT_NAMES = ("Inventory summary", "Aging equipment", "Maintenance and repair")
SUMMARY_HEADERS = ("Group", "Item", "Count")
DETAIL_HEADERS = ("Asset ID", "Name", "Category", "Status", "Year", "Age", "Classification", "Action")
ASSET_COLUMNS = (
    ("Asset ID", None), ("Name", "name"), ("Category", "category"),
    ("Serial number", "serial"), ("Year", "purchase_year"),
    ("Purchase price (SAR)", "purchase_price"), ("Status", "status"),
    ("Assigned person", "assigned_to"), ("Location", "location"), ("Notes", "notes"),
)
ASSET_HEADERS = tuple(header for header, _key in ASSET_COLUMNS)


def export_inventory(destination, records):
    """Full-fidelity asset CSV; IDs are informational and regenerated on import."""
    def rows():
        for record in records:
            fields = dict(record)
            fields["purchase_price"] = format_price(record["price_cents"])
            values = [asset_code(record["id"]) if key is None else fields[key] for _header, key in ASSET_COLUMNS]
            # Double literal apostrophes so the importer can undo formula safety
            # prefixes without corrupting names that genuinely begin with one.
            yield ["'" + value if isinstance(value, str) and value.startswith("'") else value for value in values]
    export_csv(destination, ASSET_HEADERS, rows())


def age_classification(age):
    if age < 0:
        raise ValueError("Age cannot be negative.")
    if age <= 2:
        return "New"
    if age <= 4:
        return "Standard"
    if age <= 6:
        return "Aging"
    return "Replacement recommended"


def maintenance_action(status, age):
    if status not in OPERATIONAL:
        return "Repair priority"
    if age >= 7:
        return "Review for replacement"
    if age >= 5:
        return "Schedule maintenance review"
    return "Routine checks"


def inventory_summary(assets, current_year):
    categories = Counter(asset["category"] for asset in assets)
    statuses = Counter(asset["status"] for asset in assets)
    operational = sum(statuses[status] for status in OPERATIONAL)
    repair = len(assets) - operational
    return {
        "total": len(assets),
        "operational": operational,
        "non_operational": repair,
        "aging": sum(current_year - asset["purchase_year"] >= 5 for asset in assets),
        "repair": repair,
        "maintenance": sum(
            asset["status"] not in OPERATIONAL or current_year - asset["purchase_year"] >= 5
            for asset in assets
        ),
        "categories": {category: categories[category] for category in CATEGORIES},
        "statuses": {status: statuses[status] for status in STATUSES},
    }


def report_table(assets, report, current_year=None):
    if current_year is None:
        current_year = date.today().year
    if report == REPORT_NAMES[0]:
        summary = inventory_summary(assets, current_year)
        rows = [
            ("Overview", "Total assets", summary["total"]),
            ("Condition", "Operational", summary["operational"]),
            ("Condition", "Non-operational", summary["non_operational"]),
            ("Review", "Aging (5+ years)", summary["aging"]),
            ("Review", "Repair priority", summary["repair"]),
            ("Review", "All maintenance and repair", summary["maintenance"]),
        ]
        rows.extend(("Category", label, count) for label, count in summary["categories"].items())
        rows.extend(("Status", label, count) for label, count in summary["statuses"].items())
        return SUMMARY_HEADERS, rows

    if report not in REPORT_NAMES:
        raise ValueError("Unknown report.")
    rows = []
    for asset in assets:
        age = current_year - asset["purchase_year"]
        status = asset["status"]
        if age < 5 and (report == REPORT_NAMES[1] or status in OPERATIONAL):
            continue
        rows.append((
            asset_code(asset["id"]), asset["name"], asset["category"], status,
            asset["purchase_year"], age, age_classification(age), maintenance_action(status, age),
        ))
    rows.sort(key=lambda row: (row[-1] != "Repair priority", -row[5], row[0]))
    return DETAIL_HEADERS, rows


def spreadsheet_value(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_csv(destination, headers, rows):
    """Create a new spreadsheet-friendly CSV without overwriting an existing file."""
    destination = Path(destination)
    stream = destination.open("x", encoding="utf-8-sig", newline="")
    try:
        with stream:
            writer = csv.writer(stream)
            writer.writerow(headers)
            writer.writerows([spreadsheet_value(value) for value in row] for row in rows)
    except (OSError, csv.Error):
        destination.unlink()
        raise

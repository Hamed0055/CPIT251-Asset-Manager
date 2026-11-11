"""Create a new sample database with fictional equipment only."""
import argparse
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from src.asset_service import add_asset
from src.database import backup_database, initialize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    destination = parser.parse_args().output
    year = date.today().year
    sample = [
        ("Library Desktop", "Desktop PC", "DEMO-PC-01", 5, "Available", "Library"),
        ("Coursework Laptop", "Laptop", "DEMO-LT-02", 1, "Assigned", "Lab A"),
        ("Edge Router", "Router", "DEMO-RT-03", 0, "Under Maintenance", "Network room"),
        ("Lab Switch", "Switch", "DEMO-SW-04", 7, "Available", "Lab B"),
        ("Old Document Scanner", "Peripheral", "DEMO-PR-05", 9, "Retired", "Storage"),
        ("Test Equipment Case", "Other", "", 3, "Available", "Storage"),
    ]
    with TemporaryDirectory() as directory:
        draft = Path(directory) / "demo.sqlite3"
        initialize(draft)
        for name, category, serial, age, status, location in sample:
            add_asset(draft, {
                "name": name, "category": category, "serial": serial, "purchase_year": str(year - age),
                "status": status, "location": location, "notes": "Fictional demonstration asset.",
            })
        try:
            backup_database(draft, destination)
        except FileExistsError:
            parser.error(f"File already exists: {destination}")
    print(f"Wrote {len(sample)} demo assets to {destination}")


if __name__ == "__main__":
    main()

from datetime import date

import pytest

from src.database import initialize


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "data" / "inventory.sqlite3"
    initialize(path)
    return path


@pytest.fixture
def form():
    return {
        "name": "Library Laptop",
        "category": "Laptop",
        "serial": "LT-001",
        "purchase_year": str(date.today().year),
        "purchase_price": "1150.45",
        "status": "Available",
        "assigned_to": "",
        "location": "Library",
        "notes": "Synthetic test record.",
    }

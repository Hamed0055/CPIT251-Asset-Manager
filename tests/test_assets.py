import pytest

from src import asset_service as assets
from src.validation import ValidationError


def test_crud_and_non_reused_id(db, form):
    asset_id = assets.add_asset(db, form)
    result = assets.get_asset(db, asset_id)
    assert result["price_cents"] == 115045
    assert result["name"] == "Library Laptop"
    assert assets.asset_code(asset_id) == "IT-000001"
    assets.update_asset(db, asset_id, form | {"status": "Assigned", "assigned_to": "Demo"})
    result = assets.get_asset(db, asset_id)
    assert (result["status"], result["assigned_to"]) == ("Assigned", "Demo")
    assets.delete_asset(db, asset_id)
    assert assets.list_assets(db) == []
    for call in (
        lambda: assets.get_asset(db, asset_id),
        lambda: assets.update_asset(db, asset_id, form),
        lambda: assets.delete_asset(db, asset_id),
    ):
        with pytest.raises(assets.AssetNotFound):
            call()
    assert assets.add_asset(db, form) > asset_id


def test_serial_uniqueness_create_and_edit(db, form):
    first = assets.add_asset(db, form | {"serial": "ÄBC-01"})
    with pytest.raises(ValidationError, match="already registered"):
        assets.add_asset(db, form | {"serial": "  äbc-01 "})
    second = assets.add_asset(db, form)
    with pytest.raises(ValidationError, match="already registered"):
        assets.update_asset(db, second, form | {"serial": "äbc-01"})
    assert assets.get_asset(db, second)["serial"] == form["serial"]
    assets.update_asset(db, first, form | {"serial": "äbc-01", "name": "Renamed"})


def test_missing_serial_can_repeat(db, form):
    empty = form | {"serial": " ", "purchase_price": ""}
    a = assets.add_asset(db, empty)
    assets.add_asset(db, empty)
    record = assets.get_asset(db, a)
    assert record["serial"] is None
    assert record["price_cents"] is None


def test_search_and_combined_filters(db, form):
    laptop = assets.add_asset(db, form | {"name": "Étage Laptop"})
    router = assets.add_asset(db, form | {
        "name": "Lab Router", "category": "Router", "status": "Assigned",
        "serial": "RO-%1", "purchase_year": "2020",
    })
    for term in ("étAGE", "lapt", "lt-001", "IT-000001", "1"):
        assert laptop in [row["id"] for row in assets.list_assets(db, term)]
    for term in ("RO-%1", "o-%", "%"):
        assert [row["id"] for row in assets.list_assets(db, term)] == [router]
    assert assets.list_assets(db, "' OR 1=1 --") == []
    assert [row["id"] for row in assets.list_assets(
        db, "lab", category="Router", status="Assigned", year="2020",
    )] == [router]
    assert assets.list_assets(db, category="Router", status="Available") == []
    assert [row["id"] for row in assets.list_assets(db, year="2020")] == [router]
    assert assets.purchase_years(db) == [int(form["purchase_year"]), 2020]

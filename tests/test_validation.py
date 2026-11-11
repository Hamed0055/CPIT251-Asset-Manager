from datetime import date

import pytest

from src.validation import ValidationError, validate_asset


@pytest.mark.parametrize("field", ["name", "category", "status", "purchase_year"])
def test_required_fields(form, field):
    with pytest.raises(ValidationError):
        validate_asset(form | {field: " "})


@pytest.mark.parametrize("year", ["1899", "0000", "20a0", "2020.0", "9999"])
def test_invalid_purchase_year(form, year):
    with pytest.raises(ValidationError, match="year"):
        validate_asset(form | {"purchase_year": year})


@pytest.mark.parametrize("price", ["-1", "1.234", "1,000", "1e3", "NaN", "Inf", "1000000000", "1."])
def test_invalid_price(form, price):
    with pytest.raises(ValidationError, match="price"):
        validate_asset(form | {"purchase_price": price})


def test_price_and_year_boundaries(form):
    for year in (1900, date.today().year):
        assert validate_asset(form | {"purchase_year": str(year)})["purchase_year"] == year
    for price, cents in [("", None), ("0", 0), ("0.01", 1), ("10.1", 1010), ("999999999.99", 99999999999)]:
        assert validate_asset(form | {"purchase_price": price})["price_cents"] == cents


def test_text_is_trimmed_without_losing_inner_lines(form):
    result = validate_asset(form | {"serial": " xy-Z ", "notes": " First\nSecond "})
    assert result["serial"] == "xy-Z" and result["serial_key"] == "xy-z"
    assert result["notes"] == "First\nSecond"
    with pytest.raises(ValidationError, match="at most"):
        validate_asset(form | {"notes": "x" * 4001})

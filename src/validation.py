"""Convert form strings to validated values before writing to SQLite."""
import re
from datetime import date
from decimal import Decimal

from config import CATEGORIES, MAX_PRICE_CENTS, MIN_YEAR, STATUSES


class ValidationError(ValueError):
    """An input error that can be shown directly in the form."""


def clean_text(values, key, label, limit, required=False):
    value = values.get(key, "").strip()
    if required and not value:
        raise ValidationError(f"{label} is required.")
    if len(value) > limit:
        raise ValidationError(f"{label} must have at most {limit} characters.")
    return value


def validate_asset(values):
    name = clean_text(values, "name", "Asset name", 120, required=True)
    category = values.get("category")
    status = values.get("status")
    if category not in CATEGORIES:
        raise ValidationError("Choose an equipment category.")
    if status not in STATUSES:
        raise ValidationError("Choose an operational status.")

    current_year = date.today().year
    year_text = values.get("purchase_year", "").strip()
    if not re.fullmatch(r"[0-9]{4}", year_text):
        raise ValidationError("Purchase year must be a four-digit year.")
    year = int(year_text)
    if not MIN_YEAR <= year <= current_year:
        raise ValidationError(f"Purchase year must be between {MIN_YEAR} and {current_year}.")

    price_text = values.get("purchase_price", "").strip()
    price_cents = None
    if price_text:
        if not re.fullmatch(r"[0-9]{1,9}(\.[0-9]{1,2})?", price_text):
            raise ValidationError("Enter a SAR price from 0 to 999999999.99, using at most two decimals.")
        price_cents = int(Decimal(price_text) * 100)
        if price_cents > MAX_PRICE_CENTS:
            raise ValidationError("Purchase price exceeds the allowed maximum.")

    serial = clean_text(values, "serial", "Serial number", 100)
    return {
        "name": name,
        "category": category,
        "serial": serial or None,
        "serial_key": serial.casefold() or None,
        "purchase_year": year,
        "price_cents": price_cents,
        "status": status,
        "assigned_to": clean_text(values, "assigned_to", "Assigned person", 120),
        "location": clean_text(values, "location", "Location", 120),
        "notes": clean_text(values, "notes", "Notes", 4000),
    }

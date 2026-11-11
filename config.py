"""Constants and the per-user data location."""
import os
import sys
from pathlib import Path

APP_NAME = "IT Asset Inventory"
VERSION = "1.0.1"
DATA_FOLDER = "CPIT251-Asset-Manager-Reference"
CATEGORIES = ("Desktop PC", "Laptop", "Router", "Switch", "Peripheral", "Other")
STATUSES = ("Available", "Assigned", "Under Maintenance", "Retired")
OPERATIONAL = ("Available", "Assigned")
MIN_YEAR = 1900
MAX_PRICE_CENTS = 99_999_999_999  # SAR 999,999,999.99


def database_path() -> Path:
    """Resolve the path independently of the source or frozen executable."""
    if sys.platform == "win32":
        local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return local / DATA_FOLDER / "inventory.sqlite3"
    xdg = Path(os.environ.get("XDG_DATA_HOME", ""))
    local = xdg if xdg.is_absolute() else Path.home() / ".local" / "share"
    return local / DATA_FOLDER.lower() / "inventory.sqlite3"

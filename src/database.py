"""SQLite connections, schema initialization and consistent backup."""
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from config import CATEGORIES, MAX_PRICE_CENTS, MIN_YEAR, STATUSES

SCHEMA_VERSION = 1
# These strings come exclusively from application constants, never from input.
CATEGORY_CHECK = ", ".join(repr(value) for value in CATEGORIES)
STATUS_CHECK = ", ".join(repr(value) for value in STATUSES)

SCHEMA = f"""
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
    category TEXT NOT NULL CHECK (category IN ({CATEGORY_CHECK})),
    serial TEXT CHECK (length(trim(serial)) BETWEEN 1 AND 100),
    serial_key TEXT UNIQUE CHECK ((serial IS NULL) = (serial_key IS NULL)),
    purchase_year INTEGER NOT NULL CHECK (purchase_year BETWEEN {MIN_YEAR} AND 9999),
    price_cents INTEGER CHECK (price_cents BETWEEN 0 AND {MAX_PRICE_CENTS}),
    status TEXT NOT NULL CHECK (status IN ({STATUS_CHECK})),
    assigned_to TEXT NOT NULL DEFAULT '' CHECK (length(assigned_to) <= 120),
    location TEXT NOT NULL DEFAULT '' CHECK (length(location) <= 120),
    notes TEXT NOT NULL DEFAULT '' CHECK (length(notes) <= 4000),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
) STRICT
"""


@contextmanager
def connect(path, *, read_only=False):
    """Commit on success, roll back on error and always close the handle."""
    target = Path(path).absolute().as_uri() + "?mode=ro" if read_only else path
    with closing(sqlite3.connect(target, timeout=3, uri=read_only)) as connection, connection:
        connection.row_factory = sqlite3.Row
        connection.create_function("casefold", 1, str.casefold, deterministic=True)
        yield connection


def initialize(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            connection.execute("SELECT id, serial_key FROM assets LIMIT 0")
            return
        if version != 0 or connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone():
            raise sqlite3.DatabaseError("This file is not a supported inventory database.")
        connection.execute(SCHEMA)
        connection.execute("CREATE INDEX assets_category_idx ON assets(category)")
        connection.execute("CREATE INDEX assets_status_idx ON assets(status)")
        connection.execute("CREATE INDEX assets_year_idx ON assets(purchase_year)")
        connection.execute("PRAGMA user_version = 1")


def backup_database(path, destination):
    """Use SQLite's backup API so the copy is consistent while the app is open."""
    destination = Path(destination)
    # Exclusive creation also protects the original database and older backups.
    with destination.open("xb"):
        pass
    try:
        source_uri = Path(path).absolute().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True, timeout=3)) as source, connect(destination) as target:
            if source.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                raise sqlite3.DatabaseError("This file is not a supported inventory database.")
            source.execute("SELECT id, serial_key FROM assets LIMIT 0")
            source.backup(target)
    except (OSError, sqlite3.Error):
        destination.unlink()
        raise

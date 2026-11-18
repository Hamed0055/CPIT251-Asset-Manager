"""Versioned SQLite storage, referential integrity and consistent backups."""
import sqlite3
import time
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from config import CATEGORIES, MAX_PRICE_CENTS, MIN_YEAR, STATUSES
from src.validation import ValidationError, location_key

SCHEMA_VERSION = 2
CATEGORY_CHECK = ", ".join(repr(value) for value in CATEGORIES)
STATUS_CHECK = ", ".join(repr(value) for value in STATUSES)

CATEGORY_SCHEMA = f"""
CREATE TABLE categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (name IN ({CATEGORY_CHECK}))
) STRICT
"""
LOCATION_SCHEMA = """
CREATE TABLE locations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (length(name) BETWEEN 1 AND 120 AND name = trim(name))
) STRICT
"""
SCHEMA = f"""
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    location_id INTEGER REFERENCES locations(id) ON DELETE RESTRICT,
    serial TEXT CHECK (length(trim(serial)) BETWEEN 1 AND 100),
    serial_key TEXT UNIQUE CHECK ((serial IS NULL) = (serial_key IS NULL)),
    purchase_year INTEGER NOT NULL CHECK (purchase_year BETWEEN {MIN_YEAR} AND 9999),
    price_cents INTEGER CHECK (price_cents BETWEEN 0 AND {MAX_PRICE_CENTS}),
    status TEXT NOT NULL CHECK (status IN ({STATUS_CHECK})),
    assigned_to TEXT NOT NULL DEFAULT '' CHECK (length(assigned_to) <= 120),
    notes TEXT NOT NULL DEFAULT '' CHECK (length(notes) <= 4000),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
) STRICT
"""
V1_COLUMNS = {
    "id", "name", "category", "serial", "serial_key", "purchase_year", "price_cents",
    "status", "assigned_to", "location", "notes", "created_at", "updated_at",
}
V2_COLUMNS = (V1_COLUMNS - {"category", "location"}) | {"category_id", "location_id"}


@contextmanager
def connect(path, *, read_only=False):
    """Enable FK enforcement before transactions; commit/rollback and always close."""
    target = Path(path).absolute().as_uri() + "?mode=ro" if read_only else path
    with closing(sqlite3.connect(target, timeout=3, uri=read_only)) as connection, connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise sqlite3.DatabaseError("SQLite foreign-key enforcement is unavailable.")
        connection.create_function("casefold", 1, str.casefold, deterministic=True)
        yield connection


def _unsupported():
    return sqlite3.DatabaseError("This file is not a supported inventory database.")


def _validate(connection, version):
    """Reject foreign/malformed files rather than recreating or reseeding them."""
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    )}
    expected = {"assets"} if version == 1 else {"categories", "locations", "assets"}
    columns = {row[1] for row in connection.execute("PRAGMA table_info(assets)")}
    if version not in (1, 2) or tables != expected or columns != (V1_COLUMNS if version == 1 else V2_COLUMNS):
        raise _unsupported()
    if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise sqlite3.DatabaseError("Inventory integrity check failed.")
    if version == 1:
        # Rebuilding unknown views/triggers could silently change custom behavior.
        if connection.execute("SELECT 1 FROM sqlite_schema WHERE type IN ('view', 'trigger') LIMIT 1").fetchone():
            raise sqlite3.DatabaseError("Version 1 contains custom views/triggers; review them before migration.")
        return
    strict = {r[1]: r[5] for r in connection.execute("PRAGMA table_list")}
    if any(strict.get(table) != 1 for table in expected):
        raise _unsupported()
    for table in expected:
        info = {r[1]: r for r in connection.execute(f"PRAGMA table_info({table})")}
        if set(info) != (V2_COLUMNS if table == "assets" else {"id", "name"}):
            raise _unsupported()
        required = ({"name"} if table != "assets" else
                    {"name", "category_id", "purchase_year", "status", "assigned_to", "notes", "created_at", "updated_at"})
        if not info["id"][5] or any(not info[name][3] for name in required):
            raise _unsupported()
        unique_columns = set()
        for index in connection.execute(f"PRAGMA index_list({table})"):
            if index[2] and not index[4]:  # A partial unique index is not enough.
                # SQLite supplies the identifier; quote it as an identifier.
                quoted = index[1].replace('"', '""')
                unique_columns.add(tuple(r[2] for r in connection.execute(f'PRAGMA index_info("{quoted}")')))
        if ("serial_key" if table == "assets" else "name",) not in unique_columns:
            raise _unsupported()
    category_names = [row[0] for row in connection.execute("SELECT name FROM categories")]
    if len(category_names) != len(CATEGORIES) or set(category_names) != set(CATEGORIES):
        raise sqlite3.DatabaseError("Inventory category catalogue does not match the configured choices.")
    foreign_keys = {(row[3], row[2], row[4], row[6]) for row in connection.execute("PRAGMA foreign_key_list(assets)")}
    if foreign_keys != {("category_id", "categories", "id", "RESTRICT"), ("location_id", "locations", "id", "RESTRICT")}:
        raise _unsupported()
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise sqlite3.DatabaseError("Inventory contains invalid foreign-key references.")
    names = [row[0] for row in connection.execute("SELECT name FROM locations")]
    keys = [location_key(name) for name in names]
    if any(not key or name != name.strip() for name, key in zip(names, keys)) or len(set(keys)) != len(keys):
        raise sqlite3.DatabaseError("Inventory contains empty or duplicate normalized locations.")


def _create_lookups(connection):
    connection.execute(CATEGORY_SCHEMA)
    connection.execute(LOCATION_SCHEMA)
    connection.executemany("INSERT INTO categories(name) VALUES (?)", ((name,) for name in CATEGORIES))


def _create_indexes(connection):
    for name, column in (("category", "category_id"), ("location", "location_id"),
                         ("status", "status"), ("year", "purchase_year")):
        connection.execute(f"CREATE INDEX assets_{name}_idx ON assets({column})")


def resolve_relationships(connection, values):
    """Resolve readable values inside the caller's writer transaction."""
    category = connection.execute("SELECT id FROM categories WHERE name = ?", (values["category"],)).fetchone()
    if category is None:
        raise ValidationError("Choose an equipment category.")
    name = values["location"].strip()
    location_id = None
    if name:
        row = connection.execute("SELECT id FROM locations WHERE casefold(name) = ?", (location_key(name),)).fetchone()
        location_id = row[0] if row else connection.execute("INSERT INTO locations(name) VALUES (?)", (name,)).lastrowid
    return {**values, "category_id": category[0], "location_id": location_id}


def _migrate_v1(connection):
    """Rebuild under one transaction; never use executescript (implicit commit)."""
    rows = connection.execute("SELECT * FROM assets ORDER BY id").fetchall()
    sequence = connection.execute("SELECT seq FROM sqlite_sequence WHERE name = 'assets'").fetchone()
    high_water = sequence[0] if sequence else 0
    _create_lookups(connection)
    connection.execute("ALTER TABLE assets RENAME TO assets_v1")
    connection.execute(SCHEMA)
    columns = ("id", "name", "category_id", "location_id", "serial", "serial_key", "purchase_year",
               "price_cents", "status", "assigned_to", "notes", "created_at", "updated_at")
    sql = f"INSERT INTO assets ({', '.join(columns)}) VALUES ({', '.join(':'+key for key in columns)})"
    for row in rows:
        connection.execute(sql, resolve_relationships(connection, dict(row)))
    if connection.execute("SELECT count(*) FROM assets").fetchone()[0] != len(rows):
        raise sqlite3.DatabaseError("Migration asset count does not match the original.")
    connection.execute("DROP TABLE assets_v1")
    if high_water:
        connection.execute("DELETE FROM sqlite_sequence WHERE name = 'assets'")
        connection.execute("INSERT INTO sqlite_sequence(name, seq) VALUES ('assets', ?)", (high_water,))
    _create_indexes(connection)
    _validate(connection, 2)


def initialize(path):
    """Initialize v2 or atomically migrate v1; return its verified backup path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with connect(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            _validate(connection, version)
            return None
        if version == 1:
            _validate(connection, version)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            backup = path.with_name(f"{path.stem}.pre-v2-{stamp}-{uuid4().hex[:8]}.sqlite3")
            # A separate reader can back up while this connection reserves the writer.
            # Backing up the same connection during its write transaction can hang.
            backup_database(path, backup)
            _migrate_v1(connection)
        elif version == 0 and not connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' LIMIT 1"
        ).fetchone():
            _create_lookups(connection)
            connection.execute(SCHEMA)
            _create_indexes(connection)
            _validate(connection, 2)
        else:
            raise _unsupported()
        connection.execute("PRAGMA user_version = 2")
    return backup


def backup_database(path, destination):
    """Exclusive, consistent and verified v1/v2 copy; never migrate the backup."""
    destination = Path(destination)
    with destination.open("xb"):
        pass
    try:
        with connect(path, read_only=True) as source, connect(destination) as target:
            source.execute("BEGIN")
            version = source.execute("PRAGMA user_version").fetchone()[0]
            _validate(source, version)
            count = source.execute("SELECT count(*) FROM assets").fetchone()[0]
            deadline = time.monotonic() + 10

            def progress(_status, _remaining, _total):
                if time.monotonic() > deadline:
                    raise sqlite3.OperationalError("Database backup timed out; close other writers and retry.")

            source.backup(target, pages=256, progress=progress)
            _validate(target, version)
            if target.execute("PRAGMA user_version").fetchone()[0] != version or target.execute(
                "SELECT count(*) FROM assets"
            ).fetchone()[0] != count:
                raise sqlite3.DatabaseError("Backup verification failed.")
    except (OSError, sqlite3.Error):
        destination.unlink()
        raise

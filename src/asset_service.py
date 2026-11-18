"""Asset operations shared by the GUI, tests and demo generator."""
import sqlite3

from src.database import connect, resolve_relationships
from src.validation import ValidationError, validate_asset

# Keep the established public row fields; only storage uses numerical IDs.
ASSET_QUERY = """
SELECT a.id, a.name, c.name AS category, a.serial, a.serial_key, a.purchase_year,
       a.price_cents, a.status, a.assigned_to, coalesce(l.name, '') AS location,
       a.notes, a.created_at, a.updated_at
FROM assets AS a JOIN categories AS c ON a.category_id = c.id
LEFT JOIN locations AS l ON a.location_id = l.id
"""


class AssetNotFound(LookupError):
    """The requested row was removed or does not exist."""


def asset_code(asset_id):
    return f"IT-{asset_id:06d}"


def format_price(cents):
    if cents is None:
        return ""
    return f"{cents // 100}.{cents % 100:02d}"


def add_asset(path, form):
    values = validate_asset(form)
    try:
        with connect(path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            return insert_validated_asset(connection, values)
    except sqlite3.IntegrityError as error:
        handle_integrity(error)


def insert_validated_asset(connection, values):
    """Insert validated fields using the caller's transaction; never commit here."""
    values = resolve_relationships(connection, values)
    cursor = connection.execute(
        """
        INSERT INTO assets (name, category_id, serial, serial_key, purchase_year,
                            price_cents, status, assigned_to, location_id, notes)
        VALUES (:name, :category_id, :serial, :serial_key, :purchase_year,
                :price_cents, :status, :assigned_to, :location_id, :notes)
        """, values,
    )
    return cursor.lastrowid


def get_asset(path, asset_id):
    with connect(path) as connection:
        asset = connection.execute(ASSET_QUERY + " WHERE a.id = ?", (asset_id,)).fetchone()
    if asset is None:
        raise AssetNotFound("This asset no longer exists. Refresh the inventory.")
    return asset


def update_asset(path, asset_id, form):
    values = validate_asset(form)
    values["id"] = asset_id
    try:
        with connect(path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            values = resolve_relationships(connection, values)
            cursor = connection.execute(
                """
                UPDATE assets SET name = :name, category_id = :category_id, serial = :serial,
                    serial_key = :serial_key, purchase_year = :purchase_year,
                    price_cents = :price_cents, status = :status, assigned_to = :assigned_to,
                    location_id = :location_id, notes = :notes, updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
                """,
                values,
            )
            if not cursor.rowcount:
                raise AssetNotFound("This asset no longer exists. Refresh the inventory.")
    except sqlite3.IntegrityError as error:
        handle_integrity(error)


def handle_integrity(error):
    if "assets.serial_key" in str(error):
        raise ValidationError("That serial number is already registered.") from error
    raise error


def delete_asset(path, asset_id):
    with connect(path) as connection:
        cursor = connection.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        if not cursor.rowcount:
            raise AssetNotFound("This asset no longer exists. Refresh the inventory.")


def list_assets(path, search="", category="", status="", year=""):
    """Add only fixed SQL clauses and bind all filter values separately."""
    conditions = []
    parameters = []
    search = search.strip().casefold()
    if search:
        conditions.append("""
            (instr(printf('it-%06d', a.id), ?) > 0 OR
             CAST(a.id AS TEXT) = ? OR
             instr(casefold(a.name), ?) > 0 OR instr(coalesce(a.serial_key, ''), ?) > 0)
        """)
        parameters.extend([search] * 4)
    for clause, value in (
        ("c.name = ?", category),
        ("a.status = ?", status),
        ("a.purchase_year = ?", year),
    ):
        if value != "":
            conditions.append(clause)
            parameters.append(value)
    query = ASSET_QUERY
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    with connect(path) as connection:
        return connection.execute(query + " ORDER BY a.id DESC", parameters).fetchall()


def purchase_years(path):
    with connect(path) as connection:
        rows = connection.execute("SELECT DISTINCT purchase_year FROM assets ORDER BY purchase_year DESC")
        return [row[0] for row in rows]


def category_names(path):
    with connect(path, read_only=True) as connection:
        return tuple(row[0] for row in connection.execute("SELECT name FROM categories ORDER BY id"))


def location_names(path):
    with connect(path, read_only=True) as connection:
        return tuple(row[0] for row in connection.execute("SELECT name FROM locations ORDER BY name COLLATE NOCASE, id"))

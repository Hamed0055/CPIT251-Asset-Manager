# Database schema v2

`PRAGMA user_version = 2`. Exactly three application tables use SQLite STRICT
(requires SQLite 3.37+). `sqlite_sequence` is SQLite's AUTOINCREMENT metadata,
not a fourth application table. No people, report or operational-status table
has been introduced. [Editable ERD](diagrams/inventory-v2.drawio) and
[high-resolution PNG](diagrams/inventory-v2.png) describe the actual schema.

## categories

| Column | Storage / constraint |
| --- | --- |
| id | INTEGER PRIMARY KEY |
| name | TEXT NOT NULL UNIQUE; CHECK against the configured category names |

Seeded in `config.CATEGORIES` order: Desktop PC, Laptop, Router, Switch,
Peripheral, Other. Every asset belongs to exactly one category. A category can
have zero or many assets. Valid existing databases are checked, not reseeded.

## locations

| Column | Storage / constraint |
| --- | --- |
| id | INTEGER PRIMARY KEY |
| name | TEXT NOT NULL UNIQUE COLLATE NOCASE; 1-120 characters, no outer spaces |

Location identity in the application is `name.strip().casefold()` (Unicode).
The first stripped spelling is retained for display. `Library`, ` library `
and `LIBRARY` resolve to one ID. Empty input becomes a NULL foreign key, with
no artificial Unknown record. Unused locations remain available for selection.
SQLite's built-in NOCASE uniqueness protects ASCII case differences. Full
Unicode equivalence is enforced by the shared resolver under a writer lock,
and checked on database opening. External editors must respect this rule;
NOCASE alone does not fold every Unicode character.

## assets

| Column | Storage / constraint |
| --- | --- |
| id | INTEGER PRIMARY KEY AUTOINCREMENT; displayed as IT-000001, deleted IDs not reused |
| name | TEXT NOT NULL; 1-120 characters after SQL trimming |
| category_id | INTEGER NOT NULL REFERENCES categories(id) ON DELETE RESTRICT |
| location_id | INTEGER NULL REFERENCES locations(id) ON DELETE RESTRICT |
| serial | TEXT or NULL; supplied display serial has 1-100 trimmed characters |
| serial_key | TEXT or NULL UNIQUE; NULL iff serial is NULL; Python trimmed/casefolded identity |
| purchase_year | INTEGER NOT NULL; schema 1900-9999, application additionally checks current year |
| price_cents | INTEGER or NULL; 0-99,999,999,999 hundredths of SAR, never floating point |
| status | TEXT NOT NULL; Available, Assigned, Under Maintenance, Retired |
| assigned_to | TEXT NOT NULL default ''; maximum 120 characters |
| notes | TEXT NOT NULL default ''; maximum 4,000 characters |
| created_at | TEXT NOT NULL default CURRENT_TIMESTAMP (UTC) |
| updated_at | TEXT NOT NULL default CURRENT_TIMESTAMP (UTC), updated when edited |

Both foreign keys restrict deletion of a referenced lookup row. Each location
can contain zero or many assets, while each asset has zero or one location.
Indexes cover `category_id`, `location_id`, `status` and `purchase_year`.
`serial_key` has its UNIQUE index. Operational totals are calculated from status
using the established rules, not stored redundantly.

## Queries and enforcement

Every application connection, including read-only and backup connections,
executes and verifies `PRAGMA foreign_keys = ON` before any transaction.
Every form/filter value is a bound parameter. The shared read projection is:

```sql
SELECT a.id, a.name, c.name AS category, a.serial, a.serial_key,
       a.purchase_year, a.price_cents, a.status, a.assigned_to,
       coalesce(l.name, '') AS location, a.notes, a.created_at, a.updated_at
FROM assets AS a
JOIN categories AS c ON a.category_id = c.id
LEFT JOIN locations AS l ON a.location_id = l.id
ORDER BY a.id DESC;
```

The service returns readable names with the same row fields used in v1. Filters
use `c.name`, `a.status` and `a.purchase_year`. Reports consume this joined
snapshot; the optional `report_from_database` adapter shares the same query and
report logic. Search still uses literal Unicode-casefolded substrings in ID,
name and serial, not SQL wildcard interpretation.

## Migration from v1

Version 1 stored category and location as repeated text in `assets`.
`initialize(path)` reserves the writer with BEGIN IMMEDIATE, validates the file,
and makes a verified SQLite backup using a separate read-only connection before
DDL. It creates the lookups, seeds the six configured categories, deduplicates
nonempty locations, renames the legacy assets table and copies records to the
relational assets table with bound values. It preserves original IDs, serials,
serial keys, exact integer prices, years, status, assignment, notes and both
timestamps. The AUTOINCREMENT high-water mark, including deleted IDs, survives.

Counts, structure, quick integrity and foreign keys are checked before setting
user_version to 2 and committing. Any failure rolls back the schema and records;
the verified v1 backup remains. The code never uses executescript during the
migration (it could commit prematurely) and never disables foreign keys.
Unsupported versions, foreign schemas and v1 databases with custom views or
triggers are rejected without replacement. Such customizations need review
before rebuilding a table. Valid v2 databases reopen without mutation.

## Backup and recovery

**About > Back up database** creates a new consistent, verified copy. Existing
files cannot be overwritten. Both valid v1 and v2 can be backed up without
changing their version. An automatic migration backup is beside the database:
`inventory.pre-v2-<UTC timestamp>-<unique suffix>.sqlite3`.

To investigate a backup, COPY it to a new filename first, then open that copy
with `./linux.sh --database /absolute/path/to/copy.sqlite3`. Opening a v1 copy
with v2 deliberately migrates that copy and creates another backup. To verify a
backup without migration, inspect it in SQLite/DBeaver read-only.

To recover the pre-upgrade application and database:

1. Close ALL app instances, including older Desktop launchers and executables.
2. Keep the current database and any `-wal` / `-shm` / `-journal` sidecars
   together in a separate recovery folder. Do not replace a live SQLite file.
3. Restore a COPY of the verified pre-v2 database to its original path.
4. Use the pre-v2 source/executable/launcher from the full project backup to
   remain on v1. Version 1 applications cannot open a v2 database. Launching
   v2 again migrates the restored copy again.
5. Verify integrity and known asset IDs/counts. Keep all original backups.

The exact runtime path is shown in About. Defaults are
`$XDG_DATA_HOME/cpit251-asset-manager-reference/inventory.sqlite3` (or
`~/.local/share/...`) on Linux and
`%LOCALAPPDATA%\CPIT251-Asset-Manager-Reference\inventory.sqlite3` on Windows.
The optional --database argument overrides the default; no absolute user path
is hardcoded in application code.

## Verify with DBeaver

Prefer a backup copy; use the SQLite driver and choose the actual file shown in
About. Expand Tables to see assets, categories and locations. Refresh metadata
after migration; open a table and use its Diagram tab to inspect the links
([official DBeaver diagram guide](https://dbeaver.com/docs/dbeaver/ER-Diagrams/)).
Run these in the same SQL editor connection (foreign-key enforcement is per
connection, and cannot be enabled inside an already-open transaction):

```sql
PRAGMA foreign_keys = ON;
PRAGMA foreign_keys;             -- 1
PRAGMA user_version;             -- 2
PRAGMA integrity_check;          -- ok
PRAGMA foreign_key_list(assets); -- categories/category_id and locations/location_id, RESTRICT
PRAGMA foreign_key_check;        -- zero rows
SELECT name FROM sqlite_schema
WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name;
SELECT c.name, count(a.id) AS assets
FROM categories c LEFT JOIN assets a ON a.category_id = c.id
GROUP BY c.id, c.name ORDER BY c.id;
SELECT l.name, count(a.id) AS assets
FROM locations l LEFT JOIN assets a ON a.location_id = l.id
GROUP BY l.id, l.name ORDER BY l.name;
SELECT a.id, a.name, c.name AS category, l.name AS location
FROM assets a JOIN categories c ON c.id = a.category_id
LEFT JOIN locations l ON l.id = a.location_id ORDER BY a.id;
```

Direct edits bypass form rules (current year, Unicode serial/location identity).
Use the app for edits. Test invalid foreign keys or restricted deletes only in a
disposable copy and roll back your test transaction.

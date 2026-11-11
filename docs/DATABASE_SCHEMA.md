# Database schema

The application creates schema version 1 using `PRAGMA user_version`. It
refuses unsupported schema versions and unrelated SQLite files. The
`assets` table is STRICT, which requires SQLite 3.37 or newer.

| Column | Type | Meaning and constraint |
| --- | --- | --- |
| id | INTEGER | Autoincrement primary key. Displayed as IT- followed by at least six digits. Deleted IDs are not reused by normal operations. |
| name | TEXT | Required, 1–120 characters after trimming. |
| category | TEXT | One of the six predefined equipment categories. |
| serial | TEXT or NULL | Optional displayed serial, at most 100 characters. |
| serial_key | TEXT or NULL | Trimmed serial casefolded in Python. Unique when supplied. Multiple NULLs are allowed. |
| purchase_year | INTEGER | 1900–9999 in the schema. The form also rejects years later than the current local year. |
| price_cents | INTEGER or NULL | Optional SAR value in hundredths, up to 99,999,999,999. Zero is a real price. |
| status | TEXT | Available, Assigned, Under Maintenance or Retired. |
| assigned_to | TEXT | Optional person, up to 120 characters. Empty string if absent. |
| location | TEXT | Optional location, up to 120 characters. Empty string if absent. |
| notes | TEXT | Optional multiline notes, up to 4,000 characters. |
| created_at | TEXT | SQLite UTC timestamp when inserted. |
| updated_at | TEXT | UTC timestamp when last saved. |

There are indexes on category, status and purchase year. The unique serial
key has an automatic index, and SQLite maintains its internal
`sqlite_sequence` metadata for autoincrement. Category, location and assigned
person are asset attributes. There are no separate lookup or people tables.

Read and write calls open short-lived connections. The connection manager
commits on success, rolls back on failure, and closes in both cases. All form
and filter values are bound parameters. Example service queries:

```sql
SELECT * FROM assets WHERE id = ?;

SELECT * FROM assets
WHERE category = ? AND status = ? AND purchase_year = ?
ORDER BY id DESC;

DELETE FROM assets WHERE id = ?;
```

The service assembles optional clauses from fixed SQL fragments. Search uses
literal substring matching with casefolded text, so a percent sign is an
ordinary character. Use DBeaver to inspect a demo or backup copy. Direct edits
can bypass the service's serial normalisation and current-year validation.

## Backup and restore

Use **About > Back up database** and choose a new filename. SQLite's backup
API takes a consistent copy while the app is open. The app will not replace an
existing file. Verify the backup by opening a separate copy with
`--database`. To restore, close all instances, keep the current database and
any SQLite sidecar files together in a separate recovery directory, then place
a copy of the verified backup at the original database path. Reopen and check
a known record. If the current database still has active handles or leftover
sidecars you do not understand, inspect the backup separately instead.

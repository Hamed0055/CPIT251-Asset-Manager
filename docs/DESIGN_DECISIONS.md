# Design decisions and limits

- **Independent reference.** The original project is a read-only reference.
  This project has its own code, output folder and default database.
- **One local operator.** One table, short-lived SQLite connections and a
  straightforward GUI keep the CRUD path easy to trace. Concurrent users,
  authentication, audit history, and schema migrations are outside this scope.
  Multiple instances can contend for the database and last-write-wins edits
  are possible. Work with one active instance for an inventory.
- **ID and serial.** SQLite generates stable numeric IDs. The UI formats them
  as IT-000001. Serial is optional, with Unicode casefolded uniqueness after
  trimming. Serial display casing is kept. The operator can register assets
  without knowing their serials.
- **Dates and price.** Equipment age is the current calendar year minus the
  purchase year. There is no month-level age because only the year is captured.
  Price is optional in SAR and stored exactly in hundredths.
- **Status and repair.** Available and Assigned are operational. Under
  Maintenance and Retired are non-operational. As required, every
  non-operational item is listed as Repair priority irrespective of age.
  A retired record is an exception to review in real operations, where it may
  be disposed of rather than repaired. The app does not alter its status
  based on the report.
- **Age categories.** New is 0–2 years, Standard 3–4, Aging 5–6, and
  Replacement recommended 7+. Operational equipment aged 5–6 is flagged for
  maintenance review, and at 7+ for replacement review. Non-operational rows
  take repair priority over those age recommendations.
- **Search and reporting scale.** Substring matching can scan the local
  inventory. The reports summarise a snapshot in memory. This is suitable for
  a small coursework inventory. Large installations may benefit from pagination
  and different search indexes.
- **CSV safety.** CSV uses UTF-8 with a BOM for spreadsheet compatibility.
  Text beginning with formula characters, including after whitespace, gets an
  apostrophe prefix. This changes the export representation, while leaving the
  stored asset name untouched. An export or backup requires a new filename.
- **Packaging.** One-file executables trade a short extraction step for simple
  distribution. The generated database lives under the current user's data
  root. There is no shared database, installer, or application signing.

- **CSV import is additive.** Keep schema version 1 and reuse manual-entry
  validation plus a shared non-committing insert helper. Confirmed rows commit
  in one transaction; serial collisions are skipped, all other unexpected
  failures roll back. Serial-less assets cannot be reliably deduplicated.
- **Report compatibility.** Detailed legacy reports contain enough required
  fields to import, with explicit warnings about absent optional fields.
  Aggregate summaries cannot reconstruct assets. Add a separate full inventory
  exporter instead of changing the meaning of the existing report exporter.
- **Preview and concurrency.** Hold an immutable file snapshot, not a pending
  transaction, while the operator decides. Reload serials inside the confirmed
  write transaction. Expected counts may change if another app adds a serial.
- **Scale.** CSV parsing/insertion runs off the GUI thread, but accepted records
  and issue details are retained in memory for preview/confirmation. The tested
  moderate scale is 1,000 rows. This is not an unbounded streaming ETL service.
- **Portability.** Standard-library CSV, pathlib, SQLite, threading/queue and
  Tkinter add no third-party runtime dependency. Linux is verified locally;
  Windows native builds and GUI smoke now pass on Server 2022 and Windows 11;
  Windows 10 still needs its own runtime check.

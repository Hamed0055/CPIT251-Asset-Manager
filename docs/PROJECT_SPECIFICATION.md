# CPIT251 project specification

An offline, single-user IT asset register. The actor is an inventory operator
using a local Windows or Linux desktop. Source runs on Python 3.11+ with
Tkinter/ttk and SQLite. Packaging uses Python 3.14 and PyInstaller.

| Requirement | Design | Acceptance evidence |
| --- | --- | --- |
| Register, inspect, edit, delete | Inventory table and validated modal forms, database-generated ID, confirmation before deletion | Service tests and GUI workflow |
| Search and filter | ID, name and serial substring search, combined with exact category, status and year filters | Asset and GUI tests |
| Dashboard and reports | Counts by category/status and operating condition, age and maintenance queues, CSV for each report | Report and GUI tests |
| Durable and recoverable data | OS-specific per-user file, SQLite constraints, consistent backup, isolated demonstration database | Database and GUI restart tests |
| Linux distribution | Source launcher and PyInstaller build | Actual launcher and packaged smoke run |
| Windows distribution | Native PyInstaller build and GUI smoke on Windows CI | Native run required, with remaining checks recorded in Test Plan |
| Learning handoff | File map, SQL examples, diagrams and study order | Developer and user guides |

Asset name, category, status and purchase year are required. Serial number,
price, person, location and notes are optional. Reports calculate calendar-year
age and give non-operational equipment repair priority. The app has no network
runtime, accounts, audit log, or background service.

## Incremental CSV enhancement (2026-11-11)

| Requirement | Design | Acceptance evidence |
| --- | --- | --- |
| Import assets safely | Native chooser, counts/records/errors preview, explicit valid-only confirmation | CSV GUI integration and smoke |
| Complete CSV interchange | Full inventory export; accept legacy detailed reports with missing-field warnings | Full-field roundtrip tests |
| Preserve existing data | Skip serial duplicates, regenerate IDs, no updates or deletes, atomic batch rollback | Duplicate, preservation, concurrency and rollback tests |
| Responsive interface | Worker backend plus queue/after main-thread Tk updates | Delayed-worker GUI timer and close protection checks |
| Demonstration | 50 fictional assets and mixed-invalid CSV | Sample-file automated test and walkthrough |

CSV extends the existing one-table design without migrations. See CSV_IMPORT.md
and the additional class, screen-flow and DFD diagrams in ARCHITECTURE.md.

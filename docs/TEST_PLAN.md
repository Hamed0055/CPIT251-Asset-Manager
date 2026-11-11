# Test plan and execution record

Test data is fictional or generated with pytest's temporary directory fixtures.
The GUI smoke mode overrides the OS user-data root inside its process and
cleans up the disposable inventory after testing.

## Executed on CachyOS (CSV enhancement, 2026-11-11)

| Check | Result |
| --- | --- |
| `python3 -m pytest -q` | 104 passed (including native CSV GUI integration) with Python 3.14.9, SQLite 3.54.0 and pytest 9.2.0 |
| Ruff on Python source, tests and demo script | Passed |
| POSIX syntax, ShellCheck and shfmt | Passed for both Linux scripts |
| Launcher with a missing interpreter | Exited nonzero and explained the Python requirement |
| Source GUI smoke | Passed on Tk 8.6 under Plasma's Xwayland session |
| Linux PyInstaller 6.22.2 build | Succeeded for x86-64 |
| Frozen Linux GUI smoke | Passed, with `frozen: true` in its receipt |
| GitHub workflow static validation | Passed actionlint 1.7.11 |
| Independent project verification | Tracked files and working-tree status matched the pre-task snapshot |

The pytest suite covers initialization and schema guards, rollback, backups,
platform data path selection, CRUD, serial uniqueness, invalid form values,
case-insensitive literal search, combined filters, age boundaries, repair
priority, grouped counts and CSV output including spreadsheet formula safety.

The Linux GUI smoke executes widget actions at the 780×520 minimum geometry.
It checks creation in a platform-style user directory, validation with form
retention, duplicate serial rejection, add, search, filters, details, edit,
report export, backup, deletion cancellation, persistence after recreating the
window, and confirmed deletion. Save, error, and confirmation dialog responses
are controlled by the smoke harness so it runs without operator input. The
Linux executable is also exercised from outside the source folder.

## Windows gate still to run

The native .exe has not been built or run in this delivery. The local VM was
not used for this enhancement and was left untouched. No remote
repository or CI run was created. Static workflow validation does not certify
a Windows build.

1. On a Windows runner or a Windows 10/11 desktop, install Python 3.14 x64
   with Tk and use the development dependencies listed in the developer guide.
2. Run the backend tests and `./scripts/build_windows.ps1 -SmokeTest`. On
   GitHub, use the included workflow and download the artifact only after a
   passing run.
3. Confirm that `windows-smoke.json` says passed, frozen and win32. The smoke
   requires the real frozen GUI to open and its SQLite data to persist in an
   isolated LocalAppData-equivalent location.
4. On Windows 10 and 11, double-click the .exe in an account without Python.
   Check the actual path in About, register a fictional asset, search and edit
   it, close and reopen, cancel one deletion and confirm a second. Export and
   inspect a CSV and open a backup copy. Check that the dialog fits a common
   desktop resolution. Record the OS version and observed result.

The Linux one-file executable was tested on this host. Compatibility with
older glibc versions or other Linux architectures requires a suitable native
build or use of the source launcher.


## CSV acceptance matrix

All cases below use temporary databases/files. No production database was opened.
The original 51 regression tests passed before editing; the expanded suite has
104 passing cases with native desktop access. In the restricted shell the same
run reports 103 passed and one explicit display-dependent skip; that run alone
is not counted as GUI acceptance.

| Requested case | Evidence in `tests/test_csv_import.py` or GUI workflow |
| --- | --- |
| 1. One valid asset | `test_single_preview_is_read_only_and_ids_regenerated` |
| 2. Multiple assets | `test_many` (2, 50, 1000) |
| 3. Export/reimport | `test_inventory_export_roundtrip`, both legacy detailed reports |
| 4. UTF-8 BOM | Four encoding/newline variants |
| 5. Quoted commas | Unicode, quoted name and multiline notes roundtrip |
| 6. Missing required columns | Parameterized header rejection |
| 7. Duplicate/malformed headers | Duplicate, trimmed duplicate, empty, unknown, wrong-case headers |
| 8. Empty file | UTF-8 BOM empty file rejection |
| 9. Header-only file | Zero-record preview and result |
| 10. Invalid years | Empty, nonnumeric, decimal, too old, future |
| 11. Invalid numeric fields | Negative, NaN, extra precision, grouped and excessive price |
| 12. Empty required fields | Name/category/status and year validation |
| 13. Stored duplicate serial | Existing row comparison and preserved timestamps/data |
| 14. In-file duplicate serial | Case/whitespace equivalence; invalid-first row does not reserve serial |
| 15. Rollback | Injected second-insert failure, real SQLite trigger constraint, GUI failure/retry |
| 16. Cancellation | Read-only prepared snapshot plus native chooser/preview Cancel callbacks |
| 17. Existing records preserved | Full dictionary comparison; no updates or deletes |
| 18. Accurate counts | Preview/final equations, skipped errors, duplicate inserted after preview |
| 19. 1000 rows | Entire valid batch stored with only ten preview rows retained for display |

Additional checks cover fatal UTF-8/parser failures, wrong field counts, physical
row numbers for multiline fields, missing/permission-denied files, no database
creation during preview, changed-file snapshot semantics, wrong-inventory
rejection, spreadsheet escaping/literal apostrophes, serial leading zeros and
the shipped demonstration files.

`test_gui_csv_workflow` calls the shared native smoke workflow. It exercises
visible Import/Export controls at 780x520, filechooser cancellation, first-row
preview/errors, preview cancellation, delayed worker + live Tk timer, close
protection, real database error + rollback + retry, final counts, dashboard and
filter/report refresh, full inventory export, disabled all-duplicate preview,
malformed-file recovery, and persistence through new database connections.
Unhandled Tk callbacks are collected and treated as failures. Source smoke logs
were also checked for stderr warnings after fixing Tk cleanup.

The 50-record preview was visually inspected at 940x690 and minimum 740x580;
button height is reserved so shrinking affects the scrollable panes. Horizontal
scrollbars expose every column and vertical scrollbars expose all preview rows
and errors. Sample-data category/status combinations were checked by pytest.

Windows acceptance still requires a native build and execution; no Linux test
is presented as proof of Windows runtime behavior. Add the CSV sample import,
preview/cancel, results, export roundtrip and malformed-file flow to the manual
Windows 10/11 procedure above. `--smoke-test` now includes these core CSV
callbacks in both source and frozen builds, and the existing Windows build
script/CI gate invokes it without requiring new flags or dependencies.

## Delivery evidence

The deployed reference project and rebuilt executable were rechecked after
copying: **104 passed**, source and frozen GUI smoke passed with empty logs.
See `evidence/csv-linux-validation.json`, `evidence/csv-linux-pytest.txt` and
the two `evidence/csv-linux-{source,frozen}.json` receipts. The validation JSON
records the exact binary checksum and the verified pre-change backup path.

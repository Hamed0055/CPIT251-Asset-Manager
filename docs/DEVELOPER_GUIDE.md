# Developer and learning guide

## Learn by tracing one workflow

1. **Dictionaries and conversion.** Read `validate_asset`. Trace how an empty
   price becomes None and a decimal price becomes an integer. Try a boundary
   year, then explain why the same serial with different case is rejected.
2. **SQL and transactions.** Read `initialize` and `connect`. Create a
   disposable database, inspect its constraints, and run a SELECT with a bound
   ID. Observe how a failed update rolls back.
3. **Functions, exceptions and data flow.** Trace Add from the form through
   `add_asset` and back to the Tk table. Follow how a duplicate serial becomes
   a user-facing validation error. Repeat for edit, retrieval, and delete.
4. **Events and widget state.** Trace a search button and a category selection.
   Both read Tk variables and rebuild the Treeview. Check how row selection
   enables the Details, Edit and Delete buttons.
5. **Lists, counting and file output.** Trace `report_table` and
   `export_csv`. Hand-calculate the expected report for the demo, then compare.
   Explain why the maintenance queue checks status before age.
6. **Tests and packaging.** Add a boundary test using `tmp_path`, then run the
   native build and its separate disposable smoke test.

Use PyCharm's existing Python interpreter and set this folder as the working
directory. Python 3.11+ with Tkinter and SQLite 3.37+ runs the source. The
packaging baseline uses Python 3.14 and PyInstaller 6.22.2.

## Install build tools without changing system Python

On Linux, use an explicit temporary target for tooling:

```sh
tool_dir=$(mktemp -d)
python3 -m pip install --target "$tool_dir" -r requirements-dev.txt
PYTHONPATH="$tool_dir" python3 -m pytest -q
PYTHONPATH="$tool_dir" ./scripts/build_linux.sh
```

This target is required only for development tools. No virtual environment is
needed to run the app. Installing dependencies for the build needs network
access or a prepared local wheel cache. The built app works offline.

On Windows PowerShell:

```powershell
$ToolDir = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString())
python -m pip install --target $ToolDir -r requirements-dev.txt
$env:PYTHONPATH = $ToolDir
python -m pytest -q
./scripts/build_windows.ps1 -SmokeTest
Remove-Item Env:PYTHONPATH
```

Each native script writes generated outputs under `build/` and `dist/`.
Rebuilding replaces the generated executable. The application database lives
elsewhere. Pinning the packaging tool gives a repeatable procedure. Binary
hashes can differ with host libraries, Python patch versions or build tools.

PyInstaller packages the interpreter and Tk runtime into one executable. It
extracts bundled libraries temporarily, then resolves the database via
`config.py`. Build the Windows executable on Windows. The Linux build is
glibc-dependent. See the
[PyInstaller manual](https://pyinstaller.org/en/v6.22.2/) for platform details.

## Test and demo commands

```sh
python3 -m pytest -q
./scripts/run_linux.sh --smoke-test /tmp/cpit251-source-smoke.json
./dist/CPIT251-Asset-Manager --smoke-test /tmp/cpit251-frozen-smoke.json
PYTHONPATH=. python3 scripts/create_demo.py ./new-demo.sqlite3
```

The smoke mode opens the real Tk windows and uses a disposable OS user-data
root. It substitutes predictable responses for modal confirmation, error, and
save dialogs. The workflow checks the actual storage and callback results.
Use a live graphical session. Windows CI invokes the equivalent test on the
frozen Windows executable and uploads the receipt only after success.

## Trace CSV import

Read `reports.ASSET_COLUMNS` for the explicit exported-header mapping, then
`csv_import.prepare_import`. It uses `csv.reader(strict=True)` with UTF-8/BOM,
validates every row with the existing validator, checks serials with the same
casefold rules, and returns frozen dataclasses. This function does no writes.

`import_prepared` opens one `BEGIN IMMEDIATE` transaction, revalidates the frozen
records and reloads serial keys under that write lock. All inserts use the same
`asset_service.insert_validated_asset` helper as manual registration. It never
calls `add_asset` repeatedly, which would commit individual records. Any
unexpected exception propagates out of `connect`, rolling back the entire batch.
Only serial duplicates are deliberately skipped; unrelated constraints/errors
are not silently swallowed. Success returns after the commit completes.

Trace `InventoryApp.import_csv` -> `run_csv_job` -> `ImportPreviewDialog.confirm`
-> `show_result`. The worker only runs backend functions and puts Python values
on a queue; the main Tk thread polls with `after`. The original file is not read
a second time on confirmation. This prevents an edited file bypassing preview.

The normal pytest command includes `tests/test_gui_csv.py`, which needs a real
graphical display. It explicitly skips without one. Backend tests still run,
but a skipped GUI test is **not** GUI acceptance. Use the source and frozen
smoke commands above on a native desktop to verify callback wiring and packaging.
The smoke checks use isolated temporary inventories, including its injected
SQLite trigger failure. They never open a production inventory.

All imports are statically discoverable by PyInstaller (`gui` imports
`csv_import`, which uses only standard-library modules and existing project
modules). No extra runtime package, data file or hidden-import flag is needed.
The samples are ordinary external files selected by the operator, not bundled
resources. The same frozen smoke exercises CSV on Windows when built there.

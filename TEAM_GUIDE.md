# CPIT251 team handoff

## What is included

The v2 reference application, CSV import/export, automatic v1 database migration, tests,
editable architecture diagrams, manuals, build scripts and fictional demos.
This is source code: Python is required. There are no third-party runtime
packages. `requirements-dev.txt` contains optional test/build tools only.
Git history, generated binaries, caches, personal inventories and local backup
paths are excluded. `examples/demo.sqlite3` contains fictional equipment only.

## Quick start: Windows 10/11

1. Extract the entire ZIP into a writable folder. Open that folder in your editor.
2. Install Python 3.11+ with Tcl/Tk (Python 3.14 is the tested Linux baseline).
3. Open PowerShell in the extracted project folder and run:

```powershell
python -c "import sys, tkinter, sqlite3; assert sys.version_info >= (3,11); assert sqlite3.sqlite_version_info >= (3,37); print('Dependencies OK')"
python main.py --database .\local-data\inventory.sqlite3
```

If `python` is unavailable but the Python launcher is installed, use `py -3`
instead of `python`. No database setup command is needed; the app creates it.
Use the v2 source checkout or build a new executable to open a migrated
inventory. The Windows Server 2022 and Windows 11 QEMU results in the test plan
were recorded for v1.0.1.

## Quick start: Linux

Use Python 3.11+ with Tk and SQLite 3.37+. Arch/CachyOS needs `python` and `tk`;
Debian/Ubuntu needs `python3` and `python3-tk`. From the extracted folder:

```sh
python3 main.py --database ./local-data/inventory.sqlite3
```

The existing `sh scripts/run_linux.sh --database ./local-data/inventory.sqlite3`
launcher also checks dependencies. No shell-specific syntax is required to run
Python directly, so this works from Bash or fish.

## Development and tests

Create an isolated development environment; do not modify system Python:

Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python main.py --smoke-test ./source-smoke.json
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe main.py --smoke-test .\source-smoke.json
```

Use a graphical desktop for the GUI test. Without display access pytest reports
an explicit GUI skip; that does not certify the UI. The smoke mode creates its
own disposable database and never opens the normal inventory. See docs/TEST_PLAN.md for v2 checks and earlier release evidence. Internet is needed to install
development tools unless already cached; running the app itself works offline.

## Suggested division of work

| Area | Files | Responsibility |
| --- | --- | --- |
| Validation and storage | src/validation.py, src/database.py, src/asset_service.py | Shared rules, parameterized SQL, constraints and transactions |
| GUI | src/gui.py | Forms, filters, preview/results and main-thread Tk updates |
| CSV and reports | src/csv_import.py, src/reports.py | Parsing, duplicates, export and report calculations |
| QA and report | tests/, src/smoke.py, docs/ | Regression tests, acceptance evidence and report diagrams |

Choose an owner per area and coordinate before editing shared files. Use the
existing schema and validator; avoid implementing different rules in the GUI.
Read README.md, docs/ARCHITECTURE.md and docs/DEVELOPER_GUIDE.md first.

## Collaboration workflow

1. The private team repository is https://github.com/Hamed0055/CPIT251-Asset-Manager.
   Accept the owner's collaborator invitation, then clone it with GitHub Desktop
   or `git clone https://github.com/Hamed0055/CPIT251-Asset-Manager.git`.
   A downloaded ZIP contains no Git metadata; clone when contributing changes.
2. Each member clones that repository, creates a feature branch and uses their
   own local database. Commit code/tests/docs together in small changes.
3. Run pytest and the source GUI smoke before review; attach the real results.
   Ask another member to review validation, rollback behavior and UI changes.
4. Merge reviewed changes through your team's chosen process. Configure remote
   hosting and permissions yourselves; this package publishes nothing.
5. Keep `.venv`, build/dist output, real CSV data and local databases out of Git.
   The supplied .gitignore excludes SQLite files except the fictional demo.
   Do not edit the demo database in place; work in `local-data/` instead.

SQLite is a local, single-operator database. Team collaboration means sharing
code, not simultaneously editing one database on a network/cloud/synced folder.
Use fictional CSVs to exchange test cases. The app has no authentication or
multi-user server.

## Five-minute presentation

1. Launch with a new local database using the commands above.
2. Inventory > Import CSV > examples/sample_inventory_50.csv.
3. Show 50 valid rows and Cancel once; reopen and Import Valid Records.
4. Show inventory, dashboard totals, filters and reports.
5. Export from Inventory, then reimport into the same database: serials are
   duplicates and existing records are protected.
6. Preview examples/invalid_inventory.csv to show row-specific errors.

See docs/CSV_IMPORT.md for exact counts and full format rules. Serial-less
records cannot be deduplicated, so repeated imports can add them again.

## Verify the handoff

`SHARE_INFO.json` identifies the source revision. `MANIFEST.sha256` contains a
checksum for each tracked file other than the manifest itself.
Build generated outputs on the target OS.

## Single-file Linux release

Build the v2 single-file launcher with
`python3 scripts/build_linux_sh.py --output dist/linux.sh`, then run
`sh dist/linux.sh`. The generated script includes the application.
Python/Tk/SQLite are still system prerequisites. See docs/LINUX_LAUNCHER.md.
Use a clone and feature branches when developing, rather than editing the
generated standalone script.

## Portable Windows release

For historical v1.0.1 use, download `CPIT251-Asset-Manager-Windows-x64.zip` from
that release and extract
the whole archive, then open `CPIT251-Asset-Manager.exe` or `windows.bat`.
The executable bundles Python/Tk. Keep the batch launcher beside the executable.
Native Windows tests passed (106 cases, with eight Linux-only skips); both the
EXE and batch launcher passed the frozen GUI workflow in Windows 11 QEMU.
For v2, use the [Windows build instructions](docs/WINDOWS_LAUNCHER.md).

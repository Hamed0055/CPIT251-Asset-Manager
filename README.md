# CPIT251 IT Asset Inventory Manager

An offline Python, Tkinter and SQLite reference implementation for CPIT251
Software Engineering I.

**Team members: start with [TEAM_GUIDE.md](TEAM_GUIDE.md).** This source-only
package includes code, tests, manuals and fictional demonstration data. Each
member should extract a separate copy and use their own local database.

## Download the Linux launcher

The [v1.0.0 release](https://github.com/Hamed0055/CPIT251-Asset-Manager/releases/tag/v1.0.0)
provides a self-contained **linux.sh** asset. Download it and run `sh linux.sh`.
It works offline after download and requires Python 3.11+, Tk and SQLite 3.37+.
See the [Linux launcher guide](docs/LINUX_LAUNCHER.md) for data paths, arguments,
verification and the distinction between the release asset and source launcher.

## Run on Linux

From this directory:

```sh
sh linux.sh
```

Source use requires Python 3.11+, Tkinter and the Python sqlite3 module backed by
SQLite 3.37+. Arch/CachyOS supplies Tk through the `tk` package. Debian/Ubuntu
supplies Tkinter through `python3-tk`. The launcher checks these requirements.
There are no third-party runtime Python packages.

Generated executables are excluded from this source-only package. Run the
source, or follow `docs/DEVELOPER_GUIDE.md` to build a native executable.
A Linux binary was tested before this handoff; Windows still requires a native
build and runtime check. The source launcher uses the system Python.

## Run on Windows

For source use, install the official Python distribution with the Tcl/Tk
component, then run `python main.py` in PowerShell. For the standalone
`CPIT251-Asset-Manager.exe`, build on Windows with
`./scripts/build_windows.ps1 -SmokeTest` after installing the development
dependencies. Alternatively, run **Build and verify Windows executable** under
Actions in an authorized reference repository and download the
`CPIT251-Asset-Manager-Windows-x64` artifact. Extract it and open the executable.
A successful CI artifact includes `windows-smoke.json`. The frozen executable
bundles Python. See the [test plan](docs/TEST_PLAN.md) for Windows build status.

## Data and demo

Your production database is created on first launch. **About** shows its exact
path and provides a backup button. To demo with fictional equipment, copy the
example to a new file and open the copy:

```sh
cp -n examples/demo.sqlite3 ./demo-working.sqlite3
./scripts/run_linux.sh --database ./demo-working.sqlite3
```

Use a different filename if you already have a working copy. On Windows, use
`Copy-Item examples/demo.sqlite3 demo-working.sqlite3` with a new destination
name, then run `python main.py --database demo-working.sqlite3` or pass the same
arguments to the executable from PowerShell. The database override is explicit
and optional. Normal use never opens the shipped demo.

## Project files and study order

| File or directory | Purpose |
| --- | --- |
| `main.py`, `config.py` | Startup, defaults and OS-specific data path |
| `src/validation.py`, `src/asset_service.py` | Input conversion, CRUD, search and filtering |
| `src/database.py`, `src/reports.py` | Schema, connection lifecycle, backup, reporting and CSV |
| `src/gui.py`, `src/smoke.py`, `src/__init__.py` | Tk interface, isolated GUI test and package marker |
| `tests/conftest.py`, `tests/test_{database,assets,validation,reports}.py` | Temporary DB fixtures and pytest cases |
| `scripts/run_linux.sh`, `scripts/build_linux.sh`, `scripts/build_windows.ps1` | Source launcher and native build scripts |
| `scripts/create_demo.py`, `examples/demo.sqlite3` | Fictional demo generator and database |
| `requirements-dev.txt`, `pytest.ini`, `.gitignore` | Build/test dependencies, test settings and ignored outputs |
| `.github/workflows/build-windows.yml` | On-demand Windows build and smoke gate |
| `TEAM_GUIDE.md`, `MANIFEST.sha256`, `SHARE_INFO.json` | Team setup, file checksums and source revision |
| `docs/` | Specifications, diagrams, manuals and test evidence below |

1. Read the [specification](docs/PROJECT_SPECIFICATION.md) and try the demo with
   the [user guide](docs/USER_GUIDE.md).
2. Study validation and [the database schema](docs/DATABASE_SCHEMA.md).
3. Trace the service and one Tk callback using the
   [architecture and diagrams](docs/ARCHITECTURE.md).
4. Run the tests, then study the report rules and packaging in the
   [developer guide](docs/DEVELOPER_GUIDE.md).
5. Review the [test evidence](docs/TEST_PLAN.md) and
   [design tradeoffs](docs/DESIGN_DECISIONS.md).

Run the backend tests with `python3 -m pytest -q`. Test dependencies are
development-only and pytest uses temporary databases.

## Import and export inventory CSV

Open **Inventory > Import CSV**, select a UTF-8 CSV and review the counts,
first ten records and row errors. Nothing is saved until **Import Valid
Records** is clicked. Duplicates are skipped by serial, never overwritten.
**Inventory > Export CSV** exports all editable fields for a complete roundtrip;
**Reports > Export CSV** retains the original report output.

Try `examples/sample_inventory_50.csv` in a new demo database. A deliberately
mixed-validity file is `examples/invalid_inventory.csv`. Read the
[CSV guide and presentation walkthrough](docs/CSV_IMPORT.md) for headers,
compatibility, error recovery and examples. The new backend is
`src/csv_import.py`; its integration tests are in `tests/test_csv_import.py`
and `tests/test_gui_csv.py`. No schema migration or runtime dependency is needed.

## Team access and sharing

- Repository: https://github.com/Hamed0055/CPIT251-Asset-Manager
- Download source ZIP: https://github.com/Hamed0055/CPIT251-Asset-Manager/archive/refs/heads/main.zip
- Read [TEAM_GUIDE.md](TEAM_GUIDE.md) before contributing.

This repository is private. Invite team members through Settings > Collaborators
> Add people. They must accept the invitation and sign in to open these links.
The ZIP link always downloads the current main branch; use a clone and feature
branches to contribute changes.

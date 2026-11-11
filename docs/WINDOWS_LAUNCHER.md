# Windows portable release

Download the Windows portable ZIP from the private GitHub release, extract the
whole ZIP to a writable folder, then double-click `CPIT251-Asset-Manager.exe`
or `windows.bat`. The executable bundles Python/Tk and does not require a Python
installation. Downloading only `windows.bat` does not include the application;
keep it beside the executable or use it inside a source checkout.

No installer or administrator access is required. Inventory data is stored
under `%LOCALAPPDATA%\CPIT251-Asset-Manager-Reference\inventory.sqlite3`, outside
the release folder. About shows the actual location. Replacing the portable
application does not delete that database.

To use a separate training database, from PowerShell in the extracted folder:

```powershell
.\windows.bat --database ".\local-data\training inventory.sqlite3"
```

In a source checkout, `windows.bat` checks for Python 3.11+, Tkinter and SQLite
3.37+, then starts main.py. An explicit interpreter can be selected with the
PYTHON environment variable. The existing `python main.py` command still works.
The launcher resolves application files relative to its own folder and forwards
arguments without changing the working directory.

## Build and verify on Windows

Install Python with Tcl/Tk, then use the temporary build-tool environment from
docs/DEVELOPER_GUIDE.md and run:

```powershell
python -m pytest -q
.\scripts\build_windows.ps1 -SmokeTest
```

The build produces the executable, portable ZIP, windows.bat and a frozen-GUI
smoke receipt under dist. The on-demand GitHub Windows workflow runs these
checks natively and uploads its outputs only after passing. Linux-side tests
cannot certify Windows execution. The smoke mode uses disposable inventories
and covers GUI, validation, CRUD, persistence, CSV, rollback and backup.

For a repeatable manual check, start with a new training database, import the
50-asset sample CSV, inspect the dashboard, export inventory, close/reopen and
check persistence. The portable executable also accepts `--smoke-test RECEIPT`
for the automated isolated workflow.

This repository is private. Team members must accept a collaborator invitation
and sign in to download release assets.

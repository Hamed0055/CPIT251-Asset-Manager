"""Verify the real Tk widgets and application callbacks with disposable data."""
import csv
import gc
import json
import os
import sys
import tempfile
import threading
import time
from datetime import date
from pathlib import Path
from tkinter import Tk, filedialog, messagebox
from unittest.mock import patch

from config import DATA_FOLDER, database_path
from src import asset_service as assets
from src import csv_import
from src.database import connect, initialize
from src.gui import InventoryApp
from src.reports import ASSET_HEADERS, REPORT_NAMES


def require(condition, description):
    if not condition:
        raise RuntimeError(description)


def exercise(path, workspace):
    initialize(path)
    root = Tk()
    errors = []

    def fail_dialog(title, message, **_kwargs):
        errors.append((title, message))

    try:
        app = InventoryApp(root, path)
        root.geometry("780x520")
        root.update()
        require(root.winfo_ismapped(), "Tk main window did not map.")
        require(app.metrics["total"].get() == "0", "Dashboard did not initialize.")
        require(Path(path).is_file(), "Persistent database was not created.")

        with patch.object(messagebox, "showerror", side_effect=fail_dialog):
            dialog = app.add_asset()
            dialog.save_button.invoke()
            require(dialog.winfo_exists() and "required" in errors[-1][1], "Invalid form did not remain open.")
            dialog.fields["name"].set("Demo Laptop")
            dialog.fields["serial"].set("DEMO-001")
            dialog.fields["category"].set("Laptop")
            dialog.fields["purchase_price"].set("1200.75")
            dialog.notes.insert("1.0", "Temporary smoke data")
            dialog.save_button.invoke()
            require(not dialog.winfo_exists(), "Registration did not close the dialog.")
            require(app.metrics["total"].get() == "1", "Dashboard did not update after registration.")
            item = app.inventory_tree.selection()[0]
            asset_id = int(item)

            duplicate = app.add_asset()
            duplicate.fields["name"].set("Duplicate")
            duplicate.fields["serial"].set(" demo-001 ")
            duplicate.save_button.invoke()
            require(duplicate.winfo_exists() and "already registered" in errors[-1][1], "Duplicate serial was accepted.")
            duplicate.destroy()

            app.search.set("demo-001")
            app.category.set("Laptop")
            app.year_filter.set(str(date.today().year))
            app.refresh_inventory()
            require(app.inventory_tree.get_children() == (item,), "Search and filters failed.")
            app.status_filter.set("Retired")
            app.refresh_inventory()
            require(not app.inventory_tree.get_children(), "Status filter did not narrow results.")
            app.clear_filters()
            app.select_asset(item)

            detail = app.show_details()
            require(detail.fields["purchase_price"].get() == "1200.75", "Details did not show the saved price.")
            require(detail.notes.cget("state") == "disabled", "Detail notes should be read-only.")
            detail.destroy()

            edit = app.edit_asset()
            edit.fields["status"].set("Under Maintenance")
            edit.fields["name"].set("Demo Laptop Updated")
            edit.save_button.invoke()
            require(app.metrics["repair"].get() == "1", "Dashboard did not reflect edited status.")
            app.tabs.select(app.reporting)
            app.report_name.set(REPORT_NAMES[2])
            app.refresh_reports()
            output = workspace / "maintenance.csv"
            with patch.object(filedialog, "asksaveasfilename", return_value=str(output)):
                app.csv_button.invoke()
            with output.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            require(len(rows) == 1 and rows[0]["Action"] == "Repair priority", "Report CSV is incorrect.")

            app.open_inventory()
            app.select_asset(item)
            with patch.object(messagebox, "askyesno", return_value=False) as confirm:
                app.inventory_buttons["Delete"].invoke()
                require(confirm.call_args.kwargs["default"] == "no", "Deletion confirmation did not default to No.")
            require(len(assets.list_assets(path)) == 1, "Cancelled deletion removed the asset.")

            backup = workspace / "backup.sqlite3"
            with patch.object(filedialog, "asksaveasfilename", return_value=str(backup)):
                app.save_backup()
            require(assets.get_asset(backup, asset_id)["name"] == "Demo Laptop Updated", "GUI backup was not readable.")
            require(len(errors) == 2, f"Unexpected GUI errors: {errors[2:]}")
    finally:
        root.destroy()

    # Recreate Tk and the app from the same on-disk path, with no live connections.
    root = Tk()
    try:
        initialize(path)
        app = InventoryApp(root, path)
        root.update()
        require(app.metrics["total"].get() == "1", "Reopening lost the asset.")
        require(assets.get_asset(path, asset_id)["name"] == "Demo Laptop Updated", "Reopening lost the edit.")
        app.open_inventory()
        app.select_asset(item)
        with patch.object(messagebox, "askyesno", return_value=True) as confirm:
            app.inventory_buttons["Delete"].invoke()
            require(confirm.called, "Confirmed deletion bypassed the dialog.")
        require(app.metrics["total"].get() == "0" and not assets.list_assets(path), "Confirmed deletion failed.")
    finally:
        root.destroy()


def pump_until(root, predicate, timeout=10):
    """Exercise the real event loop while background CSV work completes."""
    deadline = time.monotonic() + timeout
    while not predicate():
        root.update()
        if time.monotonic() > deadline:
            raise RuntimeError("Timed out waiting for CSV GUI work.")
        time.sleep(0.005)
    root.update()


def exercise_csv(path, workspace):
    """Chooser cancellation, preview, responsiveness, rollback/retry and results."""
    initialize(path)
    source = workspace / "gui-input.csv"
    source.write_text(
        'Name,Category,Serial number,Year,Status,Notes\n'
        '"Training, laptop",Laptop,000001,2020,Under Maintenance,"Demo, notes"\n'
        'Duplicate,Laptop,000001,2020,Available,\n'
        ',Laptop,BAD,2020,Available,\n', encoding="utf-8-sig",
    )
    root = Tk()
    callbacks, errors = [], []
    root.report_callback_exception = lambda *args: callbacks.append(str(args[1]))
    try:
        app = InventoryApp(root, path)
        app.open_inventory()
        root.geometry("780x520")
        root.update()
        require(app.import_button.winfo_ismapped() and app.inventory_export_button.winfo_ismapped(), "CSV buttons are not visible.")
        before = path.read_bytes()
        with patch.object(filedialog, "askopenfilename", return_value="") as chooser:
            app.import_button.invoke()
        require(chooser.called and not app.csv_busy and app.import_dialog is None, "File chooser cancellation failed.")
        require(path.read_bytes() == before, "Cancel modified the database.")

        # Hold the worker briefly. Tk timers and close protection must still work.
        release = threading.Event()
        heartbeat = []
        real_prepare = csv_import.prepare_import

        def delayed_prepare(*args):
            require(release.wait(3), "GUI did not release the worker.")
            return real_prepare(*args)

        with patch.object(csv_import, "prepare_import", side_effect=delayed_prepare):
            with patch.object(filedialog, "askopenfilename", return_value=str(source)):
                app.import_button.invoke()
            root.after(15, lambda: heartbeat.append(True))
            root.after(25, app.request_close)
            root.after(100, release.set)
            pump_until(root, lambda: app.import_dialog is not None)
        require(heartbeat and root.winfo_exists(), "GUI blocked during CSV preparation.")
        dialog = app.import_dialog
        require("Valid: 1" in dialog.summary.get() and "Invalid: 1" in dialog.summary.get()
                and "Duplicates: 1" in dialog.summary.get(), "Preview counts were incorrect.")
        require(len(dialog.preview_tree.get_children()) == 3, "Preview records were not shown.")
        require("Row 3" in dialog.issue_text.get("1.0", "end"), "Duplicate row error was missing.")
        dialog.cancel_button.invoke()
        require(path.read_bytes() == before and app.import_dialog is None, "Preview cancellation saved records.")

        with patch.object(filedialog, "askopenfilename", return_value=str(source)):
            app.import_button.invoke()
        pump_until(root, lambda: app.import_dialog is not None)
        dialog = app.import_dialog
        # A real SQLite failure proves the GUI reports rollback and permits retry.
        with connect(path) as connection:
            connection.execute("CREATE TRIGGER smoke_reject BEFORE INSERT ON assets BEGIN SELECT RAISE(ABORT, 'smoke failure'); END")
        with patch.object(messagebox, "showerror", side_effect=lambda *args, **kwargs: errors.append(args)):
            dialog.import_button.invoke()
            pump_until(root, lambda: not app.csv_busy)
        require(errors and "rolled back" in errors[-1][0] and not assets.list_assets(path), "Failed import did not roll back.")
        require(not dialog.import_button.instate(["disabled"]), "Retry was disabled after a failed import.")
        with connect(path) as connection:
            connection.execute("DROP TRIGGER smoke_reject")
        app.search.set("no-match")
        app.category.set("Router")
        dialog.import_button.invoke()
        pump_until(root, lambda: dialog.finished)
        require("Imported: 1" in dialog.summary.get() and "Skipped: 2" in dialog.summary.get(), "Final results were incorrect.")
        require(app.metrics["total"].get() == "1" and app.metrics["repair"].get() == "1", "Dashboard did not refresh after import.")
        require(len(app.inventory_tree.get_children()) == 1 and app.category.get() == "All", "Inventory filters did not reset.")
        require("2020" in app.year_choices.cget("values"), "Year filter did not refresh.")
        require(app.report_data[1][0][2] == 1, "Report data did not refresh.")
        dialog.cancel_button.invoke()

        exported = workspace / "gui-full.csv"
        with patch.object(filedialog, "asksaveasfilename", return_value=str(exported)):
            app.inventory_export_button.invoke()
        with exported.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        require(tuple(rows[0]) == ASSET_HEADERS and rows[1][3] == "000001", "Full inventory export lost fields.")
        require(assets.list_assets(path)[0]["notes"] == "Demo, notes", "Imported fields did not persist.")

        with patch.object(filedialog, "askopenfilename", return_value=str(exported)):
            app.import_button.invoke()
        pump_until(root, lambda: app.import_dialog is not None)
        dialog = app.import_dialog
        require(dialog.import_button.instate(["disabled"]) and dialog.preview.duplicates == 1, "All-duplicate import was not disabled.")
        dialog.close()
        malformed = workspace / "malformed.csv"
        malformed.write_text("Wrong,Headers\n", encoding="utf-8")
        with patch.object(messagebox, "showerror", side_effect=lambda *args, **kwargs: errors.append(args)):
            with patch.object(filedialog, "askopenfilename", return_value=str(malformed)):
                app.import_button.invoke()
            pump_until(root, lambda: not app.csv_busy)
        require(len(errors) == 2 and app.import_dialog is None and not app.import_button.instate(["disabled"]), "Malformed file did not recover safely.")
        require(not callbacks, f"Unhandled Tk callback errors: {callbacks}")
    finally:
        root.destroy()
    # Fresh connections verify persistence independently of the GUI's cached rows.
    require(len(assets.list_assets(path)) == 1, "Imported data did not persist.")


def write_receipt(receipt):
    with tempfile.TemporaryDirectory(prefix="cpit251-smoke-") as name:
        workspace = Path(name)
        windows = sys.platform == "win32"
        data_root = workspace / "user-data"
        env_key = "LOCALAPPDATA" if windows else "XDG_DATA_HOME"
        expected = data_root / (DATA_FOLDER if windows else DATA_FOLDER.lower()) / "inventory.sqlite3"
        try:
            with patch.dict(os.environ, {env_key: str(data_root)}):
                path = database_path()
                require(path == expected, "The app did not resolve the platform's user-data path.")
                exercise(path, workspace)
                # The harness creates multiple Tk interpreters; dispose of the
                # closed ones on the main thread before starting any workers.
                gc.collect()
                exercise_csv(workspace / "csv.sqlite3", workspace)
        except Exception as error:  # noqa: BLE001 - frozen smoke boundary writes a receipt
            result = {"passed": False, "error": str(error), "platform": sys.platform}
        else:
            result = {
                "passed": True,
                "platform": sys.platform,
                "frozen": bool(getattr(sys, "frozen", False)),
                "checks": ["GUI", "platform data path", "validation", "create", "search", "filters", "details",
                           "update", "report", "CSV", "cancel deletion", "backup", "reopen", "confirmed deletion",
                           "CSV chooser cancel", "CSV preview cancel", "CSV responsive worker", "CSV rollback/retry",
                           "CSV import/results", "CSV view refresh", "full inventory export", "CSV duplicate skip", "CSV file errors"],
            }
    receipt.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["passed"] else 1

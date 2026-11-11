"""Tk widgets and event handlers. SQL lives in the service and database modules."""
import csv
import gc
import queue
import sqlite3
import threading
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

from config import APP_NAME, CATEGORIES, STATUSES, VERSION
from src import asset_service as assets
from src import csv_import, reports
from src.database import backup_database
from src.validation import ValidationError

INVENTORY_COLUMNS = (
    ("Asset ID", 104), ("Name", 212), ("Category", 112), ("Serial number", 128),
    ("Year", 66), ("Status", 150), ("Location", 145),
)
FORM_FIELDS = (
    ("name", "Asset name *"), ("category", "Category *"), ("serial", "Serial number"),
    ("purchase_year", "Purchase year *"), ("purchase_price", "Purchase price (SAR)"),
    ("status", "Status *"), ("assigned_to", "Assigned person"), ("location", "Location"),
)
DB_ERRORS = (sqlite3.Error, OSError, assets.AssetNotFound)


def fill_tree(tree, columns, rows):
    names = [name for name, _ in columns]
    tree.configure(columns=names)
    for name, width in columns:
        tree.heading(name, text=name)
        tree.column(name, width=width, minwidth=min(width, 70), stretch=name in {"Name", "Item"})
    tree.delete(*tree.get_children())
    for key, values in rows:
        tree.insert("", "end", iid=key, values=values)


def add_table(parent):
    frame = ttk.Frame(parent)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    tree = ttk.Treeview(frame, show="headings", selectmode="browse")
    vertical = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    horizontal = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    frame.pack(expand=True, fill="both")
    return tree


class AssetDialog(tk.Toplevel):
    """Shared form for registration, editing and read-only details."""

    def __init__(self, app, title, asset=None, readonly=False):
        super().__init__(app.root)
        self.app = app
        self.asset = asset
        self.title(title)
        self.transient(app.root)
        self.resizable(True, False)
        self.minsize(460, 0)
        self.bind("<Escape>", lambda _event: self.destroy())

        initial = dict(asset) if asset else {
            "category": CATEGORIES[0], "status": STATUSES[0], "purchase_year": date.today().year,
        }
        initial["purchase_price"] = assets.format_price(initial.get("price_cents"))
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        heading = title if asset is None else f"{title}  /  {assets.asset_code(asset['id'])}"
        ttk.Label(frame, text=heading, style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.fields = {}
        first_entry = None
        for row, (key, label) in enumerate(FORM_FIELDS, 1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 14), pady=3)
            variable = tk.StringVar(self, value=str(initial.get(key) or ""))
            self.fields[key] = variable
            if not readonly and key in {"category", "status"}:
                choices = CATEGORIES if key == "category" else STATUSES
                widget = ttk.Combobox(frame, values=choices, textvariable=variable, state="readonly")
            else:
                widget = ttk.Entry(frame, textvariable=variable, state="readonly" if readonly else "normal")
            widget.grid(row=row, column=1, sticky="ew", pady=3)
            if first_entry is None:
                first_entry = widget

        row = len(FORM_FIELDS) + 1
        ttk.Label(frame, text="Notes").grid(row=row, column=0, sticky="nw", pady=4)
        self.notes = tk.Text(frame, width=33, height=4, wrap="word", font="TkDefaultFont",
                             padx=5, pady=4, relief="solid", borderwidth=1)
        self.notes.insert("1.0", initial.get("notes", ""))
        self.notes.grid(row=row, column=1, sticky="ew", pady=4)
        if readonly:
            self.notes.configure(state="disabled")
            ttk.Label(frame, text=f"Created {asset['created_at']} UTC  |  Updated {asset['updated_at']} UTC",
                      wraplength=400).grid(row=row + 1, column=0, columnspan=2, sticky="w", pady=4)
        else:
            ttk.Label(frame, text="* Required   |   Serial number must be unique when supplied.").grid(
                row=row + 1, column=0, columnspan=2, sticky="w", pady=4,
            )

        actions = ttk.Frame(frame)
        actions.grid(row=row + 2, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(actions, text="Close" if readonly else "Cancel", command=self.destroy).pack(side="left", padx=(0, 6))
        if not readonly:
            self.save_button = ttk.Button(actions, text="Save asset", command=self.save)
            self.save_button.pack(side="left")
            self.bind("<Control-Return>", lambda _event: self.save())
        self.update_idletasks()
        x = max(0, app.root.winfo_rootx() + (app.root.winfo_width() - self.winfo_reqwidth()) // 2)
        y = max(0, app.root.winfo_rooty() + (app.root.winfo_height() - self.winfo_reqheight()) // 2)
        self.geometry(f"+{x}+{y}")
        self.wait_visibility()
        self.grab_set()
        first_entry.focus_set()

    def save(self):
        form = {key: variable.get() for key, variable in self.fields.items()}
        form["notes"] = self.notes.get("1.0", "end-1c")
        try:
            if self.asset is None:
                asset_id = assets.add_asset(self.app.path, form)
                verb = "Registered"
            else:
                asset_id = self.asset["id"]
                assets.update_asset(self.app.path, asset_id, form)
                verb = "Updated"
        except (ValidationError, *DB_ERRORS) as error:
            messagebox.showerror("Asset could not be saved", str(error), parent=self)
            return
        self.destroy()
        self.app.refresh()
        self.app.open_inventory()
        self.app.select_asset(asset_id)
        self.app.notice.set(f"{verb} {assets.asset_code(asset_id)}.")


class ImportPreviewDialog(tk.Toplevel):
    """Confirm a read-only snapshot, then show the actual committed results."""

    def __init__(self, app, preview):
        super().__init__(app.root)
        self.app, self.preview = app, preview
        self.finished = False
        self.title("Preview CSV import")
        self.transient(app.root)
        self.geometry("940x690")
        self.minsize(740, 580)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Import assets from CSV", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(frame, text=str(preview.source), wraplength=710).pack(anchor="w", pady=(6, 8))
        self.summary = tk.StringVar(self, value=(
            f"Total: {preview.total}    Valid: {preview.valid}    Invalid: {preview.invalid}    Duplicates: {preview.duplicates}"
        ))
        ttk.Label(frame, textvariable=self.summary, wraplength=710).pack(anchor="w", pady=(0, 8))
        ttk.Label(frame, text="\n".join(preview.warnings), wraplength=710).pack(anchor="w", pady=(0, 8))
        ttk.Label(frame, text="First 10 records (row numbers refer to the CSV's physical lines)").pack(anchor="w")
        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True, pady=(4, 8))
        self.preview_tree = add_table(table)
        self.preview_tree.configure(height=8)
        columns = (("CSV row", 65), ("Outcome", 90), *((header, 140) for header in preview.headers))
        fill_tree(self.preview_tree, columns, (
            (str(row.row_number), (row.row_number, row.outcome, *row.values)) for row in preview.first_rows
        ))
        ttk.Label(frame, text="Skipped rows and validation errors").pack(anchor="w")
        issue_frame = ttk.Frame(frame)
        issue_frame.pack(fill="both", expand=True, pady=(4, 10))
        self.issue_text = tk.Text(issue_frame, height=6, wrap="word", font="TkDefaultFont")
        scrollbar = ttk.Scrollbar(issue_frame, command=self.issue_text.yview)
        self.issue_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.issue_text.pack(side="left", fill="both", expand=True)
        self.show_issues(preview.issues)
        actions = ttk.Frame(frame)
        # Reserve button height first; the scrollable panels absorb shrinking.
        actions.pack(side="bottom", fill="x", before=frame.winfo_children()[0])
        self.cancel_button = ttk.Button(actions, text="Cancel", command=self.close)
        self.cancel_button.pack(side="right")
        self.import_button = ttk.Button(actions, text="Import Valid Records", command=self.confirm)
        self.import_button.pack(side="right", padx=8)
        if not preview.valid:
            self.import_button.state(["disabled"])
        self.wait_visibility()
        self.grab_set()
        self.cancel_button.focus_set()

    def show_issues(self, issues):
        self.issue_text.configure(state="normal")
        self.issue_text.delete("1.0", "end")
        self.issue_text.insert("1.0", "\n".join(
            f"Row {issue.row_number} [{issue.kind}]: {issue.message}" for issue in issues
        ) or "No invalid or duplicate rows.")
        self.issue_text.configure(state="disabled")

    def close(self):
        if self.app.csv_busy:
            return
        self.app.import_dialog = None
        self.app.import_button.state(["!disabled"])
        self.destroy()

    def confirm(self):
        if self.finished or self.app.csv_busy or not self.preview.valid:
            return
        self.import_button.state(["disabled"])
        self.cancel_button.state(["disabled"])
        self.app.run_csv_job(
            lambda: csv_import.import_prepared(self.app.path, self.preview),
            self.show_result, self.import_failed, "Importing CSV: please wait for the transaction to finish...",
        )

    def import_failed(self, error):
        self.import_button.state(["!disabled"])
        self.cancel_button.state(["!disabled"])
        self.app.notice.set("CSV import failed; no rows from this batch were committed.")
        messagebox.showerror("Import failed - batch rolled back", f"No records from this batch were saved.\n\n{error}", parent=self)

    def show_result(self, result):
        self.finished = True
        self.title("CSV import results")
        self.summary.set(
            f"Total: {result.total}    Imported: {result.inserted}    Skipped: {result.skipped} "
            f"(invalid: {result.invalid}, duplicates: {result.duplicates})"
        )
        self.show_issues(result.issues)
        self.import_button.pack_forget()
        self.cancel_button.configure(text="Close")
        self.cancel_button.state(["!disabled"])
        self.cancel_button.focus_set()
        self.app.search.set("")
        for variable in (self.app.category, self.app.status_filter, self.app.year_filter):
            variable.set("All")
        try:
            self.app.refresh()
        except DB_ERRORS as error:
            # The batch has committed: a refresh failure must not claim rollback.
            messagebox.showerror("Import saved; refresh failed", f"The records were saved. Press F5 to retry refreshing.\n\n{error}", parent=self)
        self.app.notice.set(f"Imported {result.inserted} assets; skipped {result.skipped} rows.")


class InventoryApp:
    def __init__(self, root, path):
        self.root = root
        self.path = path
        self.csv_busy = False
        self.import_dialog = None
        self.notice = tk.StringVar(root, value="Ready")
        self.match_count = tk.StringVar(root)
        self.metrics = {key: tk.StringVar(root, value="0") for key in (
            "total", "operational", "aging", "repair",
        )}
        root.title(f"{APP_NAME}  |  CPIT251")
        root.minsize(780, 520)
        root.geometry("1040x670")

        style = ttk.Style(root)
        style.configure("Heading.TLabel", font=("TkDefaultFont", 15, "bold"))
        style.configure("Metric.TLabel", font=("TkDefaultFont", 24, "bold"))

        outer = ttk.Frame(root, padding=(14, 10))
        outer.pack(fill="both", expand=True)
        masthead = ttk.Frame(outer, padding=(1, 0, 1, 10))
        masthead.pack(fill="x")
        ttk.Label(masthead, text=APP_NAME, style="Heading.TLabel").pack(side="left")
        ttk.Label(masthead, text="CPIT251  /  Offline workspace").pack(side="right", pady=4)
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)
        self.dashboard = self.add_tab("Dashboard")
        self.inventory = self.add_tab("Inventory")
        self.reporting = self.add_tab("Reports")
        self.about = self.add_tab("About")
        ttk.Label(outer, textvariable=self.notice, padding=(0, 8, 0, 0)).pack(anchor="w")

        self.build_dashboard()
        self.build_inventory()
        self.build_reports()
        self.build_about()
        self.root.bind("<F5>", lambda _event: self.refresh(announce=True))
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self.refresh()

    def add_tab(self, title):
        tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(tab, text=title)
        return tab

    def build_dashboard(self):
        row = ttk.Frame(self.dashboard)
        row.pack(fill="x")
        for column, (key, label) in enumerate((
            ("total", "Registered assets"), ("operational", "Operational"),
            ("aging", "Aging (5+ years)"), ("repair", "Repair priority"),
        )):
            row.columnconfigure(column, weight=1, uniform="metrics")
            card = ttk.LabelFrame(row, text=label, padding=(12, 7))
            card.grid(row=0, column=column, padx=(0 if column == 0 else 6, 0), sticky="ew")
            ttk.Label(card, textvariable=self.metrics[key], style="Metric.TLabel").pack(anchor="w")

        actions = ttk.Frame(self.dashboard, padding=(0, 12))
        actions.pack(fill="x")
        ttk.Button(actions, text="Register asset", command=self.add_asset).pack(side="left")
        ttk.Button(actions, text="Open inventory", command=self.open_inventory).pack(side="left", padx=6)
        ttk.Button(actions, text="View reports", command=lambda: self.tabs.select(self.reporting)).pack(side="left")

        groups = ttk.Frame(self.dashboard)
        groups.pack(fill="both", expand=True)
        groups.columnconfigure((0, 1), weight=1, uniform="dashboard")
        groups.rowconfigure(0, weight=1)
        self.dashboard_tables = {}
        for column, (key, label) in enumerate((("categories", "By category"), ("statuses", "By status"))):
            section = ttk.LabelFrame(groups, text=label, padding=7)
            section.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
            self.dashboard_tables[key] = add_table(section)

    def build_inventory(self):
        panel = ttk.Frame(self.inventory)
        panel.pack(fill="x", pady=(0, 8))
        self.search = tk.StringVar(self.root)
        self.category = tk.StringVar(self.root, value="All")
        self.status_filter = tk.StringVar(self.root, value="All")
        self.year_filter = tk.StringVar(self.root, value="All")
        ttk.Label(panel, text="Search ID, name, or serial").grid(row=0, column=0, sticky="w")
        search = ttk.Entry(panel, textvariable=self.search)
        search.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        search.bind("<Return>", lambda _event: self.refresh_inventory())
        ttk.Button(panel, text="Search", command=self.refresh_inventory).grid(row=1, column=1, padx=(0, 8))
        panel.columnconfigure(0, weight=1)
        for column, (name, variable, choices, width) in enumerate((
            ("Category", self.category, CATEGORIES, 12),
            ("Status", self.status_filter, STATUSES, 15),
            ("Year", self.year_filter, (), 5),
        ), 2):
            ttk.Label(panel, text=name).grid(row=0, column=column, sticky="w")
            combo = ttk.Combobox(panel, values=("All", *choices), textvariable=variable,
                                 state="readonly", width=width)
            combo.grid(row=1, column=column, sticky="ew", padx=(0, 6))
            combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_inventory())
            if name == "Year":
                self.year_choices = combo
        ttk.Button(panel, text="Clear", command=self.clear_filters).grid(row=1, column=5)

        actions = ttk.Frame(self.inventory)
        actions.pack(fill="x", pady=(0, 8))
        self.inventory_buttons = {}
        for label, command in (
            ("Add", self.add_asset), ("Details", self.show_details), ("Edit", self.edit_asset),
            ("Delete", self.delete_asset), ("Refresh", lambda: self.refresh(announce=True)),
        ):
            button = ttk.Button(actions, text=label, command=command)
            button.pack(side="left", padx=(0, 6))
            self.inventory_buttons[label] = button
        ttk.Label(actions, textvariable=self.match_count).pack(side="right")
        csv_actions = ttk.Frame(self.inventory)
        csv_actions.pack(fill="x", pady=(0, 8))
        self.import_button = ttk.Button(csv_actions, text="Import CSV", command=self.import_csv)
        self.import_button.pack(side="left", padx=(0, 6))
        self.inventory_export_button = ttk.Button(csv_actions, text="Export CSV", command=self.export_inventory)
        self.inventory_export_button.pack(side="left")
        ttk.Label(csv_actions, text="Full inventory / duplicates are skipped").pack(side="left", padx=10)
        self.csv_progress = ttk.Progressbar(csv_actions, mode="indeterminate", length=90)
        self.csv_progress.pack(side="right")
        self.inventory_tree = add_table(self.inventory)
        self.inventory_tree.bind("<<TreeviewSelect>>", lambda _event: self.update_selection())
        self.inventory_tree.bind("<Double-1>", self.open_clicked_details)
        self.inventory_tree.bind("<Return>", lambda _event: self.show_details())

    def build_reports(self):
        controls = ttk.Frame(self.reporting)
        controls.pack(fill="x", pady=(0, 8))
        ttk.Label(controls, text="Report").pack(side="left", padx=(0, 8))
        self.report_name = tk.StringVar(self.root, value=reports.REPORT_NAMES[0])
        selection = ttk.Combobox(controls, values=reports.REPORT_NAMES, textvariable=self.report_name,
                                 state="readonly", width=26)
        selection.pack(side="left")
        selection.bind("<<ComboboxSelected>>", lambda _event: self.refresh_reports())
        self.csv_button = ttk.Button(controls, text="Export CSV", command=self.export_report)
        self.csv_button.pack(side="right")
        ttk.Label(self.reporting, text="Reports use the full inventory. Repair priority appears first.",
                  padding=(0, 0, 0, 8)).pack(anchor="w")
        self.report_tree = add_table(self.reporting)

    def build_about(self):
        ttk.Label(self.about, text=APP_NAME, style="Heading.TLabel").pack(anchor="w")
        for text in (
            f"Version {VERSION}  /  CPIT251 Software Engineering I",
            "Offline desktop reference implementation. Data belongs to this user account.",
            "Active SQLite database:",
        ):
            ttk.Label(self.about, text=text, padding=(0, 6)).pack(anchor="w")
        path = ttk.Entry(self.about, width=65)
        path.insert(0, str(self.path))
        path.configure(state="readonly")
        path.pack(fill="x", pady=(0, 12))
        ttk.Button(self.about, text="Back up database...", command=self.save_backup).pack(anchor="w")

    def open_inventory(self):
        self.tabs.select(self.inventory)

    def select_asset(self, asset_id):
        item = str(asset_id)
        if self.inventory_tree.exists(item):
            self.inventory_tree.selection_set(item)
            self.inventory_tree.focus(item)
            self.inventory_tree.see(item)
        self.update_selection()

    def update_selection(self):
        state = "normal" if self.inventory_tree.selection() else "disabled"
        for name in ("Details", "Edit", "Delete"):
            self.inventory_buttons[name].configure(state=state)

    def clear_filters(self):
        self.search.set("")
        for variable in (self.category, self.status_filter, self.year_filter):
            variable.set("All")
        self.refresh_inventory()

    def refresh(self, announce=False):
        try:
            snapshot = assets.list_assets(self.path)
            summary = reports.inventory_summary(snapshot, date.today().year)
            for key, variable in self.metrics.items():
                variable.set(str(summary[key]))
            for key, tree in self.dashboard_tables.items():
                fill_tree(tree, (("Item", 160), ("Count", 85)),
                          ((None, (name, count)) for name, count in summary[key].items()))
            years = ("All", *map(str, assets.purchase_years(self.path)))
            self.year_choices.configure(values=years)
            if self.year_filter.get() not in years:
                self.year_filter.set("All")
            self.refresh_inventory()
            self.refresh_reports(snapshot)
        except DB_ERRORS as error:
            self.show_error("Inventory could not be refreshed", error)
        else:
            if announce:
                self.notice.set("Inventory refreshed.")

    def refresh_inventory(self):
        selected = self.inventory_tree.selection()
        category, status, year = (
            "" if var.get() == "All" else var.get()
            for var in (self.category, self.status_filter, self.year_filter)
        )
        try:
            rows = assets.list_assets(self.path, self.search.get(), category, status, year)
        except DB_ERRORS as error:
            self.show_error("Search could not be completed", error)
            return
        fill_tree(self.inventory_tree, INVENTORY_COLUMNS, (
            (str(row["id"]), (assets.asset_code(row["id"]), row["name"], row["category"],
                             row["serial"] or "", row["purchase_year"], row["status"], row["location"]))
            for row in rows
        ))
        self.match_count.set(f"{len(rows)} matching")
        if selected:
            self.select_asset(selected[0])
        self.update_selection()

    def refresh_reports(self, snapshot=None):
        try:
            if snapshot is None:
                snapshot = assets.list_assets(self.path)
            headers, rows = reports.report_table(snapshot, self.report_name.get())
        except DB_ERRORS as error:
            self.show_error("Report could not be refreshed", error)
            return
        widths = (130, 235, 75) if headers == reports.SUMMARY_HEADERS else (100, 175, 106, 148, 65, 58, 181, 190)
        fill_tree(self.report_tree, tuple(zip(headers, widths)), ((None, row) for row in rows))
        self.report_data = (headers, rows)

    def show_error(self, title, error):
        messagebox.showerror(title, str(error), parent=self.root)

    def selected_record(self):
        selected = self.inventory_tree.selection()
        if not selected:
            return None
        try:
            return assets.get_asset(self.path, int(selected[0]))
        except DB_ERRORS as error:
            self.show_error("Asset could not be opened", error)
            return None

    def add_asset(self):
        return AssetDialog(self, "Register asset")

    def edit_asset(self):
        asset = self.selected_record()
        if asset is not None:
            return AssetDialog(self, "Edit asset", asset)
        return None

    def show_details(self):
        asset = self.selected_record()
        if asset is not None:
            return AssetDialog(self, "Asset details", asset, readonly=True)
        return None

    def open_clicked_details(self, event):
        item = self.inventory_tree.identify_row(event.y)
        if item:
            self.select_asset(item)
            self.show_details()

    def delete_asset(self):
        asset = self.selected_record()
        if asset is None:
            return
        code = assets.asset_code(asset["id"])
        confirmed = messagebox.askyesno(
            "Delete asset?",
            f'Delete {code} ("{asset["name"]}") permanently?\n\nThis action cannot be undone.',
            icon="warning", default="no", parent=self.root,
        )
        if not confirmed:
            return
        try:
            assets.delete_asset(self.path, asset["id"])
        except DB_ERRORS as error:
            self.show_error("Asset could not be deleted", error)
            return
        self.refresh()
        self.notice.set(f"Deleted {code}.")

    def export_report(self):
        destination = filedialog.asksaveasfilename(
            parent=self.root, title="Export current report", defaultextension=".csv",
            initialfile=self.report_name.get().lower().replace(" ", "-") + ".csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if destination:
            try:
                reports.export_csv(destination, *self.report_data)
            except FileExistsError:
                self.show_error("Choose a new CSV name", "Existing files are protected from replacement.")
            except (OSError, csv.Error) as error:
                self.show_error("Report could not be exported", error)
            else:
                self.notice.set(f"Report exported to {destination}")

    def request_close(self):
        if self.csv_busy:
            self.notice.set("CSV operation is running. Please wait before closing.")
            return
        self.root.destroy()

    def run_csv_job(self, work, on_success, on_failure, notice):
        """Workers never touch Tk; poll their result from the main event loop."""
        # Destroyed dialogs can leave Python reference cycles containing Tk
        # variables. Finalize those on this thread before a worker allocates.
        gc.collect()
        self.csv_busy = True
        self.import_button.state(["disabled"])
        self.csv_progress.start(15)
        self.notice.set(notice)
        results = queue.Queue()

        def worker():
            try:
                results.put((True, work()))
            except Exception as error:  # noqa: BLE001 - report worker failures on the GUI thread
                results.put((False, error))

        def poll():
            try:
                succeeded, result = results.get_nowait()
            except queue.Empty:
                self.root.after(40, poll)
                return
            self.csv_busy = False
            self.csv_progress.stop()
            if self.import_dialog is None:
                self.import_button.state(["!disabled"])
            (on_success if succeeded else on_failure)(result)

        threading.Thread(target=worker, name="CSV-worker", daemon=True).start()
        self.root.after(40, poll)

    def import_csv(self):
        if self.csv_busy or self.import_dialog is not None:
            return
        source = filedialog.askopenfilename(
            parent=self.root, title="Import assets from CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*")],
        )
        if not source:
            return

        def show_preview(preview):
            self.import_dialog = ImportPreviewDialog(self, preview)
            self.import_button.state(["disabled"])
            self.notice.set("Preview only: no records have been saved. Confirm or cancel.")

        def failed(error):
            self.notice.set("CSV could not be prepared; inventory unchanged.")
            self.show_error("CSV could not be read", error)

        self.run_csv_job(lambda: csv_import.prepare_import(self.path, source), show_preview, failed, "Reading and validating CSV...")

    def export_inventory(self):
        destination = filedialog.asksaveasfilename(
            parent=self.root, title="Export full inventory", defaultextension=".csv",
            initialfile="inventory.csv", filetypes=[("CSV files", "*.csv")],
        )
        if destination:
            try:
                reports.export_inventory(destination, assets.list_assets(self.path))
            except FileExistsError:
                self.show_error("Choose a new CSV name", "Existing files are protected from replacement.")
            except (csv.Error, *DB_ERRORS) as error:
                self.show_error("Inventory could not be exported", error)
            else:
                self.notice.set(f"Full inventory exported to {destination}")

    def save_backup(self):
        destination = filedialog.asksaveasfilename(
            parent=self.root, title="Back up the current inventory", defaultextension=".sqlite3",
            initialfile=f"inventory-backup-{date.today()}.sqlite3",
            filetypes=[("SQLite databases", "*.sqlite3"), ("All files", "*")],
        )
        if destination:
            try:
                backup_database(self.path, destination)
            except FileExistsError:
                self.show_error("Choose a new backup name", "Existing files are protected from replacement.")
            except DB_ERRORS as error:
                self.show_error("Backup could not be created", error)
            else:
                self.notice.set(f"Database backed up to {destination}")

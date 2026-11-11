"""Launch the desktop application or run a disposable packaged smoke test."""
import argparse
import sqlite3
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from config import database_path
from src.database import initialize
from src.gui import InventoryApp


def main():
    parser = argparse.ArgumentParser(description="CPIT251 IT Asset Inventory")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--database", type=Path, help="open a separate, explicitly chosen SQLite database")
    modes.add_argument("--smoke-test", type=Path, metavar="RECEIPT", help="exercise the GUI using a disposable inventory")
    args = parser.parse_args()
    if args.smoke_test:
        from src.smoke import write_receipt
        return write_receipt(args.smoke_test)
    path = args.database if args.database is not None else database_path()
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f"Cannot open the desktop window: {error}", file=sys.stderr)
        return 1
    try:
        initialize(path)
    except (sqlite3.Error, OSError) as error:
        root.withdraw()
        messagebox.showerror("Inventory database could not be opened", f"{path}\n\n{error}", parent=root)
        root.destroy()
        return 1
    InventoryApp(root, path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

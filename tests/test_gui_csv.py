"""Native Tk integration; run with access to a graphical display."""
import tkinter as tk

import pytest

from src.smoke import exercise_csv


def test_csv_gui_workflow(tmp_path):
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"A native graphical display is required: {error}")
    root.destroy()
    exercise_csv(tmp_path / "gui.sqlite3", tmp_path)

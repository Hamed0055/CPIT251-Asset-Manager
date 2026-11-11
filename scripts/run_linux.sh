#!/bin/sh
set -eu

project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
python=${PYTHON:-python3}

if ! command -v "$python" >/dev/null 2>&1; then
	printf '%s\n' 'Python 3.11+ is required. Install the Python package for your distribution.' >&2
	exit 1
fi
if ! "$python" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
	printf '%s\n' 'Python 3.11 or newer is required. Set PYTHON to a compatible executable.' >&2
	exit 1
fi
if ! "$python" -c 'import tkinter' >/dev/null 2>&1; then
	printf '%s\n' 'Tkinter is unavailable. Install tk on Arch/CachyOS or python3-tk on Debian/Ubuntu.' >&2
	exit 1
fi
if ! "$python" -c 'import sqlite3, sys; sys.exit(sqlite3.sqlite_version_info < (3, 37))'; then
	printf '%s\n' 'SQLite 3.37+ support is required by this Python installation.' >&2
	exit 1
fi

exec "$python" "$project_dir/main.py" "$@"

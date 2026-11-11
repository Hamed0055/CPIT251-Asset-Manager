#!/bin/sh
set -eu

project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
python=${PYTHON:-python3}
cd "$project_dir"

if ! "$python" -c 'import PyInstaller, tkinter, sqlite3; assert PyInstaller.__version__ == "6.22.2"; assert sqlite3.sqlite_version_info >= (3, 37)' >/dev/null 2>&1; then
	printf '%s\n' 'Build requires PyInstaller 6.22.2, Tkinter and SQLite 3.37+. See docs/DEVELOPER_GUIDE.md.' >&2
	exit 1
fi

"$python" -m PyInstaller --noconfirm --clean --onefile \
	--name CPIT251-Asset-Manager --distpath dist --workpath build/linux \
	--specpath build main.py
printf '%s\n' "Executable: $project_dir/dist/CPIT251-Asset-Manager"

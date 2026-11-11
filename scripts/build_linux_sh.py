"""Build an offline, source-based linux.sh without external build dependencies."""
import argparse
import base64
import hashlib
import io
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHELL_HEADER = '''#!/bin/sh
# CPIT251 standalone Linux launcher. Python 3.11+, Tk and SQLite 3.37+ required.
# Contains the application; no download, installation or administrator access.
set -eu

python=${PYTHON:-python3}
if ! command -v "$python" >/dev/null 2>&1; then
	printf '%s\\n' 'Python 3.11+ is required. Install Python and Tk for your distribution.' >&2
	exit 1
fi
exec "$python" - "$@" <<'CPIT251_PORTABLE_PYTHON'
'''


def build(destination, project=ROOT):
    """Create a new self-contained file; never overwrite an existing artifact."""
    project = Path(project)
    runtime = ["linux.sh", "main.py", "config.py", "scripts/run_linux.sh"]
    runtime += [path.relative_to(project).as_posix() for path in sorted((project / "src").glob("*.py"))]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in runtime:
            source = project / name
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"Expected an ordinary application file: {name}")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, source.read_bytes())
    payload = buffer.getvalue()
    bootstrap = (project / "scripts/linux_portable.py").read_text(encoding="utf-8")
    bootstrap = bootstrap.replace("__CPIT251_ARCHIVE_BASE64__", base64.b64encode(payload).decode("ascii"))
    bootstrap = bootstrap.replace("__CPIT251_ARCHIVE_SHA256__", hashlib.sha256(payload).hexdigest())
    compile(bootstrap, "<linux.sh bootstrap>", "exec")
    script = SHELL_HEADER + bootstrap + "\nCPIT251_PORTABLE_PYTHON\n"
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also prevents replacing an older release by accident.
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(script)
    destination.chmod(0o755)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/linux.sh")
    args = parser.parse_args()
    try:
        artifact = build(args.output)
    except (OSError, ValueError, SyntaxError) as error:
        parser.exit(1, f"Could not build linux.sh: {error}\n")
    print(f"Standalone launcher: {artifact}")


if __name__ == "__main__":
    main()

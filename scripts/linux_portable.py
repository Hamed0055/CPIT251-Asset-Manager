"""Bootstrap template embedded in the generated standalone Linux shell file."""
import base64
import hashlib
import io
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ARCHIVE_BASE64 = "__CPIT251_ARCHIVE_BASE64__"
ARCHIVE_SHA256 = "__CPIT251_ARCHIVE_SHA256__"


def main():
    if sys.version_info < (3, 11):  # noqa: UP036 - bootstrap must detect older interpreters
        print("Python 3.11 or newer is required.", file=sys.stderr)
        return 1
    try:
        payload = base64.b64decode(ARCHIVE_BASE64, validate=True)
        if hashlib.sha256(payload).hexdigest() != ARCHIVE_SHA256:
            print("The embedded application checksum failed. Download linux.sh again.", file=sys.stderr)
            return 1
        with tempfile.TemporaryDirectory(prefix="cpit251-linux-") as directory:
            root = Path(directory)
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                # Only relative application files may be extracted.
                for member in archive.infolist():
                    if member.is_dir() or Path(member.filename).is_absolute() or ".." in Path(member.filename).parts:
                        print("Invalid embedded application path.", file=sys.stderr)
                        return 1
                archive.extractall(root)
            # Keep the user's cwd, stdin/out/err and argument boundaries. The
            # existing launcher performs all Python/Tk/SQLite dependency checks.
            result = subprocess.call(["/bin/sh", str(root / "linux.sh"), *sys.argv[1:]])
            return result if result >= 0 else 128 - result
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(f"Could not unpack or launch CPIT251: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

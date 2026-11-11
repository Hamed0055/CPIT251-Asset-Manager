# Linux launchers and release

## One-file download

On the private repository's Releases page, open **v1.0.1** and download the
**linux.sh** release asset. It contains the application source and works offline
after download, without cloning or unpacking a source ZIP yourself.

From the directory containing the downloaded file:

```sh
sh linux.sh
```

Or make it executable once and run it:

```sh
chmod +x linux.sh
./linux.sh
```

The script needs Python 3.11+, Tkinter and SQLite 3.37+ supplied by Python.
On Arch/CachyOS the runtime packages are `python` and `tk`; Debian/Ubuntu uses
`python3` and `python3-tk`. Missing dependencies produce a message and nonzero
exit status. No packages, services or network settings are changed by the script.

A graphical desktop is required to open the application. `sh linux.sh --help`
works without a display. Bash, fish and other shells can all run the commands
above, because the launcher uses POSIX sh.

## Inventory data and arguments

The app uses the same persistent user-data database as the source version.
Normally this is under
`~/.local/share/cpit251-asset-manager-reference/inventory.sqlite3`, or the
absolute XDG_DATA_HOME override. About shows the active database path.
Replacing/deleting the downloaded launcher does not delete the inventory.

An explicit separate database can be selected:

```sh
sh linux.sh --database "./local-data/training inventory.sqlite3"
```

Relative paths are resolved from the directory where you run the command.
Arguments retain spaces and special characters. To choose a Python interpreter:

```sh
PYTHON=/usr/bin/python3 sh linux.sh --help
```

The standalone script unpacks only its embedded application to a private temporary
folder, runs it through the existing dependency-checking launcher, and removes
the temporary folder when the app exits. Data lives outside that folder.
It validates the embedded archive checksum before execution.

## Source checkout

When using the extracted source ZIP or Git clone, run `sh linux.sh` from its
root, or the existing `sh scripts/run_linux.sh`. The root script is a small
source launcher; the separately attached release asset is the generated
self-contained script. Both launch the same application.

## Build and verify

No PyInstaller or third-party build dependency is needed for the shell asset:

```sh
python3 scripts/build_linux_sh.py --output dist/linux.sh
sh -n dist/linux.sh
shellcheck linux.sh scripts/run_linux.sh dist/linux.sh
shfmt -d linux.sh scripts/run_linux.sh dist/linux.sh
python3 -m pytest -q
sh dist/linux.sh --smoke-test /tmp/cpit251-linux-smoke.json
```

Use a graphical desktop for the smoke command; it tests only disposable data.
The builder refuses to overwrite an existing output; choose another output name
when rebuilding. Identical runtime sources produce an identical script.

Release assets also include `CPIT251-Asset-Manager.zip` (full source, tests,
manuals and examples) and `SHA256SUMS`. After downloading all three to one folder:

```sh
sha256sum -c SHA256SUMS
```

The repository and release remain private; team members must accept a
collaborator invitation and sign in before downloading.

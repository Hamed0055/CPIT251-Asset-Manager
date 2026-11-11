#!/bin/sh
# Source checkout launcher. The GitHub release also provides a standalone linux.sh.
set -eu

project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
exec sh "$project_dir/scripts/run_linux.sh" "$@"

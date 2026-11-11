"""Exercise the delivered shell entry points through real subprocesses."""
import os
import subprocess
import sys

import pytest

from scripts.build_linux_sh import ROOT, build

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux shell launcher")


def run(script, cwd, *arguments, **overrides):
    env = os.environ.copy()
    env.update(PYTHON=sys.executable, PYTHONPATH="")
    env.update(overrides)
    return subprocess.run(["/bin/sh", str(script), *arguments], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=20, check=False)


def test_checkout_launcher_from_other_directory(tmp_path):
    result = run(ROOT / "linux.sh", tmp_path, "--help")
    assert result.returncode == 0 and "--database" in result.stdout and not result.stderr


def test_standalone_runs_without_source_checkout_and_cleans_up(tmp_path):
    folder = tmp_path / "download with spaces"
    folder.mkdir()
    script = build(folder / "linux.sh")
    temporary = tmp_path / "temporary files"
    temporary.mkdir()
    result = run(script, folder, "--help", TMPDIR=str(temporary))
    assert result.returncode == 0 and "--smoke-test" in result.stdout and not result.stderr
    assert not list(temporary.iterdir())
    assert script.stat().st_mode & 0o111


def test_argument_boundaries_and_error_status_preserved(tmp_path):
    script = build(tmp_path / "linux.sh")
    argument = "unknown argument with spaces ; $(touch SHOULD_NOT_EXIST) *"
    result = run(script, tmp_path, argument)
    assert result.returncode == 2
    assert argument in result.stderr
    assert not (tmp_path / "SHOULD_NOT_EXIST").exists()


@pytest.mark.parametrize("standalone", [False, True])
def test_missing_python_reports_useful_error(tmp_path, standalone):
    script = build(tmp_path / "linux.sh") if standalone else ROOT / "linux.sh"
    result = run(script, tmp_path, "--help", PYTHON="cpit251-python-does-not-exist")
    assert result.returncode == 1 and "Python 3.11+ is required" in result.stderr


def test_python_override_with_spaces(tmp_path):
    python = tmp_path / "python interpreter"
    python.symlink_to(sys.executable)
    script = build(tmp_path / "linux.sh")
    result = run(script, tmp_path, "--help", PYTHON=str(python))
    assert result.returncode == 0 and not result.stderr


def test_corrupt_embedded_archive_does_not_run(tmp_path):
    script = build(tmp_path / "linux.sh")
    text = script.read_text()
    text = text.replace('ARCHIVE_SHA256 = "', 'ARCHIVE_SHA256 = "broken-')
    script.write_text(text)
    result = run(script, tmp_path, "--help")
    assert result.returncode == 1 and "checksum failed" in result.stderr
    assert "usage:" not in result.stdout


def test_reproducible_build_and_existing_output_protected(tmp_path):
    first = build(tmp_path / "first.sh")
    second = build(tmp_path / "second.sh")
    assert first.read_bytes() == second.read_bytes()
    before = first.read_bytes()
    with pytest.raises(FileExistsError):
        build(first)
    assert first.read_bytes() == before

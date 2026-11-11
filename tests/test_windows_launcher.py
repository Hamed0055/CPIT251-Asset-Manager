"""Native cmd.exe launch checks; Linux cannot certify a Windows batch file."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Native Windows launcher")


def test_source_batch_launcher(tmp_path):
    env = os.environ.copy()
    env["PYTHON"] = sys.executable
    driver = tmp_path / "launch-test.cmd"
    driver.write_text(f'@echo off\ncall "{ROOT / "windows.bat"}" --help\nexit /b %errorlevel%\n')
    result = subprocess.run(["cmd.exe", "/d", "/c", str(driver)], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0 and "--database" in result.stdout and not result.stderr


def test_batch_missing_application(tmp_path):
    script = tmp_path / "windows.bat"
    script.write_bytes((ROOT / "windows.bat").read_bytes())
    result = subprocess.run(["cmd.exe", "/d", "/c", str(script)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == 1 and "Extract the complete Windows ZIP" in result.stderr

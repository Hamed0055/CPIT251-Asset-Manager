param(
    [string]$Python = "python",
    [switch]$SmokeTest
)
$ErrorActionPreference = "Stop"
$Project = Split-Path -Parent $PSScriptRoot
if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    throw "Run this build on Windows."
}

Push-Location -LiteralPath $Project
try {
    & $Python -c "import PyInstaller, tkinter, sqlite3; assert PyInstaller.__version__ == '6.22.2'; assert sqlite3.sqlite_version_info >= (3, 37)"
    if ($LASTEXITCODE -ne 0) {
        throw "Build requires PyInstaller 6.22.2, Tkinter and SQLite 3.37+."
    }

    & $Python -m PyInstaller --noconfirm --clean --onefile --windowed --name CPIT251-Asset-Manager --distpath dist --workpath build/windows --specpath build main.py
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $Executable = Join-Path $Project "dist/CPIT251-Asset-Manager.exe"
    if ($SmokeTest) {
        $Receipt = Join-Path $Project "dist/windows-smoke.json"
        if (Test-Path -LiteralPath $Receipt) { Remove-Item -LiteralPath $Receipt }
        $Process = Start-Process -FilePath $Executable -ArgumentList "--smoke-test `"$Receipt`"" -PassThru
        if (-not $Process.WaitForExit(120000)) {
            Stop-Process -Id $Process.Id -Force
            throw "The frozen GUI test did not finish within two minutes."
        }
        if (Test-Path -LiteralPath $Receipt) {
            $Result = Get-Content -Raw -LiteralPath $Receipt | ConvertFrom-Json
            Get-Content -LiteralPath $Receipt
        } else {
            throw "The frozen GUI test produced no receipt."
        }
        if ($Process.ExitCode -ne 0 -or -not $Result.passed -or -not $Result.frozen -or $Result.platform -ne "win32") {
            throw "The Windows executable failed its smoke test."
        }
    }
    $Launcher = Join-Path $Project "dist/windows.bat"
    Copy-Item -LiteralPath (Join-Path $Project "windows.bat") -Destination $Launcher -Force
    $Guide = Join-Path $Project "docs/WINDOWS_LAUNCHER.md"
    $Portable = Join-Path $Project "dist/CPIT251-Asset-Manager-Windows-x64.zip"
    Compress-Archive -LiteralPath @($Executable, $Launcher, $Guide) -DestinationPath $Portable -Force
    Write-Output "Executable: $Executable"
    Write-Output "Portable ZIP: $Portable"
} finally {
    Pop-Location
}

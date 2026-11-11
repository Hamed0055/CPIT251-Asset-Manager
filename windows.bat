@echo off
setlocal DisableDelayedExpansion
rem Run the portable executable when present, or the source checkout otherwise.
if exist "%~dp0CPIT251-Asset-Manager.exe" goto portable
if exist "%~dp0dist\CPIT251-Asset-Manager.exe" goto built
if not exist "%~dp0main.py" goto no_application
if defined PYTHON goto explicit_python
where python >nul 2>nul
if not errorlevel 1 goto system_python
where py >nul 2>nul
if not errorlevel 1 goto python_launcher
goto no_python

:portable
"%~dp0CPIT251-Asset-Manager.exe" %*
exit /b

:built
"%~dp0dist\CPIT251-Asset-Manager.exe" %*
exit /b

:explicit_python
"%PYTHON%" -c "import sys,sqlite3,tkinter; assert sys.version_info >= (3,11); assert sqlite3.sqlite_version_info >= (3,37)" >nul 2>nul
if errorlevel 1 goto no_python
"%PYTHON%" "%~dp0main.py" %*
exit /b

:system_python
python -c "import sys,sqlite3,tkinter; assert sys.version_info >= (3,11); assert sqlite3.sqlite_version_info >= (3,37)" >nul 2>nul
if errorlevel 1 goto try_launcher
python "%~dp0main.py" %*
exit /b

:try_launcher
where py >nul 2>nul
if errorlevel 1 goto no_python

:python_launcher
py -3 -c "import sys,sqlite3,tkinter; assert sys.version_info >= (3,11); assert sqlite3.sqlite_version_info >= (3,37)" >nul 2>nul
if errorlevel 1 goto no_python
py -3 "%~dp0main.py" %*
exit /b

:no_python
echo Python 3.11+, Tkinter and SQLite 3.37+ are required for source use. 1>&2
echo Use the portable Windows release to run without installing Python. 1>&2
exit /b 1

:no_application
echo Extract the complete Windows ZIP before running windows.bat. 1>&2
exit /b 1

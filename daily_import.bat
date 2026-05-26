@echo off
chcp 65001 >nul
cd /d "%~dp0"

set PATH=C:\Program Files\Git\cmd;%PATH%

echo [%date% %time%] Pulling latest collected data...
git pull origin master --ff-only
if %errorlevel% neq 0 (
    echo WARNING: git pull failed, using local data
)

echo [%date% %time%] Importing data to database...
".venv\Scripts\python.exe" run.py --import-data

echo [%date% %time%] Import complete

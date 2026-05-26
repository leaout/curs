@echo off
chcp 65001 >nul
echo [%date% %time%] Starting daily data import...

cd /d "%~dp0"

echo Pulling latest collected data...
git pull origin master --ff-only
if %errorlevel% neq 0 (
    echo WARNING: git pull failed, using local data
)

echo Importing data to database...
".venv\Scripts\python.exe" run.py --import-data

echo [%date% %time%] Import complete

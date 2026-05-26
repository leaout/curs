@echo off
chcp 65001 >nul
echo [%date% %time%] 开始每日数据导入...

cd /d "%~dp0"

echo 拉取最新采集数据...
git pull origin master --ff-only
if %errorlevel% neq 0 (
    echo 警告: git pull 失败，使用本地数据继续
)

echo 导入数据到数据库...
".venv\Scripts\python.exe" run.py --import-data

echo [%date% %time%] 导入完成

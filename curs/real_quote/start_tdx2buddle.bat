@echo off
set curs_path=E:\Quant.Pro\curs\curs
set script_path=%curs_path%\real_quote

echo start tdx_to_buddle
cd /d %script_path%
python tdx_to_buddle.py
echo done.

pause
@echo off
REM set curs_path=E:\Quant.Pro\curs\curs
REM set script_path=%curs_path%\real_quote

REM echo start tdx_to_buddle
REM cd /d %script_path%
python tdx_to_buddle.py --day_path D:/buddles/day --min_path D:/buddles/min
echo done.

pause
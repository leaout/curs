@echo off
set curs_path=E:\Quant.Pro\curs\curs
set script_path=%curs_path%\real_quote


schtasks /delete /tn start_tdx2buddle /f
schtasks /create /tn start_tdx2buddle /tr "'C:\Program Files\trading_day\trading_day_start.bat' %script_path%\start_tdx2buddle.bat" /sc WEEKLY /D MON,TUE,WED,THU,FRI /st 16:00


pause
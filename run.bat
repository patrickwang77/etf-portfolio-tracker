@echo off
title ETF 00997A Monitor Console
echo ===================================================
echo   00997A 群益美國增長主動式ETF 監控儀表板啟動器
echo ===================================================
echo.
echo 正在開啟瀏覽器前往 http://localhost:5000 ...
start "" "http://localhost:5000"
echo.
echo 正在啟動 Flask Web 伺服器...
python backend/app.py
pause

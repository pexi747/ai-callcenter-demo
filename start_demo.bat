@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
echo ======================================================
echo   AI Voice Call Center Simulator (Demo)
echo ======================================================
echo.
echo กำลังเริ่มต้นระบบจำลอง AI Call Center...
echo เปิดเบราว์เซอร์ใช้งานได้ที่: http://127.0.0.1:8088
echo.
echo กด Ctrl+C เพื่อหยุดการทำงาน
echo ======================================================
py -3.11 app.py
pause

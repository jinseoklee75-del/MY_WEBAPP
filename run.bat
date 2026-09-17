@echo off
chcp 65001 > nul
echo ========================================================
echo   TaskFlow - Python Flask 할일 관리 웹 애플리케이션
echo ========================================================
echo.
echo 웹 브라우저를 열고 Flask 서버를 구동합니다...
start http://localhost:5000
python app.py
pause

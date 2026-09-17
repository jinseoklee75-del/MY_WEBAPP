@echo off
chcp 65001 > nul
echo ========================================================
echo   AI 뉴스 브리핑 - 매경/한경 AI 기사 3줄 요약 (Flask)
echo ========================================================
echo.
echo 웹 브라우저를 열고 Flask 서버를 구동합니다...
start http://localhost:5000
python app.py
pause

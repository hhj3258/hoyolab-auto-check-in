@echo off
chcp 65001 >nul
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python이 설치되어 있지 않습니다. 아래 링크에서 설치 후 다시 실행해주세요.
    echo Python is not installed. Please install it from the link below and try again.
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)
python "%~dp0scripts\checkin.py"
pause

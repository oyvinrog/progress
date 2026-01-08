@echo off
REM Activate the virtual environment and run ActionDraw

cd /d "%~dp0"

if not exist ".venv" (
    echo Error: Virtual environment not found at .venv
    echo Please create it first with: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
    exit /b 1
)

call .venv\Scripts\activate.bat
python -m actiondraw %*

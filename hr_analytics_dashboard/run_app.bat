@echo off
REM One-click launcher for Windows
cd /d "%~dp0"
if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
streamlit run app.py

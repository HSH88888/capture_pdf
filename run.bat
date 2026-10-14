@echo off
REM Run Capture PDF with Python (keeps this window open if an error occurs)
cd /d "%~dp0"
python -m pip install --quiet pillow
python capture_pdf.py
if errorlevel 1 pause

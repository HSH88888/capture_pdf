@echo off
REM 파이썬으로 바로 실행 (콘솔 창 없이)
python -m pip install --quiet pillow
start "" pythonw capture_pdf.py

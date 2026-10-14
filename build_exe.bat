@echo off
REM Capture PDF 실행 파일(.exe) 만들기
REM 결과물: dist\CapturePDF.exe
chcp 65001 > nul
python -m pip install --upgrade pillow pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name CapturePDF capture_pdf.py
echo.
echo 완료: dist\CapturePDF.exe
pause

@echo off
REM Build CapturePDF.exe  ->  dist\CapturePDF.exe
cd /d "%~dp0"
python -m pip install --upgrade pillow pyinstaller
if errorlevel 1 goto fail
python -m PyInstaller --noconfirm --onefile --windowed --name CapturePDF capture_pdf.py
if errorlevel 1 goto fail
echo.
echo Done: dist\CapturePDF.exe
pause
exit /b 0
:fail
echo.
echo [ERROR] Build failed. See the messages above.
pause
exit /b 1

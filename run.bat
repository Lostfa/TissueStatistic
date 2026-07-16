@echo off
echo Activating conda environment boa...
call C:\Users\%USERNAME%\miniconda3\Scripts\activate.bat boa
if errorlevel 1 (
    echo Failed to activate conda environment boa
    pause
    exit /b 1
)

echo Environment activated successfully, starting application...
cd /d "%~dp0/html"
python -m uvicorn app:app --host 127.0.0.1 --port 8000

pause
@echo off
echo Installing required Python packages...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo Failed to install requirements. Please check for errors above.
    pause
    exit /b 1
)

echo.
echo All requirements installed successfully.
echo You can now run the main.pyw.
pause

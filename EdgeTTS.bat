@echo off
:: This batch file automates starting the EdgeTTS application.

ECHO Starting the application...

:: 1. Navigate to the script's directory.
:: %~dp0 expands to the path of the current batch file, making the script portable.
cd /d "%~dp0"

:: 2. Activate the Conda environment.
:: Using 'call' ensures that the script continues after the conda command is executed.
ECHO Activating Conda environment 'edgetts'...
call conda activate edgetts

:: Optional: Check if the conda environment was activated successfully.
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Failed to activate the 'edgetts' Conda environment.
    echo Please make sure Conda is installed and the environment exists.
    pause
    exit /b
)

:: 3. Start the Python web server in a new command window.
:: The new window is titled "EdgeTTS Server" and will remain open to show server logs.
ECHO Starting Python server (app.py)...
start "EdgeTTS Server" cmd /k python app.py

:: 4. Wait for the server to initialize.
:: This 5-second delay gives the server time to start up before the browser opens.
ECHO Waiting 5 seconds for the server to start...
timeout /t 5 /nobreak > nul

:: 5. Open the application URL in the default web browser.
ECHO Opening http://127.0.0.1:7860 in your browser...
start http://127.0.0.1:7860

echo.
ECHO Setup complete. The server is running in a separate window.

:: Exit this script.
exit /b

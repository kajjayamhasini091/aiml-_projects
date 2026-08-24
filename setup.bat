@echo off
title Razorpay AI Finance Controller - Full Setup
color 0A
echo.
echo ====================================================
echo   RAZORPAY AI FINANCE CONTROLLER - FULL SETUP
echo ====================================================
echo.

REM Step 1: Copy project to a clean path (no special chars)
echo [1/6] Copying project to clean path...
if exist "c:\Users\hasin\razorpay-ai-finance-controller" (
    rmdir /s /q "c:\Users\hasin\razorpay-ai-finance-controller"
)
xcopy /E /I /Y "c:\Users\hasin\Downloads\soa skill 1 & 2\razorpay-ai-finance-controller" "c:\Users\hasin\razorpay-ai-finance-controller" >nul 2>&1
echo    Done.
echo.

REM Step 2: Navigate to project
cd /d "c:\Users\hasin\razorpay-ai-finance-controller"
echo [2/6] Working directory: %CD%
echo.

REM Step 3: Rename dotfiles
echo [3/6] Setting up config files...
if exist dot_gitignore (
    ren dot_gitignore .gitignore
    echo    .gitignore created
)
if exist env.example (
    copy env.example .env.example >nul
    echo    .env.example created
)
echo.

REM Step 4: Install dependencies
echo [4/6] Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo    ERROR: pip install failed. Make sure Python and pip are installed.
    pause
    exit /b 1
)
echo    Dependencies installed.
echo.

REM Step 5: Generate sample data
echo [5/6] Generating sample data...
python data\generate_sample_data.py
echo.

REM Step 6: Run tests
echo [6/6] Running tests...
python -m pytest tests\ -v
echo.

echo ====================================================
echo   SETUP COMPLETE!
echo ====================================================
echo.
echo   Project location: c:\Users\hasin\razorpay-ai-finance-controller
echo.
echo   To start the application:
echo     1. Open TWO terminals in the project folder
echo     2. Terminal 1: uvicorn app.main:app --port 8000
echo     3. Terminal 2: streamlit run frontend\dashboard.py
echo.
echo   Or just run: start_app.bat
echo.
pause

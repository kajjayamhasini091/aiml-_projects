@echo off
title Deploy to GitHub
color 0E
echo.
echo ====================================================
echo   DEPLOYING RAZORPAY AI FINANCE CONTROLLER TO GITHUB
echo ====================================================
echo.

REM Step 1: Copy project to clean path
echo [1/7] Preparing project folder...
if exist "c:\Users\hasin\razorpay-ai-finance-controller" (
    rmdir /s /q "c:\Users\hasin\razorpay-ai-finance-controller"
)
xcopy /E /I /Y "c:\Users\hasin\Downloads\soa skill 1 & 2\razorpay-ai-finance-controller" "c:\Users\hasin\razorpay-ai-finance-controller" >nul 2>&1
echo    Done.
echo.

REM Step 2: Navigate
cd /d "c:\Users\hasin\razorpay-ai-finance-controller"
echo [2/7] Working in: %CD%
echo.

REM Step 3: Rename dotfiles
echo [3/7] Setting up dotfiles...
if exist dot_gitignore (
    ren dot_gitignore .gitignore
    echo    Renamed dot_gitignore to .gitignore
)
if exist env.example (
    copy env.example .env.example >nul
    del env.example
    echo    Renamed env.example to .env.example
)
echo.

REM Step 4: Install dependencies
echo [4/7] Installing Python dependencies...
pip install -r requirements.txt
echo.

REM Step 5: Generate sample data
echo [5/7] Generating sample data...
python data\generate_sample_data.py
echo.

REM Step 6: Run tests
echo [6/7] Running tests...
python -m pytest tests\ -v
echo.

REM Step 7: Git init and push
echo [7/7] Deploying to GitHub...
echo.

REM Remove old git if exists
if exist .git (
    rmdir /s /q .git
)

git init
git add .
git commit -m "feat: Razorpay AI Finance Controller - AI Buildathon 2026"
git branch -M main
git remote add origin https://github.com/kajjayamhasini091/aiml-_projects.git
git push -u origin main --force

echo.
echo ====================================================
echo   DEPLOYMENT COMPLETE!
echo ====================================================
echo.
echo   Your project is live at:
echo   https://github.com/kajjayamhasini091/aiml-_projects
echo.
echo   Next steps:
echo   1. Record your 5-minute pitch video
echo   2. Upload video to YouTube (unlisted)
echo   3. Add video link to README.md
echo   4. Submit to Razorpay Buildathon form
echo.
pause

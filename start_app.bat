@echo off
title Razorpay AI Finance Controller
color 0B
echo.
echo ====================================================
echo   RAZORPAY AI FINANCE CONTROLLER
echo ====================================================
echo.

cd /d "c:\Users\hasin\razorpay-ai-finance-controller"

REM Delete old database for fresh demo
if exist recon.db del recon.db

echo Starting API Server on http://localhost:8000 ...
start "Razorpay API" cmd /k "cd /d c:\Users\hasin\razorpay-ai-finance-controller && uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo Waiting for API to start...
timeout /t 4 >nul

echo Starting Dashboard on http://localhost:8501 ...
echo.
echo ====================================================
echo   API Docs:    http://localhost:8000/docs
echo   Dashboard:   http://localhost:8501
echo ====================================================
echo.

streamlit run frontend\dashboard.py

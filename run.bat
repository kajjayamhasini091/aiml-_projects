@echo off
echo ============================================
echo  Razorpay AI Finance Controller - Quick Start
echo ============================================
echo.

echo [1/4] Installing dependencies...
pip install -r requirements.txt
echo.

echo [2/4] Generating sample data...
python data\generate_sample_data.py
echo.

echo [3/4] Starting API Server (http://localhost:8000)...
start "API Server" cmd /c "uvicorn app.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 >nul

echo [4/4] Starting Dashboard (http://localhost:8501)...
echo.
echo ============================================
echo  API Docs:   http://localhost:8000/docs
echo  Dashboard:  http://localhost:8501
echo ============================================
echo.
streamlit run frontend\dashboard.py

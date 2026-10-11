@echo off
title IRSM Dashboard Sim
set PYTHONPATH=C:\Users\Lenovo\Desktop\hackathon research\simulation of iot\irsm-sim
cd /d "C:\Users\Lenovo\Desktop\hackathon research\simulation of iot\irsm-sim\backend"
echo Starting IRSM dashboard on http://127.0.0.1:8000 ...
python -m uvicorn app:app --host 127.0.0.1 --port 8000
pause

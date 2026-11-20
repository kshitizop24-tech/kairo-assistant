@echo off
title Kairo Assistant

cd /d "%~dp0"

start "" ollama serve

timeout /t 3 /nobreak >nul

python -m streamlit run app.py

pause
@echo off
title Schul-Scanner Pro (Browser)

REM --- FIX 1: Wechsel in das Verzeichnis, in dem die .bat liegt ---
cd /d "%~dp0"

echo =========================================
echo  🏫 Schul-Scanner Pro - Browser Version
echo =========================================
echo.

REM 1. Pruefen, ob Python installiert ist
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo FEHLER: Python wurde nicht gefunden!
    pause
    exit
)

REM 2. Virtuelle Umgebung erstellen
IF NOT EXIST "venv" (
    echo [1/3] Richte Programm zum ersten Mal ein...
    python -m venv venv
)

REM 3. Umgebung aktivieren
call venv\Scripts\activate

REM 4. Pakete installieren
echo [2/3] Pruefe Pakete...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1

REM 5. Streamlit starten mit Warnungs-Unterdrueckung
echo [3/3] Starte das Dashboard im Browser...
echo.
python -m streamlit run app.py --server.enableCORS false --server.enableXsrfProtection false

pause

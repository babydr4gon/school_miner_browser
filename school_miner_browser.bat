@echo off
title Schul-Scanner Pro (Browser)
echo =========================================
echo  🏫 Schul-Scanner Pro - Browser Version
echo =========================================
echo.

REM 1. Pruefen, ob Python installiert ist
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo FEHLER: Python wurde nicht gefunden!
    echo Bitte installiere Python von python.org und setze den Haken bei "Add Python to PATH".
    pause
    exit
)

REM 2. Virtuelle Umgebung erstellen (falls nicht vorhanden)
IF NOT EXIST "venv" (
    echo [1/3] Richte Programm zum ersten Mal ein (das dauert einen Moment)...
    python -m venv venv
)

REM 3. Umgebung aktivieren
call venv\Scripts\activate

REM 4. Pakete aktualisieren/installieren
echo [2/3] Pruefe auf Updates fuer benoetigte Pakete...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1

REM 5. Streamlit starten (mit dem Trick, der immer funktioniert)
echo [3/3] Starte das Dashboard im Browser...
echo.
python -m streamlit run app.py

pause

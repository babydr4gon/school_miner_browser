@echo off
title Schul-Scanner Pro (Browser)
cd /d "%~dp0"

echo =========================================
echo  🏫 school_miner - Browser Version
echo =========================================
echo.

REM --- 1. PROXY FIX ---
set NO_PROXY=localhost,127.0.0.1,::1
set no_proxy=localhost,127.0.0.1,::1

python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo FEHLER: Python wurde nicht gefunden!
    echo Bitte installiere Python von python.org und setze den Haken bei "Add Python to PATH".
    pause
    exit
)

REM 2. Virtuelle Umgebung erstellen
IF NOT EXIST "browservenv" (
    echo [1/3] Richte Programm zum ersten Mal ein...
    python -m venv browservenv
)

REM 3. Umgebung aktivieren
call browservenv\Scripts\activate

REM 4. Pakete aktualisieren/installieren
echo [2/3] Pruefe auf Updates fuer benoetigte Pakete...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt >nul 2>&1

REM --- 5. KONFIGURATION ERZWINGEN ---
IF NOT EXIST ".streamlit" mkdir .streamlit
(
echo [server]
echo port = 8501
echo address = "127.0.0.1"
echo headless = true
echo enableCORS = false
echo enableXsrfProtection = false
) > .streamlit\config.toml

echo [3/3] Starte Dashboard...
echo.

python -m streamlit run app.py


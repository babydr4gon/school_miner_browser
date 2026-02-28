#!/bin/bash

# --- 1. INS VERZEICHNIS WECHSELN ---
cd "$(dirname "$0")"

echo "========================================="
echo " 🏫 school_miner - Linux Version"
echo "========================================="
echo

# --- 2. PYTHON CHECK ---
if ! command -v python3 &> /dev/null; then
    echo "FEHLER: python3 wurde nicht gefunden. Bitte installiere Python."
    exit 1
fi

# --- 3. VIRTUAL ENV ---
if [ ! -d "browservenv" ]; then
    echo "[1/3] Ersteinrichtung der virtuellen Umgebung (venv)..."
    python3 -m venv browservenv
fi

# Umgebung aktivieren
source browservenv/bin/activate

# --- 4. REQUIREMENTS ---
echo "[2/3] Prüfe Abhängigkeiten..."
pip install --upgrade pip &> /dev/null
pip install -r requirements.txt &> /dev/null

# --- 5. STREAMLIT KONFIGURATION ---
# Wir erstellen den .streamlit Ordner und die config.toml
mkdir -p .streamlit
cat <<EOF > .streamlit/config.toml
[server]
port = 8501
address = "127.0.0.1"
headless = true
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false
EOF

echo "[3/3] Starte Dashboard..."
echo
echo "Falls der Browser nicht automatisch öffnet, gehe zu: http://127.0.0.1:8501"
echo "Nutze den 'Beenden'-Button in der App, um den Server sauber zu schließen."
echo

# --- 6. START ---
# Wir nutzen den Python-Interpreter aus dem venv
./browservenv/bin/python3 -m streamlit run app.py
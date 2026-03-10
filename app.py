import streamlit as st
import pandas as pd
import json
import os
import time
import re
import random
import sys
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
import shutil 
import webbrowser
import sys
import signal
import logging
import traceback

# Externe APIs & Tools
from google import genai
from openai import OpenAI
from ddgs import DDGS
import folium
from folium import Element
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim

# Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIG & CONSTANTS ---
CONFIG_FILE = "config.json"
DEFAULT_SCHULTYPEN = ["Grundschule", "Hauptschule", "Realschule", "Gymnasium", "Gesamtschule", "Förderschule", "Berufsschule", "Verbundschule", "Mittelstufenschule", "Oberstufengymnasium"]
DEFAULT_HARD_KEYWORDS = ["MINT", "Sport", "Musik", "Gesellschaftswissenschaften", "Sprachen", "bilingual", "themenorientiert", "Charakter", "Montessori", "Walldorf", "jahrgangsübergreifend", "altersübergreifend", "Ganztag"]
PRIORITY_LINKS_L1 = ["Schulprofil", "Schulprogramm", "Leitbild", "Über uns", "Unsere Schule", "Wir über uns"]
PRIORITY_LINKS_L2 = ["Leitbild", "Konzept", "Pädagogik", "Schwerpunkte", "Ganztag", "Angebote", "AGs", "Förderung"]
filename = "Karte.html"

st.set_page_config(page_title="school_miner ", page_icon="🏫", layout="wide")

# --- LOGGING SETUP ---
logging.basicConfig(
    filename='scanner_error.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- HELPER FUNCTIONS  ---


DEFAULT_CONFIG = {
    "INPUT_FILE": "schulen.xlsx",
    "OUTPUT_FILE": "schulen_ergebnisse.xlsx",
    "MAP_FILE": "schulen_karte.html",
    "MODEL_NAME": "gemini-2.0-flash-exp",  
    "MAP_DELAY": 1.7,  
    "COLUMN_NAME_IDX": 0,
    "COLUMN_ORT_IDX": 2,
    "GEMINI_MODEL": "gemini-2.0-flash-exp", 
    "OPENROUTER_MODEL": "meta-llama/llama-3.3-70b-instruct", 
    "GROQ_MODEL": "llama-3.3-70b-versatile",
    "WAIT_TIME": 2.0, 
    "SENSITIVITY": "normal", 
    "SCHULTYPEN_LISTE": DEFAULT_SCHULTYPEN,
    "KEYWORD_LISTE": DEFAULT_HARD_KEYWORDS,
    "AI_PRIORITY": ["openai", "gemini", "groq", "openrouter"],
    "MANUAL_RESUME_IDX": 0,
    "PROMPT_TEMPLATE": (
        "Du bist ein Schul-Analyst. Ich gebe dir Textauszüge von der Webseite.\n"
        "Fasse das pädagogische Konzept zusammen.\n"
        "Ignoriere Navigationstext.\n"
        "Maximal 3 Sätze.\n\n"
        "Text:\n{text}"
    ),
    
    "ERROR_MARKERS": ["Nicht gefunden", "Keine Daten", "KI-Fehler", "QUOTA", "Error", "Zu wenige Infos", "Strict Filter", "Nicht erreichbar"]
}

def load_config():
    """Lädt die Konfiguration und füllt fehlende Keys mit Defaults auf."""
    cfg = DEFAULT_CONFIG.copy()
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                # Werte mergen
                for k, v in loaded.items():
                    cfg[k] = v
            return cfg
        except Exception as e:
            st.error(f"Fehler beim Lesen der config.json: {e}")
            
            return cfg
            
    # Nur wenn die Datei gar nicht existiert: neu anlegen
    save_config(cfg)
    return cfg

def save_config(cfg):
    """Schreibt die Konfiguration physisch auf die Festplatte."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"❌ Fehler beim Speichern der Config: {e}")
        return False
            
# Pfad zur .env Datei explizit ermitteln 
basedir = os.path.abspath(os.path.dirname(__file__))
env_path = os.path.join(basedir, '.env')

# .env laden 
if os.path.exists(env_path):
    load_dotenv(env_path)
    
else:
    st.error(f"⚠️ Datei '.env' wurde nicht gefunden unter: {env_path}")

# Keys auslesen
gemini_key = os.getenv("GOOGLE_API_KEY")
openai_key = os.getenv("OPENAI_API_KEY")

# Kurzer Check im UI
if not gemini_key and not openai_key:
    st.warning("🔑 Keys wurden geladen, sind aber leer. Bitte prüfe die .env Datei.")
elif gemini_key:
    # Nur die ersten 4 Zeichen zeigen, um zu sehen ob er da ist
    st.sidebar.success(f"✅ Gemini Key geladen (Starts with: {gemini_key[:4]}...)")
    

# --- API CLIENT SETUP ---
def get_ai_client(provider, api_key):
    if not api_key: return None
    try:
        if provider == "gemini": return genai.Client(api_key=api_key)
        if provider == "openai": return OpenAI(api_key=api_key)
        if provider == "groq": return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
        if provider == "openrouter":
            return OpenAI(
                base_url="https://openrouter.ai/api/v1", 
                api_key=api_key,
                default_headers={"HTTP-Referer": "https://github.com/schul-scanner", "X-Title": "Schul-Scanner"}
            )
    except: return None
    return None


def check_environment():
    status = {"chrome": False, "driver": False, "msg": []}
    
    # Suche nach Browsern
    browser_names = ["google-chrome", "chrome", "chromium-browser", "chromium"]
    found_browser = any(shutil.which(b) is not None for b in browser_names)
    
    if found_browser:
        status["chrome"] = True
    else:
        status["msg"].append("❌ Kein Chrome/Chromium gefunden.")

    # Suche nach Driver
    driver_paths = ["/usr/bin/chromedriver", "/usr/lib/chromium-browser/chromedriver", "chromedriver"]
    found_driver = any(shutil.which(d) is not None or os.path.exists(d) for d in driver_paths)
    
    if found_driver:
        status["driver"] = True
    else:
        status["msg"].append("⚠️ Chromedriver nicht im Pfad (wird ggf. automatisch geladen).")
        
    return status
    
def sync_logic(existing_df, config):
    """Übernimmt EXAKT die funktionierende CLI-Logik für Streamlit."""
    if not os.path.exists(config["INPUT_FILE"]):
        st.warning(f"Datei {config['INPUT_FILE']} nicht gefunden.")
        return existing_df
    
    try:
        # WICHTIG: header=None, genau wie in der CLI!
        df_raw = pd.read_excel(config["INPUT_FILE"], header=None, engine='openpyxl')
        
        # Bestehende Schulen ermitteln (nur nach Name, wie in der CLI)
        if not existing_df.empty and 'schulname' in existing_df.columns:
            existing = set(existing_df['schulname'].astype(str).str.strip())
        else:
            existing = set()
        
        added_count = 0
        new_rows = []
        
        for _, row in df_raw.iterrows():
            # Prüfen, ob die Zeile lang genug ist 
            if len(row) <= max(config["COLUMN_NAME_IDX"], config["COLUMN_ORT_IDX"]): 
                continue
                
            n = str(row[config["COLUMN_NAME_IDX"]]).strip()
            ort = str(row[config["COLUMN_ORT_IDX"]]).strip()
            
            # exakte CLI-Bedingung:
            if len(n) > 4 and "schule" in n.lower() and "=" not in n and n not in existing:
                new_rows.append({
                    'schulname': n,
                    'ort': ort,
                    'webseite': "Nicht gefunden",
                    'schultyp': "",
                    'keywords': "",
                    'ki_zusammenfassung': "Keine Daten"
                })
                existing.add(n)
                added_count += 1
        
        if new_rows:
            df_new = pd.DataFrame(new_rows)
            updated_df = pd.concat([existing_df, df_new], ignore_index=True)
            updated_df = sanitize_dataframe(updated_df)
            st.toast(f"✅ {added_count} neue Schulen importiert!", icon="📥")
            return updated_df
        else:
            st.info("ℹ️ Keine neuen Einträge gefunden (alle schon vorhanden).")
            return existing_df
            
    except Exception as e:
        st.error(f"Fehler beim Synchronisieren: {e}")
        return existing_df

def save_dataframe(df, config):
    """Zentrale Speicherfunktion mit Backup-Logik für maximale Sicherheit."""
    output_file = config["OUTPUT_FILE"]
    try:
        # 1. Sicherheits-Backup der alten Datei erstellen
        if os.path.exists(output_file):
            try:
                shutil.copy(output_file, output_file + ".bak")
            except: pass 

        # 2. Daten bereinigen und speichern
        if 'sanitize_dataframe' in globals():
            df = sanitize_dataframe(df)
            
        df.to_excel(output_file, index=False, engine='openpyxl')
        return True
    except Exception as e:
        st.error(f"❌ Speicherfehler: {e}. Ist die Datei eventuell in Excel geöffnet?")
        # 3. Restore-Versuch bei Crash
        if os.path.exists(output_file + ".bak"):
            st.warning("Versuche Daten aus letztem Backup zu retten...")
            shutil.copy(output_file + ".bak", output_file)
        return False

def sanitize_dataframe(df):
    """Bereinigt Spaltennamen und stellt Pflichtfelder sicher."""
    # 1. Spaltennamen normalisieren (Kleinschreibung & Leerzeichen weg)
    df.columns = [str(c).strip().lower() for c in df.columns]
    
    # 2. Liste der Pflichtspalten, die die App erwartet
    required_columns = [
        'schulname', 'ort', 'webseite', 
        'schultyp', 'keywords', 'ki_zusammenfassung'
    ]
    
    # 3. Fehlende Spalten leer anlegen, damit kein KeyError mehr kommt
    for col in required_columns:
        if col not in df.columns:
            df[col] = ""
            
    return df
    
# --- SELENIUM DRIVER ---
def get_driver():
    """
    Initialisiert den Chrome/Chromium Treiber für Windows und Linux (inkl. Raspberry Pi).
    """
    chrome_options = Options()
    
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--log-level=3") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    
    # --- STRATEGIE 1: ChromeDriverManager (Standard für Windows/Mac) ---
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e_auto:
        # --- STRATEGIE 2: Feste Pfade  ---
        
        paths = [
            "/usr/bin/chromedriver",
            "/usr/lib/chromium-browser/chromedriver",
            "/usr/lib/chromium/chromedriver", # Alternative für manche Distributionen
            "/snap/bin/chromium.chromedriver"
        ]
        
        found_path = next((p for p in paths if os.path.exists(p)), None)
        
        try:
            if found_path:
                service = Service(executable_path=found_path)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Versuch 3: Einfach hoffen, dass 'chromedriver' in den Systemvariablen (PATH) ist
                driver = webdriver.Chrome(options=chrome_options)
        except Exception as e_sys:
            # Fehler, den wir in Streamlit abfangen können
            raise RuntimeError(
                f"Browser konnte nicht gestartet werden.\n\n"
                f"Fehler Auto-Mode: {e_auto}\n"
                f"Fehler System-Mode: {e_sys}\n\n"
                "Tipp für Linux/Pi: Führe 'sudo apt install chromium-chromedriver' aus."
            )

    if driver:
        driver.set_page_load_timeout(25)
        
    return driver

# --- CRAWLER LOGIC (CORE) ---
def search_ddg_robust(query):
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region='de-de', max_results=5, backend="api"))
            for res in results:
                url = res['href']
                if "wikipedia.org" in url or "facebook.com" in url or "instagram.com" in url: continue
                return url
        except: time.sleep(1.5)
    return None

def get_selenium_content(driver, url, wait_time=2.0):
    """Lädt die Seite, scrollt für Lazy-Loading und extrahiert Text/Links."""
    try:
        driver.get(url)
        
        # 1. Kurz warten für den initialen Load
        time.sleep(wait_time / 2)
        
        # 2. Einmal nach unten scrollen, um Lazy-Loading auszulösen
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # 3. Restliche Wartezeit absitzen, damit Menüs/Bilder nachladen können
        time.sleep(wait_time / 2)
        
        title = driver.title
        body = driver.find_element(By.TAG_NAME, "body").text
        links = []
        
        for elem in driver.find_elements(By.TAG_NAME, "a"):
            try: 
                href = elem.get_attribute("href")
                if href:  # Nur gültige Links speichern
                    links.append((href, elem.text.lower()))
            except: 
                continue
                
        return title, body, links
    except Exception as e: 
        return "", "", []

def find_school_type_in_text(text, type_list):
    """
    Sucht nach Schultypen, nutzt aber einen "Rückspiegel", 
    um typische False-Positives (z.B. "nach der Grundschule") auszufiltern.
    """
    found = set()
    
    # Typische Text-Fallen (Regex), die darauf hindeuten, dass eine andere Schule gemeint ist
    fallen = [
        r"nach\s+der\s+", 
        r"von\s+der\s+", 
        r"übergang\s+(von|aus)\s+(der)?\s*", 
        r"kooperation\s+mit\s+(der|einer)?\s*",
        r"schüler(innen)?\s+der\s+",
        r"abgänger(innen)?\s+der\s+"
    ]
    
    for styp in type_list:
        # Finde ALLE Vorkommen dieses Schultyps im Text
        matches = list(re.finditer(re.escape(styp), text, re.IGNORECASE))
        
        for match in matches:
            # Hole die 35 Zeichen VOR dem gefundenen Schultyp
            start_idx = max(0, match.start() - 35)
            context_before = text[start_idx:match.start()].lower()
            
            # Prüfe, ob eine der Fallen im Kontext davor auftaucht
            is_falle = any(re.search(falle, context_before) for falle in fallen)
            
            # WICHTIG: Wenn auch nur ein Vorkommen KEINE Falle ist, 
            # werten wir es als echten Treffer und können aufhören zu suchen!
            if not is_falle:
                found.add(styp)
                break 
                
    return list(found)

def validate_page_strict(text):
    text_sample = text[:10000]
    triggers = ["leitbild", "konzept", "schulprogramm", "schulprofil", "pädagogik"]
    if any(t in text_sample.lower() for t in triggers): return True
    patterns = [r"Wir\s+sind\s+eine", r"Unsere\s+ist\s+eine", r"Unsere\s+Schule", r"Wir\s+Schule", r"Die\s+Schule", r"Die\s+.{0,100}?\s+ist\s+eine"]
    for pat in patterns:
        if re.search(pat, text_sample, re.IGNORECASE): return True
    return False

def crawl_and_analyze(driver, school_input, school_ort, config):
    if school_input.startswith("http"):
        url = school_input; is_manual_url = True
    else:
        url = search_ddg_robust(f"{school_input} {school_ort} Startseite")
        is_manual_url = False

    if not url: return "Nicht gefunden", "", "", ""
    
    wait_time = config.get("WAIT_TIME", 2.0)
    title_main, text_main, links_main = get_selenium_content(driver, url, wait_time)
    
    if not text_main: return "Nicht erreichbar", "", "", ""
    
    if config["SENSITIVITY"] == "strict" and not is_manual_url:
        if not validate_page_strict(text_main): return url, "", "", ""
    
    found_types = find_school_type_in_text(title_main + "\n" + text_main, config["SCHULTYPEN_LISTE"])
    found_kws = set()
    
    # Zeichen-Limit auf 10.000 !
    chunks = [f"--- Seite 1 ({title_main}) ---\n{text_main[:10000]}"]
    
    def scan(txt):
        for k in config["KEYWORD_LISTE"]:
            if re.search(r'\b' + re.escape(k.lower()), txt.lower()): found_kws.add(k)

    scan(text_main)
    
    domain = urlparse(url).netloc
    l1_targets = []
    
    for href, txt in links_main:
        if not href: continue
        
        # absolute Links
        full_url = urljoin(url, href)
        
        if domain in urlparse(full_url).netloc:
            txt_low = txt.lower()
            if any(p.lower() in txt_low for p in PRIORITY_LINKS_L1):
                l1_targets.append(full_url)
            elif is_manual_url:
                blocklist = ["impressum", "datenschutz", "login", "anmelden", "kontakt", "sitemap"]
                if not any(b in txt_low for b in blocklist) and len(txt) > 2:
                    l1_targets.append(full_url)

    scan_list = list(dict.fromkeys(l1_targets))[:5]
    
    for l1 in scan_list:
        t1, text1, links1 = get_selenium_content(driver, l1, wait_time)
        if text1:
            scan(text1)
            chunks.append(f"--- {t1} ---\n{text1[:10000]}") # Auf 10.000 erhöht
            if not found_types: found_types.extend(find_school_type_in_text(text1, config["SCHULTYPEN_LISTE"]))
            
            if not is_manual_url:
                 l2_urls = []
                 for h, t in links1:
                     if h:
                         full_h = urljoin(l1, h)
                         if domain in urlparse(full_h).netloc and any(p.lower() in t for p in PRIORITY_LINKS_L2):
                             l2_urls.append(full_h)
                 
                 for l2 in list(dict.fromkeys(l2_urls))[:3]:
                    t2, text2, _ = get_selenium_content(driver, l2, wait_time)
                    if text2:
                        scan(text2)
                        chunks.append(f"--- {t2} ---\n{text2[:10000]}") # Auf 10.000 erhöht
                        
    schultyp_final = ", ".join(sorted(list(set(found_types))))
    return url, schultyp_final, ", ".join(sorted(list(found_kws))), "\n\n".join(chunks)

def is_entry_empty(entry, config):
    """
    Prüft, ob ein Eintrag bearbeitet werden muss. 
    Berücksichtigt dabei auch 'nan'-Strings aus Excel/Pandas.
    """
    # Bereinigt Werte von NaN und Leerzeichen
    def clean(val):
        v = str(val).strip().lower()
        return "" if v in ["nan", "none", "null", ""] else v

    schultyp = clean(entry.get('schultyp', ""))
    keywords = clean(entry.get('keywords', ""))
    ki = clean(entry.get('ki_zusammenfassung', ""))
    
    # Ist eines der Felder nach der Bereinigung leer?
    if not schultyp or not keywords or not ki:
        return True
        
    # Enthält der KI-Text einen Fehler-Marker?
    markers = [m.lower() for m in config.get("ERROR_MARKERS", [])]
    if any(m in ki for m in markers):
        return True
        
    return False
    
 #### -- KI ---

def ki_analyse(context_text, config, api_keys):
    if not context_text or len(context_text) < 50: return "Keine Daten"
    
    # Text bereinigen und das Limit auf fette 60.000 erhöhen
    clean_context = re.sub(r'\n\s*\n', '\n', context_text)
    prompt = config["PROMPT_TEMPLATE"].format(text=clean_context[:60000])

    # --- SCHRITT 1: PRIORITÄT DYNAMISCH ANPASSEN ---
    active_p = config.get("ACTIVE_PROVIDER", "Gemini").lower()
    # Wir kopieren die Liste, um das Original in der config nicht zu verändern
    priority_list = [p.lower() for p in config.get("AI_PRIORITY", ["gemini", "openai", "openrouter", "groq"])]
    
    # Wir schieben den aktiven Provider nach ganz vorne
    if active_p in priority_list:
        priority_list.remove(active_p)
    priority_list.insert(0, active_p)

    # --- SCHRITT 2: DIE SCHLEIFE DURCHLAUFEN ---
    for provider in priority_list:
        key = api_keys.get(provider)
        if not key: continue
        
        try:
            client = get_ai_client(provider, key)
            if not client: continue

            if provider == "openrouter":
                return "[Llama/Claude]: " + client.chat.completions.create(
                    model=config.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"), 
                    messages=[{"role": "user", "content": prompt}]
                ).choices[0].message.content.strip()

            elif provider == "openai":
                return "[OpenAI]: " + client.chat.completions.create(
                    model=config.get("OPENAI_MODEL", "gpt-4o-mini"), 
                    messages=[{"role": "user", "content": prompt}]
                ).choices[0].message.content.strip()

            elif provider == "gemini":
                return "[Gemini]: " + client.models.generate_content(
                    model=config.get("GEMINI_MODEL", "gemini-2.0-flash-exp"), 
                    contents=prompt
                ).text.strip()

            elif provider == "groq":
                return "[Groq]: " + client.chat.completions.create(
                    model=config.get("GROQ_MODEL", "llama-3.3-70b-versatile"), 
                    messages=[{"role": "user", "content": prompt}]
                ).choices[0].message.content.strip()
        except Exception as e:
            print(f"Fehler bei {provider}: {e}") 
            continue

    return "KI-Fehler (Alle Provider fehlgeschlagen)"

# --- MAP GENERATION ---

@st.cache_data(show_spinner=False)
def get_coordinates(name, ort, delay=1.5):
    """
    Holt die Koordinaten und speichert sie im Cache. 
    Pause nur bei echten API-Aufrufen um den MAP_DELAY Wert
    """
    geolocator = Nominatim(user_agent="schul_scanner_st_cache")
    try:
        clean_name = re.sub(r"\(.*?\)", "", name).strip()
        loc = geolocator.geocode(f"{clean_name}, {ort}, Germany", timeout=5)
        
        if loc:
            time.sleep(delay) # <-- Dynamische Pause
            return loc.latitude, loc.longitude, False
        
        time.sleep(delay) # <-- Dynamische Pause
        loc_city = geolocator.geocode(f"{ort}, Germany", timeout=5)
        if loc_city:
            lat = loc_city.latitude + random.uniform(-0.015, 0.015)
            lon = loc_city.longitude + random.uniform(-0.015, 0.015)
            time.sleep(delay) # <-- Dynamische Pause
            return lat, lon, True
            
    except Exception as e:
        print(f"Warnung bei {name}: {e}")
        
    return None, None, False


# --- MAP GENERATION ---
def generate_folium_map(data):
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)
    
    legend_html = '''
     <div style="position: fixed; bottom: 50px; right: 50px; width: 200px; height: 180px; border:2px solid grey; z-index:9999; font-size:14px; background-color:white; opacity:0.9; padding: 10px;">
     <b>Legende</b><br>
     <i style="color:purple" class="fa fa-map-marker"></i> Begabtenförderung<br>
     <i style="color:blue" class="fa fa-map-marker"></i> Gymnasium<br>
     <i style="color:green" class="fa fa-map-marker"></i> Gesamtschule<br>
     <i style="color:orange" class="fa fa-map-marker"></i> Mix (Gym/HR)<br>
     <i style="color:red" class="fa fa-map-marker"></i> Realschule<br>
     <i style="color:gray" class="fa fa-map-marker"></i> Grundschule<br>
     <i style="color:beige" class="fa fa-map-marker"></i> Sonstige/Förder<br>
     </div>
     '''
    m.get_root().html.add_child(Element(legend_html))

    progress_text = "Platziere Marker auf der Karte (nutze Cache, falls vorhanden)..."
    my_bar = st.progress(0, text=progress_text)
    total = len(data)
    
    for i, entry in enumerate(data):
        # in String umwandeln und Leerzeichen entfernen
        name = str(entry.get('schulname', '')).strip()
        ort = str(entry.get('ort', '')).strip()
        
        # Überspringen, wenn leer oder 'nan'
        if not name or name.lower() == 'nan': 
            my_bar.progress((i + 1) / total, text="Überspringe leeren Eintrag...")
            continue
            
        my_bar.progress((i + 1) / total, text=f"Platziere {name}...")
        
        # CACHE-ABFRAGE
        map_delay = st.session_state.config.get("MAP_DELAY", 1.5)
        lat, lon, is_approx = get_coordinates(name, ort, map_delay)
        
        if not lat or not lon: continue

        # DATEN VORBEREITEN 
        schultyp = str(entry.get('schultyp', 'Unbekannt'))
        ki = str(entry.get('ki_zusammenfassung', 'Keine Analyse'))
        kw = str(entry.get('keywords', '-'))
        st_lower = schultyp.lower()
        full_text_scan = (ki + " " + kw).lower()
        
        # Farb-Logik mit Wortstämmen für Beugungen
        trigger_stems = ["hochbegab", "begabung", "begabt", "akzeleration"]
        
        if any(stem in full_text_scan for stem in trigger_stems): 
            color = "purple"
        elif "gesamtschule" in st_lower: 
            color = "green"
        elif "gymnasium" in st_lower and ("haupt" in st_lower or "real" in st_lower or "verbund" in st_lower): 
            color = "orange"
        elif "gymnasium" in st_lower: 
            color = "blue"
        elif "realschule" in st_lower: 
            color = "red"
        elif "grundschule" in st_lower: 
            color = "gray"
        else: 
            color = "beige"
        
        # --- WEBSEITEN-LINK LOGIK ---
        web_link = entry.get('webseite', '')
        if web_link and web_link != "Nicht gefunden" and web_link.startswith("http"):
            link_html = f'<a href="{web_link}" target="_blank">Webseite öffnen</a>'
        else:
            link_html = '<span style="color:red; font-style:italic; font-size:11px;">(Keine Webseite hinterlegt)</span>'

        pos_hint = "<br><i style='color:red; font-size:10px'>(Position geschätzt)</i>" if is_approx else ""
        html = f"""
        <div style="font-family: Arial; width: 300px;">
            <h4>{name}</h4>
            <p style="color:grey; font-size:11px">{schultyp} {pos_hint}</p>
            <hr>
            <p><b>KW:</b> {kw}</p>
            <div style="max-height:100px;overflow-y:auto;background:#f9f9f9;padding:5px;font-size:11px;border:1px solid #eee;">{ki}</div>
            <br>{link_html}
        </div>
        """
        folium.Marker([lat, lon], popup=folium.Popup(html, max_width=350), icon=folium.Icon(color=color, icon="info-sign" if not is_approx else "question-sign")).add_to(m)
        
    my_bar.empty()
    
    # Karte lokal speichern
    try:
        m.save(filename)
        st.success(f"✅ Karte wurde erfolgreich unter **{os.path.abspath(filename)}** gespeichert.")
    except Exception as e:
        st.error(f"Fehler beim Speichern der HTML-Datei: {e}")
        
    return m

def sync_config():
    """Synchronisiert die Provider-Wahl und die Modellnamen."""
    st.session_state.config["ACTIVE_PROVIDER"] = st.session_state.provider_key
    st.session_state.config["GEMINI_MODEL"] = st.session_state.gemini_model_key
    st.session_state.config["OPENROUTER_MODEL"] = st.session_state.openrouter_model_key
    st.session_state.config["GROQ_MODEL"] = st.session_state.groq_model_key
    
    
    st.session_state.config["PROMPT_TEMPLATE"] = st.session_state.prompt_key
    kw_raw = st.session_state.keywords_key
    st.session_state.config["KEYWORD_LISTE"] = [k.strip() for k in kw_raw.split(",") if k.strip()]
    
    save_config(st.session_state.config)
    st.toast("Einstellungen gespeichert!", icon="🤖")

# --- MAIN APP LOGIC ---

def main():
    st.sidebar.title("🏫 school_miner")
    
    if 'config' not in st.session_state:
        st.session_state.config = load_config()
    
    if 'stop_scan' not in st.session_state:
        st.session_state.stop_scan = False

    config = st.session_state.config
    
    if "df" not in st.session_state:
        if os.path.exists(config["OUTPUT_FILE"]):
            # Normaler Start: Ergebnisdatei existiert bereits
            st.session_state.df = sanitize_dataframe(pd.read_excel(config["OUTPUT_FILE"]))
            
        elif os.path.exists(config["INPUT_FILE"]):
            # Erster Start: Nur Quelldatei da -> Wir erzwingen einen sauberen Sync 
            # und legen die Ergebnisdatei SOFORT physisch auf der Festplatte an!
            empty_df = pd.DataFrame(columns=['schulname', 'ort', 'webseite', 'schultyp', 'keywords', 'ki_zusammenfassung'])
            st.session_state.df = sync_logic(empty_df, config)
            save_dataframe(st.session_state.df, config)
            
        else:
            # Fallback: Weder Quelle noch Ergebnis da -> Leere Dummy-Datei anlegen
            st.session_state.df = pd.DataFrame(columns=['schulname', 'ort', 'webseite', 'schultyp', 'keywords', 'ki_zusammenfassung'])
            save_dataframe(st.session_state.df, config)
    
    # Systemcheck ---
    with st.sidebar.expander("🛠️ System-Status", expanded=True):
        env = check_environment()
        if env["chrome"]:
            st.success("Browser: Installiert ✅")
        else:
            st.error("Browser: Nicht gefunden! ❌")
            st.info("Tipp: 'sudo apt install chromium-browser' ausführen.")
            
        if env["driver"]:
            st.success("Driver: Bereit ✅")
        else:
            st.warning("Driver: Nutze Auto-Modus ⚙️")
    # --- FEHLER-PROTOKOLL (LOG) ---
    with st.sidebar.expander("📝 Fehler-Protokoll (Log)", expanded=False):
        log_file = "scanner_error.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    log_content = f.read()
                
                if log_content.strip():
                    st.text_area("Letzte Fehler:", value=log_content, height=200, disabled=True)
                    if st.button("🗑️ Log leeren", use_container_width=True):
                        open(log_file, 'w').close() # Datei leeren
                        st.success("Log wurde geleert!")
                        st.rerun()
                else:
                    st.info("Log ist leer. Bisher keine Fehler aufgetreten!")
            except Exception as e:
                st.error(f"Konnte Log nicht lesen: {e}")
        else:
            st.info("Keine Log-Datei vorhanden (bisher keine Fehler).")
    # CONFIG
    st.sidebar.title("⚙️ Einstellungen")
    
    # API Keys
    with st.sidebar.expander("🔑 API Keys", expanded=False):
        api_keys = {
            "openai": st.text_input("OpenAI Key", value=os.getenv("OPENAI_API_KEY", ""), type="password"),
            "gemini": st.text_input("Gemini Key", value=os.getenv("GEMINI_API_KEY", ""), type="password"),
            "groq": st.text_input("Groq Key", value=os.getenv("GROQ_API_KEY", ""), type="password"),
            "openrouter": st.text_input("OpenRouter Key", value=os.getenv("OPENROUTER_API_KEY", ""), type="password"),
        }
    
    with st.sidebar.expander("🤖 KI-Konfiguration", expanded=False):
    # 1. Auswahl des aktiven Anbieters
        providers = ["Gemini", "OpenRouter", "Groq"]
        current_p = config.get("ACTIVE_PROVIDER", "Gemini")
    
        st.radio(
        "Aktiver Anbieter:",
            options=providers,
            index=providers.index(current_p) if current_p in providers else 0,
            key="provider_key",
            on_change=sync_config
        )
    
        st.markdown("---")
        st.caption("Modell-Definitionen:")
    
    # 2. Eingabefelder für die spezifischen Modelle
    # Diese Felder laden ihre Werte aus der Config und speichern sie per Auto-Save
        st.text_input(
            "Gemini Modell:", 
            value=config.get("GEMINI_MODEL", "gemini-2.0-flash-exp"),
            key="gemini_model_key",
            on_change=sync_config
        )
    
        st.text_input(
        "OpenRouter Modell:", 
            value=config.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct"),
            key="openrouter_model_key",
            on_change=sync_config
        )
    
        st.text_input(
        "Groq Modell:", 
            value=config.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
            key="groq_model_key",
            on_change=sync_config
        )
     
    # Sensitivity
    config["SENSITIVITY"] = st.sidebar.selectbox("Sensibilität", ["normal", "strict"], index=0 if config["SENSITIVITY"]=="normal" else 1)
    
    # <-- NEU: Map Delay Slider -->
    config["MAP_DELAY"] = st.sidebar.slider(
        "Pause Kartengenerierung (Sek.)", 
        min_value=1.0, max_value=5.0, 
        value=float(config.get("MAP_DELAY", 1.5)), 
        step=0.1,
        help="Nominatim erlaubt max. 1 Anfrage/Sekunde. Bei Fehler 429 diesen Wert erhöhen."
    )
    
    # Keyword Editor
    with st.sidebar.expander("📝 Keywords"):
        st.text_area(
        "Keywords (kommagetrennt)", 
            value=", ".join(config["KEYWORD_LISTE"]),
            key="keywords_key",      # Interner Name
            on_change=sync_config    # Funktion startet bei Änderung
        )

    # Prompt
    with st.sidebar.expander("🤖 KI Prompt"):
        st.text_area(
        "Template", 
            value=config["PROMPT_TEMPLATE"], 
            height=150,
            key="prompt_key",        # Interner Name für den Wert
            on_change=sync_config    # Funktion startet bei Änderung
        )

#  ---Einstellungen Speichern---
        st.sidebar.markdown("---")
        if st.sidebar.button("🚀 Einstellungen speichern"):
        # WICHTIG: Nicht das Ergebnis der Funktion zuweisen!
            success = save_config(st.session_state.config) 
            if success:
                st.sidebar.success("💾 config.json aktualisiert!")
                time.sleep(0.5)
                st.rerun() # App neu laden, um Änderungen zu festigen

# --- Shutdown ---
        st.sidebar.markdown("---")
        if st.sidebar.button("🚀 Programm beenden"):
            st.sidebar.info("Schließe Server... Du kannst diesen Tab jetzt schließen.")
       # Kurze Verzögerung, damit die Meldung noch angezeigt wird
            time.sleep(1)
       # Sendet das Signal zum Beenden an den eigenen Prozess
            os.kill(os.getpid(), signal.SIGTERM)

    # 2. MAIN TABS
    tab1, tab2, tab3, tab4 = st.tabs(["📂 Daten & Upload", "🚀 Auto-Scan", "🗺️ Karte", "✏️ Einzeln bearbeiten"])

# --- TAB 1: DATA ---
    with tab1:
        st.header("Daten-Management & Vorschau")
        
        # 1. Datenvorschau
        st.subheader("📊 Aktuelle Ergebnisdatei")
        if st.session_state.df.empty:
            st.info("Noch keine Daten vorhanden. Bitte lade eine Quelldatei hoch oder synchronisiere.")
        else:
            st.dataframe(st.session_state.df, height=350, width="stretch")
            st.caption(f"Insgesamt {len(st.session_state.df)} Einträge geladen.")
        
        st.divider()
        
        # 2. Buttons & Uploads
        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("🔄 1. Daten synchronisieren")
            st.info(f"Sucht in '{config['INPUT_FILE']}' nach neuen Einträgen und hängt sie sicher an.")
            if st.button("Jetzt Synchronisieren", type="primary", use_container_width=True):
                st.session_state.df = sync_logic(st.session_state.df, config) 
                save_dataframe(st.session_state.df, config) 
                st.rerun()

        with col_b:
            st.subheader("📥 2. Neue Quelldatei laden")
            st.info(f"Ersetzt die lokale '{config['INPUT_FILE']}' für den nächsten Sync.")
            uploaded_file = st.file_uploader("Quelldatei (Excel, ohne Header)", type=["xlsx"])
            
            if uploaded_file and st.button("Quelldatei ersetzen", width="stretch"):
                try:
                    # Speichert die hochgeladene Datei physisch unter dem Namen der INPUT_FILE ab
                    with open(config["INPUT_FILE"], "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    st.success(f"✅ Datei '{config['INPUT_FILE']}' wurde aktualisiert! Du kannst nun links auf Synchronisieren klicken.")
                except Exception as e:
                    st.error(f"Fehler beim Speichern der Datei: {e}")

# --- TAB 2: SCANNER ---
    with tab2:
        st.header("Automatischer Crawler")
        
        # 1. Fortschritt-Management
        if 'df' not in st.session_state:
            st.session_state.df = load_data(config)
        if 'current_scan_idx' not in st.session_state:
        # Index aus der Config!
            st.session_state.current_scan_idx = config.get("AUTO_RESUME_IDX", 0)
        if 'scan_active' not in st.session_state:
            st.session_state.scan_active = False

        col_info, col_reset = st.columns([3, 1])
        with col_info:
            st.info(f"Nächster Schritt: Zeile {st.session_state.current_scan_idx + 1}")
        with col_reset:
            # Button zum Zurücksetzen des Fortschritts
            if st.button("🔄 Scan-Fortschritt auf 0 zurücksetzen", use_container_width=True):
                st.session_state.current_scan_idx = 0
                config["AUTO_RESUME_IDX"] = 0
                with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                st.toast("Fortschritt wurde für App und CLI auf 0 gesetzt!", icon="✅")
                st.rerun()

        # 2. Einstellungen        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            scan_mode = st.radio("Modus:", ["Nur neue/leere Einträge", "Alles überschreiben"], horizontal=True)
        
        with col2:
            st.write("") # Abstandshalter
            start_trigger = st.button("🚀 Start", type="primary", use_container_width=True)
            
        with col3:
            st.write("") # Abstandshalter
            # Der Stopp-Button setzt die Variable im Session State auf True
            if st.button("🛑 Stopp", type="secondary", use_container_width=True):
                st.session_state.stop_scan = True
                

        if start_trigger:
            # WICHTIG: Beim Starten setzen wir den Stopp-Schalter zurück auf False
            st.session_state.stop_scan = False
            
            df = st.session_state.df
            total_rows = len(df)
            
            progress_bar = st.progress(0)
            status_text = st.empty()

            driver = None
            try:
                status_text.write("🌐 Initialisiere Browser...")
                driver = get_driver()
                
                if driver:
                    for i in range(st.session_state.current_scan_idx, total_rows):
                        # HIER wird geprüft, ob der Stopp-Button gedrückt wurde
                        if st.session_state.get("stop_scan", False):
                            st.warning(f"⚠️ Scan bei Zeile {i+1} angehalten.")
                            save_dataframe(st.session_state.df, config) # <-- NEU: Sofort speichern!
                            break
                        
                        entry = df.iloc[i].to_dict()
                        progress_bar.progress((i + 1) / total_rows)

                        # Prüfen ob übersprungen werden soll
                        if scan_mode == "Nur neue/leere Einträge" and not is_entry_empty(entry, config):
                            st.session_state.current_scan_idx = i + 1
                            continue

                        status_text.write(f"🔍 Scanne ({i+1}/{total_rows}): **{entry['schulname']}**...")
                        
                        # --- DER SCHUTZSCHILD FÜR STREAMLIT ---
                        try:
                            # Crawling & Analyse
                            url, typ, kw, context = crawl_and_analyze(driver, entry['schulname'], entry['ort'], config)
                            
                            # KI-Teil 
                            ki_res = "Keine Daten"
                            if context:
                                ki_res = ki_analyse(context, config, api_keys)

                            # Daten zurückschreiben
                            st.session_state.df.at[i, 'webseite'] = url
                            st.session_state.df.at[i, 'schultyp'] = typ
                            st.session_state.df.at[i, 'keywords'] = kw
                            st.session_state.df.at[i, 'ki_zusammenfassung'] = ki_res

                        except Exception as inner_e:
                            # Loggen, Toast anzeigen und Fehler in die Zelle schreiben
                            error_msg = f"Fehler bei Zeile {i+1} ({entry.get('schulname')}):\n{traceback.format_exc()}"
                            logging.error(error_msg)
                            st.toast(f"⚠️ Fehler bei {entry.get('schulname')} - Schule wurde übersprungen!", icon="⚠️")
                            st.session_state.df.at[i, 'ki_zusammenfassung'] = "Absturz während des Scans"
                        # --- ENDE SCHUTZSCHILD ---

                        
                        # Fortschritt speichern
                        st.session_state.current_scan_idx = i + 1
                        
                        # Fortschritt sofort in die globale Config schreiben
                        config["AUTO_RESUME_IDX"] = i + 1
                        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                            json.dump(config, f, indent=4, ensure_ascii=False)

                        if (i + 1) % 5 == 0 or (i + 1) == total_rows:
                            save_dataframe(st.session_state.df, config)
                            st.toast(f"💾 Zwischenstand gespeichert ({i+1}/{total_rows})", icon="💾")

                    if st.session_state.current_scan_idx >= total_rows and not st.session_state.stop_scan:
                        st.success("🎉 Scan erfolgreich beendet!")
                        st.balloons()
                    
                else:
                    st.error("Browser konnte nicht gestartet werden.")

            except Exception as e:
                st.error(f"Fehler: {e}")
            finally:
                if driver:
                    driver.quit()
                status_text.empty()
                
    # --- TAB 3: MAP ---
    with tab3:
        st.header("Interaktive Karte")
        if st.button("🗺️ Karte generieren"):
            if st.session_state.df.empty:
                st.warning("Keine Daten.")
            else:
                with st.spinner("Geocoding läuft (kann dauern)..."):
                    folium_map = generate_folium_map(st.session_state.df.to_dict('records'))
                    st_folium(folium_map, width=1000, height=600)

# --- TAB 4: EDITOR ---
    with tab4:
        st.header("Manuelle Bearbeitung")
        
        if st.session_state.df.empty:
            st.warning("Keine Daten geladen. Bitte in Tab 1 eine Datei importieren.")
        else:
            # Auswahl der Schule
            idx = st.selectbox(
                "Schule zum Bearbeiten auswählen:", 
                range(len(st.session_state.df)), 
                format_func=lambda x: f"{st.session_state.df.iloc[x]['schulname']} ({st.session_state.df.iloc[x]['ort']})"
            )
            
            row = st.session_state.df.iloc[idx]
            
            col_e1, col_e2 = st.columns(2)
            
            with col_e1:
                new_name = st.text_input("Name der Schule", row["schulname"])
                new_ort = st.text_input("Ort", row["ort"])
                new_url = st.text_input("Webseite URL", row["webseite"])
                
                # Button-Reihe
                c1, c2 = st.columns(2)
                with c1:
                    is_valid = isinstance(new_url, str) and new_url.startswith("http")
                    if is_valid:
                        st.link_button("↗️ URL im Browser öffnen", new_url, width="stretch")
                    else:
                        st.button("↗️ URL öffnen", disabled=True, width="stretch")
                
                with c2:
                    if st.button("🔍 Deep Scan (KI)", width="stretch"):
                        
                        driver = get_driver()
                        if driver:
                           st.info(f"Analysiere: {new_url}")
                           u, t, k, c = crawl_and_analyze(driver, new_url, new_ort, config) 
                           st.session_state.df.at[idx, 'schultyp'] = t
                           st.session_state.df.at[idx, 'keywords'] = k
                        if c:
                             ai_res = ki_analyse(c, config, api_keys)
                             st.session_state.df.at[idx, 'ki_zusammenfassung'] = ai_res
                        driver.quit()
                        st.rerun()
                        
            
            with col_e2:
                new_typ = st.text_area("Schultyp", row.get("schultyp", ""))
                new_kw = st.text_area("Gefundene Keywords", row.get("keywords", ""))
                new_ki = st.text_area("KI Zusammenfassung", row.get("ki_zusammenfassung", ""), height=200)

            st.divider()
            
            # DER SPEICHER-BUTTON 
            if st.button("💾 Änderungen dauerhaft speichern", type="primary", width="stretch"):
                # 1. Update im Arbeitsspeicher (Session State)
                st.session_state.df.at[idx, 'schulname'] = new_name
                st.session_state.df.at[idx, 'ort'] = new_ort
                st.session_state.df.at[idx, 'webseite'] = new_url
                st.session_state.df.at[idx, 'schultyp'] = new_typ
                st.session_state.df.at[idx, 'keywords'] = new_kw
                st.session_state.df.at[idx, 'ki_zusammenfassung'] = new_ki
                
                # 2. Update auf der Festplatte
                if save_dataframe(st.session_state.df, config): 
                    st.toast("Erfolgreich gespeichert!", icon="✅")
                    time.sleep(1)
                    st.rerun()




if __name__ == "__main__":
    main()

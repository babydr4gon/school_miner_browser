import os
import pandas as pd
import json
import time
import warnings
import re
import random
import sys
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
import shutil 
import webbrowser
import logging
import traceback


from openai import OpenAI
from google import genai
from ddgs import DDGS
import folium
from folium import Element
from geopy.geocoders import Nominatim

# Selenium & Webdriver Manager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- SETUP & CONFIG ---
warnings.filterwarnings("ignore")
load_dotenv()

CONFIG_FILE = "config.json"

DEFAULT_SCHULTYPEN = ["Grundschule", "Hauptschule", "Realschule", "Gymnasium", "Gesamtschule", "Förderschule", "Berufsschule", "Verbundschule", "Mittelstufenschule", "Oberstufengymnasium"]
DEFAULT_HARD_KEYWORDS = ["MINT", "Sport", "Musik", "Gesellschaftswissenschaften", "Sprachen", "bilingual", "Lernlabor", "Lernloft", "Lernatelier", "themenorientiert", "Makerspace", "Multikultur", "Charakter", "Montessori", "Walldorf", "Jenaplan", "jahrgangsübergreifend", "altersübergreifend", "Ganztag"]

PRIORITY_LINKS_L1 = ["Schulprofil", "Profil", "Schulprogramm", "Leitbild", "Über uns", "Unsere Schule", "Wir über uns"]
PRIORITY_LINKS_L2 = ["Leitbild", "Konzept", "Pädagogik", "Schwerpunkte", "Ganztag", "Angebote", "AGs", "Förderung"]

DEFAULT_CONFIG = {
    "INPUT_FILE": "schulen.xlsx",
    "OUTPUT_FILE": "schulen_ergebnisse.xlsx",
    "MAP_FILE": "schulen_karte.html",
    "COLUMN_NAME_IDX": 0,
    "COLUMN_ORT_IDX": 2,
    "GEMINI_MODEL": "gemini-2.0-flash-exp", 
    "OPENROUTER_MODEL": "meta-llama/llama-3.3-70b-instruct", 
    "GROQ_MODEL": "llama-3.3-70b-versatile",
    "WAIT_TIME": 5.0, 
    "SENSITIVITY": "normal", 
    "SCHULTYPEN_LISTE": DEFAULT_SCHULTYPEN,
    "KEYWORD_LISTE": DEFAULT_HARD_KEYWORDS,
    "AI_PRIORITY": ["openai", "gemini", "groq", "openrouter"],
    "MANUAL_RESUME_IDX": 0,
    "PROMPT_TEMPLATE": (
        "Du bist ein Analyst für Schulprofile. Analysiere den folgenden Webseiten-Text. Erstelle eine Zusammenfassung in exakt 2 bis 3 Sätzen. Text: {text}"
    ),
    
    "ERROR_MARKERS": ["Nicht gefunden", "Keine Daten", "KI-Fehler", "QUOTA", "Error", "Zu wenige Infos", "Strict Filter", "Nicht erreichbar"]
}

# --- LOGGING SETUP ---
logging.basicConfig(
    filename='scanner_error.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for k, v in loaded.items(): cfg[k] = v
        except: pass
    return cfg

def save_config_to_file(cfg):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        print("💾 Config gespeichert.")
    except Exception as e:
        print(f"❌ Fehler beim Speichern der Config: {e}")

CONFIG = load_config()

def open_browser_search(query):
    """
    Versucht, Chrome/Chromium zu öffnen (Linux/Windows).
    Fallback auf Standard-Browser.
    """
    url = f"https://duckduckgo.com/?q={query}"
    
   
    browsers_to_try = []
    if sys.platform.startswith("linux"):
        browsers_to_try = ['chromium-browser', 'chromium', 'google-chrome']
    elif sys.platform.startswith("win"):
        browsers_to_try = ['google-chrome', 'chrome'] 
    
    # Versuch 1: Spezifische Browser
    for b in browsers_to_try:
        try:
            webbrowser.get(b).open(url)
            return
        except: continue
            
    # Versuch 2: Standard-Browser (Fallback)
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"   ⚠️ Konnte Browser nicht öffnen: {e}")

# --- API CLIENT SETUP ---
clients = {}
keys = {
    "gemini": os.getenv("GEMINI_API_KEY"),
    "openai": os.getenv("OPENAI_API_KEY"),
    "openrouter": os.getenv("OPENROUTER_API_KEY"),
    "groq": os.getenv("GROQ_API_KEY")
}
status_flags = {k: bool(v) for k, v in keys.items()}

if status_flags["gemini"]: clients["gemini"] = genai.Client(api_key=keys["gemini"])
if status_flags["openai"]: clients["openai"] = OpenAI(api_key=keys["openai"])
if status_flags["groq"]: clients["groq"] = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=keys["groq"])
if status_flags["openrouter"]:
    clients["openrouter"] = OpenAI(
        base_url="https://openrouter.ai/api/v1", 
        api_key=keys["openrouter"],
        default_headers={"HTTP-Referer": "https://github.com/schul-scanner", "X-Title": "Schul-Scanner"}
    )

def print_system_status():
    print("\n🔌 SYSTEM-CHECK API KEYS:")
    for service, active in status_flags.items():
        print(f"   • {service.title()}: {'✅' if active else '❌'}")
    print(f"   • Sensibilität: {CONFIG['SENSITIVITY'].upper()}")
    print("-" * 30)

# --- SELENIUM DRIVER ---

def get_driver():
    print("   🔌 Starte Browser-Engine...", end="\r")

    chrome_options = Options()
    # "--headless=new" scheinbar stabiler als das alte "--headless"
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--window-size=1920,1080")
    # Unterdrückt unnötige USB-Fehlermeldungen in der Konsole
    chrome_options.add_argument("--log-level=3") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = None
    
    # --- VERSUCH 1: Automatisch (Standard für Windows/Mac) ---
    try:
        # Versucht, den Treiber passend zum installierten Chrome herunterzuladen
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e_auto:
        # --- VERSUCH 2: System-Pfad (Fallback für Linux) ---
        
        try:
            # Liste typischer Pfade auf Linux
            paths = [
                "/usr/bin/chromedriver",
                "/usr/lib/chromium-browser/chromedriver",
                "/snap/bin/chromium.chromedriver"
            ]
            
            found = next((p for p in paths if os.path.exists(p)), None)
            
            if found:
                service = Service(executable_path=found)
                driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Letzter Versuch: 'chromedriver' im globalen PATH ?
                driver = webdriver.Chrome(options=chrome_options)
                
        except Exception as e_sys:
            print("\n\n❌ FEHLER: Konnte keinen Chrome-Treiber starten.")
            print("   Bitte sicherstellen, dass Google Chrome oder Chromium installiert ist.")
            print(f"   Fehler Auto-Mode: {e_auto}")
            print(f"   Fehler System-Mode: {e_sys}")
            print("\n   Tipp für Raspberry Pi: 'sudo apt install chromium-chromedriver'")
            return None

    if driver:
        driver.set_page_load_timeout(20) # 20 Sek Timeout
        print("   ✅ Browser-Engine bereit.   ")
        
    return driver

# --- DATA MANAGEMENT ---

def load_data():
    data = []
    # Versuch 1: Hauptdatei laden
    if os.path.exists(CONFIG["OUTPUT_FILE"]):
        try: 
            data = pd.read_excel(CONFIG["OUTPUT_FILE"]).to_dict('records')
        except Exception as e: 
            print(f"⚠️ Hauptdatei beschädigt oder leer ({e}). Versuche Backup...")
            
    # Versuch 2: Backup laden, falls Hauptdatei leer/kaputt
    if not data and os.path.exists(CONFIG["OUTPUT_FILE"] + ".bak"):
        try:
            print("🔄 RESTORE: Stelle Daten aus Backup wieder her!")
            shutil.copy(CONFIG["OUTPUT_FILE"] + ".bak", CONFIG["OUTPUT_FILE"])
            data = pd.read_excel(CONFIG["OUTPUT_FILE"]).to_dict('records')
        except Exception as e:
            print(f"❌ Auch Backup konnte nicht geladen werden: {e}")

    return data

def save_data(data):
    try:
        # 1. Sicherheits-Backup der alten Datei erstellen 
        if os.path.exists(CONFIG["OUTPUT_FILE"]):
            try:
                shutil.copy(CONFIG["OUTPUT_FILE"], CONFIG["OUTPUT_FILE"] + ".bak")
            except: pass # Wenn Backup fehlschlägt, ist das kein Beinbruch
        
        # 2. Neue Datei schreiben
        pd.DataFrame(data).to_excel(CONFIG["OUTPUT_FILE"], index=False)
    except Exception as e:
        print(f"❌ KRITISCHER FEHLER beim Speichern: {e}")
        # Versuchen, wenigstens das Backup zurückzuspielen
        if os.path.exists(CONFIG["OUTPUT_FILE"] + ".bak"):
            print("   -> Stelle alte Version wieder her, um Datenverlust zu minimieren.")
            shutil.copy(CONFIG["OUTPUT_FILE"] + ".bak", CONFIG["OUTPUT_FILE"])

def sync_with_source(current_data):
    print("\n🔄 Sync mit Ursprungsdatei...")
    if not os.path.exists(CONFIG["INPUT_FILE"]): 
        print(f"❌ Datei {CONFIG['INPUT_FILE']} fehlt.")
        return current_data
        
    try:
        df_raw = pd.read_excel(CONFIG["INPUT_FILE"], header=None)
        
        # Aktuelle Daten temporär in einen DataFrame wandeln
        df_current = pd.DataFrame(current_data) if current_data else pd.DataFrame(columns=['schulname', 'ort', 'schultyp', 'keywords', 'webseite', 'ki_zusammenfassung'])
        
        # Composite Key (Name + Ort) aufbauen
        if not df_current.empty:
            existing_keys = set(zip(
                df_current['schulname'].astype(str).str.strip().str.lower(),
                df_current['ort'].astype(str).str.strip().str.lower()
            ))
        else:
            existing_keys = set()
            
        new_rows = []
        for _, row in df_raw.iterrows():
            if len(row) <= max(CONFIG["COLUMN_NAME_IDX"], CONFIG["COLUMN_ORT_IDX"]): continue
            
            name = str(row[CONFIG["COLUMN_NAME_IDX"]]).strip()
            ort = str(row[CONFIG["COLUMN_ORT_IDX"]]).strip()
            key = (name.lower(), ort.lower())
            
            # Überprüfen, ob die Schule neu ist
            if len(name) > 4 and "schule" in name.lower() and "=" not in name and key not in existing_keys:
                new_rows.append({
                    'schulname': name, 'ort': ort,
                    'schultyp': "", 'keywords': "", 
                    'webseite': "Nicht gefunden", 'ki_zusammenfassung': "Keine Daten"
                })
                existing_keys.add(key)
                
        # Zusammenführen via pd.concat
        if new_rows:
            df_new = pd.DataFrame(new_rows)
            df_final = pd.concat([df_current, df_new], ignore_index=True)
            
            # Zurück in die Listen-Struktur für die weitere Verarbeitung schreiben
            current_data.clear()
            current_data.extend(df_final.to_dict('records'))
            save_data(current_data)
            print(f"✅ {len(new_rows)} neue Schulen angefügt.")
        else:
            print("ℹ️ Keine neuen Einträge gefunden.")
            
    except Exception as e: 
        print(f"❌ Sync-Fehler: {e}")
        
    return current_data

# --- CRAWLER LOGIC ---

def search_ddg_robust(query, max_retries=3):
    """Sucht URL. Filtert Wikipedia explizit raus."""
    for attempt in range(max_retries):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, region='de-de', max_results=5, backend="api"))
            
            for res in results:
                url = res['href']
                # FILTER
                if "wikipedia.org" in url or "facebook.com" in url or "instagram.com" in url:
                    continue
                return url
        except: time.sleep(1.5)
    return None

def get_selenium_content(driver, url, wait_time=2.0):
    """Lädt die Seite, scrollt für Lazy-Loading und extrahiert Text/Links (auch versteckte!)."""
    try:
        driver.get(url)
        time.sleep(wait_time / 2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time / 2)
        
        title = driver.title
        body = driver.find_element(By.TAG_NAME, "body").text
        links = []
        
        for elem in driver.find_elements(By.TAG_NAME, "a"):
            try: 
                href = elem.get_attribute("href")
                
                #  textContent liest auch eingeklappte Dropdown-Menüs!
                link_text = elem.get_attribute("textContent")
                
                # alls textContent unerwartet leer ist
                if not link_text:
                    link_text = elem.text
                    
                if href and link_text: 
                    # keine Leerzeichen/Zeilenumbrüchen
                    clean_text = " ".join(link_text.split()).lower()
                    links.append((href, clean_text))
            except: 
                continue
                
        return title, body, links
    except Exception as e: 
        return "", "", []

def find_school_type_in_text(text):
    """
    Sucht nach Schultypen mit einem "Rückspiegel", 
    um False-Positives (z.B. "nach der Grundschule") auszufiltern.
    Greift direkt auf die globale CONFIG zu.
    """
    found = set()
    
    # Typische Text-Fallen, die darauf hindeuten, dass eine andere Schule gemeint ist
    fallen = [
        r"nach\s+der\s+", 
        r"von\s+der\s+", 
        r"über\s+die\s+"
        r"über\s+Ihre\s+"
        r"übergang\s+(von|aus)\s+(der)?\s*", 
        r"kooperation\s+mit\s+(der|einer)?\s*",
        r"schüler(innen)?\s+der\s+",
        r"abgänger(innen)?\s+der\s+"
    ]
    
    for styp in CONFIG["SCHULTYPEN_LISTE"]:
        # Finde ALLE Vorkommen dieses Schultyps im Text
        matches = list(re.finditer(re.escape(styp), text, re.IGNORECASE))
        
        for match in matches:
            # Hole die 35 Zeichen VOR dem gefundenen Schultyp
            start_idx = max(0, match.start() - 35)
            context_before = text[start_idx:match.start()].lower()
            
            # Prüfe, ob eine der Fallen im Kontext davor auftaucht
            is_falle = any(re.search(falle, context_before) for falle in fallen)
            
            # Wenn auch nur ein Vorkommen KEINE Falle ist, 
            # ist es ein echter Treffer -> speichern und zum nächsten Typ wechseln!
            if not is_falle:
                found.add(styp)
                break 
                
    return list(found)

def validate_page_strict(text):
    """
    Der TÜV-Modus: Prüft, ob es sich wirklich um eine offizielle Schulwebseite handelt.
    Kriterien: Spezielle Phrasen oder Keywords.
    """
    text_sample = text[:10000] # Wir prüfen die ersten 10.000 Zeichen
        
    # 1. Hard Keywords (reichen alleine aus)
    triggers = ["leitbild", "konzept", "schulprogramm", "schulprofil", "pädagogik"]
    if any(t in text_sample.lower() for t in triggers):
        return True

    # 2. Satzfragmente (Flexibel mit Regex)
    
    # "Wir sind eine..." (z.B. "Wir sind eine offene Ganztagsschule")
    # \s+ erlaubt beliebige Leerzeichen/Tabs
    if re.search(r"Wir\s+sind\s+eine", text_sample, re.IGNORECASE):
        return True
        
     # "Wir sind eine..." (z.B. "Wir sind eine offene Ganztagsschule")
    # \s+ erlaubt beliebige Leerzeichen/Tabs
    if re.search(r"Unsere\s+ist\s+eine", text_sample, re.IGNORECASE):
        return True
        
     # "Wir sind eine..." (z.B. "Wir sind eine offene Ganztagsschule")
    # \s+ erlaubt beliebige Leerzeichen/Tabs
    if re.search(r"Unsere\s+Schule", text_sample, re.IGNORECASE):
        return True
        
    # "Wir sind eine..." (z.B. "Wir sind eine offene Ganztagsschule")
    # \s+ erlaubt beliebige Leerzeichen/Tabs
    if re.search(r"Wir\s+Schule", text_sample, re.IGNORECASE):
        return True    
    
    # "Wir sind eine..." (z.B. "Wir sind eine offene Ganztagsschule")
    # \s+ erlaubt beliebige Leerzeichen/Tabs
    if re.search(r"Die\s+Schule", text_sample, re.IGNORECASE):
        return True

    # "Die ... ist eine ..." (z.B. "Die Goetheschule ist eine Grundschule")
    # .{0,100}? erlaubt bis zu 100 Zeichen zwischen "Die" und "ist eine" (für Name + Adjektive)
    if re.search(r"Die\s+.{0,100}?\s+ist\s+eine", text_sample, re.IGNORECASE):
        return True
        
    return False

def crawl_and_analyze(driver, school_input, school_ort):
    if school_input.startswith("http"):
        url = school_input
        is_manual_url = True 
    else:
        url = search_ddg_robust(f"{school_input} {school_ort} Startseite")
        is_manual_url = False

    if not url: return "Nicht gefunden", "", "", ""
    
    print(f"      -> URL: {url} {'(Deep Scan)' if is_manual_url else ''}")
    
    wait_time = CONFIG.get("WAIT_TIME", 2.0)
    title_main, text_main, links_main = get_selenium_content(driver, url, wait_time)
    
    if not text_main: return "Nicht erreichbar", "", "", ""
    
    if CONFIG["SENSITIVITY"] == "strict" and not is_manual_url:
        is_valid = validate_page_strict(text_main)
        if not is_valid:
            print("      🛑 Strict Mode: Seite abgelehnt.")
            return url, "", "", ""
            
    found_types = find_school_type_in_text(title_main + "\n" + text_main)
    found_kws = set()
    chunks = [f"--- Seite 1 ({title_main}) ---\n{text_main[:2500]}"]
    
    def scan(txt):
        for k in CONFIG["KEYWORD_LISTE"]:
            if re.search(r'\b' + re.escape(k.lower()), txt.lower()): found_kws.add(k)

    scan(text_main)
    
    domain = urlparse(url).netloc
    l1_targets = []
    
    for href, txt in links_main:
        if not href: continue
        
        # absolute Links (https://.../profil)
        full_url = urljoin(url, href)
        
        
        if domain in urlparse(full_url).netloc:
            txt_low = txt.lower()
            if any(p.lower() in txt_low for p in PRIORITY_LINKS_L1):
                l1_targets.append(full_url) # WICHTIG: Die volle URL speichern!
            elif is_manual_url:
                blocklist = ["impressum", "datenschutz", "login", "anmelden", "kontakt", "sitemap"]
                if not any(b in txt_low for b in blocklist) and len(txt) > 2:
                    l1_targets.append(full_url)

    scan_list = list(dict.fromkeys(l1_targets))[:5]
    
    for l1 in scan_list:
        print(f"      -> Scan Deep: {l1}") # (Nur für CLI wichtig)
        t1, text1, links1 = get_selenium_content(driver, l1, wait_time)
        if text1:
            scan(text1)
            chunks.append(f"--- {t1} ---\n{text1[:2500]}")
            if not found_types: found_types.extend(find_school_type_in_text(text1))
            
            if not is_manual_url:
                 l2_urls = []
                 for h, t in links1:
                     if h:
                         # TRICK auch für Level 2 anwenden!
                         full_h = urljoin(l1, h)
                         if domain in urlparse(full_h).netloc and any(p.lower() in t for p in PRIORITY_LINKS_L2):
                             l2_urls.append(full_h)
                 
                 for l2 in list(dict.fromkeys(l2_urls))[:3]:
                    t2, text2, _ = get_selenium_content(driver, l2, wait_time)
                    if text2:
                        scan(text2)
                        chunks.append(f"--- {t2} ---\n{text2[:2500]}")

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
    
    #  Ist eines der Felder nach der Bereinigung leer?
    if not schultyp or not keywords or not ki:
        return True
        
    # Enthält der KI-Text einen Fehler-Marker?
    markers = [m.lower() for m in config.get("ERROR_MARKERS", [])]
    if any(m in ki for m in markers):
        return True
        
    return False

# --- KI ---

def ki_analyse(context_text):
    if not context_text or len(context_text) < 50: return "Keine Daten"
    
    # 1. Text bereinigen 
    clean_context = re.sub(r'\n\s*\n', '\n', context_text)
    
    # 2. Limit vervierfachen! (60.000 Zeichen statt 15.000)
    prompt = CONFIG["PROMPT_TEMPLATE"].format(text=clean_context[:60000])

    for provider in CONFIG["AI_PRIORITY"]:
        provider = provider.lower()
        if not status_flags.get(provider, False): continue
        try:
            if provider == "openrouter":
                return "[Llama/Claude]: " + clients["openrouter"].chat.completions.create(model=CONFIG["OPENROUTER_MODEL"], messages=[{"role": "user", "content": prompt}]).choices[0].message.content.strip()
            elif provider == "openai":
                return "[OpenAI]: " + clients["openai"].chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]).choices[0].message.content.strip()
            elif provider == "gemini":
                return "[Gemini]: " + clients["gemini"].models.generate_content(model=CONFIG["GEMINI_MODEL"], contents=prompt).text.strip()
            elif provider == "groq":
                return "[Groq]: " + clients["groq"].chat.completions.create(model=CONFIG["GROQ_MODEL"], messages=[{"role": "user", "content": prompt}]).choices[0].message.content.strip()
        except: continue
    return "KI-Fehler"

# --- MAPPING ---

def generate_map(data):
    print("\n🗺️  Erstelle Landkarte (mit Fallback-Suche)...")
    
    # User-Agent muss eindeutig sein
    geolocator = Nominatim(user_agent=f"schul_scanner_{int(time.time())}")
    
    # Karte zentrieren (Deutschland Mitte)
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6) 
    
    # 1. LEGENDE 
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

    count = 0
    missing_count = 0
    
    print("   (Dieser Schritt kann dauern, um die OSM-Server nicht zu überlasten...)")

    for i, entry in enumerate(data):
        name = entry.get('schulname', ''); ort = entry.get('ort', '')
        
        # NEUER FILTER: Ignoriere nur Einträge komplett ohne Namen
        if not name: 
            continue
        
        try:
            # --- GEOCODING STRATEGIE ---
            lat, lon = None, None
            is_approx = False
            
            # Versuch 1: Exakte Suche (Schule + Ort)
            clean_name = re.sub(r"\(.*?\)", "", name).strip()
            query = f"{clean_name}, {ort}, Germany"
            loc = geolocator.geocode(query, timeout=10)
            
            if loc:
                lat, lon = loc.latitude, loc.longitude
            else:
                # Versuch 2: NUR ORT (Fallback)
                loc_city = geolocator.geocode(f"{ort}, Germany", timeout=10)
                if loc_city:
                    lat = loc_city.latitude
                    lon = loc_city.longitude
                    lat += random.uniform(-0.015, 0.015) 
                    lon += random.uniform(-0.015, 0.015)
                    is_approx = True
            
            if not lat or not lon:
                print(f"   ❌ Ort nicht gefunden: {ort} (Schule: {name})")
                missing_count += 1
                continue

            # --- DATEN VORBEREITEN ---
            schultyp = str(entry.get('schultyp', 'Unbekannt'))
            ki = str(entry.get('ki_zusammenfassung', 'Keine Analyse'))
            kw = str(entry.get('keywords', '-'))
            st_lower = schultyp.lower()
            full_text_scan = (ki + " " + kw).lower()
        
            # Farb-Logik 
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
                link_html = f'<a href="{web_link}" target="_blank" style="background-color:#007bff;color:white;padding:3px 8px;text-decoration:none;border-radius:3px;font-size:11px">Webseite öffnen</a>'
            else:
                link_html = '<span style="color:red; font-style:italic; font-size:11px;">(Keine Webseite hinterlegt)</span>'
            
            # --- POPUP HTML ---
            pos_hint = "<br><i style='color:red; font-size:10px'>(Position geschätzt/Stadtmitte)</i>" if is_approx else ""
            
            html = f"""
            <div style="font-family: Arial; width: 300px;">
                <h4>{name}</h4>
                <p style="color:grey; font-size:11px">{schultyp} {pos_hint}</p>
                <hr>
                <p><b>KW:</b> {kw}</p>
                <div style="max-height:150px;overflow-y:auto;background:#f9f9f9;padding:5px;font-size:11px;border:1px solid #eee;">
                    {ki}
                </div>
                <br>
                {link_html}
            </div>
            """
            
            # Marker setzen
            icon_type = "info-sign" if not is_approx else "question-sign"
            folium.Marker(
                [lat, lon], 
                popup=folium.Popup(html, max_width=350), 
                icon=folium.Icon(color=color, icon=icon_type)
            ).add_to(m)
            
            count += 1
            
            # Fortschritt alle 50 Schulen anzeigen
            if count % 50 == 0:
                print(f"   ... {count} Schulen platziert ...")
                
            # WICHTIG: Höflichkeitspause für OSM (sonst blockieren sie dich)
            time.sleep(2.2) 
            
        except Exception as e:
            # Fehler ausgeben, statt pass
            print(f"   ⚠️ Fehler bei {name}: {e}")
            pass

    m.save(CONFIG["MAP_FILE"])
    print(f"\n✅ Karte gespeichert: '{CONFIG['MAP_FILE']}'")
    print(f"   📊 Ergebnis: {count} platziert, {missing_count} ohne Ort.")

# --- MENU HELPERS ---

def manage_list_setting(key_name, display_name):
    while True:
        current_list = CONFIG[key_name]
        print(f"\n⚙️ {display_name} ({len(current_list)} Einträge)")
        print(f"   Auszug: {', '.join(current_list[:5])}...")
        print("   [+] Hinzufügen | [-] Löschen | [*] Neu schreiben | [B] Zurück")
        opt = input("   👉 Aktion: ").strip().lower()
        if opt == "b": break
        elif opt == "+":
            add = input("   Neuer Eintrag (Komma für mehrere): ")
            new_items = [x.strip() for x in add.split(",") if x.strip()]
            CONFIG[key_name] = list(set(current_list + new_items))
        elif opt == "-":
            for idx, val in enumerate(current_list): print(f"   {idx+1}: {val}")
            rem = input("   Nummer zum Löschen: ").strip()
            if rem.isdigit():
                idx = int(rem) - 1
                if 0 <= idx < len(current_list): CONFIG[key_name].pop(idx)
        elif opt == "*":
            if input("   ⚠️ Sicher? (j/n): ").lower() == "j":
                new_full = input("   Neue Liste (kommagetrennt): ")
                CONFIG[key_name] = [x.strip() for x in new_full.split(",") if x.strip()]
        save_config_to_file(CONFIG)

def menu_settings():
    global CONFIG
    while True:
        print("\n⚙️ EINSTELLUNGEN")
        print(f"1: Input Datei    [{CONFIG['INPUT_FILE']}]")
        print(f"2: Schultypen     ({len(CONFIG['SCHULTYPEN_LISTE'])})")
        print(f"3: Keywords       ({len(CONFIG['KEYWORD_LISTE'])})")
        print(f"4: KI-Priorität   {CONFIG['AI_PRIORITY']}")
        print(f"5: Prompt Text")
        print(f"6: Sensibilität   [{CONFIG['SENSITIVITY'].upper()}]")
        print("7: Zurück")
        
        c = input("👉 Wahl: ").strip()
        if c == "1": CONFIG["INPUT_FILE"] = input("Datei: ")
        elif c == "2": manage_list_setting("SCHULTYPEN_LISTE", "Schultypen")
        elif c == "3": manage_list_setting("KEYWORD_LISTE", "Keywords")
        elif c == "4": 
            inp = input("Neue Reihenfolge: ")
            if inp: CONFIG["AI_PRIORITY"] = [x.strip().lower() for x in inp.split(",")]
        elif c == "5":
            print(f"\nPrompt:\n{CONFIG['PROMPT_TEMPLATE']}")
            new_p = input("Neuer Text (Enter = behalten): ")
            if len(new_p) > 10: CONFIG["PROMPT_TEMPLATE"] = new_p
        elif c == "6":
            print("\nModus wählen:")
            print("  normal = Akzeptiert alle gefundenen Seiten")
            print("  strict = Prüft auf 'Wir sind eine...' / 'Leitbild' etc.")
            new_s = input(f"  Aktuell: {CONFIG['SENSITIVITY']} -> Neu (normal/strict): ").strip().lower()
            if new_s in ["normal", "strict"]: CONFIG["SENSITIVITY"] = new_s
        elif c == "7": save_config_to_file(CONFIG); break
        save_config_to_file(CONFIG)

# --- RUNNERS ---

def run_auto_scan(data):
    print(f"\n🤖 AUTO-SCAN V13.1 (Safe Mode) | Sensibilität: {CONFIG['SENSITIVITY'].upper()}")
    
    start_idx = CONFIG.get("AUTO_RESUME_IDX", 0)
    if start_idx >= len(data): start_idx = 0
    
    print(f"ℹ️ Start bei Zeile {start_idx + 1} von {len(data)}. Drücke STRG+C zum Pausieren.")
    
    driver = get_driver()
    unsaved_changes = False 
    
    try:
        for i in range(start_idx, len(data)):
            entry = data[i]
            CONFIG["AUTO_RESUME_IDX"] = i
            
            if not is_entry_empty(entry, CONFIG):
                continue
            
            print(f"\n[{i+1}/{len(data)}] {entry['schulname']}...")
            
            # --- DER SCHUTZSCHILD: Jeder einzelne Scan wird abgesichert ---
            try:
                url, typ, kw, ctx = crawl_and_analyze(driver, entry['schulname'], entry['ort'])
                
                entry['webseite'] = url; entry['schultyp'] = typ; entry['keywords'] = kw
                unsaved_changes = True

                print(f"      -> Typ: {typ if typ else '-'}")
                print(f"      -> KW:  {kw if kw else '-'}")

                if (typ or kw) and ctx:
                    if CONFIG["SENSITIVITY"] == "strict" and not ctx:
                        entry['ki_zusammenfassung'] = "Zu wenige Infos (Strict Filter)"
                    else:
                        print("      🧠 Kontext gefunden -> KI...")
                        entry['ki_zusammenfassung'] = ki_analyse(ctx)
                else:
                    entry['ki_zusammenfassung'] = "Zu wenige Infos (Strict Filter)" if CONFIG["SENSITIVITY"] == "strict" else "Keine relevanten Daten gefunden"
                
            except Exception as inner_e:
                # Fehler abfangen, ins Log schreiben und einfach weitermachen!
                print(f"      ⚠️ Fehler bei dieser Schule! Überspringe... (Siehe Log)")
                error_msg = f"Fehler bei Index {i} ({entry.get('schulname')}):\n{traceback.format_exc()}"
                logging.error(error_msg)
                
                # Wir markieren den Eintrag als fehlerhaft, damit wir ihn später filtern können
                entry['ki_zusammenfassung'] = "Absturz während des Scans" 
                continue # Springt sofort zur nächsten Schule
            # --- ENDE SCHUTZSCHILD ---

            if (i + 1) % 10 == 0:
                print("      💾 Zwischenspeicherung (Backup & Save)...")
                save_data(data)
                save_config_to_file(CONFIG)
                unsaved_changes = False
            
    except KeyboardInterrupt:
        print("\n🛑 PAUSE durch Benutzer! Speichere den exakten Stand...")
        save_data(data)
        save_config_to_file(CONFIG)
        unsaved_changes = False
    except Exception as fatal_e:
        
        print(f"\n🚨 KRITISCHER FEHLER! Skript wurde abgebrochen. Details im Log.")
        logging.critical(f"Kritischer Systemabsturz:\n{traceback.format_exc()}")
    finally:
        if unsaved_changes:
            print("💾 Letzte Änderungen werden gespeichert...")
            save_data(data)
        
        if CONFIG.get("AUTO_RESUME_IDX", 0) >= len(data) - 1:
            CONFIG["AUTO_RESUME_IDX"] = 0
            
        save_config_to_file(CONFIG)
        if driver: driver.quit()

def run_manual_review(data):
    # Lade aktuellen Startpunkt aus der Config
    start_idx = CONFIG.get("MANUAL_RESUME_IDX", 0)
    
    # Falls der Index ungültig ist (z.B. Liste wurde kleiner), auf 0 setzen
    if start_idx >= len(data): start_idx = 0

    print(f"\n🕵️ MANUELLE KONTROLLE (Lückenfüller)")
    print(f"ℹ️  Start bei Zeile {start_idx + 1} von {len(data)}.")
    if start_idx > 0:
        print(f"   (Nutze Option [7], um wieder ganz von vorne zu beginnen)")
    
    driver = None
    found_count = 0
    
    try:
        for i in range(start_idx, len(data)):
            entry = data[i]
            
            # Index für den nächsten Start merken & speichern
            CONFIG["MANUAL_RESUME_IDX"] = i
                        
            # --- TRIGGER LOGIK ---
            ki_text = str(entry.get('ki_zusammenfassung', ''))
            typ_text = str(entry.get('schultyp', ''))
            keyw_text = str(entry.get('keywords', ''))
            is_error_ki = any(m in ki_text for m in CONFIG["ERROR_MARKERS"])
            is_empty_ki = len(ki_text) < 10
            is_empty_typ = len(typ_text) < 3
            
            if not is_error_ki and not is_empty_ki and not is_empty_typ:
                continue

            found_count += 1
            
            
            # --- 3. ANZEIGE ---
            print(f"\n[{i+1}/{len(data)}] 🏫 {entry['schulname']} ({entry['ort']})")
            print(f"   URL:  {entry.get('webseite', 'N/A')}")
            print(f"   Typ:  {typ_text if len(typ_text) > 2 else '❌ FEHLT'}")
            print(f"   Keywords:  {keyw_text if len(keyw_text) > 2 else '❌ FEHLT'}")
            
            # Statusanzeige für KI-Text
            if any(m in ki_text for m in CONFIG["ERROR_MARKERS"]):
                print(f"   KI:   ⚠️ {ki_text}")
            elif len(ki_text) < 10:
                print("   KI:   ❌ FEHLT / LEER")
            else:
                print(f"   KI:   {ki_text[:50]}...")
            
            #Browser zur Kontrolle öffnen    
            open_browser_search(f"{entry['schulname']} {entry['ort']} Startseite")
            
            # --- 4. INTERAKTION ---
            while True:
                print("\n   [1] Auto-Scan (Komplett neu suchen)")
                print("   [2] KI-Check wiederholen (Bypass Strict Filter)")
                print("   [3] URL Paste (Link manuell setzen)")
                print("   [4] Typ manuell nachtragen")
                print("   [5] Keywords manuell nachtragen")
                print("   [6] Skip (Diesen Eintrag überspringen)")
                print("   [7] Reset des Indexes. Suche beginnt wieder oben in der Liste)")
                print("   [8] Exit (Zurück zum Menü)")
                
                c = input("   👉 Wahl: ").strip()
                
                if c == "1":
                    if not driver: driver = get_driver()
                    url, typ, kw, ctx = crawl_and_analyze(driver, entry['schulname'], entry['ort'])
                    entry['webseite'] = url; entry['schultyp'] = typ; entry['keywords'] = kw
                    entry['ki_zusammenfassung'] = ki_analyse(ctx) if ctx else "Nicht gefunden"
                    save_data(data); break 

                elif c == "2":
                    curr = entry.get('webseite', '')
                    u = input("   🔗 URL (Enter = behalten): ").strip()
                    target_url = u if u.startswith("http") else curr
                    if target_url and target_url != "Nicht gefunden":
                        if not driver: driver = get_driver()
                        t, text, _ = get_selenium_content(driver, target_url)
                        entry['ki_zusammenfassung'] = ki_analyse(text[:15000]) if text else "Inhalt leer"
                        save_data(data)
                    break

                elif c == "3": # URL Paste (Via Deep-Scan)
                    u = input("   🔗 URL eingeben: ").strip()
                    if u.startswith("http"):
                        if not driver: driver = get_driver()
                        
                        print(f"   🤖 Starte Deep-Scan für: {u}")
                        # Wir übergeben die URL direkt als erstes Argument.
                        
                        url, typ, kw, ctx = crawl_and_analyze(driver, u, entry['ort'])
                        
                        # Ergebnisse übernehmen
                        entry['webseite'] = url
                        
                        # Nur überschreiben, wenn auch was gefunden wurde, sonst behalten was da war
                        if typ: entry['schultyp'] = typ
                        if kw: entry['keywords'] = kw
                        
                        if ctx:
                            print("   🧠 Kontext gefunden (Startseite + Unterseiten). Sende an KI...")
                            entry['ki_zusammenfassung'] = ki_analyse(ctx)
                            print("   ✅ Analyse erfolgreich.")
                        else:
                            print("   ⚠️ URL geladen, aber 'crawl_and_analyze' hat keine Inhalte validiert.")
                            print("      (Möglicherweise hat der Strict-Filter den Ort nicht im Impressum gefunden)")
                            entry['ki_zusammenfassung'] = "Inhalt abgelehnt (Strict Filter)"
                        
                        save_data(data)
                    break
                elif c == "4":
                    new_typ = input(f"   ✍️ Typ ({entry.get('schultyp')}): ").strip()
                    if new_typ: entry['schultyp'] = new_typ
                    
                    save_data(data); break
                
                elif c == "5":
                    new_kw = input(f"Keywords ({entry.get('keywords')}): ").strip()
                    if new_kw: entry['keywords'] = new_kw
                    
                    save_data(data); break

                elif c == "6": # SKIP
                    print("   ⏭️ Merke Position und gehe weiter...")
                    save_config_to_file(CONFIG) # Position sichern
                    break
                
                elif c == "8": # EXIT
                    save_config_to_file(CONFIG)
                    return 

                elif c == "7": # RESET
                    CONFIG["MANUAL_RESUME_IDX"] = 0
                    save_config_to_file(CONFIG)
                    print("   ♻️ Index zurückgesetzt. Beim nächsten Start geht es bei 1 los.")

        # Wenn wir am Ende der Liste angekommen sind
        print("\n✅ Ende der Liste erreicht.")
        CONFIG["MANUAL_RESUME_IDX"] = 0
        save_config_to_file(CONFIG)

    except KeyboardInterrupt:
        save_config_to_file(CONFIG)
        print("\n🛑 Pause. Position gespeichert.")
    finally:
        if driver: driver.quit()


def run_single_edit(data):
    print("\n✏️ EINZELNE ZEILE BEARBEITEN")
    row = input("👉 Zeilennummer (aus Excel/Liste): ").strip()
    if not row.isdigit(): return
    idx = int(row) - 2 # Header ist Zeile 1, Index start bei 0
    
    if 0 <= idx < len(data):
        e = data[idx]
        print(f"\nGewählt: {e['schulname']} ({e['ort']})")
        print(f"URL: {e.get('webseite')}")
        print(f"Typ: {e.get('schultyp')}")
        print(f"Keywords:{e.get('keywords')}")
        
        
        # Browser öffnen
        open_browser_search(f"{e['schulname']} {e['ort']}")

        print("\n[1] Auto-Scan")
        print("[2] URL manuell eingeben")
        print("[3] Daten manuell editieren (Typ/Keywords)")
        print("[4] Zurück")
        
        c = input("👉 Wahl: ").strip()
        driver = None
        
        try:
            if c == "1" or c == "2":
                driver = get_driver() # Brauchen wir nur hier

            if c == "1":
                url, typ, kw, ctx = crawl_and_analyze(driver, e['schulname'], e['ort'])
                e['webseite'] = url; e['schultyp'] = typ; e['keywords'] = kw
                if ctx: e['ki_zusammenfassung'] = ki_analyse(ctx)
                
            elif c == "2":
                u = input("URL: ").strip()
                if u.startswith("http"):
                    e['webseite'] = u
                    t, text, _ = get_selenium_content(driver, u)
                    e['schultyp'] = ", ".join(find_school_type_in_text(text))
                    if text: e['ki_zusammenfassung'] = ki_analyse(text[:15000])

            elif c == "3":
                new_typ = input(f"Schultyp ({e.get('schultyp')}): ").strip()
                if new_typ: e['schultyp'] = new_typ
                
                # Keywords anpassen
                new_kw = input(f"Keywords ({e.get('keywords')}): ").strip()
                if new_kw: e['keywords'] = new_kw
                
                print("💾 Daten aktualisiert.")

            save_data(data)
            
        finally:
            if driver: driver.quit()
    else:
        print("❌ Ungültige Zeilennummer.")

def main():
    print_system_status()
    while True:
        data = load_data()
        if not data and os.path.exists(CONFIG["INPUT_FILE"]): data = sync_with_source([])
        if data:
            for d in data:
                if 'schultyp' not in d: d['schultyp'] = ""
                if 'keywords' not in d: d['keywords'] = ""
            save_data(data)

        done = sum(1 for x in data if str(x.get('ki_zusammenfassung')) not in ["Keine Daten", "Keine relevanten Daten gefunden", "", "Zu wenige Infos (Strict Filter)"])
        print(f"\n--- SCANNER V13.0 (National/Strict) | Fertig: {done}/{len(data)} ---")
        print("1️⃣ Auto-Scan")
        print("2️⃣ Manuelle Kontrolle")
        print("3️⃣ Einzelne Zeile")
        print("4️⃣ Karte erstellen")
        print("5️⃣ Sync mit Input-Datei")
        print("6️⃣ Einstellungen")
        print("7️⃣ Beenden")
        
        try:
            c = input("\n👉 Wahl: ").strip()
            if c == "1": run_auto_scan(data)
            elif c == "2": run_manual_review(data)
            elif c == "3": run_single_edit(data)
            elif c == "4": generate_map(data)
            elif c == "5": data = sync_with_source(data)
            elif c == "6": menu_settings()
            elif c == "7": break
        except KeyboardInterrupt:
            print("\n(Im Hauptmenü: '7' zum Beenden)")

if __name__ == "__main__":
    main()

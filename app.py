import streamlit as st
import pandas as pd
import json
import os
import time
import re
import random
import shutil
from urllib.parse import urlparse
from dotenv import load_dotenv

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
DEFAULT_HARD_KEYWORDS = ["MINT", "Sport", "Musik", "Gesellschaftswissenschaften", "Sprachen", "bilingual", "themenorientiert", "Makerspace", "Charakter", "Montessori", "Walldorf", "jahrgangsübergreifend", "altersübergreifend", "Ganztag"]
PRIORITY_LINKS_L1 = ["Schulprofil", "Schulprogramm", "Leitbild", "Über uns", "Unsere Schule", "Wir über uns"]
PRIORITY_LINKS_L2 = ["Leitbild", "Konzept", "Pädagogik", "Schwerpunkte", "Ganztag", "Angebote", "AGs", "Förderung"]
filename = "Karte.html"

st.set_page_config(page_title="school_miner ", page_icon="🏫", layout="wide")

# --- HELPER FUNCTIONS  ---

@st.cache_data
def load_config():
    cfg = {
        "INPUT_FILE": "schulen.xlsx",
        "OUTPUT_FILE": "schulen_ergebnisse.xlsx",
        "GEMINI_MODEL": "gemini-2.0-flash-exp", 
        "OPENROUTER_MODEL": "meta-llama/llama-3.3-70b-instruct", 
        "GROQ_MODEL": "llama-3.3-70b-versatile",
        "SENSITIVITY": "normal", 
        "SCHULTYPEN_LISTE": DEFAULT_SCHULTYPEN,
        "KEYWORD_LISTE": DEFAULT_HARD_KEYWORDS,
        "AI_PRIORITY": ["openai", "gemini", "groq", "openrouter"],
        "PROMPT_TEMPLATE": (
            "Du bist ein Schul-Analyst. Ich gebe dir Textauszüge von der Webseite.\n"
            "Fasse das pädagogische Konzept zusammen.\n"
            "Ignoriere Navigationstext.\n"
            "Maximal 3 Sätze.\n\n"
            "Text:\n{text}"
        ),
        "ERROR_MARKERS": ["Nicht gefunden", "Keine Daten", "KI-Fehler", "QUOTA", "Error", "Zu wenige Infos", "Strict Filter", "Nicht erreichbar"]
    }
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
    except Exception as e:
        st.error(f"Fehler beim Speichern der Config: {e}")

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
    
# --- SELENIUM DRIVER ---
def get_driver():
    """
    Initialisiert den Chrome/Chromium Treiber für Windows und Linux (inkl. Raspberry Pi).
    """
    chrome_options = Options()
    # Wichtig für Server/Raspberry Pi ohne Monitor
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
        # --- STRATEGIE 2: Feste Pfade (Speziell für Linux / Raspberry Pi / Debian) ---
        # Auf dem Pi wird der Treiber meist über apt installiert (chromium-chromedriver)
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
            # Wir werfen hier einen Fehler, den wir in Streamlit abfangen können
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

def get_selenium_content(driver, url):
    try:
        driver.get(url)
        time.sleep(1.5)
        title = driver.title
        body = driver.find_element(By.TAG_NAME, "body").text
        links = []
        for elem in driver.find_elements(By.TAG_NAME, "a"):
            try: links.append((elem.get_attribute("href"), elem.text.lower()))
            except: continue
        return title, body, links
    except: return "", "", []

def find_school_type_in_text(text, type_list):
    found = set()
    text_lower = text.lower()
    for styp in type_list:
        if styp.lower() in text_lower: found.add(styp)
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
    
    title_main, text_main, links_main = get_selenium_content(driver, url)
    if not text_main: return "Nicht erreichbar", "", "", ""
    
    if config["SENSITIVITY"] == "strict" and not is_manual_url:
        if not validate_page_strict(text_main): return url, "", "", ""
    
    found_types = find_school_type_in_text(title_main + "\n" + text_main, config["SCHULTYPEN_LISTE"])
    found_kws = set()
    chunks = [f"--- Seite 1 ({title_main}) ---\n{text_main[:2500]}"]
    
    def scan(txt):
        for k in config["KEYWORD_LISTE"]:
            if re.search(r'\b' + re.escape(k.lower()), txt.lower()): found_kws.add(k)

    scan(text_main)
    
    domain = urlparse(url).netloc
    l1_targets = []
    
    for href, txt in links_main:
        if href and domain in urlparse(href).netloc:
            txt_low = txt.lower()
            if any(p.lower() in txt_low for p in PRIORITY_LINKS_L1):
                l1_targets.append(href)
            elif is_manual_url:
                blocklist = ["impressum", "datenschutz", "login", "anmelden", "kontakt", "sitemap"]
                if not any(b in txt_low for b in blocklist) and len(txt) > 2:
                    l1_targets.append(href)

    scan_list = list(dict.fromkeys(l1_targets))[:3]
    
    for l1 in scan_list:
        t1, text1, links1 = get_selenium_content(driver, l1)
        if text1:
            scan(text1)
            chunks.append(f"--- {t1} ---\n{text1[:2500]}")
            if not found_types: found_types.extend(find_school_type_in_text(text1, config["SCHULTYPEN_LISTE"]))
            
            if not found_kws and not is_manual_url:
                 l2_urls = [h for h, t in links1 if h and domain in urlparse(h).netloc and any(p.lower() in t for p in PRIORITY_LINKS_L2)]
                 for l2 in list(dict.fromkeys(l2_urls))[:2]:
                    t2, text2, _ = get_selenium_content(driver, l2)
                    if text2:
                        scan(text2)
                        chunks.append(f"--- {t2} ---\n{text2[:2500]}")
                        
    schultyp_final = ", ".join(sorted(list(set(found_types))))
    return url, schultyp_final, ", ".join(sorted(list(found_kws))), "\n\n".join(chunks)

def ki_analyse(context_text, config, api_keys):
    if not context_text or len(context_text) < 50: return "Keine Daten"
    prompt = config["PROMPT_TEMPLATE"].format(text=context_text[:15000])

    for provider in config["AI_PRIORITY"]:
        provider = provider.lower()
        key = api_keys.get(provider)
        if not key: continue
        
        try:
            client = get_ai_client(provider, key)
            if not client: continue

            if provider == "openrouter":
                return "[Llama/Claude]: " + client.chat.completions.create(model=config["OPENROUTER_MODEL"], messages=[{"role": "user", "content": prompt}]).choices[0].message.content.strip()
            elif provider == "openai":
                return "[OpenAI]: " + client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]).choices[0].message.content.strip()
            elif provider == "gemini":
                return "[Gemini]: " + client.models.generate_content(model=config["GEMINI_MODEL"], contents=prompt).text.strip()
            elif provider == "groq":
                return "[Groq]: " + client.chat.completions.create(model=config["GROQ_MODEL"], messages=[{"role": "user", "content": prompt}]).choices[0].message.content.strip()
        except: continue
    return "KI-Fehler"

# --- MAP GENERATION ---
# --- HELPER FÜR CACHING ---
@st.cache_data(show_spinner=False)
def get_coordinates(name, ort):
    """
    Holt die Koordinaten und speichert sie im Cache. 
    Pausiert (time.sleep) NUR bei echten API-Aufrufen!
    """
    geolocator = Nominatim(user_agent="schul_scanner_st_cache")
    try:
        clean_name = re.sub(r"\(.*?\)", "", name).strip()
        loc = geolocator.geocode(f"{clean_name}, {ort}, Germany", timeout=5)
        
        if loc:
            time.sleep(1.2) # Höflichkeitspause nach echtem Request
            return loc.latitude, loc.longitude, False
        
        time.sleep(1.2) # Pause vor dem Fallback-Request
        loc_city = geolocator.geocode(f"{ort}, Germany", timeout=5)
        if loc_city:
            lat = loc_city.latitude + random.uniform(-0.015, 0.015)
            lon = loc_city.longitude + random.uniform(-0.015, 0.015)
            time.sleep(1.2)
            return lat, lon, True
            
    except Exception as e:
        print(f"Warnung bei {name}: {e}")
        
    return None, None, False


# --- MAP GENERATION ---
def generate_folium_map(data):
    m = folium.Map(location=[51.1657, 10.4515], zoom_start=6)
    
    legend_html = '''
     <div style="position: fixed; bottom: 50px; right: 50px; width: 200px; height: 160px; border:2px solid grey; z-index:9999; font-size:14px; background-color:white; opacity:0.9; padding: 10px;">
     <b>Legende</b><br>
     <i style="color:purple" class="fa fa-map-marker"></i> Begabtenförderung<br>
     <i style="color:blue" class="fa fa-map-marker"></i> Gymnasium<br>
     <i style="color:green" class="fa fa-map-marker"></i> Gesamtschule<br>
     <i style="color:orange" class="fa fa-map-marker"></i> Mix (Gym/HR)<br>
     <i style="color:red" class="fa fa-map-marker"></i> Realschule<br>
     <i style="color:gray" class="fa fa-map-marker"></i> Sonstige/Förder<br>
     </div>
     '''
    m.get_root().html.add_child(Element(legend_html))

    progress_text = "Platziere Marker auf der Karte (nutze Cache, falls vorhanden)..."
    my_bar = st.progress(0, text=progress_text)
    total = len(data)
    
    for i, entry in enumerate(data):
        name = entry.get('schulname', '')
        ort = entry.get('ort', '')
        
        if not name or not entry.get('webseite') or entry.get('webseite') == "Nicht gefunden": 
            my_bar.progress((i + 1) / total, text=f"Überspringe {name}...")
            continue
            
        my_bar.progress((i + 1) / total, text=f"Platziere {name}...")
        
        # --- CACHE-ABFRAGE STATT DIREKTEM AUFRUF ---
        lat, lon, is_approx = get_coordinates(name, ort)
        
        if not lat or not lon: continue

        schultyp = str(entry.get('schultyp', 'Unbekannt'))
        ki = str(entry.get('ki_zusammenfassung', 'Keine Analyse'))
        kw = str(entry.get('keywords', '-'))
        st_lower = schultyp.lower()
        full_text_scan = (ki + " " + kw).lower()
        
        # Farb-Logik
        if any(word in full_text_scan for word in ["hochbegabt", "hochbegabte", "begabte", "akzeleration"]): color = "purple"
        elif "gesamtschule" in st_lower: color = "green"
        elif "gymnasium" in st_lower and ("haupt" in st_lower or "real" in st_lower): color = "orange"
        elif "gymnasium" in st_lower: color = "blue"
        elif "realschule" in st_lower: color = "red"
        else: color = "gray"
        
        pos_hint = "<br><i style='color:red; font-size:10px'>(Position geschätzt)</i>" if is_approx else ""
        html = f"""
        <div style="font-family: Arial; width: 300px;">
            <h4>{name}</h4>
            <p style="color:grey; font-size:11px">{schultyp} {pos_hint}</p>
            <hr>
            <p><b>KW:</b> {kw}</p>
            <div style="max-height:100px;overflow-y:auto;background:#f9f9f9;padding:5px;font-size:11px;border:1px solid #eee;">{ki}</div>
            <br><a href="{entry.get('webseite','#')}" target="_blank">Webseite</a>
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

# --- MAIN APP LOGIC ---

def main():
    st.sidebar.title("🏫 Schul-Scanner Pro")
    
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
    
    # Load Config
    if 'config' not in st.session_state:
        st.session_state.config = load_config()
    
    config = st.session_state.config
    
    # Sensitivity
    config["SENSITIVITY"] = st.sidebar.selectbox("Sensibilität", ["normal", "strict"], index=0 if config["SENSITIVITY"]=="normal" else 1, help="'strict' prüft auf 'Wir sind eine Schule' Sätze.")
    
    # Keyword Editor
    with st.sidebar.expander("📝 Keywords & Typen"):
        kws = st.text_area("Keywords (kommagetrennt)", ", ".join(config["KEYWORD_LISTE"]))
        config["KEYWORD_LISTE"] = [k.strip() for k in kws.split(",") if k.strip()]
        
        types = st.text_area("Schultypen (kommagetrennt)", ", ".join(config["SCHULTYPEN_LISTE"]))
        config["SCHULTYPEN_LISTE"] = [t.strip() for t in types.split(",") if t.strip()]

    # Prompt
    with st.sidebar.expander("🤖 KI Prompt"):
        prompt_txt = st.text_area("Template", config["PROMPT_TEMPLATE"], height=150)
        config["PROMPT_TEMPLATE"] = prompt_txt

    # 2. MAIN TABS
    tab1, tab2, tab3, tab4 = st.tabs(["📂 Daten & Upload", "🚀 Auto-Scan", "🗺️ Karte", "✏️ Einzeln bearbeiten"])
    
    # --- TAB 1: DATA ---
    with tab1:
        st.header("Datenverwaltung")
        
        uploaded_file = st.file_uploader("Excel-Datei hochladen (Format: Name, leer, Ort)", type=["xlsx"])
        
        if 'df' not in st.session_state:
            # Versuche lokale Datei zu laden wenn kein Upload
            if os.path.exists(config["OUTPUT_FILE"]):
                st.session_state.df = pd.read_excel(config["OUTPUT_FILE"])
            elif uploaded_file:
                # Initial Load from Upload
                 pass # Wird unten behandelt
            else:
                st.session_state.df = pd.DataFrame(columns=["schulname", "ort", "webseite", "schultyp", "keywords", "ki_zusammenfassung"])

        if uploaded_file:
            if st.button("📥 Neue Daten aus Upload importieren"):
                raw_df = pd.read_excel(uploaded_file, header=None)
                # Simple logic: col 0 is name, col 2 is ort (based on original script)
                new_data = []
                for _, row in raw_df.iterrows():
                    if len(row) > 2:
                        name = str(row[0]).strip()
                        ort = str(row[2]).strip()
                        if len(name) > 3 and "schule" in name.lower():
                            new_data.append({
                                "schulname": name, "ort": ort, 
                                "webseite": "Nicht gefunden", "schultyp": "", 
                                "keywords": "", "ki_zusammenfassung": ""
                            })
                
                # Merge with existing
                if not st.session_state.df.empty:
                    existing_names = set(st.session_state.df["schulname"].astype(str))
                    added_count = 0
                    for item in new_data:
                        if item["schulname"] not in existing_names:
                            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([item])], ignore_index=True)
                            added_count += 1
                    st.success(f"{added_count} neue Schulen hinzugefügt.")
                else:
                    st.session_state.df = pd.DataFrame(new_data)
                    st.success("Datenbank neu erstellt.")

        st.dataframe(st.session_state.df, use_container_width=True)
        
        # Download Button
        if not st.session_state.df.empty:
            @st.cache_data
            def convert_df(df):
                return df.to_excel(index=False).encode('utf-8') # Needs openpyxl installed, otherwise use CSV

            # Workaround for Excel Bytes without IO buffer complexity in snippet
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                st.session_state.df.to_excel(writer, index=False)
                
            st.download_button(
                label="💾 Ergebnisse herunterladen (Excel)",
                data=buffer,
                file_name="schulen_ergebnisse_streamlit.xlsx",
                mime="application/vnd.ms-excel"
            )

    # --- TAB 2: SCANNER ---
    with tab2:
        st.header("Automatischer Crawler")
        
        col1, col2 = st.columns(2)
        with col1:
            scan_mode = st.radio("Was scannen?", ["Nur neue/leere Einträge", "Alles neu scannen (Überschreiben)"])
        with col2:
            st.info("Der Browser läuft im Hintergrund (Headless). Bitte warten.")

        if st.button("🚀 Scan starten", type="primary"):
            df = st.session_state.df
            if df.empty:
                st.warning("Keine Daten vorhanden.")
            else:
                progress_bar = st.progress(0)
                status_text = st.empty()
                log_container = st.container(height=300)
                
                driver = get_driver()
                if driver:
                    try:
                        total_rows = len(df)
                        for index, row in df.iterrows():
                            # Skip check
                            if scan_mode == "Nur neue/leere Einträge":
                                ki_val = str(row.get('ki_zusammenfassung', ''))
                                if ki_val and ki_val not in config["ERROR_MARKERS"] and len(ki_val) > 10:
                                    continue
                            
                            status_text.text(f"Scanne: {row['schulname']}...")
                            
                            url, typ, kw, ctx = crawl_and_analyze(driver, row['schulname'], row['ort'], config)
                            
                            # Update DataFrame in Session State
                            df.at[index, 'webseite'] = url
                            df.at[index, 'schultyp'] = typ
                            df.at[index, 'keywords'] = kw
                            
                            ki_result = "Zu wenige Infos"
                            if (typ or kw) and ctx:
                                log_container.code(f"AI Analysing: {row['schulname']}")
                                ki_result = ki_analyse(ctx, config, api_keys)
                            elif config["SENSITIVITY"] == "strict" and not ctx:
                                ki_result = "Strict Filter Block"
                            else:
                                ki_result = "Keine relevanten Daten"
                            
                            df.at[index, 'ki_zusammenfassung'] = ki_result
                            
                            log_container.write(f"✅ {row['schulname']} -> {typ} | {kw}")
                            progress_bar.progress((index + 1) / total_rows)
                            
                            # Autosave logic (optional, here update session state is enough till download)
                            st.session_state.df = df 
                            
                            try:
                                df.to_excel(config["OUTPUT_FILE"], index=False, engine='openpyxl')
                                # Visuelles Feedback für jede Schule
                                st.toast(f"Gespeichert: {row['schulname']}", icon="💾")
                            except Exception as e:
                                st.warning(f"Konnte Datei nicht zwischenspeichern: {e}")

                            st.balloons() # Kleiner visueller Feiereffekt am Ende

                        st.success("Scan abgeschlossen!")
                    except Exception as e:
                        st.error(f"Fehler im Scan-Prozess: {e}")
                    finally:
                        driver.quit()
                else:
                    st.error("Konnte Treiber nicht laden.")

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
            st.warning("Keine Daten.")
        else:
            # Select Box for School
            school_names = st.session_state.df["schulname"].tolist()
            selected_school = st.selectbox("Schule wählen", school_names)
            
            # Find row
            idx = st.session_state.df[st.session_state.df["schulname"] == selected_school].index[0]
            row = st.session_state.df.iloc[idx]
            
            col_e1, col_e2 = st.columns(2)
            
            with col_e1:
                new_name = st.text_input("Name", row["schulname"])
                new_ort = st.text_input("Ort", row["ort"])
                new_url = st.text_input("Webseite", row["webseite"])
                
                if st.button("🌐 URL testen / Deep Scan"):
                     driver = get_driver()
                     if driver:
                        st.info(f"Analysiere: {new_url}")
                        u, t, k, c = crawl_and_analyze(driver, new_url, new_ort, config) # new_url is handled as manual because starts with http
                        st.session_state.df.at[idx, 'schultyp'] = t
                        st.session_state.df.at[idx, 'keywords'] = k
                        if c:
                             ai_res = ki_analyse(c, config, api_keys)
                             st.session_state.df.at[idx, 'ki_zusammenfassung'] = ai_res
                        driver.quit()
                        st.rerun()

            with col_e2:
                new_typ = st.text_area("Schultyp", row["schultyp"])
                new_kw = st.text_area("Keywords", row["keywords"])
                new_ki = st.text_area("KI Zusammenfassung", row["ki_zusammenfassung"], height=200)
            
            if st.button("💾 Änderungen speichern & in Ergebnisdatei schreiben"):
               # Update Session State
               st.session_state.df.at[idx, 'schulname'] = new_name
               st.session_state.df.at[idx, 'ort'] = new_ort
               st.session_state.df.at[idx, 'webseite'] = new_url
               st.session_state.df.at[idx, 'schultyp'] = new_typ
               st.session_state.df.at[idx, 'keywords'] = new_kw
               st.session_state.df.at[idx, 'ki_zusammenfassung'] = new_ki
               st.success("Gespeichert!")
    
    
    # Update Datei
               try:
                st.session_state.df.to_excel(config["OUTPUT_FILE"], index=False, engine='openpyxl')
                st.toast("Datei erfolgreich aktualisiert!", icon="💾")
                
                # reload App
                # 
                st.rerun()
               except Exception as e:
                st.error(f"Fehler beim Speichern: {e}")

if __name__ == "__main__":
    main()

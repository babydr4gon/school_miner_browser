<h1 align="center">
  <img src="https://github.com/wiemachendiedasnur/school_miner/blob/main/images/dragon_mine.png" alt="School_miner icon" width="400" height="400"/>
  <br>
  School_Miner
</h1>


Dieses Tool hilft Eltern, Schulwebseiten automatisch nach Keywords (MINT, Ganztag, Montessori, etc.) zu durchsuchen und die pädagogischen Konzepte mit KI zusammenzufassen.

Es handelt sich um die Browserversion des Kommandozeilentools mit dem gleichen Namen, das <a href="https://github.com/babydr4gon/school_miner_browser/tree/main">hier</a> zu finden ist. 

<h1>Installation</h1>

**Repository klonen** oder als ZIP herunterladen und entpacken.

**Abhängigkeiten installieren:**

Dazu einen Terminal / eine Eingabeaufforderung öffnen und 
   
   ```bash
   pip install -r requirements.txt
   ```
eingeben. Falls es dabei unter Windows Fehlermeldungen gibt, dass die Installation zwar erfolgreich aber "not on PATH" war, muss gegebenenfalls noch eine System-Einstellung verändert werden. Wie das geht, steht <a href="https://www.geeksforgeeks.org/python/how-to-add-python-to-windows-path/">hier</a>. 


**API-Keys** in einer Datei namens .env im gleichen Ordner hinterlegen. Ohne API-Key läuft das Skript auch, liefert aber keine KI-Zusammenfassungen, sondern nur die gefundenen Keywords.
   ```bash
   OPENROUTER_API_KEY=dein_schluessel_hier
   ```

**Schulliste anlegen:** Eine Liste mit Schulnamen und Adressen herunterladen und unter "schulen.xlsx" abspeichern. Das Skript erwartet, dass sich der Name der Schue in der Spalte A und der Ort in Spalte C befinden. Wer das ändern möchte, muss im Code folgende Angaben anpassen:

```bash
"COLUMN_NAME_IDX": 0,
"COLUMN_ORT_IDX": 2,
```

**Starten:**
   Einen Terminal / eine Eingabeaufforderung starten und in den Ordner wechseln, in dem das Skript liegt, z.B.:
   unter Windows
   ```bash
   cd Ein_Ordner\ein_Unterordner\...
   ```
   oder unter Linux
   ```bash
   cd Ein_Ordner/ein_Unterordner/ ...
   ```
   Dann das Skript starten mit

   ```bash
   streamlit run app.py
   ```
   
<h1>Nutzung</h1>

<h3>Die Basis: eine Liste mit Schulen</h3>

Zunächst sollte man eine Liste der Schulen erstellen, über die man Informationen sammeln möchte. In allen Bundesländern gibt es entsprechende Listen, die in der Regel von den Kultusministerien oder von den statistischen Landesämtern gepflegt werden.

Diese Listen muss man für die eigenen Bedürfnisse anpassen, also beispielsweise die Schulen rauslöschen, die geographisch zu weit weg sind. Voreingestellt ist als Name für diese Liste "schulen.xlsx". 

Das Skript wird für jede der Schulen in dieser Liste nach der offiziellen Webseite suchen. Dort identifiziert es den Schultyp und erkennt bestimmte Keywords. Sobald es diese Dinge gefunden hat, versucht eine KI die gefundenen Informationen zum Konzept oder zu Besonderheiten der Schule in wenigen Sätzen zusammenzufassen. 

Am Ende wird  eine Tabelle mit den Ergebnissen der Suche erstellt. Darin stehen der Name und der Ort der Schule, die gefundenen Keywords, die verwendete Webseite und die Zusammenfassung der KI. Es gibt die Möglichkeit, Fehler, die bei der automatisierten Suche passieren, individuell zu korrigieren. 

<img src="https://github.com/wiemachendiedasnur/school_miner/blob/main/images/Karte.jpg" alt="Landkarte" width="650" height="650"/>

Abschließend kann man sich eine Landkarte erstellen lassen. Auf dieser Landkarte sind die Schulen mit Markern eingezeichnet. Klickt man auf einen der Marker, erscheint eine kurze Übersicht: der Name der Schule, die gefundenen Keywords und die KI-Zusammenfassung. 

<h3>Nach dem Start</h3>

Es erscheint startet der Browser mit einem Übersichtsfenster. Hier kann man neue Schuldaten hochladen, Einstellungen vornehmen und die Landkarte erstellen.

**Systemstatus:** Automatisch wird an dieser Stelle überprüft, ob nötige Werkzeuge für die Nutzung des Skripts installiert sind. Erwartet werden die Python-Module aus der Datei requirments.txt sowie der Internetbrower Chrome (Windows / Linux) oder Chromium (Linux).

**API Keys:** In der linken Seitenleiste sind die Felder für API Keys (OpenAI, Gemini, etc.). Diese müssen dort eingetragen werden.

**Sensibilität:** Mit der Sensibilität stellt man ein, wie streng das Skript bei der Kontrolle der gefundenen Webseiten sein soll. Im Modus "Normal" wird nur geschaut, ob Name und Ort der Schule auf der gefundenen Webseite stehen. Das kann in Einzelfällen dazu führen, dass eine völlig falsche Webseite als Grundlage für die Suche genommen wird, nur weil dort zufällig Name und Ort der Schule genannt werden (Stayfriends, Wikipedia, etc.). 

Im Modus "strict" werden weitere Bedingungen genannt, damit eine Webseite als offizielle Webseite der Schule angenommen und gegebenenfalls von der KI ausgewertet wird. 

<img src="https://github.com/wiemachendiedasnur/school_miner/blob/main/images/Browser.jpg" alt="Hauptmenü" width="650" height="650"/>

**Keywords & Typen:** Hier lassen sich bestimme Schlüsselwörter festlegen, nach denen die Webseiten durchsucht werden. Einige sind schon voreingestellt, jede Änderung an dieser Stelle wird aber übernommen. Gespeichert werden die Eintstellungen in einer Daei config.json, die automatisch angelegt wird.

**KI-Prompt:** Hier lässt sich der Prompt festlegen, der zum Beispiel für die Beschreibung des pädagogischen Konzepts der jeweiligen Schule genutzt werden kann. Auch hier ist gibt es eine sehr einfache Vorgabe und jede Änderung an der Stelle wird in der config.json-Datei gespeichert und übenommen.

**Datei laden:** Im Tab "Daten & Upload" kann man eine bestehende Quelldatei "schulen.xlsx" hochladen. Falls es schon eine Ergebnisliste "schulen_ergebnisse.xlsx" gibt, wird diese automatisch geladen.

**Scannen:** Mit einem Klick auf den Tab "Auto-Scan" und anschließend auf "Scan starten" beginnt das Skript mit der Arbeit. Man kann live mitverfolgen, welche Schule gerade bearbeitet wird. Der Browser läuft im Hintergrund (Headless), stört also nicht. Alternativ gibt es auch hier die Mögichkeit, eine bereits vorhandenen Ergebnisliste Manuel nachzubearbeiten.

**Karte:** Der Tab "Karte" generiert eine HTML-Datei mit der Landkarte.

<h1>Zu guter Letzt: </h1>
Wem diese Arbeit gefallen hat oder wer einfach nur einen Nutzen von dem Programm hat, der darf mir gerne einen Kaffee kaufen :-). Ich freue mnich darüber.

<p align="center">
  <a href="https://www.buymeacoffee.com/gernotzumc2" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 90px !important;width: 324px !important;"></a>
 </p>

##########

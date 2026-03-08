<h1 align="center">
  <img src="https://github.com/babydr4gon/school_miner/blob/main/images/dragon_mine.png" alt="School_miner icon" width="400" height="400"/>
  <br>
  School_Miner
</h1>


Dieses Tool hilft Eltern, Schulwebseiten automatisch nach Keywords (MINT, Ganztag, Montessori, etc.) zu durchsuchen und die pädagogischen Konzepte mit KI zusammenzufassen.

Es handelt sich um die Browserversion des Kommandozeilentools mit dem gleichen Namen, das <a href="https://github.com/babydr4gon/school_miner_browser/tree/main">hier</a> zu finden ist. 

<h1>Automatische Installation</h1>

**Vorbereitung und Systemvoraussetzungen:** Auf dem Rechner muss Python installiert sein, mindestens in der Version 3.11. Wer Python auf einem Windows-Rechner nachinstalliert, muss darauf achten, dass der  Haken bei "Add Python to PATH" gesetzt ist. Außerdem erwartet das Programm den Browser Google Chrome oder Chromium.

**Repository klonen** oder als ZIP herunterladen und entpacken.

**API Keys:** Die Datei .env.example in .env umbenennen und API-Keys hinter dem Gleichheitszeichen einfügen.

   ```bash
   OPENROUTER_API_KEY=dein_schluessel_hier
   ```
**Schulliste anlegen:** Eine Liste mit Schulnamen und Adressen herunterladen und unter "schulen.xlsx" abspeichern. Das Skript erwartet, dass sich der Name der Schule in der Spalte A und der Ort in Spalte C befinden. Wer das ändern möchte, muss im Code folgende Angaben anpassen (0 ist A und 2 ist C): 

```bash
"COLUMN_NAME_IDX": 0,
"COLUMN_ORT_IDX": 2,
```

<h1>Manuelle Installation</h1>

**Repository klonen** oder als ZIP herunterladen und entpacken.

**Abhängigkeiten installieren:** Dazu einen Terminal / eine Eingabeaufforderung öffnen und 
   
   ```bash
   pip install -r requirements.txt
   ```
eingeben. Falls es dabei unter Windows Fehlermeldungen gibt, dass die Installation zwar erfolgreich aber "not on PATH" war, muss gegebenenfalls noch eine System-Einstellung verändert werden. Wie das geht, steht <a href="https://www.geeksforgeeks.org/python/how-to-add-python-to-windows-path/">hier</a>. 


**API-Keys:** Die Datei .env.example in .env umbenennen und API-Keys hinter dem Gleichheitszeichen einfügen.
   ```bash
   OPENROUTER_API_KEY=dein_schluessel_hier
   ```

**Schulliste anlegen:** Eine Liste mit Schulnamen und Adressen herunterladen und unter "schulen.xlsx" abspeichern. Das Skript erwartet, dass sich der Name der Schue in der Spalte A und der Ort in Spalte C befinden. Wer das ändern möchte, muss im Code folgende Angaben anpassen (0 ist A und 2 ist C):

```bash
"COLUMN_NAME_IDX": 0,
"COLUMN_ORT_IDX": 2,
```
<h1>Start</h1>

Auf Windows-Rechnern Doppelklick auf die Datei "school_miner_browser.bat". 

Auf Linux-Rechnern die Datei "school_miner_startbrowser.sh" starten. Gegebenenfalls die Datei vorher ausführbar machen. 

Alternativ einen Terminal / eine Eingabeaufforderung öffnen und in den Ordner wechseln, in dem das Skript liegt. Starten mit

 ```bash
   streamlit run app.py
   ```
  oder, falls das nicht funktioniert:
  ```bash
  python -m streamlit run app.py
   ```

Hinweis: Beim ersten Start werden alle nötigen Bibliotheken geladen. Das kann 1–2 Minuten dauern. Danach ploppt der Browser mit dem Dashboard auf. Falls der Browser sich nicht automatisch öffnet, muss man die angegebene Netzwerkadresse (127.0.0.. etc.) manuell in einen Browser kopieren.
   
<h1>Nutzung</h1>

<h3>Die Basis: eine Liste mit Schulen</h3>

In allen Bundesländern in Deutschland gibt es Listen mit den Namen und Adressen der Schulen. Sie werden in der Regel von den Kultusministerien oder von den statistischen Landesämtern gepflegt.

Diese Listen muss man für die eigenen Bedürfnisse anpassen, also beispielsweise die Schulen löschen, die geographisch zu weit weg sind. Voreingestellt ist als Name für diese Liste "schulen.xlsx". 

Das Skript wird für jede der Schulen in dieser Liste nach der offiziellen Webseite suchen. Dort identifiziert es den Schultyp und erkennt bestimmte Keywords. Sobald es diese Dinge gefunden hat, versucht eine KI die gefundenen Informationen zum Konzept oder zu Besonderheiten der Schule in wenigen Sätzen zusammenzufassen. 

Am Ende wird  eine Tabelle mit den Ergebnissen der Suche erstellt. Darin stehen der Name und der Ort der Schule, die gefundenen Keywords, die verwendete Webseite und die Zusammenfassung der KI. Es gibt die Möglichkeit, Fehler, die bei der automatisierten Suche passieren, individuell zu korrigieren. 

<img src="https://github.com/babydr4gon/school_miner/blob/main/images/Karte.jpg" alt="Landkarte" width="650" height="650"/>

Abschließend kann man sich eine Landkarte erstellen lassen. Auf dieser Landkarte sind die Schulen mit Markern eingezeichnet. Klickt man auf einen der Marker, erscheint eine kurze Übersicht: der Name der Schule, die gefundenen Keywords und die KI-Zusammenfassung. 

<h3>Liste laden, Suchen und Karte erstellen</h3>

Nach dem Start öffnet sich der Browser mit einem Übersichtsfenster. Hier kann man neue Schuldaten hochladen, Einstellungen vornehmen und die Landkarte erstellen.

Bei manchen Systemvarianten kann es sein, dass sich der Browser nicht automatisch öffnet. Dann muss man manuell einen Browser öffnen und die angegebene Netzwerkadresse (127.0.0.. etc. ) reinkopieren.

**Systemstatus:** Automatisch wird an dieser Stelle überprüft, ob nötige Werkzeuge für die Nutzung des Skripts installiert sind. Erwartet werden die Python-Module aus der Datei requirements.txt sowie der Internetbrower Chrome (Windows / Linux) oder Chromium (Linux).

<img src="https://github.com/babydr4gon/school_miner_browser/blob/main/images/StartBrowser.jpg" alt="Hauptmenü" width="650" height="650"/>

**API Keys:** In der linken Seitenleiste sind die Felder für API Keys (OpenAI, Gemini, etc.). Diese müssen dort eingetragen werden.

**Sensibilität:** Mit der Sensibilität stellt man ein, wie streng das Skript bei der Kontrolle der gefundenen Webseiten sein soll. Im Modus "Normal" wird nur geschaut, ob Name und Ort der Schule auf der gefundenen Webseite stehen. Das kann in Einzelfällen dazu führen, dass eine völlig falsche Webseite als Grundlage für die Suche genommen wird, nur weil dort zufällig Name und Ort der Schule genannt werden (Stayfriends, Suchmaschinenlinks, etc.). 

Im Modus "strict" werden weitere Bedingungen genannt, damit eine Webseite als offizielle Webseite der Schule angenommen und gegebenenfalls von der KI ausgewertet wird. 

**Keywords & Typen:** Hier lassen sich bestimme Schlüsselwörter festlegen, nach denen die Webseiten durchsucht werden. Einige sind schon voreingestellt, jede Änderung an dieser Stelle wird aber übernommen. Gespeichert werden die Einstellungen in einer Daei config.json, die automatisch angelegt wird.

<img src="https://github.com/babydr4gon/school_miner/blob/main/images/Browser.jpg" alt="Kontrolle" width="650" height="650"/>

**KI-Prompt:** Hier lässt sich der Prompt festlegen, der zum Beispiel für die Beschreibung des pädagogischen Konzepts der jeweiligen Schule genutzt werden kann. Auch hier ist gibt es eine sehr einfache Vorgabe und jede Änderung an der Stelle wird in der config.json-Datei gespeichert und übernommen.

**Einstellungen speichern:** Übernimmt die aktuellen Änderungen bei KI-Prompt, Keywords, Sensibilität etc. in die config.json.

**Datei laden:** Im Tab "Daten & Upload" kann man eine bestehende Quelldatei "schulen.xlsx" hochladen. Falls es schon eine Ergebnisliste "schulen_ergebnisse.xlsx" gibt, wird diese automatisch geladen.

**Scannen:** Mit einem Klick auf den Tab "Auto-Scan" und anschließend auf "Scan starten" beginnt das Skript mit der Arbeit. Man kann live mitverfolgen, welche Schule gerade bearbeitet wird. Der Browser läuft im Hintergrund (Headless), stört also nicht. 

**Einzeln bearbeiten:** Nach dem ersten Durchlauf des Skripts werden einige Einträge unvollständig sein. Hier kann man die Ergebnisse für jede Schule nachbearbeiten. Oben steht der Schulname in einem Dropdown-Menü. Bei einem Klick auf "Aktuelle URL aufrufen" wird die derzeit gespeicherte Webseite in einem neuen Tab geöffnet. Bei einem Klick auf "URL testen / Deep Scan" wird die aktuell gespeicherte URL neu vom Skript auf Keywords etc. durchsucht. Alle Änderungen kann man mit einem Klick auf den Button "Änderungen speichern und in Ergebnisliste übernehmen" in der Datei "schulen_ergebnisse.xlsx" speichern.

**Karte:** Der Tab "Karte" generiert eine HTML-Datei mit der Landkarte.

**Programm beenden:** Ein Klick beendet den Server und das Browserfenster kann geschlossen werden.

<h1>Tipps und Tricks </h1>

Schulwebseiten zu scannen ist eine Herausforderung. Viele dieser Seiten sind entweder veraltet oder ziemlich zusammengestückelt. Deshalb muss man, wenn man erfolgreich Informationen sammeln will, etwas Zeit und Mühe investieren. Dazu folgende Ideen:

**Mit einer kleinen Testliste anfangen:** Es hat sich bewährt, zunächst höchstens 10 Schulen als Quelle zu nehmen und das Programm ein paar Mal mit verschiedenen Keywords und einem individuell gestalteten Prompt durchlaufen zu lassen. Sehr unterschiedlich wirkt es sich beispielsweise aus, die Sensibilität von "strict" auf "normal" zu stellen. Dann tauchen zwar plötzlich vielleicht ein paar Zeitungsberichte in der Suche auf, aber da stehen manchmal auch ganz interessante Sachen über die gesuchte Schule drin. Die Keywordliste zu erweitern kann dafür sorgen, dass das Skript auf Unterseiten der Schulhomepage Dinge findet, die sonst verloren gegangen wären.

**Einen guten Prompt formulieren:** Es lohnt sich sicher, hier etwas Arbeit reinzustecken und mehrere unterschiedliche Versionen zu vergleichen. Es kann helfen, zunächst einen sehr allgemeinen Prompt zu formulieren, bei dem vielleicht einfach nur nach Besonderheiten der Schule gefragt wird. Im zweiten Schritt probiert man dann einen Prompt, der sehr genau auf den eigenen Fokus bei der Schulsuche hin geschrieben ist. Stück für Stück nähert man sich so einem Prompt an, der individuell auf den eigenen Bedarf zugeschnitten, aber gleichzeitig auch für größere Listen geeignet ist.

**Den Index in der config.json nutzen:** Manchmal hat man Pech und in der Ergebnisliste gibt es einen längeren Abschnitt ohne vernünftige Ergebnisse. Über mehrere Zeilen hinweg hat das Programm möglicherweise keine oder keine vernünftigen Daten geliefert. Wenn man nun den Autoscan wieder bei 0 startet, werden andere Ergebnisse überschrieben. In diesem Fall kann man besser ganz unten in der config.json den Wert "AUTO_RESUME_IDX" auf die Zeile stellen, wo man wieder anfangen möchte. Wenn die fehlenden Zeilen abgearbeitet sind, einfach das Programm mit einem Klick auf Button "Stop" unterbrechen.

**Eine andere KI ausprobieren:** Das Programm bietet die Möglichkeit, zwischen unterschiedlichen KI-Anbietern und Modellen zu wechseln. Dabei können sehr unterschiedliche Antworten herauskommen.

**Viele graue Marker auf der Landkarte:** Wahrscheinlich sind viele Schulen noch ohne Schultyp und werden dann den anderen Farben nicht zugeordnet. Da hilft nur eine manuelle Kontrolle oder ein ganz neuer Autoscan.

<h1>Kauf mir einen Kaffee! </h1>
Wem diese Arbeit gefallen hat oder wer einfach nur einen Nutzen von dem Programm hat, der darf mir gerne einen Kaffee kaufen :-). Ich freue mnich darüber.

<p align="center">
  <a href="https://www.buymeacoffee.com/gernotzumc2" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 90px !important;width: 324px !important;"></a>
 </p>


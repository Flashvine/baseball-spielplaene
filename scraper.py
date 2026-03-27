import pandas as pd
import requests
import subprocess
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from icalendar import Calendar, Event
from io import StringIO
from pathlib import Path # NEU: Für bombensichere Dateipfade

print("Starte NBSV Scraper...")

TEAMS_CONFIG = [
    {
        "team_suchbegriff": "Oldenburg Hornets",
        "url": "https://www.nbsv.de/spielbetrieb/ligen-und-uebersicht/tabelle/?bsm_league=6302&bsm_season=2026#", # Landesliga Nord
        "dateiname": "oldenburg_hornets.ics"
    },
    {
        "team_suchbegriff": "Bremen Dockers",
        "url": "https://www.nbsv.de/spielbetrieb/ligen-und-uebersicht/tabelle/?bsm_league=6136&bsm_season=2026", # Bitte anpassen!
        "dateiname": "bremen_dockers.ics"
    },
    {
        "team_suchbegriff": "Hamburg Stealers",
        "url": "https://www.nbsv.de/spielbetrieb/ligen-und-uebersicht/tabelle/?bsm_league=6127&bsm_season=2026", # Bitte anpassen!
        "dateiname": "hamburg_stealers.ics"
    }
]


# --- Webscraping Teil ---
def erstelle_team_kalender(team, url, speicher_pfad):
    print(f"\n---> Verarbeite: {team}")

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        print("Webseite geladen. Lese Tabellen...")
        html_data = StringIO(response.text)
        tabellen = pd.read_html(html_data)
        
        # Der Spielplan ist die zweite Tabelle (Index 1)
        df = tabellen[1]
        
        # --- BeautifulSoup Teil (Orte reparieren) ---
        print("Repariere Spielorte...")
        soup = BeautifulSoup(response.text, 'html.parser')
        ort_zellen = soup.find_all('td', attrs={'data-cell-for': 'field'})
        
        echte_orte = []
        for zelle in ort_zellen:
            link = zelle.find('a')
            if link and link.has_attr('title'):
                echte_orte.append({"Field": link['title'].split(" - ")[0], "Adresse": link['title'].split(" - ")[1]})  # Assuming the title is in the format "Ort Name"
            else:
                echte_orte.append({"Field": '', "Adresse": ''})
                
        df["Field"] = [ort['Field'] for ort in echte_orte]
        df["Adresse"] = [ort['Adresse'] for ort in echte_orte]

        df = df[df.Heim == team]
        df = df[["Datum", "Zeit", "Gast", "Field", "Adresse"]]
        
        # --- iCal Erstellung ---
        print("Generiere Kalender...")
        kalender = Calendar()
        kalender.add('prodid', '-//NBSV Spielplan//DE')
        kalender.add('version', '2.0')
        kalender.add('X-WR-TIMEZONE', 'Europe/Berlin')

        for index, row in df.iterrows():
            event = Event()
            event.add('summary', f"Spiel: {team} vs {row['Gast']}")
            
            datum_str = row['Datum']
            zeit_str = row['Zeit']
            try:
                start_datetime = datetime.strptime(f"{datum_str} {zeit_str}", "%d.%m.%Y %H:%M")
                end_datetime = start_datetime + timedelta(hours=2)  # Assuming a game lasts 2 hours
                
                event.add('dtstart', start_datetime)
                event.add('dtend', end_datetime)
                event.add('location', f"{row['Field']}, {row['Adresse']}")
                
                kalender.add_component(event)
            except ValueError:
                pass # Fehlerhafte Zeilen leise überspringen

        # 2. Puzzleteil: Mit dem sicheren Pfad abspeichern
        with open(speicher_pfad, 'wb') as f:
            f.write(kalender.to_ical())

        print(f"Erfolg! Kalender gespeichert unter:\n{speicher_pfad}")

    else:
        print(f"Fehler beim Laden der Seite. Status Code: {response.status_code}")


if __name__ == "__main__":
    # Ermittelt den Ordner, in dem dieses Python-Skript auf dem Pi liegt
    skript_ordner = Path(__file__).resolve().parent
    
    print("=== Starte automatischen Spielplan-Download ===")
    
    # Schleife durch unsere Liste aus Schritt 1
    for config in TEAMS_CONFIG:
        # Bastelt den absoluten Pfad für jede .ics Datei zusammen
        voller_pfad = skript_ordner / config["dateiname"]
        
        # Ruft die Funktion auf
        erstelle_team_kalender(
            team=config["team_suchbegriff"], 
            url=config["url"], 
            speicher_pfad=voller_pfad
        )
    
    print("\n=== Lade geänderte Kalender zu GitHub hoch ===")
    
    try:
        # 1. Alle geänderten .ics Dateien "vormerken"
        subprocess.run(["git", "add", "*.ics"], check=True, cwd=skript_ordner)
        
        # 2. Eine Nachricht mit dem aktuellen Zeitstempel generieren
        commit_msg = f"Auto-Update Spielpläne: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        # 3. Den Commit erstellen
        # (Wenn sich nichts geändert hat, wirft dieser Befehl einen Fehler, 
        # den wir unten mit 'except' abfangen)
        subprocess.run(["git", "commit", "-m", commit_msg], check=True, cwd=skript_ordner)
        
        # 4. Hochladen zu GitHub
        subprocess.run(["git", "push"], check=True, cwd=skript_ordner)
        
        print("Upload erfolgreich!")
        
    except subprocess.CalledProcessError:
        # Wenn sich an den .ics Dateien kein einziges Zeichen verändert hat, 
        # schlägt 'git commit' fehl. Das ist aber gewollt, denn dann gibt 
        # es auch nichts hochzuladen!
        print("Keine neuen Änderungen an den Spielplänen. Nichts hochgeladen.")
        
    print("\n=== Alle Downloads abgeschlossen! ===")
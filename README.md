# Limodor Airodor für Home Assistant

Lokale Home-Assistant-Integration für den Wohnraum-/Kellerlüfter **Limodor Airodor** (WLAN-Variante „Airodor-G“). Der Lüfter wird direkt im Heimnetz per HTTP angesprochen – ohne Cloud.

> **Inoffizielles Projekt.** Nicht mit Limodor verbunden. Das Protokoll wurde aus eigenen Beobachtungen abgeleitet. Nutzung auf eigene Verantwortung.

## Wofür?

- Lüfter aus Home Assistant **ein-/ausschalten** sowie **Richtung** und **Volumenstrom** manuell einstellen.
- **Alle Automatiken des Lüfters sicher stoppen** und im Normalbetrieb laufen lassen (Abluft, minimaler Volumenstrom).
- **Aktuellen Zustand anzeigen**, auch wenn er anderweitig geändert wurde (regelmäßiges Polling).
- **Temperatur und Feuchte** des Lüfters als Sensoren nutzen, inkl. absoluter Feuchte und Taupunkt – Grundlage für eine Taupunktlüftung per Automation.

## Funktionsübersicht

| Entität | Funktion |
|---|---|
| **Lüfter** (`fan`) | Ein/Aus und Volumenstrom in 3 Stufen (Minimal 33 % · Mittel 66 % · Maximal 100 %) |
| **Richtung** (`select`) | Wechsel (Ab-/Zuluft im Wechsel) · Abluft · Zuluft |
| **Volumenstrom** (`select`) | Aus · Minimal · Mittel · Maximal |
| **Automatiken stoppen** (`button`) | Beendet die Automatikprogramme des Lüfters |
| **Normalbetrieb (Abluft, minimal)** (`button`) | Automatiken stoppen und Abluft/minimal setzen |
| **Stummmodus** (`number`) | Stummmodus in Stunden (0 = beenden, max. 24) |
| **Feuchte-/Temperatur-Programm** (`number`, `select`, `button`) | Schwelle, Richtung und Volumenstrom einstellen und das Programm per Button aktivieren |
| **Programm-Anzeige** (`sensor`) | Je Programm Schwelle, Richtung und Volumenstrom „(aktiv)“: zeigt die gesendeten Werte, solange das Programm läuft, sonst **Inaktiv** (bzw. *Unbekannt*, wenn es anderweitig gestartet wurde) |
| **Sensoren** | Temperatur · Luftfeuchtigkeit · Absolute Feuchte (g/m³) · Taupunkt · aktives Programm · Stummmodus-Restzeit |

Jede manuelle Einstellung (Lüfter, Richtung, Volumenstrom) beendet zuerst laufende Automatiken, damit der gewünschte Zustand sicher gilt.

### Automatik-Programme
Der Lüfter kennt ein Feuchte-Programm (P1) und ein Temperatur-Programm (P2). Die Einstellungen kann der Lüfter **nicht zurückmelden**: Home Assistant merkt sich Schwelle, Richtung und Volumenstrom selbst (auch nach Neustart) und sendet sie erst beim Drücken von **„… aktivieren“**. Beenden: „Automatiken stoppen“ oder eine manuelle Einstellung.

Zusätzlich gibt es die Dienste `limodor_airodor.set_humidity_program` und `limodor_airodor.set_temperature_program` (Schwelle, Richtung, Volumenstrom) für Automationen.

### Taupunkt
Taupunkt und absolute Feuchte werden in Home Assistant aus Temperatur und relativer Feuchte des Lüfters berechnet (Magnus-Näherung; die Eingangswerte des Lüfters sind ganzzahlig, der Taupunkt ist daher auf etwa ±0,5 °C genau). Für eine Taupunktlüftung (Zuluft nur, wenn es draußen deutlich trockener ist) werden zusätzlich Außenwerte benötigt – ein eigener Sensor oder eine Wetterintegration. Diese Logik ist als Home-Assistant-Automation gedacht.

## Voraussetzungen

- Home Assistant 2024.12 oder neuer
- Der Lüfter ist im selben Netzwerk erreichbar (im Heimnetz-WLAN eingebunden, am besten mit fester IP/DHCP-Reservierung)

## Installation

### Mit HACS (als benutzerdefiniertes Repository)
1. HACS → Integrationen → Menü (⋮) → **Benutzerdefinierte Repositories**.
2. `https://github.com/gbg-pf/Airodor-HA` als Repository eintragen, Kategorie **Integration**.
3. „Limodor Airodor" installieren und Home Assistant **neu starten**.

### Manuell
(Repository herunterladen: `git clone https://github.com/gbg-pf/Airodor-HA`)
1. Den Ordner `custom_components/limodor_airodor` nach `<HA-Konfiguration>/custom_components/` kopieren.
2. Home Assistant **neu starten** (bei Codeänderungen reicht ein Neuladen nicht).

## Konfiguration

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen → „Limodor Airodor"**.
2. Namen und **IP-Adresse oder Hostname** des Lüfters eingeben. Beim Anlegen wird eine Statusabfrage gesendet; schlägt sie fehl, erscheint ein Verbindungsfehler.
3. Optional: **Abfrageintervall** unter *Konfigurieren* an der Integration ändern (Standard **15 s**, Minimum 10 s). Änderungen laden die Integration automatisch neu.

Bereits vorhandene `rest:`-/Template-Sensoren für den Lüfter aus der `configuration.yaml` sollten entfernt werden, da die Integration die Sensoren selbst liefert.

## Beispiele

Normalbetrieb jede Nacht sicherstellen:

```yaml
automation:
  - alias: "Lüfter Normalbetrieb"
    trigger:
      - platform: time
        at: "03:00:00"
    action:
      - service: button.press
        target:
          entity_id: button.airodor_luefter_normalbetrieb_abluft_minimal
```

Die tatsächlichen Entitäts-IDs richten sich nach dem vergebenen Namen und lassen sich unter *Einstellungen → Geräte & Dienste → Entitäten* nachsehen.

## Protokoll (Kurzfassung)

Alle Befehle: `GET http://<IP>/msg?befehl=<BEFEHL>`

| Befehl | Bedeutung |
|---|---|
| `STA` | Status → `STA` + 11 Ziffern |
| `NVF<R><V>` | Manuell: Richtung R (0 Wechsel, 1 Abluft, 2 Zuluft), Volumen V (0 aus … 3 max) |
| `STU<h>` | Stummmodus für h Stunden (0 = beenden) |
| `SP1<rF><R><V>` / `SP2<°C><R><V>` | Feuchte-/Temperatur-Programm mit Schwelle (2 Ziffern) setzen |
| `P1S` / `P2S` / `P3S` | Programm 1/2/3 beenden |

Aufbau der `STA`-Antwort (Ziffern nach „STA“):

| Stelle | Bedeutung |
|---|---|
| 1 | Programm: 0 manuell · 1 Feuchte · 2 Temperatur · 3 CO₂ · 4 Zeitprogramm · 5 Zentrale |
| 2 | CO₂-Sensor-Flag |
| 3 | Filterstatus (0 = OK) |
| 4–5 | Restzeit Stummmodus (Stunden) |
| 6 | Richtung (0 Wechsel · 1 Abluft · 2 Zuluft) |
| 7 | Volumenstrom (0 aus · 1 min · 2 med · 3 max) |
| 8–9 | Temperatur (°C) |
| 10–11 | relative Feuchte (%) |

## Bekannte Einschränkungen / Roadmap

- Gespeicherte Programmeinstellungen sind nicht auslesbar (siehe oben).
- Negative Temperaturen und einstellige Werte: das genaue Format am Gerät ist nicht verifiziert; der Parser akzeptiert `09`, ` 9` und `-5`.
- Noch nicht umgesetzt: **Zeitprogramm** (5 Schaltuhren, `ZP`/`PZ`, inkl. Uhrzeit-Synchronisation `SDT`), Richtung „Durchluft“, Filterstatus als Entität, CO₂-Programm und Zentrale.
- Die Taupunkt-Automatik ist als Home-Assistant-Automation/Blueprint geplant.

## Haftungsausschluss

Dies ist ein inoffizielles Community-Projekt ohne Gewähr. Limodor, Airodor und Airodor-G sind Marken ihrer jeweiligen Inhaber.

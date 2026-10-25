"""Konstanten für die Limodor-Airodor-Integration."""
from __future__ import annotations

DOMAIN = "limodor_airodor"

CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 15  # Sekunden
MIN_SCAN_INTERVAL = 10

# STA-Antwort: Programm (Position 1)
PROGRAMS = {0: "manuell", 1: "feuchte", 2: "temperatur", 3: "co2"}

# Richtung (Position 6)
DIR_ALTERNATING = 0  # Wechsel AB/ZU
DIR_EXHAUST = 1  # Abluft (AB)
DIR_SUPPLY = 2  # Zuluft (ZU)
DIRECTIONS = {
    DIR_ALTERNATING: "Wechsel",
    DIR_EXHAUST: "Abluft",
    DIR_SUPPLY: "Zuluft",
}

# Volumenstrom (Position 7)
VOL_OFF = 0
VOL_MIN = 1
VOL_MED = 2
VOL_MAX = 3
VOLUMES = [VOL_MIN, VOL_MED, VOL_MAX]
VOLUME_NAMES = {VOL_OFF: "Aus", VOL_MIN: "Minimal", VOL_MED: "Mittel", VOL_MAX: "Maximal"}

# Befehle zum Beenden der Automatik-Programme (P1 Feuchte, P2 Temperatur, P3 CO2)
STOP_PROGRAM_COMMANDS = ("P1S", "P2S", "P3S")

# Standardbetrieb: Abluft, minimaler Volumenstrom
DEFAULT_DIRECTION = DIR_EXHAUST
DEFAULT_VOLUME = VOL_MIN

MAX_MUTE_HOURS = 24

# Automatik-Programme: Befehlspräfix -> (Anzeigename, Einheit, Min, Max)
PROGRAM_DEFS = {
    "SP1": ("Feuchte-Programm", "%", 30, 90),
    "SP2": ("Temperatur-Programm", "°C", 5, 35),
}
PROGRAM_VOLUME_NAMES = {k: v for k, v in VOLUME_NAMES.items() if k != VOL_OFF}

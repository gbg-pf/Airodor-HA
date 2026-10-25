"""Minimaler HTTP-Client für den Limodor-Airodor-Lüfter.

Protokoll (aus der Android-App und eigenen Tests):
  GET http://<host>/msg?befehl=<BEFEHL>

  STA          -> "STA" + 11 Ziffern, siehe parse_status()
  NVF<d><v>    -> manuell: Richtung d (0 Wechsel, 1 Abluft, 2 Zuluft), Volumen v (0..3)
  STU<h>       -> Stummmodus für h Stunden (0 = beenden)
  SP1<rF><d><v>-> Programm 1 (Feuchte): Schwelle (2 Ziffern), Richtung, Volumen
  SP2<T><d><v> -> Programm 2 (Temperatur): Schwelle (2 Ziffern), Richtung, Volumen
  P1S/P2S/P3S  -> Programm 1/2/3 beenden
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

import aiohttp

# Feste Breite wie in der App: 11 Zeichen; Temperatur/rF je 2 Zeichen (Ziffern, ggf. "-" oder Leerzeichen).
_STA_RE = re.compile(r"STA(\d{7})([-\d ]{2})([-\d ]{2})")
REQUEST_TIMEOUT = 8


class LimodorError(Exception):
    """Fehler bei der Kommunikation mit dem Lüfter."""


@dataclass(frozen=True)
class LimodorState:
    """Dekodierter Status (STA)."""

    program: int  # 0 manuell, 1 Feuchte, 2 Temperatur, (3 CO2)
    mute_hours: int  # Restzeit Stummmodus in Stunden
    direction: int  # 0 Wechsel, 1 Abluft, 2 Zuluft
    volume: int  # 0 aus, 1 min, 2 med, 3 max
    temperature: int  # °C
    humidity: int  # % rF
    unknown: str  # Positionen 2-3 (noch nicht entschlüsselt)
    raw: str


def parse_status(text: str) -> LimodorState:
    """STA-Antwort zerlegen. Wirft LimodorError bei unerwartetem Format."""
    match = _STA_RE.search(text)
    if not match:
        raise LimodorError(f"Unerwartete Antwort auf STA: {text!r}")
    head, temp_s, hum_s = match.groups()
    try:
        temperature = int(temp_s.strip())
        humidity = int(hum_s.strip())
    except ValueError as err:
        raise LimodorError(f"Ungültige Temperatur/Feuchte in {text!r}") from err
    return LimodorState(
        program=int(head[0]),
        unknown=head[1:3],
        mute_hours=int(head[3:5]),
        direction=int(head[5]),
        volume=int(head[6]),
        temperature=temperature,
        humidity=humidity,
        raw=match.group(0)[3:],
    )


class LimodorApi:
    """Sendet Befehle an den Lüfter (sequenziell, das Gerät ist single-threaded)."""

    def __init__(self, session: aiohttp.ClientSession, host: str) -> None:
        self._session = session
        self._host = host
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        return self._host

    async def command(self, befehl: str) -> str:
        url = f"http://{self._host}/msg"
        last_err: Exception | None = None
        async with self._lock:
            for attempt in range(2):
                try:
                    async with asyncio.timeout(REQUEST_TIMEOUT):
                        async with self._session.get(
                            url, params={"befehl": befehl}
                        ) as resp:
                            resp.raise_for_status()
                            return await resp.text()
                except (aiohttp.ClientError, TimeoutError) as err:
                    last_err = err
                    await asyncio.sleep(0.5)
        raise LimodorError(f"Befehl {befehl} fehlgeschlagen: {last_err}") from last_err

    async def get_status(self) -> LimodorState:
        return parse_status(await self.command("STA"))

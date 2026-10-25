"""Limodor Airodor Lüfter – Home-Assistant-Integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LimodorApi, LimodorError, LimodorState
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_DIRECTION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_VOLUME,
    DOMAIN,
    STOP_PROGRAM_COMMANDS,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.FAN,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.BUTTON,
]

SERVICE_SET_HUMIDITY_PROGRAM = "set_humidity_program"
SERVICE_SET_TEMPERATURE_PROGRAM = "set_temperature_program"

_PROGRAM_SCHEMA = {
    vol.Optional("entry_id"): cv.string,
    vol.Required("threshold"): vol.All(vol.Coerce(int), vol.Range(min=0, max=99)),
    vol.Required("direction"): vol.In(["alternating", "exhaust", "supply"]),
    vol.Required("volume"): vol.In(["min", "med", "max"]),
}
_DIR_CODE = {"alternating": 0, "exhaust": 1, "supply": 2}
_VOL_CODE = {"min": 1, "med": 2, "max": 3}


class LimodorCoordinator(DataUpdateCoordinator[LimodorState]):
    """Pollt den Status und führt Befehle aus."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: LimodorApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.api = api
        # Programm-Einstellungen (der Lüfter liefert sie nicht zurück); werden von den
        # Number-/Select-Entitäten befüllt und per Button an den Lüfter gesendet.
        # Zuletzt an den Lüfter gesendete Programmwerte (für die Anzeige "aktiv/inaktiv")
        self.applied_programs: dict[str, dict[str, int]] = {}
        self._store: Store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
        self.program_settings: dict[str, dict[str, int]] = {
            "SP1": {"threshold": 65, "direction": 1, "volume": 2},  # Feuchte
            "SP2": {"threshold": 18, "direction": 1, "volume": 2},  # Temperatur
        }

    async def _async_update_data(self) -> LimodorState:
        try:
            return await self.api.get_status()
        except LimodorError as err:
            raise UpdateFailed(str(err)) from err

    async def async_send(self, *commands: str) -> None:
        """Befehle nacheinander senden, danach Status neu lesen."""
        try:
            for cmd in commands:
                await self.api.command(cmd)
            self.async_set_updated_data(await self.api.get_status())
        except LimodorError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_stop_programs(self) -> None:
        await self.async_send(*STOP_PROGRAM_COMMANDS)

    async def async_set_manual(self, direction: int, volume: int) -> None:
        """Alle Automatiken beenden (falls aktiv) und manuell Richtung/Volumen setzen."""
        cmds: list[str] = []
        if self.data is None or self.data.program != 0:
            cmds.extend(STOP_PROGRAM_COMMANDS)
        cmds.append(f"NVF{direction}{volume}")
        await self.async_send(*cmds)

    async def async_load_applied(self) -> None:
        self.applied_programs = await self._store.async_load() or {}

    async def async_apply_program(
        self, prefix: str, threshold: int, direction: int, volume: int
    ) -> None:
        """Programm (SP1 Feuchte / SP2 Temperatur) senden und die Werte merken."""
        await self.async_send(f"{prefix}{int(threshold):02d}{direction}{volume}")
        self.applied_programs[prefix] = {
            "threshold": int(threshold),
            "direction": int(direction),
            "volume": int(volume),
        }
        await self._store.async_save(self.applied_programs)
        self.async_update_listeners()

    async def async_activate_program(self, prefix: str) -> None:
        """Programm mit den in Home Assistant eingestellten Werten aktivieren."""
        p = self.program_settings[prefix]
        await self.async_apply_program(prefix, p["threshold"], p["direction"], p["volume"])

    async def async_set_default(self) -> None:
        """Normalbetrieb: Abluft, minimaler Volumenstrom."""
        await self.async_set_manual(DEFAULT_DIRECTION, DEFAULT_VOLUME)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = LimodorApi(async_get_clientsession(hass), entry.data[CONF_HOST])
    coordinator = LimodorCoordinator(hass, entry, api)
    await coordinator.async_load_applied()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SET_HUMIDITY_PROGRAM):
        return

    def _coordinator(call: ServiceCall) -> LimodorCoordinator:
        coordinators = hass.data.get(DOMAIN, {})
        entry_id = call.data.get("entry_id")
        if entry_id:
            if entry_id not in coordinators:
                raise HomeAssistantError(f"Unbekannte entry_id {entry_id}")
            return coordinators[entry_id]
        if not coordinators:
            raise HomeAssistantError("Kein Limodor-Lüfter eingerichtet")
        return next(iter(coordinators.values()))

    def _handler(prefix: str):
        async def handle(call: ServiceCall) -> None:
            await _coordinator(call).async_apply_program(
                prefix,
                call.data["threshold"],
                _DIR_CODE[call.data["direction"]],
                _VOL_CODE[call.data["volume"]],
            )

        return handle

    hass.services.async_register(
        DOMAIN, SERVICE_SET_HUMIDITY_PROGRAM, _handler("SP1"), vol.Schema(_PROGRAM_SCHEMA)
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_TEMPERATURE_PROGRAM,
        _handler("SP2"),
        vol.Schema(_PROGRAM_SCHEMA),
    )

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
from homeassistant.helpers import entity_registry as er
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
    PROGRAM_NUMBER,
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
# Entitäten früherer Versionen (Programm-Buttons, getrennte Programm-Entitäten, ...)
_OBSOLETE_KEYS = {
    "stop_programs",
    "SP1_activate", "SP2_activate",
    "SP1_direction", "SP1_volume", "SP1_threshold",
    "SP2_direction", "SP2_volume", "SP2_threshold",
    "SP1_threshold_active", "SP1_direction_active", "SP1_volume_active",
    "SP2_threshold_active", "SP2_direction_active", "SP2_volume_active",
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
        # Programm-Einstellungen: der Lüfter liefert sie nicht zurück, Home Assistant merkt
        # sie sich selbst (persistent). "applied": Programme, die HA schon gesendet hat.
        self._store: Store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
        self.program_settings: dict[str, dict[str, int]] = {
            "SP1": {"threshold": 65, "direction": 1, "volume": 2},  # Feuchte
            "SP2": {"threshold": 18, "direction": 1, "volume": 2},  # Temperatur
        }
        self.applied: set[str] = set()
        self.config_prefix = "SP1"  # Programm, dessen Einstellungen angezeigt/bearbeitet werden

    @property
    def active_prefix(self) -> str | None:
        """SP1/SP2, wenn das Feuchte-/Temperatur-Programm gerade läuft, sonst None."""
        if self.data is None:
            return None
        for prefix, number in PROGRAM_NUMBER.items():
            if self.data.program == number:
                return prefix
        return None

    @property
    def settings_prefix(self) -> str:
        """Programm, auf das sich die Programm-Einstellungen gerade beziehen."""
        return self.active_prefix or self.config_prefix

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

    async def async_load_state(self) -> None:
        data = await self._store.async_load() or {}
        for prefix, values in (data.get("settings") or {}).items():
            if prefix in self.program_settings and isinstance(values, dict):
                for key in ("threshold", "direction", "volume"):
                    if isinstance(values.get(key), int):
                        self.program_settings[prefix][key] = values[key]
        self.applied = {p for p in data.get("applied", []) if p in self.program_settings}
        if data.get("config") in self.program_settings:
            self.config_prefix = data["config"]
        # Altes Format (zuletzt gesendete Werte je Programm)
        for prefix in self.program_settings:
            old = data.get(prefix)
            if isinstance(old, dict) and "settings" not in data:
                for key in ("threshold", "direction", "volume"):
                    if isinstance(old.get(key), int):
                        self.program_settings[prefix][key] = old[key]
                self.applied.add(prefix)

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "settings": self.program_settings,
                "applied": sorted(self.applied),
                "config": self.config_prefix,
            }
        )

    async def async_start_program(
        self,
        prefix: str,
        threshold: int | None = None,
        direction: int | None = None,
        volume: int | None = None,
    ) -> None:
        """Programm starten bzw. neu senden. Zuvor laufende andere Programme werden gestoppt."""
        settings = self.program_settings[prefix]
        if threshold is not None:
            settings["threshold"] = int(threshold)
        if direction is not None:
            settings["direction"] = int(direction)
        if volume is not None:
            settings["volume"] = int(volume)
        cmds: list[str] = []
        if self.data is None or self.data.program not in (0, PROGRAM_NUMBER[prefix]):
            cmds.extend(STOP_PROGRAM_COMMANDS)
        cmds.append(
            f"{prefix}{settings['threshold']:02d}{settings['direction']}{settings['volume']}"
        )
        await self.async_send(*cmds)
        self.applied.add(prefix)
        self.config_prefix = prefix
        await self._async_save()
        self.async_update_listeners()

    async def async_update_setting(self, key: str, value: int) -> None:
        """Einstellung des aktiven bzw. zuletzt gewählten Programms ändern.

        Läuft das Programm, wird es sofort mit den neuen Werten neu gesendet.
        """
        prefix = self.settings_prefix
        self.program_settings[prefix][key] = int(value)
        if self.active_prefix == prefix:
            await self.async_start_program(prefix)
        else:
            await self._async_save()
            self.async_update_listeners()

    async def async_set_default(self) -> None:
        """Normalbetrieb: Abluft, minimaler Volumenstrom."""
        await self.async_set_manual(DEFAULT_DIRECTION, DEFAULT_VOLUME)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = LimodorApi(async_get_clientsession(hass), entry.data[CONF_HOST])
    coordinator = LimodorCoordinator(hass, entry, api)
    await coordinator.async_load_state()
    _remove_obsolete_entities(hass, entry)
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


def _remove_obsolete_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Entitäten früherer Versionen aus der Registry entfernen."""
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        key = ent.unique_id.removeprefix(prefix)
        if key in _OBSOLETE_KEYS or (ent.domain == "sensor" and key == "program"):
            registry.async_remove(ent.entity_id)


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
            await _coordinator(call).async_start_program(
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

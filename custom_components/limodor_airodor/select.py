"""Auswahlfelder: Richtung/Volumenstrom (manuell), Programm und Programm-Einstellungen."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LimodorCoordinator
from .const import (
    DIRECTIONS,
    DOMAIN,
    PROGRAM_DEFS,
    PROGRAM_MANUAL,
    PROGRAM_NUMBER,
    PROGRAM_OPTIONS,
    PROGRAM_PREFIX_BY_NAME,
    PROGRAM_VOLUME_NAMES,
    VOLUME_NAMES,
)
from .entity import LimodorEntity

_DIR_BY_NAME = {name: code for code, name in DIRECTIONS.items()}
_VOL_BY_NAME = {name: code for code, name in VOLUME_NAMES.items()}
_PROGRAM_NAME_BY_NUMBER = {
    PROGRAM_NUMBER[prefix]: d[0] for prefix, d in PROGRAM_DEFS.items()
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            LimodorDirectionSelect(coordinator),
            LimodorVolumeSelect(coordinator),
            LimodorProgramSelect(coordinator),
            LimodorProgramSettingSelect(coordinator, "direction"),
            LimodorProgramSettingSelect(coordinator, "volume"),
        ]
    )


class LimodorDirectionSelect(LimodorEntity, SelectEntity):
    """Richtung im manuellen Modus."""

    _attr_name = "Richtung"
    _attr_icon = "mdi:swap-vertical"
    _attr_options = list(DIRECTIONS.values())

    def __init__(self, coordinator: LimodorCoordinator) -> None:
        super().__init__(coordinator, "direction")

    @property
    def current_option(self) -> str | None:
        return DIRECTIONS.get(self.coordinator.data.direction)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_manual(
            _DIR_BY_NAME[option], self.coordinator.data.volume
        )


class LimodorVolumeSelect(LimodorEntity, SelectEntity):
    """Volumenstrom im manuellen Modus."""

    _attr_name = "Volumenstrom"
    _attr_icon = "mdi:fan-speed-2"
    _attr_options = list(VOLUME_NAMES.values())

    def __init__(self, coordinator: LimodorCoordinator) -> None:
        super().__init__(coordinator, "volume")

    @property
    def current_option(self) -> str | None:
        return VOLUME_NAMES.get(self.coordinator.data.volume)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_manual(
            self.coordinator.data.direction, _VOL_BY_NAME[option]
        )


class LimodorProgramSelect(LimodorEntity, SelectEntity):
    """Aktuelles Programm anzeigen und wechseln (Manuell / Feuchte / Temperatur).

    Beim Wechsel werden zuerst alle laufenden Programme gestoppt.
    """

    _attr_name = "Programm"
    _attr_icon = "mdi:robot"
    _attr_options = PROGRAM_OPTIONS

    def __init__(self, coordinator: LimodorCoordinator) -> None:
        super().__init__(coordinator, "program_select")

    @property
    def current_option(self) -> str | None:
        program = self.coordinator.data.program
        if program == 0:
            return PROGRAM_MANUAL
        return _PROGRAM_NAME_BY_NUMBER.get(program)  # CO2/Zeit/Zentrale: unbekannt

    async def async_select_option(self, option: str) -> None:
        if option == PROGRAM_MANUAL:
            await self.coordinator.async_stop_programs()
        else:
            await self.coordinator.async_start_program(PROGRAM_PREFIX_BY_NAME[option])


class LimodorProgramSettingSelect(LimodorEntity, SelectEntity):
    """Richtung/Volumenstrom des aktiven (bzw. zuletzt gewählten) Programms.

    Läuft das Programm, wird die Änderung sofort an den Lüfter gesendet.
    """

    def __init__(self, coordinator: LimodorCoordinator, kind: str) -> None:
        super().__init__(coordinator, f"program_setting_{kind}")
        self._kind = kind
        names = DIRECTIONS if kind == "direction" else PROGRAM_VOLUME_NAMES
        self._names = names
        self._codes = {name: code for code, name in names.items()}
        self._attr_options = list(names.values())
        label = "Richtung" if kind == "direction" else "Volumenstrom"
        self._attr_name = f"Programm-Einstellung {label}"
        self._attr_icon = "mdi:swap-vertical" if kind == "direction" else "mdi:fan-speed-2"

    @property
    def current_option(self) -> str | None:
        prefix = self.coordinator.settings_prefix
        return self._names.get(self.coordinator.program_settings[prefix][self._kind])

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"programm": PROGRAM_DEFS[self.coordinator.settings_prefix][0]}

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_update_setting(self._kind, self._codes[option])

"""Stummmodus in Stunden (0 = beenden)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LimodorCoordinator
from .const import DOMAIN, MAX_MUTE_HOURS, PROGRAM_DEFS
from .entity import LimodorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LimodorMuteNumber(coordinator), LimodorProgramThreshold(coordinator)])


class LimodorMuteNumber(LimodorEntity, NumberEntity):
    _attr_name = "Stummmodus"
    _attr_icon = "mdi:volume-off"
    _attr_native_min_value = 0
    _attr_native_max_value = MAX_MUTE_HOURS
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: LimodorCoordinator) -> None:
        super().__init__(coordinator, "mute")

    @property
    def native_value(self) -> float:
        return self.coordinator.data.mute_hours

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_send(f"STU{int(value)}")


class LimodorProgramThreshold(LimodorEntity, NumberEntity):
    """Schwelle des aktiven (bzw. zuletzt gewählten) Programms.

    Einheit und Bereich folgen dem Programm (Feuchte: %, Temperatur: °C). Läuft das
    Programm, wird die Änderung sofort an den Lüfter gesendet.
    """

    _attr_name = "Programm-Einstellung Schwelle"
    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_icon = "mdi:tune"

    def __init__(self, coordinator: LimodorCoordinator) -> None:
        super().__init__(coordinator, "program_setting_threshold")

    @property
    def _definition(self) -> tuple[str, str, int, int]:
        return PROGRAM_DEFS[self.coordinator.settings_prefix]

    @property
    def native_unit_of_measurement(self) -> str:
        return self._definition[1]

    @property
    def native_min_value(self) -> float:
        return self._definition[2]

    @property
    def native_max_value(self) -> float:
        return self._definition[3]

    @property
    def native_value(self) -> float:
        return self.coordinator.program_settings[self.coordinator.settings_prefix]["threshold"]

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        return {"programm": self._definition[0]}

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_update_setting("threshold", int(value))

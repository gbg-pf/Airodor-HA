"""Stummmodus in Stunden (0 = beenden)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
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
    async_add_entities(
        [LimodorMuteNumber(coordinator)]
        + [LimodorProgramThreshold(coordinator, prefix) for prefix in PROGRAM_DEFS]
    )


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


class LimodorProgramThreshold(LimodorEntity, RestoreNumber):
    """Schwelle eines Automatik-Programms (wird in HA gemerkt, nicht vom Lüfter gelesen)."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_icon = "mdi:tune"

    def __init__(self, coordinator: LimodorCoordinator, prefix: str) -> None:
        super().__init__(coordinator, f"{prefix}_threshold")
        name, unit, vmin, vmax = PROGRAM_DEFS[prefix]
        self._prefix = prefix
        self._attr_name = f"{name} Schwelle"
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = vmin
        self._attr_native_max_value = vmax
        self._attr_native_value = coordinator.program_settings[prefix]["threshold"]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_number_data()
        if last is not None and last.native_value is not None:
            self._attr_native_value = last.native_value
        self.coordinator.program_settings[self._prefix]["threshold"] = int(
            self._attr_native_value
        )

    @property
    def native_value(self) -> float:
        return self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.coordinator.program_settings[self._prefix]["threshold"] = int(value)
        self.async_write_ha_state()

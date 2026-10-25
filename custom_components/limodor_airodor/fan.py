"""Lüfter-Entität: Ein/Aus und Volumenstrom (min/med/max) im manuellen Modus."""
from __future__ import annotations

from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import LimodorCoordinator
from .const import (
    DIR_ALTERNATING,
    DIR_SUPPLY,
    DIRECTIONS,
    DOMAIN,
    PROGRAMS,
    VOL_MIN,
    VOL_OFF,
    VOLUMES,
)
from .entity import LimodorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([LimodorFan(hass.data[DOMAIN][entry.entry_id])])


class LimodorFan(LimodorEntity, FanEntity):
    _attr_name = None  # Gerätename
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = len(VOLUMES)

    def __init__(self, coordinator: LimodorCoordinator) -> None:
        super().__init__(coordinator, "fan")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.volume > VOL_OFF

    @property
    def percentage(self) -> int | None:
        vol = self.coordinator.data.volume
        if vol == VOL_OFF:
            return 0
        if vol not in VOLUMES:
            return None
        return ordered_list_item_to_percentage(VOLUMES, vol)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        return {
            "richtung": DIRECTIONS.get(data.direction),
            "programm": PROGRAMS.get(data.program),
            "stumm_rest_h": data.mute_hours,
        }

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        volume = percentage_to_ordered_list_item(VOLUMES, percentage)
        await self.coordinator.async_set_manual(self.coordinator.data.direction, volume)

    async def async_turn_on(
        self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any
    ) -> None:
        if percentage:
            await self.async_set_percentage(percentage)
        else:
            await self.coordinator.async_set_manual(
                self.coordinator.data.direction, VOL_MIN
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Beobachtet: "NVF20" = aus, Richtung zu. Bei Wechsel-Richtung "zu" verwenden.
        direction = self.coordinator.data.direction
        if direction == DIR_ALTERNATING:
            direction = DIR_SUPPLY
        await self.coordinator.async_set_manual(direction, VOL_OFF)

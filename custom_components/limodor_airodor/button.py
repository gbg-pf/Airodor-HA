"""Buttons: Automatiken stoppen, Normalbetrieb herstellen."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LimodorCoordinator
from .const import DOMAIN, PROGRAM_DEFS
from .entity import LimodorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [LimodorStopPrograms(coordinator), LimodorDefaultMode(coordinator)]
        + [LimodorActivateProgram(coordinator, prefix) for prefix in PROGRAM_DEFS]
    )


class LimodorStopPrograms(LimodorEntity, ButtonEntity):
    _attr_name = "Automatiken stoppen"
    _attr_icon = "mdi:robot-off"

    def __init__(self, coordinator: LimodorCoordinator) -> None:
        super().__init__(coordinator, "stop_programs")

    async def async_press(self) -> None:
        await self.coordinator.async_stop_programs()


class LimodorDefaultMode(LimodorEntity, ButtonEntity):
    _attr_name = "Normalbetrieb (Abluft, minimal)"
    _attr_icon = "mdi:fan-chevron-down"

    def __init__(self, coordinator: LimodorCoordinator) -> None:
        super().__init__(coordinator, "default_mode")

    async def async_press(self) -> None:
        await self.coordinator.async_set_default()


class LimodorActivateProgram(LimodorEntity, ButtonEntity):
    """Aktiviert ein Automatik-Programm mit den in HA eingestellten Werten."""

    _attr_icon = "mdi:play-circle"

    def __init__(self, coordinator: LimodorCoordinator, prefix: str) -> None:
        super().__init__(coordinator, f"{prefix}_activate")
        self._prefix = prefix
        self._attr_name = f"{PROGRAM_DEFS[prefix][0]} aktivieren"

    async def async_press(self) -> None:
        await self.coordinator.async_activate_program(self._prefix)

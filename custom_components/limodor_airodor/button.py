"""Button: Normalbetrieb (Automatiken stoppen, Abluft, minimaler Volumenstrom)."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LimodorCoordinator
from .const import DOMAIN
from .entity import LimodorEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([LimodorDefaultMode(coordinator)])


class LimodorDefaultMode(LimodorEntity, ButtonEntity):
    _attr_name = "Normalbetrieb (Abluft, minimal)"
    _attr_icon = "mdi:fan-chevron-down"

    def __init__(self, coordinator: LimodorCoordinator) -> None:
        super().__init__(coordinator, "default_mode")

    async def async_press(self) -> None:
        await self.coordinator.async_set_default()

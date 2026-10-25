"""Basisklasse der Entitäten."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LimodorCoordinator
from .const import DOMAIN


class LimodorEntity(CoordinatorEntity[LimodorCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: LimodorCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name=coordinator.config_entry.title,
            manufacturer="Limodor",
            model="Airodor",
            configuration_url=f"http://{coordinator.api.host}/",
        )

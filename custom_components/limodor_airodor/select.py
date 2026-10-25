"""Auswahl der Richtung (Wechsel / Abluft / Zuluft) im manuellen Modus."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import LimodorCoordinator
from .const import DIRECTIONS, DOMAIN, PROGRAM_DEFS, PROGRAM_VOLUME_NAMES, VOLUME_NAMES
from .entity import LimodorEntity

_BY_NAME = {name: code for code, name in DIRECTIONS.items()}
_VOL_BY_NAME = {name: code for code, name in VOLUME_NAMES.items()}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [LimodorDirectionSelect(coordinator), LimodorVolumeSelect(coordinator)]
    for prefix in PROGRAM_DEFS:
        entities.append(LimodorProgramSelect(coordinator, prefix, "direction"))
        entities.append(LimodorProgramSelect(coordinator, prefix, "volume"))
    async_add_entities(entities)


class LimodorDirectionSelect(LimodorEntity, SelectEntity):
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
            _BY_NAME[option], self.coordinator.data.volume
        )


class LimodorVolumeSelect(LimodorEntity, SelectEntity):
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


class LimodorProgramSelect(LimodorEntity, SelectEntity, RestoreEntity):
    """Richtung bzw. Volumenstrom eines Automatik-Programms (in HA gemerkt)."""

    def __init__(self, coordinator: LimodorCoordinator, prefix: str, kind: str) -> None:
        super().__init__(coordinator, f"{prefix}_{kind}")
        self._prefix = prefix
        self._kind = kind
        names = DIRECTIONS if kind == "direction" else PROGRAM_VOLUME_NAMES
        self._codes = {name: code for code, name in names.items()}
        self._attr_options = list(names.values())
        label = "Richtung" if kind == "direction" else "Volumenstrom"
        self._attr_name = f"{PROGRAM_DEFS[prefix][0]} {label}"
        self._attr_icon = "mdi:swap-vertical" if kind == "direction" else "mdi:fan-speed-2"
        self._attr_current_option = names[coordinator.program_settings[prefix][kind]]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in self._codes:
            self._attr_current_option = last.state
        self._store()

    def _store(self) -> None:
        self.coordinator.program_settings[self._prefix][self._kind] = self._codes[
            self._attr_current_option
        ]

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        self._store()
        self.async_write_ha_state()

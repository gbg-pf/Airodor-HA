"""Sensoren: Temperatur, Feuchte, absolute Feuchte, Taupunkt, Programm, Stummrest."""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LimodorCoordinator
from .api import LimodorState
from .const import DIRECTIONS, DOMAIN, PROGRAM_DEFS, PROGRAMS, VOLUME_NAMES
from .entity import LimodorEntity


def absolute_humidity(temp_c: float, rh: float) -> float:
    """Absolute Feuchte in g/m³ (Formel aus den Notizen)."""
    sat = math.exp(19.016 - 4064.95 / (temp_c + 236.25))
    return round(1000 * sat * 100 / (461.66 * (temp_c + 273.15)) * rh / 100, 2)


def dew_point(temp_c: float, rh: float) -> float | None:
    """Taupunkt in °C (Magnus)."""
    if rh <= 0:
        return None
    a, b = 17.62, 243.12
    gamma = math.log(rh / 100) + a * temp_c / (b + temp_c)
    return round(b * gamma / (a - gamma), 1)


@dataclass(frozen=True, kw_only=True)
class LimodorSensorDescription(SensorEntityDescription):
    value_fn: Callable[[LimodorState], float | str | None]


SENSORS: tuple[LimodorSensorDescription, ...] = (
    LimodorSensorDescription(
        key="temperature",
        name="Temperatur",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.temperature,
    ),
    LimodorSensorDescription(
        key="humidity",
        name="Luftfeuchtigkeit",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.humidity,
    ),
    LimodorSensorDescription(
        key="absolute_humidity",
        name="Absolute Feuchte",
        native_unit_of_measurement="g/m³",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent-alert",
        value_fn=lambda s: absolute_humidity(s.temperature, s.humidity),
    ),
    LimodorSensorDescription(
        key="dew_point",
        name="Taupunkt",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: dew_point(s.temperature, s.humidity),
    ),
    LimodorSensorDescription(
        key="program",
        name="Programm",
        device_class=SensorDeviceClass.ENUM,
        options=list(PROGRAMS.values()),
        icon="mdi:robot",
        value_fn=lambda s: PROGRAMS.get(s.program),
    ),
    LimodorSensorDescription(
        key="mute_remaining",
        name="Stummmodus Restzeit",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.mute_hours,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [LimodorSensor(coordinator, d) for d in SENSORS]
    for prefix in PROGRAM_DEFS:
        for kind in ("threshold", "direction", "volume"):
            entities.append(LimodorProgramSensor(coordinator, prefix, kind))
    async_add_entities(entities)


class LimodorSensor(LimodorEntity, SensorEntity):
    entity_description: LimodorSensorDescription

    def __init__(
        self, coordinator: LimodorCoordinator, description: LimodorSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)


PROGRAM_NUMBER = {"SP1": 1, "SP2": 2}  # Wert in Stelle 1 der STA-Antwort
_KIND_LABEL = {"threshold": "Schwelle", "direction": "Richtung", "volume": "Volumenstrom"}
_KIND_ICON = {
    "threshold": "mdi:tune",
    "direction": "mdi:swap-vertical",
    "volume": "mdi:fan-speed-2",
}


class LimodorProgramSensor(LimodorEntity, SensorEntity):
    """Wirksame Programmwerte; "Inaktiv", solange das Programm nicht läuft.

    Der Lüfter meldet die Werte nicht zurück. Angezeigt werden die zuletzt aus
    Home Assistant gesendeten Werte ("Unbekannt", falls das Programm anderweitig
    gestartet wurde).
    """

    def __init__(self, coordinator: LimodorCoordinator, prefix: str, kind: str) -> None:
        super().__init__(coordinator, f"{prefix}_{kind}_active")
        self._prefix = prefix
        self._kind = kind
        self._attr_name = f"{PROGRAM_DEFS[prefix][0]} {_KIND_LABEL[kind]} (aktiv)"
        self._attr_icon = _KIND_ICON[kind]

    @property
    def native_value(self) -> str:
        if self.coordinator.data.program != PROGRAM_NUMBER[self._prefix]:
            return "Inaktiv"
        applied = self.coordinator.applied_programs.get(self._prefix)
        if not applied:
            return "Unbekannt"
        value = applied[self._kind]
        if self._kind == "direction":
            return DIRECTIONS.get(value, "Unbekannt")
        if self._kind == "volume":
            return VOLUME_NAMES.get(value, "Unbekannt")
        return f"{value} {PROGRAM_DEFS[self._prefix][1]}"

"""Green Mountain Grill diagnostic sensors.

Surfaces grill health fields the API returns but the climate entities don't:
fire state, fire percentage, warning code, and power state. Enum meanings are
from the reverse-engineered GMG UDP protocol
(ref: github.com/brandenc40/green-mountain-grill).
"""
from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# raw byte value -> human label
FIRE_STATE = {0: "Default", 1: "Off", 2: "Startup", 3: "Running",
              4: "Cool Down", 5: "Fail", 198: "Cold Smoke"}
WARN_CODE = {0: "None", 1: "Fan Overload", 2: "Auger Overload",
             3: "Ignitor Overload", 4: "Low Voltage Battery",
             5: "Fan Disconnect", 6: "Auger Disconnect",
             7: "Ignitor Disconnect", 8: "Low Pellet"}
POWER_STATE = {0: "Off", 1: "On", 2: "Fan", 3: "Cold Smoke"}
UNKNOWN = "Unknown"


def _build_entities(coordinator):
    """Build sensor entities for one grill's coordinator."""
    return [
        GmgTempSensor(coordinator, "Temperature", "temperature",
                      "temp", is_probe=False),
        GmgTempSensor(coordinator, "Probe 1 Temperature",
                      "probe_1_temperature", "probe1_temp", is_probe=True),
        GmgTempSensor(coordinator, "Probe 2 Temperature",
                      "probe_2_temperature", "probe2_temp", is_probe=True),
        GmgEnumSensor(coordinator, "Fire State", "fire_state",
                      "fireState", FIRE_STATE, "mdi:fire"),
        GmgEnumSensor(coordinator, "Warning", "warn_code",
                      "warnState", WARN_CODE, "mdi:alert"),
        GmgEnumSensor(coordinator, "Power State", "power_state",
                      "powerState", POWER_STATE, "mdi:power"),
        GmgFirePercentSensor(coordinator),
        GmgApiVersionSensor(coordinator),
    ]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Green Mountain Grill sensors from the shared coordinators."""
    entities = []
    for coordinator in hass.data[DOMAIN][entry.entry_id]:
        entities.extend(_build_entities(coordinator))
    async_add_entities(entities)


class _GmgSensorBase(CoordinatorEntity, SensorEntity):
    """Shared plumbing: read the coordinator's shared status, never poll."""

    def __init__(self, coordinator, label, key_suffix, icon) -> None:
        super().__init__(coordinator)
        self._grill = coordinator.grill
        self._attr_name = f"Green Mountain Grill {label}"
        self._attr_unique_id = f"{self._grill._serial_number}_{key_suffix}"
        self._attr_icon = icon

    @property
    def _state(self) -> dict:
        """Latest shared status from the coordinator."""
        return self.coordinator.data or {}


class GmgEnumSensor(_GmgSensorBase):
    """An enum sensor mapping a raw status byte to a human label."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, coordinator, label, key_suffix, state_key, mapping, icon) -> None:
        self._state_key = state_key
        self._mapping = mapping
        self._attr_options = list(mapping.values()) + [UNKNOWN]
        super().__init__(coordinator, label, key_suffix, icon)

    @property
    def native_value(self):
        raw = self._state.get(self._state_key)
        if raw is None:
            return None
        return self._mapping.get(raw, UNKNOWN)


class GmgFirePercentSensor(_GmgSensorBase):
    """Progress through the current fire state, in four 25% steps (byte 33).

    GMG's own cloud API names this field `fireStateProgress`, which is what it
    is: it steps 25/50/75/100 up through Startup, lands on 100 at the exact
    Startup -> Running edge, and steps back down to 0 through Cool Down. It is
    NOT a continuous fan/fire drive percentage, and it is NOT a pellet-hopper
    level. See the README's "Fire state progress".

    What each step physically means is still unsourced - show the step number,
    not an invented label.
    """

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(
            coordinator, "Fire State Progress", "fire_state_progress", "mdi:fire"
        )

    @property
    def native_value(self):
        return self._state.get("fireStatePercentage")


class GmgApiVersionSensor(_GmgSensorBase):
    """Grill protocol/API version - a static diagnostic value (byte 8)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "API Version", "api_version", "mdi:chip")

    @property
    def native_value(self):
        return self._state.get("apiVersion")


class GmgTempSensor(_GmgSensorBase):
    """Grill / probe temperature as a graphable, gauge-able sensor (F).

    Mirrors the climate entities' current_temperature but as a first-class
    numeric sensor so it can drive gauges, history graphs, and threshold
    automations. Probes report None when unplugged (>257 F sentinel).
    """

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, label, key_suffix, state_key, is_probe=False) -> None:
        self._state_key = state_key
        self._is_probe = is_probe
        super().__init__(coordinator, label, key_suffix, "mdi:thermometer")

    @property
    def native_value(self):
        temp = self._state.get(self._state_key)
        if temp is None:
            return None
        if self._is_probe and temp > self._grill.MAX_TEMP_F_PROBE:
            return None  # probe unplugged
        return temp

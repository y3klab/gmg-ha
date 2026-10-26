"""Green Mountain Grill probe-connectivity and low pellet binary sensors.

A food probe reports a sentinel above its max (~607 F) when unplugged, so
"connected" = the reading is a physically valid probe temperature. Exposed as
connectivity binary sensors so you can see at a glance - and automate on - a
probe falling out mid-cook.

The grill's low pellet alarm is a problem binary sensor: the stable thing to
automate or notify on, where the Warning sensor is the human detail.
"""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .entity import GmgEntity
from .const import DOMAIN, WARN_LOW_PELLET, WARN_NONE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up probe and low pellet sensors from the shared coordinators."""
    entities = []
    for coordinator in hass.data[DOMAIN][entry.entry_id]:
        for probe in (1, 2):
            entities.append(GmgProbeConnection(coordinator, probe))
        entities.append(GmgLowPellet(coordinator))
    async_add_entities(entities)


class GmgProbeConnection(GmgEntity, BinarySensorEntity):
    """True when a food probe is plugged in (reading a valid temperature)."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, probe_count) -> None:
        super().__init__(coordinator, f"probe_{probe_count}_connection")
        self._probe = probe_count
        self._attr_name = f"Probe {probe_count} Connection"

    @property
    def _state(self) -> dict:
        """Latest shared status from the coordinator."""
        return self._status

    @property
    def is_on(self):
        """connectivity device_class: on = connected."""
        temp = self._state.get(f'probe{self._probe}_temp')
        if temp is None:
            return None
        return temp <= self._grill.MAX_TEMP_F_PROBE


class GmgLowPellet(GmgEntity, BinarySensorEntity):
    """True when the grill raises its low pellet alarm (warning code 0x80).

    Off only at warning code 0. Any other code is unknown, not off: it has no
    observed meaning, and reading it as "pellets fine" could hide the alarm.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "low_pellet")
        self._attr_name = "Low Pellet"

    @property
    def _state(self) -> dict:
        """Latest shared status from the coordinator."""
        return self._status

    @property
    def is_on(self):
        """problem device_class: on = low pellet alarm raised."""
        return {WARN_NONE: False, WARN_LOW_PELLET: True}.get(
            self._state.get("warnState")
        )

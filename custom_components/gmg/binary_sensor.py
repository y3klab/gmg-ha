"""Green Mountain Grill probe-connectivity binary sensors.

A food probe reports a sentinel above its max (~607 F) when unplugged, so
"connected" = the reading is a physically valid probe temperature. Exposed as
connectivity binary sensors so you can see at a glance - and automate on - a
probe falling out mid-cook.
"""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)

from .entity import GmgEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up probe connectivity sensors from the shared coordinators."""
    entities = []
    for coordinator in hass.data[DOMAIN][entry.entry_id]:
        for probe in (1, 2):
            entities.append(GmgProbeConnection(coordinator, probe))
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

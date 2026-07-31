"""The shared entity base - device identity and coordinator plumbing.

Every entity in this integration belongs to one device: the grill. Grouping
them under a device registry entry is what gives Home Assistant somewhere to
show them together, and what lets a user rename the grill once rather than
thirteen times.
"""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

# The company is "Green Mountain Grills", plural. A single appliance is a
# grill, singular - which is why the manufacturer and the device name differ
# by a letter on purpose.
MANUFACTURER = "Green Mountain Grills"
DEVICE_NAME = "Green Mountain Grill"


class GmgEntity(CoordinatorEntity):
    """Base for every gmg entity: one device, one coordinator, no polling.

    ``has_entity_name`` means each entity supplies only its own short name and
    Home Assistant composes the rest from the device. So this class sets
    ``"Fire State Progress"`` rather than ``"Green Mountain Grill Fire State
    Progress"`` - the brand appears once, on the device, and follows a user's
    rename instead of being frozen into thirteen strings.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator, unique_id_suffix: str | None = None) -> None:
        super().__init__(coordinator)
        self._grill = coordinator.grill

        serial = self._grill.serial_number
        self._attr_unique_id = f"{serial}_{unique_id_suffix}" if unique_id_suffix else serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial)},
            name=DEVICE_NAME,
            manufacturer=MANUFACTURER,
            serial_number=serial,
        )

    @property
    def _status(self) -> dict[str, Any]:
        """Most recent status the coordinator fetched, empty before first poll."""
        return self.coordinator.data or {}

    @property
    def _power(self) -> int | None:
        """The grill's power byte - 0 off, 1 on, 2 fan-only."""
        return self._status.get("powerState")

"""Polling coordinator for the Green Mountain Grill integration.

One coordinator per grill. It owns the only conversation with the hardware:
every entity reads ``coordinator.data`` instead of polling for itself. That
matters here more than in most integrations - the grill answers a single client
at a time, so N entities polling independently knock each other offline.

The cadence adapts (see ``gmg.poll_interval_for``): ~10s while the grill is
doing something, ~60s once it is off. A brisket cook is worth a tight loop; a
cold grill sitting in the yard for three days is not.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from gmg_local import POLL_ACTIVE, poll_interval_for

_LOGGER = logging.getLogger(__name__)


class GmgCoordinator(DataUpdateCoordinator):
    """Fetch grill status once per cycle and share it with every entity."""

    def __init__(self, hass: HomeAssistant, grill) -> None:
        self.grill = grill
        super().__init__(
            hass,
            _LOGGER,
            name=f"Green Mountain Grill {grill.serial_number}",
            update_interval=timedelta(seconds=POLL_ACTIVE),
        )

    async def _async_update_data(self) -> dict:
        """One status round-trip, in the executor (the grill library blocks)."""
        try:
            data = await self.hass.async_add_executor_job(self.grill.status)
        except Exception as err:
            # Entities go unavailable via CoordinatorEntity.available, and the
            # last good data is retained for us - no stale-grace bookkeeping.
            raise UpdateFailed(str(err)) from err

        wanted = timedelta(seconds=poll_interval_for(data))
        if wanted != self.update_interval:
            _LOGGER.debug(
                "GMG %s: poll interval %s -> %s",
                self.grill.serial_number, self.update_interval, wanted,
            )
            # The base class reschedules the timer after every refresh, so the
            # new interval takes effect from the next cycle either way.
            self.update_interval = wanted

        return data

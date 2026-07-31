"""Climate entities for a Green Mountain Grills pellet grill.

Three entities per grill: the grill itself, and one for each food probe. All of
them read from the shared coordinator and none of them touch the network on
their own - the grill answers a single client at a time, so concurrent
conversations lose messages.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import GmgEntity

_LOGGER = logging.getLogger(__name__)

# The controller itself moves in 5-degree steps, so a 1-degree dial invites
# setpoints it will silently round. Probes are different: a food target is an
# exact number (203 F brisket), not a coarse dial.
STEP_GRILL = 5
STEP_PROBE = 1

# The grill refuses setpoint changes until it is up to temperature; its manual
# puts that at 150 F. A few degrees of slack avoids fighting sensor jitter.
SETPOINT_FLOOR_F = 145

# powerState byte: 0 off, 1 on, 2 fan-only.
_POWER_OFF = 0
_POWER_ON = 1
_POWER_FAN = 2

# Returned by the setpoint pre-check when nothing needs sending and nothing is
# wrong - distinct from a refusal, which is worth logging.
_ALREADY_SET = "already the target"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Hand a legacy ``climate: - platform: gmg`` block to the config flow."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Build one grill entity and two probe entities per discovered grill."""
    entities: list[ClimateEntity] = []
    for coordinator in hass.data[DOMAIN][entry.entry_id]:
        entities.append(GmgGrill(coordinator))
        entities.extend(GmgGrillProbe(coordinator, n) for n in (1, 2))
    async_add_entities(entities)


class _GmgClimateBase(GmgEntity, ClimateEntity):
    """Shared plumbing: read the coordinator, never poll.

    Both report Fahrenheit - the wire format is Fahrenheit regardless of what
    the app displays.
    """

    _attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
    _enable_turn_on_off_backwards_compatibility = False

    async def _push(self, func, *args) -> bool:
        """Run a blocking grill call off the event loop, then refresh.

        Returns False if the call raised, so callers can skip the refresh and
        any read-back check that would only report the same failure twice.
        """
        try:
            await self.hass.async_add_executor_job(func, *args)
        except Exception:  # noqa: BLE001 - surface whatever the grill throws
            _LOGGER.exception("Grill rejected %s%r", func.__name__, args)
            return False
        await self.coordinator.async_request_refresh()
        return True


class GmgGrill(_GmgClimateBase):
    """The grill itself - target temperature, and on / fan / off."""

    _attr_icon = "mdi:grill"
    _attr_target_temperature_step = STEP_GRILL
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.FAN_ONLY, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    # The primary entity of the device: `None` means "just the device name",
    # so this reads as "Green Mountain Grill" rather than "... Grill Grill".
    _attr_name = None

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)

    # --- what the grill is doing ------------------------------------------

    @property
    def hvac_mode(self) -> HVACMode:
        if self._power == _POWER_ON:
            return HVACMode.HEAT
        if self._power == _POWER_FAN:
            return HVACMode.FAN_ONLY
        return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        return self._status.get("temp")

    @property
    def target_temperature(self) -> float | None:
        return self._status.get("grill_set_temp")

    @property
    def min_temp(self) -> float:
        return self._grill.MIN_TEMP_F

    @property
    def max_temp(self) -> float:
        return self._grill.MAX_TEMP_F

    # --- changing it -------------------------------------------------------

    def _refusal_reason(self, wanted: float) -> str | None:
        """Why the grill would not take this setpoint, or None if it would.

        Checked before sending rather than after, because the grill
        acknowledges nothing - on the wire a refused write looks exactly like
        an accepted one.
        """
        if wanted == self._status.get("grill_set_temp"):
            return _ALREADY_SET
        if self._power == _POWER_OFF:
            return "the grill is off"
        reading = self._status.get("temp", 0)
        if reading < SETPOINT_FLOOR_F:
            return f"it is only at {reading} F and must reach 150 F first"
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        wanted = kwargs.get(ATTR_TEMPERATURE)
        if wanted is None:
            return

        reason = self._refusal_reason(wanted)
        if reason is not None:
            if reason is not _ALREADY_SET:
                _LOGGER.warning("Not setting grill to %s F: %s", wanted, reason)
            return

        await self._push(self._grill.set_temp, int(wanted))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        command = {
            HVACMode.HEAT: self._grill.power_on,
            HVACMode.FAN_ONLY: self._grill.power_on_cool,
            HVACMode.OFF: self._grill.power_off,
        }.get(hvac_mode)

        if command is None:
            _LOGGER.error("Cannot put the grill into %s", hvac_mode)
            return

        await self._push(command)

    async def async_turn_on(self) -> None:
        await self._push(self._grill.power_on)

    async def async_turn_off(self) -> None:
        await self._push(self._grill.power_off)


class GmgGrillProbe(_GmgClimateBase):
    """One food probe: a target temperature, and whether it is plugged in.

    Modelled as a climate entity because it carries a setpoint, but it has no
    modes of its own - the grill decides whether anything is cooking.
    """

    _attr_icon = "mdi:thermometer-lines"
    _attr_target_temperature_step = STEP_PROBE
    _attr_hvac_modes = [HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(self, coordinator, number: int) -> None:
        super().__init__(coordinator, f"probe_{number}")
        self._attr_name = f"Probe {number}"
        self._number = number

    # --- reading -----------------------------------------------------------

    @property
    def _temp_key(self) -> str:
        return f"probe{self._number}_temp"

    @property
    def _target_key(self) -> str:
        return f"probe{self._number}_set_temp"

    def _is_connected(self) -> bool:
        """Unplugged probes read a sentinel well above their rated maximum."""
        reading = self._status.get(self._temp_key)
        return reading is not None and reading <= self._grill.MAX_TEMP_F_PROBE

    @property
    def hvac_mode(self) -> HVACMode:
        if self._power == _POWER_ON and self._is_connected():
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """None while unplugged, rather than the sentinel value."""
        return self._status.get(self._temp_key) if self._is_connected() else None

    @property
    def target_temperature(self) -> float | None:
        return self._status.get(self._target_key)

    @property
    def min_temp(self) -> float:
        """Zero, not the probe's 32 F floor, so the dial can clear the target.

        Whether the grill actually treats 0 as "no target" is UNVERIFIED
        against hardware.
        """
        return self._grill.PROBE_TARGET_CLEAR

    @property
    def max_temp(self) -> float:
        return self._grill.MAX_TEMP_F_PROBE

    # --- writing -----------------------------------------------------------

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Send a probe target, then confirm the grill actually took it.

        The grill **silently discards probe writes while it is off** - verified
        against hardware 2026-07-24, when a write of 203 read back as 0 with no
        error. Refusing up front is honest; sending anyway would leave the dial
        showing a target the grill never accepted.

        That test could not separate "grill off" from "probe unplugged", since
        both were true at the time. If it turns out only the probe must be
        connected, this guard can relax to :meth:`_is_connected`.
        """
        wanted = kwargs.get(ATTR_TEMPERATURE)
        if wanted is None or wanted == self._status.get(self._target_key):
            return

        if self._power == _POWER_OFF:
            _LOGGER.warning(
                "Grill is off - probe %d target %s not sent, it would be discarded",
                self._number,
                wanted,
            )
            return

        if not await self._push(self._grill.set_temp_probe, int(wanted), self._number):
            return

        # The grill acknowledges nothing, so the read-back is the only
        # acknowledgement available.
        accepted = self._status.get(self._target_key)
        if accepted != int(wanted):
            _LOGGER.warning(
                "Probe %d target %d was not accepted - grill still reports %s",
                self._number,
                int(wanted),
                accepted,
            )

"""Config flow for the Green Mountain Grill integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from gmg_local import grills

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class GmgConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Green Mountain Grill."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user setup step: confirm, then discover the grill."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}
        if user_input is not None:
            host = (user_input.get("host") or "").strip() or None
            found = await self.hass.async_add_executor_job(
                grills, 2, "0.0.0.0", host
            )
            if found:
                return self.async_create_entry(
                    title="Green Mountain Grill", data={"host": host}
                )
            errors["base"] = "no_devices_found"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Optional("host"): str}),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Migrate an existing ``climate: - platform: gmg`` YAML setup."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        _LOGGER.info(
            "Importing Green Mountain Grill YAML configuration into a config entry"
        )
        return self.async_create_entry(title="Green Mountain Grill", data={})

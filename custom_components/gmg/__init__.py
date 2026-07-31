"""The Green Mountain Grill integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from gmg_local import grills

from .const import DOMAIN, PLATFORMS
from .coordinator import GmgCoordinator

_LOGGER = logging.getLogger(__name__)

# Entity renames, keyed by old unique_id suffix.
#   (new unique_id suffix, old entity_id object_id, new entity_id object_id)
#
# Byte 33 shipped as "Fire Percentage" until GMG's own cloud API showed the
# vendor calls the field `fireStateProgress`. Changing the unique_id suffix
# alone would orphan the old entity and start a fresh one with no history, so
# it is carried across instead.
#
# This predates 1.0.0 - the integration ran privately through several
# iterations before this repository existed, so the rename is only relevant to
# installs that came from those. Harmless everywhere else: the loop finds
# nothing to migrate and does no work.
_RENAMED_ENTITIES = {
    "fire_percent": (
        "fire_state_progress",
        "green_mountain_grill_fire_percentage",
        "green_mountain_grill_fire_state_progress",
    ),
}


async def _async_migrate_renamed_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Carry renamed entities forward, keeping their history.

    Idempotent: every rename is skipped if its target already exists, so a
    second start after migrating is a no-op.
    """
    registry = er.async_get(hass)

    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        for old_suffix, (new_suffix, old_oid, new_oid) in _RENAMED_ENTITIES.items():
            if not item.unique_id.endswith(f"_{old_suffix}"):
                continue

            new_uid = f"{item.unique_id[: -len(old_suffix)]}{new_suffix}"
            if registry.async_get_entity_id(item.domain, DOMAIN, new_uid):
                # Already migrated; leave the stale row for the user to delete.
                continue

            updates = {"new_unique_id": new_uid}

            # Only touch the entity_id if it is still the generated one and
            # the target is free - never clobber a user's own rename.
            wanted = f"{item.domain}.{new_oid}"
            if item.entity_id == f"{item.domain}.{old_oid}" and not registry.async_get(
                wanted
            ):
                updates["new_entity_id"] = wanted

            registry.async_update_entity(item.entity_id, **updates)
            _LOGGER.info(
                "Migrated %s -> %s (unique_id %s -> %s)",
                item.entity_id,
                updates.get("new_entity_id", item.entity_id),
                item.unique_id,
                new_uid,
            )


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Green Mountain Grill component.

    The legacy ``climate: - platform: gmg`` YAML is migrated to a config entry
    from the climate platform's ``async_setup_platform`` import.
    """
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Green Mountain Grill from a config entry.

    Discover the grill ONCE here, then give it ONE coordinator that every
    platform shares. The grill serves a single client at a time, so
    per-platform discovery or per-entity polling contends and knocks entities
    offline.

    If the grill cannot be reached we raise ConfigEntryNotReady so HA retries
    with backoff, rather than loading an entry with zero entities behind it.
    """
    await _async_migrate_renamed_entities(hass, entry)

    all_grills = await hass.async_add_executor_job(
        grills, 2, "0.0.0.0", entry.data.get("host")
    )
    if not all_grills:
        raise ConfigEntryNotReady(
            "no Green Mountain Grill answered discovery "
            f"(host={entry.data.get('host') or 'broadcast'})"
        )

    coordinators = []
    for my_grill in all_grills:
        # Firmware is static; fetch it once here rather than every poll. Not
        # fatal if it fails - the device page just shows no firmware until the
        # next start.
        try:
            await hass.async_add_executor_job(my_grill.firmware)
        except Exception as err:  # noqa: BLE001 - any failure is non-fatal
            _LOGGER.debug(
                "Could not read firmware from grill %s: %s",
                my_grill.serial_number,
                err,
            )

        coordinator = GmgCoordinator(hass, my_grill)
        # Raises ConfigEntryNotReady itself if the first poll fails.
        await coordinator.async_config_entry_first_refresh()
        coordinators.append(coordinator)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded

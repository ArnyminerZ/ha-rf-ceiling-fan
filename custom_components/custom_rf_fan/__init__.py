"""The Universal RF Ceiling Fan integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_RECEIVER_ID, DOMAIN, SIGNAL_STATE_UPDATED
from .entity import async_subscribe_payloads

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["fan", "light", "select"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Universal RF Ceiling Fan component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Universal RF Ceiling Fan from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    receiver_id = entry.data.get(CONF_RECEIVER_ID)
    if receiver_id:
        @callback
        def _async_rf_payload_received(payload: str) -> None:
            """Forward received RF payloads to the entities to synchronize state."""
            async_dispatcher_send(hass, SIGNAL_STATE_UPDATED, entry.entry_id, payload)

        entry.async_on_unload(
            async_subscribe_payloads(hass, receiver_id, _async_rf_payload_received)
        )
    else:
        _LOGGER.warning(
            "No RF receiver configured; physical remote presses will not update state"
        )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok

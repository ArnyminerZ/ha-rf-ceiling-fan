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

from .const import DOMAIN, EVENT_RF_RAW, SIGNAL_STATE_UPDATED

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

    @callback
    def _async_rf_event_received(event: Any) -> None:
        """Handle incoming RF events to synchronize state."""
        payload = event.data.get("payload")
        if not payload:
            return

        # Check if this payload matches any learned codes for this entry
        # Flip the state of the corresponding entity if it's a toggle
        # The entities themselves will handle the signal and update their state
        async_dispatcher_send(hass, SIGNAL_STATE_UPDATED, entry.entry_id, payload)

    entry.async_on_unload(
        hass.bus.async_listen(EVENT_RF_RAW, _async_rf_event_received)
    )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok

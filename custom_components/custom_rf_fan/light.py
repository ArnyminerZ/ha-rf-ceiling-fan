"""Light platform for Universal RF Ceiling Fan."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.radio_frequency import async_send_command

from .entity import UniversalRFEntity
from .const import (
    DOMAIN,
    CONF_TRANSMITTER_ID,
    CONF_LIGHT_TOGGLE,
    CONF_LIGHT_DIMMING,
    CONF_COLOR_TEMP,
    CONF_OPTIONAL_FEATURES,
    SIGNAL_STATE_UPDATED,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Universal RF Ceiling Fan Light."""
    async_add_entities([UniversalRFLight(hass, entry)])

class UniversalRFLight(UniversalRFEntity, LightEntity):
    """Representation of an RF Light."""

    _attr_name = "Light"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the light."""
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}_light"
        
        self._transmitter_id = entry.data[CONF_TRANSMITTER_ID]
        self._light_toggle_code = entry.data[CONF_LIGHT_TOGGLE]
        self._attr_is_on = False

        features = entry.data.get(CONF_OPTIONAL_FEATURES, [])
        
        self._attr_supported_color_modes = set()
        
        if CONF_COLOR_TEMP in features:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
            # Add simple range
            self._attr_min_color_temp_kelvin = 2700
            self._attr_max_color_temp_kelvin = 6500
        elif CONF_LIGHT_DIMMING in features:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
        else:
            self._attr_supported_color_modes.add(ColorMode.ONOFF)
            
        self._attr_color_mode = list(self._attr_supported_color_modes)[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {"toggle_code": self._light_toggle_code}
        for key in ["brighten", "dim", "temp_warm", "temp_neutral", "temp_cool"]:
            if val := self._entry.data.get(key):
                attrs[f"{key}_code"] = val
        return attrs


    @callback
    def _handle_rf_payload(self, entry_id: str, payload: str) -> None:
        """Handle received RF payload."""
        if entry_id != self._entry.entry_id:
            return
            
        if payload == self._light_toggle_code:
            self._attr_is_on = not self._attr_is_on
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        sent_code = False
        
        if not self._attr_is_on:
            await async_send_command(
                self.hass,
                self._transmitter_id,
                self._get_command(self._light_toggle_code),
            )
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if self._attr_is_on:
            await async_send_command(
                self.hass,
                self._transmitter_id,
                self._get_command(self._light_toggle_code),
            )
            self._attr_is_on = False
            self.async_write_ha_state()

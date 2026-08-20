"""Light platform for Universal RF Ceiling Fan."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    LightEntityFeature,
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
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
    DEFAULT_DIMMING_LEVELS,
    DEFAULT_DIMMING_DELAY_MS,
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
    _attr_translation_key = "rf_light"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the light."""
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}_light"
        
        self._transmitter_id = entry.data[CONF_TRANSMITTER_ID]
        self._light_toggle_code = entry.data[CONF_LIGHT_TOGGLE]
        self._attr_is_on = False

        features = entry.data.get(CONF_OPTIONAL_FEATURES, [])
        
        self._attr_supported_color_modes = set()
        
        if CONF_LIGHT_DIMMING in features:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
        else:
            self._attr_supported_color_modes.add(ColorMode.ONOFF)
            
        if CONF_COLOR_TEMP in features:
            
            # Setup effects for discrete buttons
            self._attr_effect_list = []
            if entry.data.get("temp_warm"):
                self._attr_effect_list.append("warm")
            if entry.data.get("temp_neutral"):
                self._attr_effect_list.append("neutral")
            if entry.data.get("temp_cool"):
                self._attr_effect_list.append("cool")
                
            if self._attr_effect_list:
                self._attr_supported_features = LightEntityFeature.EFFECT
        self._attr_color_mode = list(self._attr_supported_color_modes)[0]
        self._attr_brightness = 255 if ColorMode.BRIGHTNESS in self._attr_supported_color_modes else None

    async def async_added_to_hass(self) -> None:
        """Restore state when added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
            if "brightness" in last_state.attributes:
                self._attr_brightness = last_state.attributes["brightness"]
            if "effect" in last_state.attributes:
                self._attr_effect = last_state.attributes["effect"]

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
            
        if self._codes_match(payload, self._light_toggle_code):
            self._attr_is_on = not self._attr_is_on
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Handle effect
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            code_key = None
            if effect == "warm":
                code_key = "temp_warm"
            elif effect == "neutral":
                code_key = "temp_neutral"
            elif effect == "cool":
                code_key = "temp_cool"
                
            if code_key and (code := self._entry.data.get(code_key)):
                await async_send_command(self.hass, self._transmitter_id, self._get_command(code))
                self._attr_effect = effect
                self._attr_is_on = True
                self.async_write_ha_state()
                return
        # Handle brightness slider
        if ATTR_BRIGHTNESS in kwargs:
            new_brightness = kwargs[ATTR_BRIGHTNESS]
            dimming_levels = self._entry.data.get("dimming_levels", DEFAULT_DIMMING_LEVELS)
            dimming_delay_ms = self._entry.data.get("dimming_delay_ms", DEFAULT_DIMMING_DELAY_MS)
            
            new_level = max(1, round((new_brightness / 255) * dimming_levels))
            
            if self._attr_brightness is not None:
                # Calculate step difference
                current_level = round((self._attr_brightness / 255) * dimming_levels)
                steps = new_level - current_level
                
                if steps > 0:
                    code_key = "brighten"
                    num_presses = steps
                elif steps < 0:
                    code_key = "dim"
                    num_presses = abs(steps)
                else:
                    code_key = None
                    num_presses = 0
                    
                if code_key and num_presses > 0 and (code := self._entry.data.get(code_key)):
                    for i in range(num_presses):
                        await async_send_command(self.hass, self._transmitter_id, self._get_command(code))
                        if i < num_presses - 1:
                            await asyncio.sleep(dimming_delay_ms / 1000.0)
                    
            # Snap the UI brightness to the actual calculated step level
            self._attr_brightness = round((new_level / dimming_levels) * 255)
            self._attr_is_on = True
            self.async_write_ha_state()
            return

        # Handle simple toggle on
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

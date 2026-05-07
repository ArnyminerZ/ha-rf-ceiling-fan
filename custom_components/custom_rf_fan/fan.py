"""Fan platform for Universal RF Ceiling Fan."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.radio_frequency import async_send_command

from rf_protocols import OOKCommand

from .entity import UniversalRFEntity
from .const import (
    DOMAIN,
    CONF_TRANSMITTER_ID,
    CONF_FAN_TOGGLE,
    CONF_FAN_SPEEDS,
    CONF_FAN_DIRECTION,
    CONF_OPTIONAL_FEATURES,
    SIGNAL_STATE_UPDATED,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Universal RF Ceiling Fan."""
    async_add_entities([UniversalRFFan(hass, entry)])

class UniversalRFFan(UniversalRFEntity, FanEntity):
    """Representation of an RF Fan."""

    _attr_name = "Fan"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the fan."""
        super().__init__(hass, entry)
        self._attr_unique_id = f"{entry.entry_id}_fan"
        
        # Configure supported features
        features = entry.data.get(CONF_OPTIONAL_FEATURES, [])
        self._attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        self._speed_count = 0
        
        if CONF_FAN_SPEEDS in features:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED
            self._speed_count = entry.data.get("speed_count", 3)
            
        if CONF_FAN_DIRECTION in features:
            self._attr_supported_features |= FanEntityFeature.DIRECTION
            self._fan_direction_code = entry.data.get("fan_direction")
            self._attr_current_direction = "forward"
            
        self._transmitter_id = entry.data[CONF_TRANSMITTER_ID]
        self._fan_toggle_code = entry.data[CONF_FAN_TOGGLE]
        self._attr_is_on = False
        self._attr_percentage = 0

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self._attr_is_on

    async def async_added_to_hass(self) -> None:
        """Restore state when added to hass."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
            if "percentage" in last_state.attributes:
                self._attr_percentage = last_state.attributes["percentage"]
            if "current_direction" in last_state.attributes:
                self._attr_current_direction = last_state.attributes["current_direction"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        attrs = {"toggle_code": self._fan_toggle_code}
        if self._speed_count > 0:
            for i in range(1, self._speed_count + 1):
                speed_code = self._entry.data.get(f"speed_{i}")
                if speed_code:
                    attrs[f"speed_{i}_code"] = speed_code
        if getattr(self, "_fan_direction_code", None):
            attrs["direction_code"] = self._fan_direction_code
        return attrs


    @callback
    def _handle_rf_payload(self, entry_id: str, payload: str) -> None:
        """Handle received RF payload."""
        if entry_id != self._entry.entry_id:
            return

        update_needed = False
        if payload == self._fan_toggle_code:
            self._attr_is_on = not self._attr_is_on
            if not self._attr_is_on:
                self._attr_percentage = 0
            elif self._speed_count > 0 and self._attr_percentage == 0:
                self._attr_percentage = 100
            update_needed = True
            
        # Handle speed codes if configured
        if self._speed_count > 0:
            for i in range(1, self._speed_count + 1):
                speed_code = self._entry.data.get(f"speed_{i}")
                if speed_code and payload == speed_code:
                    self._attr_is_on = True
                    self._attr_percentage = int((i / self._speed_count) * 100)
                    update_needed = True
                    break
            
        if getattr(self, "_fan_direction_code", None) and payload == self._fan_direction_code:
            self._attr_current_direction = "reverse" if self._attr_current_direction == "forward" else "forward"
            update_needed = True
            
        if update_needed:
            self.async_write_ha_state()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        # If percentage is provided and we support speeds, send that speed code
        if percentage is not None and self._speed_count > 0:
            # Map percentage to a speed step
            step = max(1, round((percentage / 100) * self._speed_count))
            speed_code = self._entry.data.get(f"speed_{step}")
            if speed_code:
                await async_send_command(
                    self.hass,
                    self._transmitter_id,
                    self._get_command(speed_code),
                )
                self._attr_percentage = percentage
                self._attr_is_on = True
                self.async_write_ha_state()
                return

        # Fallback to standard toggle if no speed specified or supported,
        # but only if it's currently off (assumed)
        if not self._attr_is_on:
            await async_send_command(
                self.hass,
                self._transmitter_id,
                self._get_command(self._fan_toggle_code),
            )
            self._attr_is_on = True
            if percentage is not None:
                self._attr_percentage = percentage
            elif self._speed_count > 0:
                # Default to full speed if turning on without specific percentage
                self._attr_percentage = 100
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        if self._attr_is_on:
            await async_send_command(
                self.hass,
                self._transmitter_id,
                self._get_command(self._fan_toggle_code),
            )
            self._attr_is_on = False
            self._attr_percentage = 0
            self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        if percentage == 0:
            await self.async_turn_off()
            return
            
        await self.async_turn_on(percentage=percentage)

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if getattr(self, "_fan_direction_code", None):
            await async_send_command(
                self.hass,
                self._transmitter_id,
                self._get_command(self._fan_direction_code),
            )
            self._attr_current_direction = direction
            self.async_write_ha_state()

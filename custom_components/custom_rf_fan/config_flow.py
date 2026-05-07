"""Config flow for Universal RF Ceiling Fan integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_TRANSMITTER_ID,
    CONF_LIGHT_TOGGLE,
    CONF_FAN_TOGGLE,
    CONF_FAN_SPEEDS,
    CONF_FAN_DIRECTION,
    CONF_LIGHT_DIMMING,
    CONF_COLOR_TEMP,
    CONF_OPTIONAL_FEATURES,
    EVENT_RF_RAW,
)

_LOGGER = logging.getLogger(__name__)

class UniversalRFFanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Universal RF Ceiling Fan."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}
        self._learning_keys: list[str] = []
        self._current_learning_key: str | None = None
        self._learning_phase: str = "mandatory"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step (Hardware Selection)."""
        if user_input is not None:
            self._data[CONF_TRANSMITTER_ID] = user_input[CONF_TRANSMITTER_ID]
            self._learning_keys = [CONF_LIGHT_TOGGLE, CONF_FAN_TOGGLE]
            self._learning_phase = "mandatory"
            return await self.async_step_learn_code()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRANSMITTER_ID): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="radio_frequency")
                    ),
                }
            ),
        )

    def _get_button_label(self, key: str) -> str:
        """Get a human readable label for a button key."""
        return key.replace("_", " ").title()

    async def async_step_learn_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Learn a specific code by capturing radio_frequency.raw_event."""
        if not self._learning_keys:
            if self._learning_phase == "mandatory":
                return await self.async_step_optional_features()
            else:
                return self.async_create_entry(
                    title="Universal RF Ceiling Fan", data=self._data
                )

        self._current_learning_key = self._learning_keys[0]
        button_label = self._get_button_label(self._current_learning_key)

        if user_input is not None:
            # Check for manual code entry first
            manual_code = user_input.get("manual_code")
            if manual_code:
                # Clean up the input (remove brackets, spaces, etc.)
                # This allows pasting directly from ESPHome: [123, -456, ...]
                cleaned_code = (
                    manual_code.replace("[", "")
                    .replace("]", "")
                    .replace(" ", "")
                    .strip()
                )
                self._data[self._current_learning_key] = cleaned_code
                self._learning_keys.pop(0)
                return await self.async_step_learn_code()

            # Otherwise, start the learning process
            future: asyncio.Future[str] = asyncio.Future()

            @callback
            def _async_rf_event_received(event: Any) -> None:
                """Handle RF event."""
                if not future.done():
                    future.set_result(event.data.get("payload"))

            unsub = self.hass.bus.async_listen(EVENT_RF_RAW, _async_rf_event_received)

            try:
                # Wait up to 30 seconds for a code
                # Note: This blocks the config flow, but that is acceptable for learning steps
                payload = await asyncio.wait_for(future, timeout=30.0)
                self._data[self._current_learning_key] = payload
                self._learning_keys.pop(0)
                
                # Still codes to learn, recursively show the same step
                return await self.async_step_learn_code()
            except asyncio.TimeoutError:
                return self.async_show_form(
                    step_id="learn_code",
                    errors={"base": "timeout"},
                    data_schema=vol.Schema(
                        {
                            vol.Optional("manual_code"): str,
                        }
                    ),
                    description_placeholders={"button": button_label},
                )
            finally:
                unsub()

        return self.async_show_form(
            step_id="learn_code",
            data_schema=vol.Schema(
                {
                    vol.Optional("manual_code"): str,
                }
            ),
            description_placeholders={"button": button_label},
        )

    async def async_step_optional_features(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle selection of optional features."""
        if user_input is not None:
            features = user_input.get(CONF_OPTIONAL_FEATURES, [])
            self._data[CONF_OPTIONAL_FEATURES] = features
            
            if CONF_FAN_SPEEDS in features:
                return await self.async_step_fan_speeds_config()
                
            return await self.async_step_optional_learning_setup()

        return self.async_show_form(
            step_id="optional_features",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_OPTIONAL_FEATURES): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                CONF_FAN_SPEEDS,
                                CONF_FAN_DIRECTION,
                                CONF_LIGHT_DIMMING,
                                CONF_COLOR_TEMP,
                            ],
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                            translation_key="optional_features",
                        )
                    )
                }
            ),
        )

    async def async_step_fan_speeds_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for number of fan speeds."""
        if user_input is not None:
            self._data["speed_count"] = int(user_input["speed_count"])
            return await self.async_step_optional_learning_setup()

        return self.async_show_form(
            step_id="fan_speeds_config",
            data_schema=vol.Schema(
                {
                    vol.Required("speed_count", default="3"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["3", "5"],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="speed_count",
                        )
                    )
                }
            ),
        )

    async def async_step_optional_learning_setup(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Setup learning queue for optional features."""
        features = self._data.get(CONF_OPTIONAL_FEATURES, [])
        self._learning_keys = []
        self._learning_phase = "optional"
        
        if CONF_FAN_SPEEDS in features:
            count = self._data.get("speed_count", 3)
            for i in range(1, count + 1):
                self._learning_keys.append(f"speed_{i}")
                
        if CONF_FAN_DIRECTION in features:
            self._learning_keys.append("fan_direction")
            
        if CONF_LIGHT_DIMMING in features:
            self._learning_keys.extend(["brighten", "dim"])
            
        if CONF_COLOR_TEMP in features:
            self._learning_keys.extend(["temp_warm", "temp_neutral", "temp_cool"])
            
        return await self.async_step_learn_code()

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
    DEFAULT_DIMMING_LEVELS,
    DEFAULT_DIMMING_DELAY_MS,
    EVENT_RF_RAW,
)
from .entity import extract_first_frame, normalize_payload

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
        self._learn_task: asyncio.Task[str | None] | None = None

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

    async def _async_wait_for_payload(self) -> str | None:
        """Wait up to 30 seconds for an RF payload from the ESPHome receiver."""
        future: asyncio.Future[str | None] = self.hass.loop.create_future()

        @callback
        def _async_rf_event_received(event: Any) -> None:
            """Handle RF event."""
            if not future.done():
                future.set_result(normalize_payload(event.data.get("payload")))

        unsub = self.hass.bus.async_listen(EVENT_RF_RAW, _async_rf_event_received)
        _LOGGER.debug("Listening for %s while learning a code", EVENT_RF_RAW)
        try:
            payload = await asyncio.wait_for(future, timeout=30.0)
            _LOGGER.debug("Received %s payload while learning: %s", EVENT_RF_RAW, payload)
            return payload
        except asyncio.TimeoutError:
            _LOGGER.debug("Timed out waiting for %s", EVENT_RF_RAW)
            return None
        finally:
            unsub()

    @callback
    def async_remove(self) -> None:
        """Cancel any pending code capture when the flow is removed."""
        if self._learn_task is not None:
            self._learn_task.cancel()

    async def async_step_learn_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Learn a specific code by capturing the `esphome.rf_raw` event.

        Listening starts as soon as the step is shown, so the button can be
        pressed right away; the flow falls back to manual entry on timeout.
        """
        if not self._learning_keys:
            if self._learning_phase == "mandatory":
                return await self.async_step_optional_features()
            else:
                return self.async_create_entry(
                    title="Universal RF Ceiling Fan", data=self._data
                )

        self._current_learning_key = self._learning_keys[0]

        if self._learn_task is None:
            self._learn_task = self.hass.async_create_task(
                self._async_wait_for_payload()
            )

        if not self._learn_task.done():
            return self.async_show_progress(
                step_id="learn_code",
                progress_action="listening",
                progress_task=self._learn_task,
                description_placeholders={
                    "button": self._get_button_label(self._current_learning_key)
                },
            )

        payload = self._learn_task.result()
        self._learn_task = None
        if not payload:
            return self.async_show_progress_done(next_step_id="learn_manual")

        self._data[self._current_learning_key] = extract_first_frame(payload)
        self._learning_keys.pop(0)
        return self.async_show_progress_done(next_step_id="learn_code")

    async def async_step_learn_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Enter a code manually, or retry listening, after a capture timeout."""
        if user_input is not None:
            manual_code = user_input.get("manual_code")
            if not manual_code:
                return await self.async_step_learn_code()

            # Clean up the input (remove brackets, spaces, etc.)
            # This allows pasting directly from ESPHome: [123, -456, ...]
            self._data[self._current_learning_key] = (
                manual_code.replace("[", "")
                .replace("]", "")
                .replace(" ", "")
                .strip()
            )
            self._learning_keys.pop(0)
            return await self.async_step_learn_code()

        return self.async_show_form(
            step_id="learn_manual",
            errors={"base": "timeout"},
            data_schema=vol.Schema({vol.Optional("manual_code"): str}),
            description_placeholders={
                "button": self._get_button_label(self._current_learning_key)
            },
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
            if CONF_LIGHT_DIMMING in features:
                return await self.async_step_light_dimming_config()
                
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
            features = self._data.get(CONF_OPTIONAL_FEATURES, [])
            if CONF_LIGHT_DIMMING in features:
                return await self.async_step_light_dimming_config()
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

    async def async_step_light_dimming_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for dimming configuration."""
        if user_input is not None:
            self._data["dimming_levels"] = int(user_input["dimming_levels"])
            self._data["dimming_delay_ms"] = int(user_input["dimming_delay_ms"])
            return await self.async_step_optional_learning_setup()

        return self.async_show_form(
            step_id="light_dimming_config",
            data_schema=vol.Schema(
                {
                    vol.Required("dimming_levels", default=DEFAULT_DIMMING_LEVELS): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
                    vol.Required("dimming_delay_ms", default=DEFAULT_DIMMING_DELAY_MS): vol.All(vol.Coerce(int), vol.Range(min=0, max=2000)),
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

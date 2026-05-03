"""Base entity for Universal RF Ceiling Fan."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.entity import Entity

from rf_protocols import OOKCommand

from .const import DOMAIN, SIGNAL_STATE_UPDATED, SIGNAL_ENTITY_STATE_UPDATED


class UniversalRFEntity(Entity):
    """Base representation of a Universal RF entity."""

    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the base entity."""
        super().__init__()
        self.hass = hass
        self._entry = entry

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Universal RF Ceiling Fan",
            "manufacturer": "Custom RF Fan",
        }

    @callback
    def async_write_ha_state(self) -> None:
        """Write state and notify listeners."""
        super().async_write_ha_state()
        if self.unique_id:
            async_dispatcher_send(
                self.hass,
                f"{SIGNAL_ENTITY_STATE_UPDATED}_{self.unique_id}",
                "on" if self.is_on else "off"
            )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_STATE_UPDATED,
                self._handle_rf_payload
            )
        )
        if self.unique_id:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{DOMAIN}_calibrate_{self.unique_id}",
                    self._handle_calibration
                )
            )

    @callback
    def _handle_rf_payload(self, entry_id: str, payload: str) -> None:
        """Handle received RF payload. Must be implemented by subclasses."""
        raise NotImplementedError()

    @callback
    def _handle_calibration(self, state: str) -> None:
        """Force update internal state without transmitting."""
        self._attr_is_on = (state == "on")
        self.async_write_ha_state()

    def _get_command(self, payload: str) -> OOKCommand:
        """Convert raw payload string to OOKCommand.
        
        Handles conversion from ESPHome-style alternating positive pulses
        to signed timings (positive for pulse, negative for space).
        """
        raw_pulses = [int(p.strip()) for p in payload.split(",")]
        # Ensure alternating signs: positive for pulse (even), negative for space (odd)
        pulses = [
            val if i % 2 == 0 else -abs(val)
            for i, val in enumerate(raw_pulses)
        ]
        # Add a 9ms gap at the end to ensure the receiver can distinguish repetitions
        if pulses[-1] > 0:
            pulses.append(-9000)
        else:
            pulses[-1] = -9000
            
        frequency = 433920000 # 433.92 MHz
        return OOKCommand(frequency=frequency, timings=pulses, repeat_count=6)


"""Select platform for Universal RF Ceiling Fan."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send

from .const import DOMAIN, SIGNAL_ENTITY_STATE_UPDATED

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Universal RF Ceiling Fan select entities."""
    entities = [
        UniversalRFCalibrationSelect(hass, entry, "fan", "Fan Calibration"),
        UniversalRFCalibrationSelect(hass, entry, "light", "Light Calibration"),
    ]
    async_add_entities(entities)

class UniversalRFCalibrationSelect(SelectEntity):
    """Representation of an RF Calibration Select entity."""

    _attr_options = ["on", "off"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

    def __init__(
        self, 
        hass: HomeAssistant, 
        entry: ConfigEntry, 
        entity_type: str,
        name: str
    ) -> None:
        """Initialize the calibration select."""
        self.hass = hass
        self._entry = entry
        self._entity_type = entity_type
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{entity_type}_calibration"
        self._target_unique_id = f"{entry.entry_id}_{entity_type}"
        self._attr_current_option = "off"

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Universal RF Ceiling Fan",
            "manufacturer": "Custom RF Fan",
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_ENTITY_STATE_UPDATED}_{self._target_unique_id}",
                self._handle_state_update
            )
        )

    @callback
    def _handle_state_update(self, state: str) -> None:
        """Handle state update from the target entity."""
        if state != self._attr_current_option:
            self._attr_current_option = state
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        async_dispatcher_send(
            self.hass,
            f"{DOMAIN}_calibrate_{self._target_unique_id}",
            option
        )
        self.async_write_ha_state()

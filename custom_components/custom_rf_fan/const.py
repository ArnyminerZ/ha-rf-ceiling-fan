"""Constants for the Universal RF Ceiling Fan integration."""

DOMAIN = "custom_rf_fan"

CONF_TRANSMITTER_ID = "transmitter_id"
CONF_LIGHT_TOGGLE = "light_toggle"
CONF_FAN_TOGGLE = "fan_toggle"

# Optional features
CONF_FAN_SPEEDS = "fan_speeds"
CONF_FAN_DIRECTION = "fan_direction"
CONF_LIGHT_DIMMING = "light_dimming"
CONF_COLOR_TEMP = "color_temp"

CONF_OPTIONAL_FEATURES = "optional_features"

DEFAULT_DIMMING_LEVELS = 30
DEFAULT_DIMMING_DELAY_MS = 100

EVENT_RF_RAW = "radio_frequency.raw_event"

SIGNAL_STATE_UPDATED = f"{DOMAIN}_state_updated"
SIGNAL_ENTITY_STATE_UPDATED = f"{DOMAIN}_entity_state_updated"

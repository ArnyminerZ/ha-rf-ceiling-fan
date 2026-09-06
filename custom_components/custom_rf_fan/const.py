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

# Tolerance applied when comparing a received RF payload against a learned
# code. Real remotes rarely reproduce byte-identical pulse timings on every
# press, so each pulse is allowed to differ by up to this fraction of the
# learned pulse's duration (relative tolerance), or PULSE_TOLERANCE_MIN_US,
# whichever is larger (absolute floor, needed since short pulses would
# otherwise get an unrealistically tight allowance).
PULSE_TOLERANCE_RATIO = 0.25
PULSE_TOLERANCE_MIN_US = 100

# A physical remote repeats its code several times per button press, and the
# receiver often reports the whole burst as a single payload with a long gap
# between repeats (the inter-repeat gap, e.g. ~9ms) but no gap anywhere near
# that long inside a single frame. This threshold is used to tell the two
# apart: any space pulse longer than this is treated as a boundary between
# repeats rather than part of the frame itself.
REPEAT_GAP_THRESHOLD_US = 3000

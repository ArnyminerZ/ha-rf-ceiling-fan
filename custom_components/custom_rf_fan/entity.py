"""Base entity for Universal RF Ceiling Fan."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect, async_dispatcher_send
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity import Entity

from rf_protocols.commands.ook import OOKCommand

from .const import (
    DOMAIN,
    SIGNAL_STATE_UPDATED,
    SIGNAL_ENTITY_STATE_UPDATED,
    PULSE_TOLERANCE_RATIO,
    PULSE_TOLERANCE_MIN_US,
    REPEAT_GAP_THRESHOLD_US,
)


def _parse_pulses(payload: str) -> list[int] | None:
    """Parse a comma-separated pulse-timing payload into ints."""
    try:
        return [int(p.strip()) for p in payload.split(",") if p.strip()]
    except ValueError:
        return None


def _pulses_match(
    received_pulses: list[int],
    learned_pulses: list[int],
    tolerance: float,
    min_tolerance_us: int,
) -> bool:
    """Compare two equal-length pulse sequences within tolerance."""
    for received_val, learned_val in zip(received_pulses, learned_pulses):
        allowed = max(min_tolerance_us, abs(learned_val) * tolerance)
        if abs(abs(received_val) - abs(learned_val)) > allowed:
            return False
    return True


def extract_first_frame(
    payload: str, gap_threshold_us: int = REPEAT_GAP_THRESHOLD_US
) -> str:
    """Trim a raw RF capture down to its first repeat/frame.

    A physical remote repeats its code several times per button press, and
    the receiver often reports the whole burst (all repeats back to back,
    separated by large inter-repeat gaps) as a single payload. Learned codes
    are stored as one frame, so when capturing a code live, keep only the
    pulses up to the first oversized gap.
    """
    if not payload:
        return payload

    pulses = _parse_pulses(payload)
    if not pulses:
        return payload

    for i, val in enumerate(pulses):
        # A gap at position 0 means the capture started mid-gap, before any
        # frame was collected, so it isn't a real frame boundary — keep
        # looking rather than trimming to an empty result.
        if i > 0 and val < 0 and abs(val) > gap_threshold_us:
            return ",".join(str(p) for p in pulses[:i])

    return payload


def codes_match(
    received: str | None,
    learned: str | None,
    tolerance: float = PULSE_TOLERANCE_RATIO,
    min_tolerance_us: int = PULSE_TOLERANCE_MIN_US,
) -> bool:
    """Compare a received RF payload against a learned code with tolerance.

    Physical remotes rarely reproduce byte-identical pulse timings between
    presses (drift, temperature, RF noise), so an exact string match misses
    real presses. Instead, both payloads are parsed into their pulse-timing
    sequences and compared pulse-by-pulse, allowing each pulse to differ by
    up to `tolerance` of its learned duration (or `min_tolerance_us`,
    whichever is larger).

    A learned code is stored as a single frame, but a real button press is
    usually reported as several repeats of that frame back to back (the
    remote repeats its transmission, and the receiver's idle window doesn't
    always split each repeat into its own event). So when the payloads
    differ in length, look for one occurrence of the learned frame anywhere
    inside the received burst instead of requiring a whole-payload match.
    """
    if not received or not learned:
        return False
    if received == learned:
        return True

    received_pulses = _parse_pulses(received)
    learned_pulses = _parse_pulses(learned)
    if received_pulses is None or learned_pulses is None:
        return False

    if len(received_pulses) == len(learned_pulses):
        return _pulses_match(received_pulses, learned_pulses, tolerance, min_tolerance_us)

    frame_len = len(learned_pulses)
    if frame_len == 0 or len(received_pulses) < frame_len:
        return False

    # Every other pulse in a frame is a space (negative); only try aligning
    # the window at offsets that preserve that mark/space parity.
    first_pulse_positive = learned_pulses[0] >= 0
    for start in range(len(received_pulses) - frame_len + 1):
        if (received_pulses[start] >= 0) != first_pulse_positive:
            continue
        window = received_pulses[start : start + frame_len]
        if _pulses_match(window, learned_pulses, tolerance, min_tolerance_us):
            return True

    return False


class UniversalRFEntity(RestoreEntity):
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

    def _codes_match(self, received: str | None, learned: str | None) -> bool:
        """Check whether a received payload matches a learned code, with tolerance."""
        return codes_match(received, learned)

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


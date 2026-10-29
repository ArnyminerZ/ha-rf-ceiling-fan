# Universal RF Ceiling Fan

A [Home Assistant](https://www.home-assistant.io/) custom integration that lets you control generic RF-remote-operated ceiling fans (and their integrated lights) as native `fan` and `light` entities.

It works by learning the raw OOK codes transmitted by your existing physical remote and replaying them through a 433.92MHz transmitter exposed by the `radio_frequency` integration, so no remote hardware needs to be replaced.

## Features

- Exposes the fan as a standard `fan` entity (on/off, optional speed steps, optional direction).
- Exposes the light as a standard `light` entity (on/off, optional dimming, optional color temperature presets).
- Learns codes directly from your physical remote during setup, or accepts codes pasted manually (e.g. from an ESPHome dump).
- Listens for RF signals from the physical remote at runtime and keeps Home Assistant's state in sync when the remote is used directly, with tolerance for the timing noise/jitter naturally present between button presses.
- Per-entity calibration helpers to manually resync state if it ever drifts out of sync with the physical device.

## Requirements

- A `radio_frequency` transmitter/receiver entity already configured in Home Assistant.
- The physical remote for your fan/light, used once during setup to learn its codes.

## Installation

### HACS

1. In HACS, go to **Integrations**, click the three-dot menu, and choose **Custom repositories**.
2. Add `https://github.com/ArnyminerZ/ha-rf-ceiling-fan` as an **Integration**.
3. Install "Universal RF Ceiling Fan" and restart Home Assistant.

### Manual

1. Copy `custom_components/custom_rf_fan` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.

## Receiving the physical remote (ESPHome)

Home Assistant's `radio_frequency` integration currently only supports transmitting, so signals from your physical remote are reported to this integration through an ESPHome event. Add an `on_raw` trigger to your `remote_receiver`; it fires the `esphome.rf_raw` event with the first frame of every press:

```yaml
remote_receiver:
  id: cc1101_rx_hub
  pin: GPIO03
  idle: 15ms
  on_raw:
    then:
      - homeassistant.event:
          event: esphome.rf_raw
          data_template:
            payload: "{{ payload }}"
          variables:
            payload: !lambda |-
              std::string out;
              for (size_t i = 0; i < x.size(); i++) {
                // Stop at the first inter-repeat gap: keep a single frame
                if (i > 0 && x[i] < -3000) break;
                if (i > 0) out += ",";
                out += std::to_string(x[i]);
              }
              return out;
```

The device must be allowed to perform Home Assistant actions (**Settings → Devices & services → ESPHome → your device → Configure**). You can check it works in **Developer Tools → Events** by listening to `esphome.rf_raw` and pressing the remote. The same event is used when learning codes during setup.

## Configuration

Configuration is done entirely through the UI:

1. Go to **Settings → Devices & Services → Add Integration** and search for "Universal RF Ceiling Fan".
2. Select the `radio_frequency` transmitter entity to use.
3. Follow the prompts to learn the fan and light toggle codes, and any optional features (speed steps, direction, dimming, color temperature).

## Contributing

Issues and pull requests are welcome at the [issue tracker](https://github.com/ArnyminerZ/ha-rf-ceiling-fan/issues).

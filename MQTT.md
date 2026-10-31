# Testing MQTT

For a broker running on the Pi with commands sent from your laptop, follow
[the MQTT infrastructure setup guide](docs/mqtt-setup.md).

The listener queues received messages and prints them to the app's console.
In the app, `ON` interrupts the current display wait and shows the requested mode for one
normal display period, then returns to the interrupted rotation entry and continues
from there. The interrupted entry restarts its usual duration. `OFF` is reported and ignored.
The standalone listener only prints messages.

## Install and start a local broker

On Ubuntu, Debian, or Raspberry Pi OS, install Mosquitto (the broker) and its
command-line clients:

```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl start mosquitto
```

From the project directory, install the Python dependencies, including `paho-mqtt`:

```bash
uv sync --group dev --frozen
```

## Start the app

In the first terminal:

```bash
uv run --group dev --frozen python main.py --mqtt --dummy-data
```

`--mqtt` enables the listener. `--dummy-data` supplies local sample data so testing
doesn't use external API quotas or require API keys.

| Argument | Default | Purpose |
|---|---|---|
| `--mqtt` | Disabled | Enable MQTT in the app |
| `--mqtt-host` | `127.0.0.1` | Broker hostname or IP address |
| `--mqtt-port` | `1883` | Broker TCP port |
| `--mqtt-topic` | `matrix/display/+/set` | Subscription filter; `+` matches one topic segment |
| `--matterbridge` | Disabled | Enable MQTT and announce the five Matterbridge virtual controls |
| `--matterbridge-topic` | `matterbridge` | Base topic configured in the Matterbridge MQTT plugin |

To test without starting the matrix, run the standalone listener instead:

```bash
uv run --frozen python mqtt_listener.py
```

It accepts the same host, port, and topic options; `--mqtt` isn't needed.

## Send messages

Once the app reports it is connected, run these in a second terminal:

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/train/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/f-trains/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/r-trains/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/clock/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/weather/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/train/set -m OFF
```

The app's console should show:

```text
MQTT topic='matrix/display/train/set' payload=b'ON' -> command='trains'
MQTT topic='matrix/display/f-trains/set' payload=b'ON' -> command='trains' stop_ids=('F23N',)
MQTT topic='matrix/display/r-trains/set' payload=b'ON' -> command='trains' stop_ids=('R33N',)
MQTT topic='matrix/display/clock/set' payload=b'ON' -> command='clock'
MQTT topic='matrix/display/weather/set' payload=b'ON' -> command='weather'
MQTT topic='matrix/display/train/set' payload=b'OFF'
```

Use matching host, port, and topic values in the app and publisher if you change
the defaults. The listener retries if the broker is unavailable. Press Ctrl+C in
the app terminal to stop it.

Requested modes use their duration from the pending rotation. When absent from
that rotation, defaults are trains 5 seconds, clock 30 seconds, and weather 5 seconds
(train and weather renderers retain their normal multi-view timing). `OFF` is
ignored for all supported topics. If `--mqtt-topic` was explicitly set to the old train
topic, remove it or use `--mqtt-topic 'matrix/display/+/set'` to receive all modes.

`train/set` uses the configured stop rotation. `f-trains/set` selects only `F23N`
and `r-trains/set` selects only `R33N` (both northbound). These selections apply
only to that request; scheduled all-stop and uptown displays keep their original
configuration. The default subscription receives all five topics.

Switching interrupts display sleeps and animation waits. A synchronous API request
already running must finish first; `--dummy-data` avoids that delay while testing.

## Matterbridge virtual controls

With the `matterbridge-mqtt` plugin connected to the same broker:

```bash
uv run --frozen python main.py --dummy-data --matterbridge --mqtt-host PI_IP
```

This registers All Trains, F Trains, R Trains, Pixie Clock, and Pixie Weather
as virtual outlets. Activating one triggers its display mode once and immediately
resets its reported switch state to off, ready for another activation. Existing
manual MQTT topics keep working. Use `--matterbridge-topic` if the plugin's base
topic differs from `matterbridge`.

See [the infrastructure guide](docs/mqtt-setup.md#register-the-applications-virtual-controls)
for registration topics, Google Home pairing, and troubleshooting.

References: [Mosquitto installation](https://mosquitto.org/download/),
[mosquitto_pub options](https://mosquitto.org/man/mosquitto_pub-1.html).

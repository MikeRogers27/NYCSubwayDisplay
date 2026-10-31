# Testing MQTT

For a broker running on the Pi with commands sent from your laptop, follow
[the MQTT infrastructure setup guide](docs/mqtt-setup.md).

The listener queues received messages and prints them to the app's console.
In the app, `ON` interrupts the current display wait and shows trains for one
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
| `--mqtt-topic` | `matrix/display/train/set` | Topic to subscribe to |

To test without starting the matrix, run the standalone listener instead:

```bash
uv run --frozen python mqtt_listener.py
```

It accepts the same host, port, and topic options; `--mqtt` isn't needed.

## Send messages

Once the app reports it is connected, run these in a second terminal:

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/train/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/train/set -m OFF
```

The app's console should show:

```text
MQTT topic='matrix/display/train/set' payload=b'ON' -> command='trains'
MQTT topic='matrix/display/train/set' payload=b'OFF'
```

Use matching host, port, and topic values in the app and publisher if you change
the defaults. The listener retries if the broker is unavailable. Press Ctrl+C in
the app terminal to stop it.

Switching interrupts display sleeps and animation waits. A synchronous API request
already running must finish first; `--dummy-data` avoids that delay while testing.

References: [Mosquitto installation](https://mosquitto.org/download/),
[mosquitto_pub options](https://mosquitto.org/man/mosquitto_pub-1.html).

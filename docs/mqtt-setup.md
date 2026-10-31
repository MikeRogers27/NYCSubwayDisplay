# MQTT infrastructure: laptop to Raspberry Pi

This setup runs the MQTT broker and display app on the Pi. The laptop publishes
test commands over the local network; the app connects to the broker on localhost.

```text
Laptop: mosquitto_pub
    │ TCP to PI_IP:1883
    ▼
Pi: Mosquitto broker
    │ app subscribes through 127.0.0.1:1883
    ▼
Pi: NYCSubwayDisplay → command queue → matrix display
```

| Component | Installed on | Purpose |
|---|---|---|
| `mosquitto` | Pi | Broker that receives and forwards MQTT messages |
| `mosquitto-clients` | Pi and laptop | `mosquitto_pub` and `mosquitto_sub` testing tools |
| `paho-mqtt` | Pi's project virtual environment | Python MQTT client used by the display app |

The broker runs as its own system service. It is separate from the Python app.

## 1. Install Mosquitto on the Pi

Run on the Pi (Raspberry Pi OS / Debian):

```bash
sudo apt update
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable --now mosquitto
```

This starts the broker and enables it at boot.

## 2. Allow connections from the laptop

Mosquitto's default local-only listener cannot receive laptop connections.
Create or edit this configuration file on the Pi:

```bash
sudo nano /etc/mosquitto/conf.d/matrix.conf
```

Use these contents:

```conf
listener 1883 0.0.0.0
allow_anonymous true
```

The listener accepts IPv4 connections on the Pi's network interfaces, including
localhost. Anonymous access matches the app's current client, which does not
configure a username or password. This setup is for a trusted home LAN; anyone
who can reach port 1883 can send commands. Do not forward this port to the internet.

Use one listener for port 1883: if you previously added one elsewhere, edit that
configuration rather than adding another. The Raspberry Pi OS package normally
loads `/etc/mosquitto/conf.d` through an `include_dir` entry in
`/etc/mosquitto/mosquitto.conf`; confirm that entry exists if this is a custom install.

Restart and check the broker:

```bash
sudo systemctl restart mosquitto
sudo systemctl status mosquitto --no-pager
sudo ss -ltnp 'sport = :1883'
```

The service should be active, and the listening address should be `0.0.0.0:1883`.

## 3. Find the Pi's LAN IP

On the Pi:

```bash
hostname -I
```

Use the address for its Wi-Fi or Ethernet connection, for example `192.168.1.42`.
If several addresses appear, `ip -4 addr show` identifies which belongs to `wlan0`
or `eth0`. A DHCP reservation in your router can keep this address stable.

The laptop and Pi must be on networks that can reach each other. Guest Wi-Fi may
isolate devices. If the Pi has a firewall, allow TCP port 1883 from the laptop's IP.

## 4. Start the Pi's listener

First complete the native matrix driver and project setup in [setup.md](setup.md).
Then, from the project directory on the Pi:

```bash
uv sync --extra pi --no-dev --locked
```

This installs `paho-mqtt` with the other Python dependencies. It does not install
the Mosquitto broker, which is managed by the OS package installed above.

To test MQTT reception without running the matrix or requiring API keys:

```bash
.venv/bin/python mqtt_listener.py --mqtt-host 127.0.0.1 --mqtt-port 1883
```

Or run the display with dummy data, using the hardware settings from our Pi setup:

```bash
sudo .venv/bin/python main.py \
  --mqtt --dummy-data \
  --led-gpio-mapping=adafruit-hat-pwm \
  --led-rows=32 --led-cols=64 \
  --led-rgb-sequence=RBG --led-brightness=40 \
  --led-slowdown-gpio=1 --led-no-drop-privs
```

Adjust LED arguments for your hardware. `--dummy-data` avoids external API requests
and API-key requirements while testing. For the existing `matrix.service`, add
`--mqtt` to the app command in `~/run-matrix.sh`, then restart `matrix.service`.
Add `--dummy-data` there too if you want the service to use sample data.

The app's defaults are `--mqtt-host 127.0.0.1`, `--mqtt-port 1883`, and
`--mqtt-topic matrix/display/train/set`. Only `--mqtt` is needed to enable it.
The app does not need to listen on its LAN IP: the broker accepts the laptop's
connection and forwards messages through the app's localhost connection.

## 5. Send a message from the laptop

On an Ubuntu/Debian laptop, install just the client tools:

```bash
sudo apt install mosquitto-clients
```

Keep the Pi app or standalone listener running. Once it reports it is connected,
publish from a laptop terminal, replacing the example IP with the Pi's address:

```bash
mosquitto_pub -h 192.168.1.42 -p 1883 -t matrix/display/train/set -m ON
```

The Pi console should show:

```text
MQTT topic='matrix/display/train/set' payload=b'ON' -> command='trains'
```

In the display app, `ON` interrupts the current rendering wait and runs the normal
train rotation once, then returns to the interrupted rotation entry and continues
through the remaining entries. The interrupted entry restarts its usual duration.
The standalone listener only prints
the message. `OFF` is printed and ignored:

```bash
mosquitto_pub -h 192.168.1.42 -p 1883 -t matrix/display/train/set -m OFF
```

## Troubleshooting

- **Connection refused:** check `systemctl status mosquitto` and `ss` on the Pi.
- **Connection timed out:** check the Pi IP, network isolation, and firewall.
- **Not authorised:** check that the active listener has `allow_anonymous true`.
- **Publish succeeds but nothing happens:** confirm the app has `--mqtt` enabled
  and uses the same broker and topic. Start it before publishing; these test
  messages are not retained for later subscribers.

Broker logs on the Pi:

```bash
sudo journalctl -u mosquitto -n 50 --no-pager
sudo tail -n 50 /var/log/mosquitto/mosquitto.log
```

The package may send detailed broker logs to the file rather than the journal.
To verify laptop-to-broker delivery independently of the app, run this on the Pi
and publish again from the laptop:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t matrix/display/train/set -v
```

References: [Mosquitto listener behavior](https://mosquitto.org/man/mosquitto-8.html),
[anonymous access configuration](https://mosquitto.org/documentation/authentication-methods/).

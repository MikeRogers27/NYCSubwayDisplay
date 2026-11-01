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
| `matterbridge` + `matterbridge-mqtt` | Laptop | Development bridge between Google Home and the Pi's MQTT broker |

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
`--mqtt-topic 'matrix/display/+/set'`. The `+` matches the train, f-trains, r-trains,
clock, or weather topic segment. Only `--mqtt` is needed to enable it.
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
mosquitto_pub -h 192.168.1.42 -p 1883 -t matrix/display/f-trains/set -m ON
mosquitto_pub -h 192.168.1.42 -p 1883 -t matrix/display/r-trains/set -m ON
mosquitto_pub -h 192.168.1.42 -p 1883 -t matrix/display/clock/set -m ON
mosquitto_pub -h 192.168.1.42 -p 1883 -t matrix/display/weather/set -m ON
```

The Pi console should show:

```text
MQTT topic='matrix/display/train/set' payload=b'ON' -> command='trains'
```

In the display app, `ON` interrupts the current rendering wait and runs the
requested mode once, then returns to the interrupted rotation entry and continues
through the remaining entries. The interrupted entry restarts its usual duration.
Use `f-trains/set` for only stop `F23N` or `r-trains/set` for only stop `R33N`.
The normal `train/set` topic uses all configured stops; per-request selections do
not change that configuration.
The standalone listener only prints
the message. `OFF` is printed and ignored:

```bash
mosquitto_pub -h 192.168.1.42 -p 1883 -t matrix/display/train/set -m OFF
```

## 6. Install and configure Matterbridge on the laptop

Matterbridge runs on the laptop during development; Mosquitto and the display app
stay on the Pi. The intended control path is:

```text
Google Home Mini → Matterbridge + MQTT plugin on laptop
                → Mosquitto on Pi → display app on Pi
```

### Install Node.js and Matterbridge

Install **Node.js 24 LTS** using the [Node.js installation options](https://nodejs.org/en/download).
Node.js 20 is no longer supported by current Matterbridge. Check the active
versions, then install Matterbridge:

```bash
node --version
npm --version
npm install -g matterbridge --omit=dev
matterbridge --version
matterbridge --bridge
```

If the global npm installation requires system permissions, use
`sudo npm install -g matterbridge --omit=dev`. Run `matterbridge` itself as your
normal laptop user. These commands install laptop software separately from the
project's uv environment.

Leave it running and open [the local frontend](http://localhost:8283).
Keep the laptop awake while testing. IPv6 must be enabled on the local network;
internet-side IPv6 is not required. The phone, speaker, and laptop must be able to
discover and communicate with each other. With multiple network interfaces, select
the home LAN interface in the frontend's **Settings → Mdns Interface**.

See [Matterbridge installation, prerequisites, and frontend configuration](https://matterbridge.io/README.html).

### Install the MQTT plugin

In the Matterbridge frontend, install **`matterbridge-mqtt`**, then configure its
connection to the existing Pi broker:

| Plugin setting | Value |
|---|---|
| `host` | `mqtt://192.168.1.42` — replace with the Pi's actual LAN IP |
| `port` | `1883` |
| `topic` | `matterbridge` |
| `username`, `password` | Empty for our anonymous LAN broker |

Save the settings and restart Matterbridge if prompted. Verify its logs show the
plugin connecting to the broker. Do not use `localhost` here: on the laptop that
would point to a laptop broker. The Pi display app should continue using
`127.0.0.1` to reach its own broker.

The plugin stores configuration in
`~/.matterbridge/matterbridge-mqtt.config.json`. See the
[plugin configuration and messaging protocol](https://github.com/Luligu/matterbridge-mqtt)
for all settings and message formats.

### Register the application's virtual controls

Run the updated app on the Pi with `--matterbridge` added to its usual launch
command. This flag also enables MQTT; `--mqtt` is not required separately.
For the existing service, add `--matterbridge` to `~/run-matrix.sh` and restart
`matrix.service`. Keep `--dummy-data` during testing to avoid API requests.

Or run the emulator on the laptop, pointing it to the same Pi broker:

```bash
uv run --group dev --frozen python main.py \
  --dummy-data --matterbridge --mqtt-host 192.168.1.42
```

Replace the example IP with the Pi's address. When running on the Pi, omit
`--mqtt-host` to keep using localhost. `--matterbridge-topic` defaults to
`matterbridge` and must match the plugin's `topic` setting. The manual
`matrix/display/.../set` commands remain available.

Each successful broker connection subscribes to the controls' write topics and
publishes retained configuration, initial off state, and attribute subscriptions:

| Device ID | Name shown in Matterbridge / Google Home | Display request |
|---|---|---|
| `matrix-trains` | All Trains | Configured train stops |
| `matrix-f-trains` | F Trains | Only `F23N` |
| `matrix-r-trains` | R Trains | Only `R33N` |
| `matrix-clock` | Pixie Clock | Clock |
| `matrix-weather` | Pixie Weather | Weather |

The controls are exposed as on/off plug-in units (virtual outlets). Their stable
IDs preserve endpoint identities between application restarts. The app announces
all five controls automatically; no manual device registration is needed.

The plugin sends commands as JSON on topics such as:

```text
matterbridge/matrix-f-trains/write/root
{"OnOff":{"onOff":true}}
```

The app translates boolean `onOff: true` into the same interruptible `DisplayMode`
request as a manual `ON` command, then publishes `onOff: false` to the control's
state topic. This momentary reset allows repeated voice activations and does not
stop the display. False, malformed, and retained write commands are ignored.
Configuration remains retained when the app exits; leave the app running to act
on commands. Keep one app instance responsible for this display during testing.

To register and inspect commands without running a matrix:

```bash
uv run --frozen python mqtt_listener.py --matterbridge --mqtt-host 192.168.1.42
```

This standalone mode also resets virtual switches but only reports commands to
the console. To monitor registration and state feedback from the laptop:

```bash
mosquitto_sub -h 192.168.1.42 -t 'matterbridge/#' -v
```

After the controls appear in the plugin frontend, test F Trains using this command
while the app is running (do not add `-r` to activation messages):

```bash
mosquitto_pub -h 192.168.1.42 -t matterbridge/matrix-f-trains/write/root \
  -m '{"OnOff":{"onOff":true}}'
```

### Pair with Google Home once the first control is registered

Keep the Google Home Mini connected to the same household and LAN. Google lists
it as a [Matter-over-Wi-Fi hub](https://support.google.com/googlehome/answer/12391458?hl=en);
this setup does not require Thread hardware.

1. Open the Google Home app on your phone and choose **Add → Device**.
2. Scan the Matterbridge pairing QR code shown in its frontend; follow the prompts
   to add it to the household containing the Mini.
3. Verify the F Trains control appears and works from the phone app.
4. Test a voice command such as “Hey Google, turn on F Trains.”

See [Google Home Matter pairing instructions](https://support.google.com/googlehome/answer/13127223?hl=en-CA)
for the current app flow. Once F Trains works, test R Trains, All Trains,
Pixie Clock, and Pixie Weather in the same way.

## Troubleshooting

- **Connection refused:** check `systemctl status mosquitto` and `ss` on the Pi.
- **Connection timed out:** check the Pi IP, network isolation, and firewall.
- **Not authorised:** check that the active listener has `allow_anonymous true`.
- **Publish succeeds but nothing happens:** confirm the app has `--mqtt` enabled
  and uses the same broker and topic. Start it before publishing; these test
  messages are not retained for later subscribers.
- **Matterbridge controls appear but do not send write messages:** restart
  Matterbridge once after initial registration so the plugin can reapply the
  retained state and attribute subscriptions, then try the control again.

Broker logs on the Pi:

```bash
sudo journalctl -u mosquitto -n 50 --no-pager
sudo tail -n 50 /var/log/mosquitto/mosquitto.log
```

The package may send detailed broker logs to the file rather than the journal.
To verify laptop-to-broker delivery independently of the app, run this on the Pi
and publish again from the laptop:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'matrix/display/+/set' -v
```

References: [Mosquitto listener behavior](https://mosquitto.org/man/mosquitto-8.html),
[anonymous access configuration](https://mosquitto.org/documentation/authentication-methods/).

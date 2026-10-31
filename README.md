# NYC Subway Display

A Raspberry Pi-powered LED matrix display that cycles through NYC subway arrival times, weather forecasts, live sports scores, a clock, and seasonal holiday animations — all on a 64×32 RGB LED panel.

![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)

## Features

### 🚇 Subway Arrivals
Real-time NYC subway train arrival times using MTA's GTFS real-time feeds (via `nyct-gtfs`). Displays route indicators with colored circles (matching official MTA line colors for B/D/F/M, G, N/Q/R/W), destination, direction, and minutes until arrival. Configurable stop IDs for your local station.

### 🌤️ Weather
Current conditions and forecasts powered by OpenWeatherMap (via `pyowm`). Shows temperature, weather description, and condition icons (sun, clouds, rain, snow, fog, lightning, etc.). Displays today's and tomorrow's forecast summaries with high/low temperatures.

### ⚽ Live Sports Scores
Tracks games across multiple leagues and APIs:

- **Football (Soccer)** — Premier League, Championship, FA Cup, League Cup, Friendlies via RapidAPI
- **Rugby** — Super League via RapidAPI
- **MLB, NHL, NFL, MLS** — via SportsGameOdds API

Displays team icons, opponent name, score (with W/D/L prefix for completed games), and match date/time. Supports configurable team lists and score-hiding rules for spoiler avoidance.

### 🕐 Clock
Simple time-of-day display.

### 🎃 Seasonal Animations
Animated GIF and PNG displays for holidays:
- 4th of July (fireworks)
- Halloween (ghosts, skeletons, witches)
- Bonfire Night (fireworks)
- Thanksgiving (themed animations)
- Christmas (trees, snowmen, Santa)
- New Year's Eve (fireworks)
- Winter (snow scenes)

Each seasonal event has configurable display windows (days before/after the holiday).

## Smart Scheduling

The display automatically decides what to show based on day and time:

| When | What's Shown |
|---|---|
| Weekday mornings (7–10am) | Uptown trains, clock, weather |
| Weekday daytime (10am–8pm) | All trains, clock, weather |
| Evenings (after 8pm) | Clock, weather, sports, seasonal |
| Weekends (9am–midnight) | Trains, clock, weather, sports, seasonal |
| Overnight | Display off (checks every 10 min) |

## Hardware Requirements

- Raspberry Pi (tested with Pi models supporting GPIO)
- 64×32 RGB LED matrix panel
- Adafruit RGB Matrix HAT or Bonnet
- 5V power supply for the LED panel

## Software Requirements

- Python 3.13
- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) library (for Raspberry Pi)
- [RGBMatrixEmulator](https://github.com/ty-porter/RGBMatrixEmulator) (for Windows/desktop development)

## API Keys Required

| Service | Environment Variable | Purpose |
|---|---|---|
| [OpenWeatherMap](https://home.openweathermap.org/api_keys) | `OWM_API_KEY` | Weather data |
| [SportsGameOdds](https://sportsgameodds.com/) | `SGO_API_KEYS` | MLB, NHL, NFL, MLS scores (comma-separated list of keys for rotation) |
| [RapidAPI](https://rapidapi.com/) | `RPA_API_KEY` | Football and rugby scores |

## Installation

### On Raspberry Pi

See [docs/setup.md](docs/setup.md) for full step-by-step instructions covering:
- Pi OS setup and audio/Bluetooth disabling (required for LED matrix)
- Building and installing `rpi-rgb-led-matrix`
- Python virtual environment setup
- Systemd service configuration for auto-start on boot

### Quick Start (Development / Emulator)

```bash
# Clone the repo
git clone git@github.com:MikeRogers27/NYCSubwayDisplay.git
cd NYCSubwayDisplay

# Install development dependencies, including the emulator (Linux/macOS/Windows)
uv sync --group dev --frozen

# Activate the environment (optional, but useful for local shells)
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Set environment variables
export OWM_API_KEY=your_key
export SGO_API_KEYS=key1,key2
export RPA_API_KEY=your_key

# Run
python main.py
```

The emulator serves a browser-based preview at `http://localhost:8888` (configurable in `emulator_config.json`).

The `dev` group installs the emulator on every platform and is included by default
by uv. Windows always installs and uses the emulator, even with `--no-dev`.
Use `--frozen` on development machines to install from the committed lockfile
without needing the local Pi driver checkout to validate or resolve dependencies.
On Linux, the application uses the emulator when it is installed; otherwise it uses
the native `rgbmatrix` driver. For Raspberry Pi deployment, install only the Pi
dependencies and use the same selection when running:

```bash
uv sync --extra pi --no-dev --locked
uv run --extra pi --no-dev --locked python main.py
```

The Pi installation expects the native driver checkout at
`../rpi-rgb-led-matrix/bindings/python`; see [docs/setup.md](docs/setup.md).
Updating the lockfile with `uv lock` also requires this checkout.

## Usage

```bash
python main.py [options]
```

### LED Panel Options

| Flag | Description | Default |
|---|---|---|
| `-r`, `--led-rows` | Display rows | 32 |
| `--led-cols` | Panel columns | 32 |
| `-b`, `--led-brightness` | Brightness (1–100) | 100 |
| `-m`, `--led-gpio-mapping` | Hardware mapping (`regular`, `adafruit-hat`, `adafruit-hat-pwm`) | — |
| `--led-rgb-sequence` | Color channel order | RGB |
| `--led-slowdown-gpio` | GPIO slowdown (0–4) | 1 |
| `--led-no-drop-privs` | Don't drop root privileges after init | — |
| `--log` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | ERROR |

### Example (Raspberry Pi with Adafruit HAT)

```bash
sudo python main.py \
  --led-gpio-mapping=adafruit-hat-pwm \
  --led-rows=32 \
  --led-cols=64 \
  --led-rgb-sequence=RBG \
  --led-brightness=40 \
  --led-slowdown-gpio=1 \
  --led-no-drop-privs
```

## Configuration

### Subway Stops
Edit the `stop_ids` and `uptown_stop_ids` in the `main()` function to match your local station. The default is configured for stops F23 and R33.

### Sports Teams
Modify the team lists at the top of `main.py`:
- `RAPI_FOOTBALL_TEAMS` — Football team IDs (RapidAPI)
- `RAPI_RUGBY_TEAMS` — Rugby team codes
- `SGO_MLB_TEAMS`, `SGO_NHL_TEAMS`, `SGO_NFL_TEAMS`, `SGO_MLS_TEAMS` — US sports teams

### Score Hiding
The `HIDE_SCORES` dictionary lets you hide scores for specific teams/competitions for a time window — useful if you plan to watch a recording later.

### Emulator
Adjust `emulator_config.json` to change pixel size, style, browser port, and FPS for the desktop emulator.

### MQTT Listener

MQTT is optional and uses `paho-mqtt` 2.x. Enable it alongside the display with:

```bash
uv run --group dev --frozen python main.py --mqtt
```

Or run just the listener, without the matrix or API keys:

```bash
uv run --group dev --frozen python mqtt_listener.py
```

An MQTT broker must be running separately. The defaults are `127.0.0.1:1883`
and subscription filter `matrix/display/+/set`. Both commands accept `--mqtt-host`,
`--mqtt-port`, and `--mqtt-topic` to override these. This basic interface uses
an unauthenticated TCP connection. If the broker is unavailable, the listener
retries in the background.

With Mosquitto's command-line clients installed, publish from another terminal:

```bash
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/train/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/f-trains/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/r-trains/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/clock/set -m ON
mosquitto_pub -h 127.0.0.1 -p 1883 -t matrix/display/weather/set -m ON
```

Each received message goes into a `SimpleQueue`, then a console worker consumes
it and prints its topic and raw payload. For `ON`, the output also identifies the
`trains` command:

```text
MQTT topic='matrix/display/train/set' payload=b'ON' -> command='trains'
```

In the app, `ON` interrupts the current display wait and selects trains, clock,
or weather according to the topic, then returns to the
interrupted rotation entry and continues with the remaining entries. The resumed
entry starts its usual duration again; the time-based schedule is refreshed once
that rotation finishes. `OFF` and other payloads are
reported but do not interrupt the display. The standalone listener only reports
messages. Pending commands are coalesced so the latest command wins.
Requested modes use their duration from the pending rotation; if absent, defaults
are trains 5 seconds, clock 30 seconds, and weather 5 seconds, with existing
multi-view timings preserved. See [MQTT.md](MQTT.md) for examples.
The `f-trains` and `r-trains` topics show only `F23N` or `R33N`, respectively,
without changing the stops used by later scheduled displays. Modes carry optional
stop selections as immutable `DisplayMode` objects.
Console reporting runs independently of display sleeps. Ctrl+C stops the listener
and its network thread; the display also cleans up MQTT when it exits.
Display sleeps and animations can be interrupted; an in-progress synchronous API
request must finish before the renderer can switch modes. Use `--dummy-data` to
try switching without external requests.

### Development with Dummy Data

Use `--dummy-data` to conserve external API quotas while developing:

```bash
uv run --group dev --frozen python main.py --dummy-data
# Combine with MQTT if needed:
uv run --group dev --frozen python main.py --dummy-data --mqtt
```

This mode needs no API keys and skips the SGO account-usage check. It uses local
fixtures for every data service, including refreshes and football team metadata:

| Service | Sample data |
|---|---|
| MTA | F/G/R trains arriving in 3, 8, 15, and 22 minutes, in both directions |
| OWM | 18°C current weather and five days of three-hour forecasts |
| RAPI football | Sunderland leading Manchester United 2–1 in a live game |
| RAPI rugby | Wigan beating St Helens 24–18 in a completed game |
| SGO | MLB, NHL, NFL, and MLS games covering completed, live, and upcoming events |

The sample values are fixed; timestamps are relative to today so arrivals and
forecasts remain useful. The existing schedule and score-hiding rules still apply.
Dummy sports data bypasses the live caches entirely. Edit `dummy_data.py` to adjust
the samples. Omitting `--dummy-data` uses the normal live services. The emulator
preview and optional MQTT connection continue to work in dummy mode.

## Project Structure

```
├── main.py                 # Main application (display logic, API integrations, game classes)
├── samplebase.py           # Base class for RGB matrix initialization
├── matrix_backend.py       # Shared emulator/native driver selection
├── mqtt_listener.py        # MQTT queue and console listener (also runnable alone)
├── dummy_data.py           # Local MTA, OWM, RAPI, and SGO fixtures
├── display_control.py      # Queued display commands and interruptible waits
├── weather.py              # Weather API experimentation script
├── utils/
│   └── colors.py           # Image color extraction utilities
├── fonts/                  # BDF bitmap fonts for the LED display
├── icons/32/               # 32×32 PNG icons (weather, sports teams)
├── images/                 # Seasonal animated GIFs and PNGs
├── data/                   # Static data files (team info)
├── cache/                  # Cached API responses
├── docs/
│   └── setup.md            # Raspberry Pi setup guide
├── emulator_config.json    # RGBMatrixEmulator settings
├── pyproject.toml          # Dependencies and development/Pi selections
└── uv.lock                 # Locked dependency versions
```

## License

MIT — see [LICENSE](LICENSE).

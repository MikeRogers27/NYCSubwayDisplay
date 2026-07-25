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

- Python 3.10+
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

# Create and sync the uv environment
uv sync --group dev

# Activate the environment (optional, but useful for local shells)
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install platform-specific dependencies
uv pip install -r requirements.txt          # Raspberry Pi
uv pip install -r requirements_win.txt      # Windows (includes RGBMatrixEmulator)

# Set environment variables
export OWM_API_KEY=your_key
export SGO_API_KEYS=key1,key2
export RPA_API_KEY=your_key

# Run
python main.py
```

On Windows, the emulator serves a browser-based preview at `http://localhost:8888` (configurable in `emulator_config.json`).

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

## Project Structure

```
├── main.py                 # Main application (display logic, API integrations, game classes)
├── samplebase.py           # Base class for RGB matrix initialization
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
├── requirements.txt        # Python dependencies (Raspberry Pi)
└── requirements_win.txt    # Python dependencies (Windows/emulator)
```

## License

MIT — see [LICENSE](LICENSE).

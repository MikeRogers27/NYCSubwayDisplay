"""Local service fixtures with fixed values and dates relative to the current day."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from types import SimpleNamespace
from typing import Any

from pyowm.weatherapi30.forecast import Forecast
from pyowm.weatherapi30.forecaster import Forecaster
from pyowm.weatherapi30.weather import Weather


@dataclass
class DummyFeed:
    """Supply the subset of the NYCT feed interface used by the display."""

    route_id: str
    timezone: Any

    def refresh(self) -> None:
        """Keep the feed local; trips are generated when requested."""

    def filter_trips(self, headed_for_stop_id: str) -> list[SimpleNamespace]:
        """Return sample arrivals for either direction at the requested station."""
        if headed_for_stop_id.startswith("F23") and self.route_id == "R":
            return []
        if headed_for_stop_id.startswith("R33") and self.route_id != "R":
            return []
        now = datetime.now(tz=self.timezone).replace(tzinfo=None)
        return [
            SimpleNamespace(
                route_id=self.route_id,
                headsign_text="Jamaica" if headed_for_stop_id.endswith("N") else "Coney Island",
                location_status="IN_TRANSIT_TO",
                location=None,
                underway=True,
                last_position_update=now,
                stop_time_updates=[
                    SimpleNamespace(stop_id=headed_for_stop_id, arrival=now + timedelta(minutes=minutes))
                ],
            )
            for minutes in (3, 8, 15, 22)
        ]


def weather(now: datetime) -> tuple[Weather, Forecaster]:
    """Return 18°C current weather and five days of three-hour forecasts."""

    def sample(at: datetime, code: int = 801) -> Weather:
        return Weather(
            reference_time=int(at.timestamp()),
            sunset_time=int(at.replace(hour=18).timestamp()),
            sunrise_time=int(at.replace(hour=6).timestamp()),
            clouds=25,
            rain={},
            snow={},
            wind={"speed": 3.0, "deg": 180},
            humidity=60,
            pressure={"press": 1015},
            temperature={"temp": 291.15, "temp_min": 288.15, "temp_max": 294.15},
            status="Clouds",
            detailed_status="few clouds",
            weather_code=code,
            weather_icon_name="02d" if 6 <= at.hour < 18 else "02n",
            visibility_distance=10000,
            dewpoint=None,
            humidex=None,
            heat_index=None,
        )

    forecasts = [
        sample(now.tzinfo.localize(datetime.combine(now.date() + timedelta(days=day), time(hour))))
        for day in range(5)
        for hour in range(0, 24, 3)
    ]
    return sample(now), Forecaster(Forecast("3h", int(now.timestamp()), None, forecasts))


def football(now: datetime, league_id: int, team_id: int) -> list[dict[str, Any]]:
    """Return a live Sunderland fixture in the football API's format."""
    return [
        {
            "fixture": {
                "id": "dummy-football",
                "timestamp": int((now - timedelta(minutes=60)).timestamp()),
                "status": {"short": "2H", "elapsed": 60},
            },
            "league": {"id": league_id, "name": "Premier League"},
            "teams": {"home": {"id": team_id, "name": "Sunderland"}, "away": {"id": 33, "name": "Manchester United"}},
            "goals": {"home": 2, "away": 1},
            "score": {"penalty": {"home": None, "away": None}, "extratime": {"home": None, "away": None}},
        }
    ]


def rugby(now: datetime) -> list[dict[str, Any]]:
    """Return a completed Wigan fixture in the rugby API's format."""
    return [
        {
            "id": "dummy-rugby",
            "startTimestamp": int((now - timedelta(hours=3)).timestamp()),
            "tournament": {"id": 302, "name": "Super League"},
            "homeTeam": {"nameCode": "WGW", "teamColors": {"primary": "#D71920"}},
            "awayTeam": {"nameCode": "STH", "teamColors": {"primary": "#FFFFFF"}},
            "homeScore": {"display": 24},
            "awayScore": {"display": 18},
            "status": {"type": "finished"},
            "time": {"played": 4800},
        }
    ]


def sgo(now: datetime, league_id: str) -> list[dict[str, Any]]:
    """Return sample MLB, NHL, NFL, or MLS events in SGO's format."""
    teams = {
        "MLB": ("NEW_YORK_METS_MLB", "NYM", "NEW_YORK_YANKEES_MLB", "NYY"),
        "NHL": ("NEW_YORK_RANGERS_NHL", "NYR", "NEW_JERSEY_DEVILS_NHL", "NJD"),
        "NFL": ("NEW_YORK_GIANTS_NFL", "NYG", "NEW_YORK_JETS_NFL", "NYJ"),
        "MLS": ("LOS_ANGELES_GALAXY_MLS", "LAG", "AUSTIN_MLS", "ATX"),
    }
    if league_id not in teams:
        return []
    home, home_name, away, away_name = teams[league_id]
    upcoming = league_id == "NFL"
    finished = league_id in ("MLB", "MLS")
    start = now + timedelta(hours=3) if upcoming else now - timedelta(hours=3)
    return [
        {
            "eventID": f"dummy-sgo-{league_id}",
            "leagueID": league_id,
            "teams": {
                "home": {"teamID": home, "names": {"short": home_name}, "colors": {"primary": "#005A9C"}, "score": 3},
                "away": {"teamID": away, "names": {"short": away_name}, "colors": {"primary": "#CC0000"}, "score": 2},
            },
            "status": {
                "startsAt": start.isoformat(),
                "started": not upcoming,
                "ended": finished,
                "displayShort": "F" if finished else "Live",
            },
        }
    ]

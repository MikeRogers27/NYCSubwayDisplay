"""Local service fixtures with fixed values and dates relative to the current day."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo
from typing import NotRequired, TypedDict

# PyOWM 3.5.0 does not publish type stubs or a py.typed marker.
from pyowm.weatherapi30.forecast import Forecast  # type: ignore[import-untyped]
from pyowm.weatherapi30.forecaster import Forecaster  # type: ignore[import-untyped]
from pyowm.weatherapi30.weather import Weather  # type: ignore[import-untyped]
from pytz.tzinfo import DstTzInfo, StaticTzInfo


@dataclass
class DummyStopTimeUpdate:
    """A predicted arrival at one stop."""

    stop_id: str
    arrival: datetime


@dataclass
class DummyTrain:
    """Train fields consumed by the display and arrival calculations."""

    route_id: str
    headsign_text: str
    location_status: str
    location: str | None
    underway: bool
    last_position_update: datetime
    stop_time_updates: list[DummyStopTimeUpdate]


class HomeAway[T](TypedDict):
    """Values for the home and away teams."""

    home: T
    away: T


class League(TypedDict):
    """Numeric league identity shared by football and rugby fixtures."""

    id: int
    name: str


class FootballStatus(TypedDict):
    """Football match phase and elapsed minutes."""

    short: str
    elapsed: int


class FootballFixture(TypedDict):
    """Football match identity, start time, and status."""

    id: str
    timestamp: int
    status: FootballStatus


class FootballTeam(TypedDict):
    """Football team identity used for local team metadata."""

    id: int
    name: str


class FootballGame(TypedDict):
    """Football API payload consumed by GameRAPIFootball."""

    fixture: FootballFixture
    league: League
    teams: HomeAway[FootballTeam]
    goals: HomeAway[int]
    score: dict[str, HomeAway[int | None]]


class RugbyTeam(TypedDict):
    """Rugby team abbreviation and display colors."""

    nameCode: str
    teamColors: dict[str, str]


class RugbyGame(TypedDict):
    """Rugby API payload consumed by GameRAPIRugby."""

    id: str
    startTimestamp: int
    tournament: League
    homeTeam: RugbyTeam
    awayTeam: RugbyTeam
    homeScore: dict[str, int]
    awayScore: dict[str, int]
    status: dict[str, str]
    time: dict[str, int]


class SGOTeam(TypedDict):
    """SGO team identity, display metadata, and score."""

    teamID: str
    names: dict[str, str]
    colors: NotRequired[dict[str, str | None] | None]
    score: int


class SGOStatus(TypedDict):
    """SGO event start time and lifecycle flags."""

    startsAt: str
    started: bool
    ended: bool
    displayShort: str


class SGOEvent(TypedDict):
    """SportsGameOdds event payload consumed by GameSGO."""

    eventID: str
    leagueID: str
    teams: HomeAway[SGOTeam]
    status: SGOStatus


@dataclass
class DummyFeed:
    """Supply the subset of the NYCT feed interface used by the display."""

    route_id: str
    timezone: tzinfo

    def refresh(self) -> None:
        """Keep the feed local; trips are generated when requested."""

    def filter_trips(self, headed_for_stop_id: str) -> list[DummyTrain]:
        """Return sample arrivals for either direction at the requested station."""
        if headed_for_stop_id.startswith("F23") and self.route_id == "R":
            return []
        if headed_for_stop_id.startswith("R33") and self.route_id != "R":
            return []
        now = datetime.now(tz=self.timezone)
        return [
            DummyTrain(
                route_id=self.route_id,
                headsign_text="Jamaica" if headed_for_stop_id.endswith("N") else "Coney Island",
                location_status="IN_TRANSIT_TO",
                location=None,
                underway=True,
                last_position_update=now,
                stop_time_updates=[
                    DummyStopTimeUpdate(stop_id=headed_for_stop_id, arrival=now + timedelta(minutes=minutes))
                ],
            )
            for minutes in (3, 8, 15, 22)
        ]


def weather(now: datetime) -> tuple[Weather, Forecaster]:
    """Return 18°C current weather and five days of three-hour forecasts."""
    timezone = now.tzinfo
    if timezone is None or now.utcoffset() is None:
        raise ValueError("Dummy weather requires a timezone-aware datetime")

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

    forecasts: list[Weather] = []
    for day in range(5):
        for hour in range(0, 24, 3):
            forecast_time = datetime.combine(now.date() + timedelta(days=day), time(hour))
            if isinstance(timezone, (DstTzInfo, StaticTzInfo)):
                forecast_time = timezone.localize(forecast_time)
            else:
                forecast_time = forecast_time.replace(tzinfo=timezone)
            forecasts.append(sample(forecast_time))
    return sample(now), Forecaster(Forecast("3h", int(now.timestamp()), None, forecasts))


def football(now: datetime, league_id: int, team_id: int) -> list[FootballGame]:
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


def rugby(now: datetime) -> list[RugbyGame]:
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


def sgo(now: datetime, league_id: str) -> list[SGOEvent]:
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

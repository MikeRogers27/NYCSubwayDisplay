from abc import ABC, abstractmethod
import argparse
from collections import namedtuple
from datetime import datetime, time as dt_time, date as dt_date, timedelta
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
import importlib
import logging
from logging import Logger
import os
import pickle
import random
import requests
import tempfile
import time
from typing import Optional
import signal
import warnings

import holidays
from nyct_gtfs import NYCTFeed
from PIL import Image
from pyowm import OWM
import pytz

if os.name == 'nt':
    graphics = importlib.import_module('RGBMatrixEmulator', 'graphics')
else:
    from rgbmatrix import graphics

from samplebase import SampleBase

LOCAL_TZ = pytz.timezone("America/New_York")
NOW = datetime.now()

LOG = Optional[Logger]
MIN_DISPLAY_TIME = 3

MTA_FEEDS = None
MTA_TIMESTAMP = None
MTA_TRAINS = None
MTA_REFRESH_RATE = 60

OWM_FORECAST = None
OWM_MGR = None
OWM_REFRESH_RATE = 3600 * 0.5
OWN_TIMESTAMP = None
OWM_WEATHER = None

RAPI_FOOTBALL_GAMES = None
RAPI_FOOTBALL_GAMES_LAST_UPDATE = {}
RAPI_FOOTBALL_TIMESTAMP = None
RAPI_FOOTBALL_NEXT_REFRESH = None
RAPI_FOOTBALL_REFRESH_RATE = 360
RAPI_FOOTBALL_TEAMS = [746, ]
RAPI_FOOTBALL_PREMIER_LEAGUE_ID = 39
RAPI_FOOTBALL_CHAMPIONSHIP_ID = 40
RAPI_FOOTBALL_FA_CUP_ID = 45
RAPI_FOOTBALL_LEAGUE_CUP_ID = 48
RAPI_FOOTBALL_FRIENDLIES_ID = 667
RAPI_FOOTBALL_SEASON_ID = 2025  # TODO: Must be updated every year

RAPI_RUGBY_GAMES = None
RAPI_RUGBY_GAMES_LAST_UPDATE = {}
RAPI_RUGBY_TIMESTAMP = None
RAPI_RUGBY_NEXT_REFRESH = None
RAPI_RUGBY_REFRESH_RATE = 360
RAPI_RUGBY_TEAMS = ['WGW', ]
RAPI_RUGBY_SUPER_LEAGUE_ID = 345

Seasonal = namedtuple(
    'Seasonal',
    ('name', 'date', 'display_days_before', 'display_days_after', 'images', 'image_behaviour')
)
_us_holidays = holidays.US(years=NOW.year)
SEASONAL_DATA = [
    Seasonal(
        name='4thjuly',
        date=datetime(year=NOW.year, month=7, day=4),
        display_days_before=1,
        display_days_after=1,
        images=['images/fireworks.gif', 'images/fireworks2.gif', 'images/fireworks_newyork.gif', ],
        image_behaviour=['scroll_up_animate_centre', 'scroll_up_animate_centre', 'scroll_up_animate_centre', ],
    ),
    Seasonal(
        name='halloween',
        date=datetime(year=NOW.year, month=10, day=31),
        display_days_before=11,
        display_days_after=1,
        images=['images/halloween.png', 'images/halloween_anim.gif', 'images/halloween_witch.gif',
                'images/halloween_ghost_skel.gif', 'images/halloween_skel.gif', 'images/halloween_ghostbusters.gif',
                'images/halloween_pump_skel.gif', ],
        image_behaviour=['scroll_up', 'scroll_up_animate_centre', 'scroll_up_animate_centre',
                         'scroll_up', 'scroll_up', 'scroll_up_animate_centre',
                         'scroll_up', ],
    ),
    Seasonal(
        name='bonfire night',
        date=datetime(year=NOW.year, month=11, day=5),
        display_days_before=1,
        display_days_after=1,
        images=['images/bonfire_night.gif', 'images/fireworks.gif', 'images/fireworks2.gif', ],
        image_behaviour=['scroll_up_pause', 'scroll_up_animate_centre', 'scroll_up_animate_centre', ],
    ),
    Seasonal(
        name='thanksgiving',
        date=datetime.combine(_us_holidays.get_named('Thanksgiving')[0], datetime.min.time()),
        display_days_before=3,
        display_days_after=3,
        images=['images/thanksgiving.gif', 'images/thanksgiving_band.gif', 'images/thanksgiving_snoopy.gif',
                'images/thanksgiving_beaver.gif', ],
        image_behaviour=['scroll_up_animate_centre', 'scroll_up_pause', 'scroll_up_pause',
                         'scroll_up_pause', ],
    ),
    Seasonal(
        name='christmas',
        date=datetime(year=NOW.year, month=12, day=25),
        display_days_before=15,
        display_days_after=2,
        images=['images/christmas_tree.gif', 'images/christmas_snowman.gif', 'images/snow_cat.gif',
                'images/merry_christmas_santa.gif', 'images/merry_christmas_tree.gif', ],
        image_behaviour=['scroll_up', 'scroll_up_animate_centre', 'scroll_up_pause',
                         'scroll_up_pause', 'scroll_up_pause'],
    ),
    Seasonal(
        name='newyearseve',
        date=datetime(year=NOW.year, month=12, day=31),
        display_days_before=1,
        display_days_after=1,
        images=['images/fireworks.gif', 'images/fireworks2.gif', 'images/fireworks_newyork.gif', ],
        image_behaviour=['scroll_up_animate_centre', 'scroll_up_animate_centre', 'scroll_up_animate_centre', ],
    ),
    Seasonal(
        name='winter',
        date=datetime(year=NOW.year, month=12, day=31),
        display_days_before=31,
        display_days_after=31,
        images=['images/christmas_snowman.gif', 'images/snow_cat.gif', 'images/winter_snow.gif',
                'images/winter_grouch.gif', ],
        image_behaviour=['scroll_up_animate_centre', 'scroll_up_pause', 'scroll_up_animate_centre',
                         'scroll_up_animate_centre', ],
    ),
]

SGO_GAMES = None
SGO_TIMESTAMP = None
SGO_GAMES_LAST_UPDATE = {}
SGO_NEXT_REFRESH = None
SGO_REFRESH_RATE = 1800  # 30 mins
SGO_MLB_TEAMS = ['NEW_YORK_METS_MLB', 'NEW_YORK_YANKEES_MLB', 'LOS_ANGELES_DODGERS_MLB']
SGO_NHL_TEAMS = ['NEW_YORK_RANGERS_NHL', 'NEW_YORK_ISLANDERS_NHL', 'NEW_JERSEY_DEVILS_NHL', 'LOS_ANGELES_KINGS_NHL']
SGO_NFL_TEAMS = ['NEW_YORK_GIANTS_NFL', 'NEW_YORK_JETS_NFL', 'SEATTLE_SEAHAWKS_NFL']
SGO_MLS_TEAMS = ['LOS_ANGELES_GALAXY_MLS', 'AUSTIN_MLS']

HIDE_SCORES = {
    'LOS_ANGELES_KINGS_NHL': [relativedelta(months=3, weeks=2), relativedelta(months=6)],
    'WGW': [relativedelta(), relativedelta(months=12)],
    RAPI_FOOTBALL_TEAMS[0]: [relativedelta(), relativedelta(months=12)],
}


class Game(ABC):
    def __init__(self, game):
        super().__init__()
        self.game = game

    @abstractmethod
    def away_team_colour(self):
        pass

    @abstractmethod
    def away_team_id(self):
        pass

    @abstractmethod
    def away_team_score(self):
        pass

    def away_team_score_str(self):
        if self.has_started() or self.has_ended():
            score_str = self._hide_scores()
            if score_str is not None:
                return score_str

            if self.has_ended():
                if self.away_team_score() > self.home_team_score():
                    score_prefix = 'W'
                elif self.away_team_score() == self.home_team_score():
                    score_prefix = 'D'
                else:
                    score_prefix = 'L'
            else:
                score_prefix = ''

            score_str = f"{score_prefix}{self.away_team_score()}-{self.home_team_score()}"
        else:
            score_str = self.start_time().strftime('%H:%M')
        return score_str

    @abstractmethod
    def away_team_short_name(self):
        pass

    @abstractmethod
    def away_team_title_symbol(self):
        pass

    @abstractmethod
    def has_ended(self):
        pass

    @abstractmethod
    def date_str(self):
        pass

    @abstractmethod
    def has_started(self):
        pass

    @abstractmethod
    def home_team_colour(self):
        pass

    @abstractmethod
    def home_team_id(self):
        pass

    def home_team_score_str(self):
        if self.has_started() or self.has_ended():
            score_str = self._hide_scores()
            if score_str is not None:
                return score_str

            if self.has_ended():
                if self.home_team_score() > self.away_team_score():
                    score_prefix = 'W'
                elif self.home_team_score() == self.away_team_score():
                    score_prefix = 'D'
                else:
                    score_prefix = 'L'
            else:
                score_prefix = ''

            score_str = f"{score_prefix}{self.home_team_score()}-{self.away_team_score()}"
        else:
            score_str = self.start_time().strftime('%H:%M')
        return score_str

    @abstractmethod
    def home_team_score(self):
        pass

    @abstractmethod
    def home_team_short_name(self):
        pass

    @abstractmethod
    def home_team_title_symbol(self):
        pass

    @abstractmethod
    def icon(self):
        pass

    @abstractmethod
    def id(self):
        pass

    @abstractmethod
    def league_id(self):
        pass

    @abstractmethod
    def league_name(self):
        pass

    @abstractmethod
    def start_time(self):
        pass

    def _hide_scores(self):
        if self.away_team_id() in HIDE_SCORES or self.home_team_id() in HIDE_SCORES:

            # Get the current year
            current_year = datetime.now().year

            # Define the start of the year
            start_of_year = datetime(current_year, 1, 1)

            # Calculate relative dates
            # start date to hide scores
            hide_scores_start = datetime(current_year, 12, 31)
            hide_scores_end = start_of_year

            if self.away_team_id() in HIDE_SCORES:
                hide_scores_start = min(hide_scores_start, start_of_year + HIDE_SCORES[self.away_team_id()][0])
                hide_scores_end = max(hide_scores_start, start_of_year + HIDE_SCORES[self.away_team_id()][1])
            if self.home_team_id() in HIDE_SCORES:
                hide_scores_start = min(hide_scores_start, start_of_year + HIDE_SCORES[self.home_team_id()][0])
                hide_scores_end = max(hide_scores_start, start_of_year + HIDE_SCORES[self.home_team_id()][1])

            hide_scores_start = to_local_tz(hide_scores_start)
            hide_scores_end = to_local_tz(hide_scores_end)

            if hide_scores_start <= self.start_time() < hide_scores_end:
                score_str = '-'
                return score_str
        return None

class GameRAPIFootball(Game):
    RAPI_TEAM_CODES = {
        33: 'MUN',  # Manchester United
        34: 'NEW',  # Newcastle
        35: 'BOU',  # Bournemouth
        36: 'FUL',  # Fulham
        38: 'WAT',  # Watford
        39: 'WOL',  # Wolves
        40: 'LIV',  # Liverpool
        42: 'ARS',  # Arsenal
        43: 'CAR',  # Cardiff City
        44: 'BUR',  # Burnley
        45: 'EVE',  # Everton
        47: 'TOT',  # Tottenham
        48: 'WHU',  # West Ham
        49: 'CHE',  # Chelsea
        50: 'MNC',  # Man City
        51: 'BRI',  # Brighton
        52: 'CRY',  # Crystal Palace
        55: 'BRE',  # Brentford
        56: 'BRC',  # Bristol City
        58: 'MIL',  # Millwall
        59: 'PNE',  # Preston North End
        60: 'WBA',  # West Bromwich Albion
        62: 'SHU',  # Sheffield United
        63: 'LEE',  # Leeds
        64: 'HUL',  # Hull City
        65: 'NOT',  # Nottingham Forest
        66: 'AST',  # Aston Villa
        67: 'BBR',  # Blackburn Rovers
        69: 'DER',  # Derby
        70: 'MID',  # Middlesbrough
        71: 'NOR',  # Norwich
        72: 'QPR',  # Queens Park Rangers
        74: 'SHW',  # Sheffield Wednesday
        75: 'STO',  # Stoke City
        76: 'SWA',  # Swansea City
        746: 'SUN',  # Sunderland
        1338: 'OXF',  # Oxford United
        1346: 'COV',  # Coventry City
        1355: 'POR',  # Portsmouth
        1357: 'PLY',  # Plymouth Argyle
        1359: 'LUT',  # Luton Town
    }
    RAPI_TEAM_COLOURS = {
        33: (218, 2, 14),  # Manchester United
        34: (255, 255, 255),  # Newcastle
        35: (181, 14, 18),  # Bournemouth
        36: (255, 255, 255),  # Fulham
        38: (237, 33, 39),  # Watford
        39: (253, 185, 19),  # Wolves
        40: (208, 0, 39),  # Liverpool
        42: (239, 1, 7),  # Arsenal
        43: (0, 112, 181),  # Cardiff City
        44: (128, 0, 0),  # Burnley
        45: (39, 68, 136),  # Everton
        47: (255, 255, 255),  # Tottenham
        48: (122, 38, 58),  # West Ham
        49: (3, 70, 148),  # Chelsea
        50: (108, 171, 221),  # Man City
        51: (0, 87, 184),  # Brighton
        52: (27, 69, 143),  # Crystal Palace
        55: (210, 0, 0),  # Brentford
        56: (226, 26, 35),  # Bristol City
        58: (0, 25, 74),  # Millwall
        59: (0, 33, 86),  # Preston North End
        60: (6, 0, 103),  # West Bromwich Albion
        62: (236, 34, 39),  # Sheffield United
        63: (255, 255, 255),  # Leeds
        64: (241, 138, 1),  # Hull City
        65: (229, 50, 51),  # Nottingham Forest
        66: (128, 0, 0),  # Aston Villa
        67: (0, 158, 224),  # Blackburn Rovers
        69: (255, 255, 255),  # Derby
        70: (222, 27, 34),  # Middlesbrough
        72: (29, 91, 164),  # Queens Park Rangers
        71: (255, 242, 0),  # Norwich
        74: (14, 0, 247),  # Sheffield Wednesday
        75: (224, 58, 62),  # Stoke City
        76: (255, 255, 255),  # Swansea City
        746: (255, 0, 0),  # Sunderland
        1338: (255, 221, 0),  # Oxford United
        1346: (5, 157, 217),  # Coventry City
        1355: (0, 20, 137),  # Portsmouth
        1357: (20, 135, 62),  # Plymouth Argyle
        1359: (255, 255, 255),  # Luton Town
    }

    def __init__(self, *args):
        super().__init__(*args)
        self.text_colour = (74, 214, 9)

    def away_team_colour(self):
        if self.away_team_id() in self.RAPI_TEAM_COLOURS:
            team_colour = graphics.Color(*self.RAPI_TEAM_COLOURS[self.away_team_id()])
        else:
            team_colour = graphics.Color(*self.text_colour)
        return team_colour

    def away_team_id(self):
        return self.game['teams']['away']['id']

    def away_team_score(self):
        return self.game['goals']['away']

    def away_team_short_name(self):
        if self.away_team_id() in self.RAPI_TEAM_CODES:
            short_name = self.RAPI_TEAM_CODES[self.away_team_id()]
        else:
            short_name = self.game['teams']['away']['name'][:3].upper()
        return short_name

    def away_team_title_symbol(self):
        return 'A'

    def date_str(self):
        today = dt_date.today()
        start_time = self.start_time()
        has_ended = self.has_ended()
        in_progress = self.has_started() and not has_ended
        if in_progress:
            date_str = (self.game['fixture']['status']['short'] + ' ' +
                        str(self.game['fixture']['status']['elapsed']))
        elif has_ended:
            if start_time.date() == today:
                if self.game['score']['extratime']['home'] is not None:
                    date_str = 'AET'
                elif self.game['score']['penalty']['home'] is not None:
                    date_str = 'PEN'
                else:
                    date_str = 'FT'
            else:
                date_str = start_time.strftime('%a')
        else:
            if start_time.date() == today:
                date_str = 'Today'
            else:
                date_str = start_time.strftime('%a')
        return date_str

    def has_ended(self):
        return self.game['fixture']['status']['short'] == 'FT' or self.game['fixture']['status']['short'] == 'AET'

    def has_started(self):
        return self.has_ended() or self.game['fixture']['status']['short'] != 'NS'

    def home_team_colour(self):
        if self.home_team_id() in self.RAPI_TEAM_COLOURS:
            team_colour = graphics.Color(*self.RAPI_TEAM_COLOURS[self.home_team_id()])
        else:
            team_colour = graphics.Color(*self.text_colour)
        return team_colour

    def home_team_id(self):
        return self.game['teams']['home']['id']

    def home_team_score(self):
        return self.game['goals']['home']

    def home_team_short_name(self):
        if self.home_team_id() in self.RAPI_TEAM_CODES:
            short_name = self.RAPI_TEAM_CODES[self.home_team_id()]
        else:
            short_name = self.game['teams']['home']['name'][:3].upper()
        return short_name

    def home_team_title_symbol(self):
        return 'H'

    def icon(self):
        icon_file = 'icons/32/SUNDERLAND.png'
        return icon_file

    def id(self):
        return self.game['fixture']['id']

    def league_id(self):
        return 40

    def league_name(self):
        return 'Championship'

    def start_time(self):
        return datetime.fromtimestamp(self.game['fixture']['timestamp'], tz=LOCAL_TZ)

    def update(self, games_last_update):
        try:
            querystring = {
                'id': self.id(),
            }
            headers = {
                'x-rapidapi-key': f'{os.environ["RPA_API_KEY"]}',
                'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
            }
            url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
            response = requests.request("GET", url, headers=headers, params=querystring)
        except requests.exceptions.ConnectionError as e:
            LOG.error(f'GameRAPIFootball::update - ConnectionError {e}')
            return self, games_last_update

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            LOG.warning(f'GameRAPIFootball::update - response.json() failed to decode'
                        f' {response.request.url}')
            return self, games_last_update

        if 'response' not in data:
            LOG.warning(f'GameRAPIFootball::update - response not in json data'
                        f' {response.request.url}')
            return self, games_last_update

        game = GameRAPIFootball(data['response'][0])
        games_last_update[game.id()] = datetime.now()
        return game, games_last_update


class GameRAPIRugby(Game):

    def __init__(self, *args):
        super().__init__(*args)

    def away_team_colour(self):
        return graphics.Color(*hex_to_rgb(self.game['awayTeam']['teamColors']['primary']))

    def away_team_id(self):
        return self.game['awayTeam']['nameCode']

    def away_team_score(self):
        if 'display' in self.game['awayScore']:
            return self.game['awayScore']['display']
        return '-'

    def away_team_short_name(self):
        return self.game['awayTeam']['nameCode']

    def away_team_title_symbol(self):
        return 'A'

    def date_str(self):
        today = dt_date.today()
        start_time = self.start_time()
        has_ended = self.has_ended()
        in_progress = self.has_started() and not has_ended
        if in_progress:
            date_str = str(int(self.game['time']['played'] / 60))
        elif has_ended:
            if start_time.date() == today:
                # TODO: AET
                date_str = 'FT'
            else:
                date_str = start_time.strftime('%a')
        else:
            if start_time.date() == today:
                date_str = 'Today'
            else:
                date_str = start_time.strftime('%a')
        return date_str

    def has_ended(self):
        return self.game['status']['type'] == 'finished'

    def has_started(self):
        return self.has_ended() or self.game['status']['type'] == 'inprogress'

    def home_team_colour(self):
        return graphics.Color(*hex_to_rgb(self.game['homeTeam']['teamColors']['primary']))

    def home_team_id(self):
        return self.game['homeTeam']['nameCode']

    def home_team_score(self):
        if 'display' in self.game['homeScore']:
            return self.game['homeScore']['display']
        return '-'

    def home_team_short_name(self):
        return self.game['homeTeam']['nameCode']

    def home_team_title_symbol(self):
        return 'H'

    def icon(self):
        icon_file = 'icons/32/WIGAN_WARRIORS_SL.png'
        return icon_file

    def id(self):
        return self.game['id']

    def league_id(self):
        return self.game['tournament']['id']

    def league_name(self):
        return self.game['tournament']['name']

    def start_time(self):
        return datetime.fromtimestamp(self.game['startTimestamp'], tz=LOCAL_TZ)

    def update(self, games_last_update):
        try:
            querystring = {
                'id': self.id(),
            }
            headers = {
                'x-rapidapi-key': f'{os.environ["RPA_API_KEY"]}',
                'x-rapidapi-host': 'rugbyapi2.p.rapidapi.com',
            }
            url = f"https://rugbyapi2.p.rapidapi.com/api/rugby/match/{querystring['id']}"
            response = requests.request("GET", url, headers=headers)
        except requests.exceptions.ConnectionError as e:
            LOG.error(f'GameRAPIRugby::update - ConnectionError {e}')
            return self, games_last_update

        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError:
            LOG.warning(f'GameRAPIRugby::update - response.json() failed to decode'
                        f' {response.request.url}')
            return self, games_last_update

        if 'response' not in data:
            LOG.warning(f'GameRAPIRugby::update - response not in json data'
                        f' {response.request.url}')
            return self, games_last_update

        game = GameRAPIRugby(data['response'])
        games_last_update[game.id()] = datetime.now()
        return game, games_last_update


class GameSGO(Game):

    def __init__(self, *args):
        super().__init__(*args)

    def away_team_colour(self):
        # overrides
        if self.away_team_id() == 'CHICAGO_WHITE_SOX_MLB':
            return graphics.Color(*hex_to_rgb('#FFFFFF'))
        elif self.away_team_id() == 'SAN_FRANCISCO_GIANTS_MLB':
            return graphics.Color(*hex_to_rgb('#FD5A1E'))
        elif self.away_team_id() == 'PITTSBURGH_PIRATES_MLB':
            return graphics.Color(*hex_to_rgb('#FDB827'))
        # default
        return graphics.Color(*hex_to_rgb(self.game['teams']['away']['colors']['primary']))

    def away_team_id(self):
        return self.game['teams']['away']['teamID']

    def away_team_score(self):
        if 'score' in self.game['teams']['away']:
            return self.game['teams']['away']['score']
        return '-'

    def away_team_short_name(self):
        return self.game['teams']['away']['names']['short']

    def away_team_title_symbol(self):
        return '@'

    def date_str(self):
        today = dt_date.today()
        start_time = self.start_time()
        has_ended = self.has_ended()
        in_progress = self.has_started() and not has_ended
        if in_progress or has_ended:
            if start_time.date() == today and 'displayShort' in self.game['status']:
                date_str = self.game['status']['displayShort']
                if date_str == 'F':
                    date_str = 'Final'
            else:
                date_str = start_time.strftime('%a')
        else:
            if start_time.date() == today:
                date_str = 'Today'
            else:
                date_str = start_time.strftime('%a')
        return date_str

    def has_ended(self):
        return self.game['status']['ended']

    def has_started(self):
        return self.game['status']['started']

    def home_team_colour(self):
        # overrides
        if self.home_team_id() == 'CHICAGO_WHITE_SOX_MLB':
            return graphics.Color(*hex_to_rgb('#FFFFFF'))
        elif self.home_team_id() == 'SAN_FRANCISCO_GIANTS_MLB':
            return graphics.Color(*hex_to_rgb('#FD5A1E'))
        elif self.home_team_id() == 'PITTSBURGH_PIRATES_MLB':
            return graphics.Color(*hex_to_rgb('#FDB827'))
        # default
        return graphics.Color(*hex_to_rgb(self.game['teams']['home']['colors']['primary']))

    def home_team_id(self):
        return self.game['teams']['home']['teamID']

    def home_team_score(self):
        if 'score' in self.game['teams']['home']:
            return self.game['teams']['home']['score']
        return '-'

    def home_team_short_name(self):
        return self.game['teams']['home']['names']['short']

    def home_team_title_symbol(self):
        return 'v'

    def icon(self):
        if self.away_team_id() in \
                SGO_MLB_TEAMS + SGO_NHL_TEAMS + SGO_NFL_TEAMS + SGO_MLS_TEAMS:
            icon_file = 'icons/32/' + self.away_team_id() + '.png'
        else:
            icon_file = 'icons/32/' + self.home_team_id() + '.png'

        return icon_file

    def id(self):
        return self.game['eventID']

    def league_id(self):
        return self.game['leagueID']

    def league_name(self):
        return self.game['leagueID']

    def start_time(self):
        return to_local_tz(parse(self.game['status']['startsAt']))

    def update(self, games_last_update):
        try:
            response = requests.get(
                'https://api.sportsgameodds.com/v2/events',
                headers={'X-Api-Key': os.environ['SGO_API_KEY']},
                params={
                    'eventID': self.id(),
                    'oddIDs': 'points-home-game-sp-home',
                })

            if response.status_code == 429:
                LOG.warning(f'GameSGO.update - Rate limits hit {response.status_code} {response.reason}'
                          f' {response.request.url}')
                setup_env()
                return self, games_last_update

            if response.status_code != 200:
                LOG.error(f'GameSGO.update - Response returned code {response.status_code} {response.reason}'
                          f' {response.request.url}')
                return self, games_last_update

            data = response.json()
            if not data['success']:
                LOG.error(f'GameSGO.update - Data["success"] == False')
                return self, games_last_update

            self.game = data['data'][0]
            games_last_update[self.id()] = datetime.now()

        except requests.exceptions.ConnectionError as e:
            LOG.error(f'GameSGO.update - ConnectionError {e}')
            return self, games_last_update

        except Exception as error:
            print(f'GameSGO.update - Error fetching events: {error}')
            return self, games_last_update

        return self, games_last_update

        # # we can update the whole league for the cost of one game
        # games, games_last_update = sgo_get_games_league(self.league_id(), games_last_update)
        # return next((g for g in games if g.id() == self.id()), self), games_last_update


class GracefulKiller:
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True


class RunMatrix(SampleBase):
    def __init__(self, stop_ids, uptown_stop_ids, args):
        super(RunMatrix, self).__init__(args)

        self.stop_ids = stop_ids
        self.uptown_stop_ids = uptown_stop_ids
        self.font = graphics.Font()
        self.font.LoadFont("./fonts/helvR12.bdf")
        self.circle_font = graphics.Font()
        self.circle_font.LoadFont('./fonts/6x10.bdf')
        self.sports_font = graphics.Font()
        self.sports_font.LoadFont('./fonts/5x8.bdf')

        self.text_colour = graphics.Color(74, 214, 9)
        self.text_colour_arriving = graphics.Color(247, 75, 25)

        self.circle_colour_bdfm = graphics.Color(255, 99, 25)
        self.circle_colour_g = graphics.Color(108, 190, 69)
        self.circle_colour_nqrw = graphics.Color(252, 204, 10)

    def draw_game(self, canvas, game: Game):
        LOG.debug(f'RunMatrix.draw_game - drawing game {game}')
        league_name = game.league_name()
        if league_name == 'MLB':
            league_teams = SGO_MLB_TEAMS
        elif league_name == 'NHL':
            league_teams = SGO_NHL_TEAMS
        elif league_name == 'NFL':
            league_teams = SGO_NFL_TEAMS
        elif league_name == 'MLS':
            league_teams = SGO_MLS_TEAMS
        elif league_name in ['Premier League', 'Championship', 'Friendlies Clubs', 'League Cup', 'FA Cup']:
            league_teams = RAPI_FOOTBALL_TEAMS
        elif league_name == 'Super League':
            league_teams = RAPI_RUGBY_TEAMS
        else:
            return canvas

        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        icon_file = game.icon()
        im = Image.open(icon_file)
        im = im.convert('RGB')
        canvas.SetImage(im)

        if game.away_team_id() in league_teams:
            title_symbol = game.away_team_title_symbol()
            title_str = game.home_team_short_name()
            score_str = game.away_team_score_str()
            team_colour = game.home_team_colour()
        else:
            title_symbol = game.home_team_title_symbol()
            title_str = game.away_team_short_name()
            score_str = game.home_team_score_str()
            team_colour = game.away_team_colour()

        date_str = game.date_str()

        if isinstance(game, (GameRAPIFootball, GameRAPIRugby)):
            graphics.DrawText(canvas, self.circle_font, 34, text_y_top, team_colour, title_str)
            graphics.DrawText(canvas, self.circle_font, 56, text_y_top, self.text_colour, title_symbol)
        else:
            graphics.DrawText(canvas, self.circle_font, 34, text_y_top, self.text_colour, title_symbol)
            graphics.DrawText(canvas, self.circle_font, 40, text_y_top, team_colour, title_str)
        graphics.DrawText(canvas, self.sports_font, 34, text_y_middle, self.text_colour, score_str)
        graphics.DrawText(canvas, self.sports_font, 34, text_y_bottom, self.text_colour, date_str)

        return canvas

    def draw_train_row(self,
                       canvas,
                       row_ind,
                       arrival_order,
                       text_colour,
                       circle_colour,
                       route_id,
                       headsign_text,
                       direction,
                       arrival_mins):
        # Top line
        if row_ind == 0:
            circle_y = 8
            text_y = 13
        else:
            # Bottom line
            circle_y = 23
            text_y = 28

        if len(route_id) == 1:
            route_id_offset_width = self.circle_font.CharacterWidth(ord(route_id))
            route_id_offset = int(route_id_offset_width / 2) - 1
        else:
            # this has happened once so far!
            route_id_offset = 0

        graphics.DrawText(canvas, self.font, 1, text_y, text_colour, f'{arrival_order}')
        graphics.DrawText(canvas, self.font, 7, text_y, text_colour, f'.')
        # graphics.DrawCircle(canvas, 16, circle_y, 5, circle_colour)
        self._draw_filled_circle(canvas, 15, circle_y, circle_colour)
        graphics.DrawText(canvas, self.circle_font, 15 - route_id_offset, text_y - 1, graphics.Color(0, 0, 0), route_id)
        # graphics.DrawText(canvas, self.font, 26, text_y, text_colour, headsign_text)
        if direction == 'N':
            graphics.DrawText(canvas, self.circle_font, 24, text_y - 1, text_colour, '↑')
        else:
            graphics.DrawText(canvas, self.circle_font, 24, text_y - 1, text_colour, '↓')
        if isinstance(arrival_mins, int):
            minutes_text = f'{arrival_mins:2d}'
            minutes_width = sum(self.font.CharacterWidth(ord(letter)) for letter in minutes_text)
            graphics.DrawText(canvas, self.font, 45 - minutes_width, text_y, text_colour, minutes_text)
            graphics.DrawText(canvas, self.font, 45, text_y, text_colour, "min")
        else:
            graphics.DrawText(canvas, self.font, 32, text_y, text_colour, arrival_mins)

    def draw_train(self, row_ind, arrival_order, train, stop_id, canvas):
        arrival_mins = mta_arrival_minutes(train, stop_id)
        # arrival_mins = 0
        text_colour = self.text_colour

        # see: https://www.6sqft.com/did-you-know-the-mta-uses-pantone-colors-to-distinguish-train-lines/
        if train.route_id in ['B', 'D', 'F', 'M']:
            circle_colour = self.circle_colour_bdfm
        elif train.route_id in ['G', ]:
            circle_colour = self.circle_colour_g
        else:
            circle_colour = self.circle_colour_nqrw

        # 0 mins is arriving
        if arrival_mins <= 0:
            text_colour = self.text_colour_arriving

        # one minute late just report as arriving
        if arrival_mins == -1:
            arrival_mins = 0

        # more than one minute late report as delay
        if arrival_mins < -1:
            arrival_mins = 'delay'

        if stop_id.endswith('N'):
            direction = 'N'
        else:
            direction = 'S'

        self.draw_train_row(canvas,
                            row_ind=row_ind,
                            arrival_order=arrival_order,
                            text_colour=text_colour,
                            circle_colour=circle_colour,
                            route_id=train.route_id,
                            headsign_text=train.headsign_text,
                            direction=direction,
                            arrival_mins=arrival_mins)

    def draw_train_no_data(self,
                           stop_id,
                           canvas,
                           ):
        LOG.debug(f'RunMatrix.draw_train_no_data - stop_id {stop_id}')

        # Top line
        text_y_top = 13
        text_y_bottom = 28

        stop_name, direction = mta_get_stop_name_and_direction(stop_id)

        graphics.DrawText(canvas, self.font, 1, text_y_top, self.text_colour, f'{stop_name} {direction}')
        if stop_id.startswith('F23'):
            graphics.DrawText(canvas, self.circle_font, 44, text_y_top - 1, self.circle_colour_bdfm, 'F')
            graphics.DrawText(canvas, self.circle_font, 50, text_y_top - 1, self.circle_colour_g, 'G')
        else:
            graphics.DrawText(canvas, self.circle_font, 38, text_y_top - 1, self.circle_colour_nqrw, 'R')
            graphics.DrawText(canvas, self.circle_font, 44, text_y_top - 1, self.circle_colour_nqrw, 'W')
            graphics.DrawText(canvas, self.circle_font, 50, text_y_top - 1, self.circle_colour_nqrw, 'N')
            graphics.DrawText(canvas, self.circle_font, 56, text_y_top - 1, self.circle_colour_bdfm, 'D')

        graphics.DrawText(canvas, self.font, 7, text_y_bottom, self.text_colour, '*no data*')

    def draw_trains_none(self,
                         stop_id,
                         canvas,
                         ):
        LOG.debug(f'RunMatrix.draw_trains_none - stop_id {stop_id}')

        # Top line
        text_y_top = 13
        text_y_bottom = 28

        stop_name, direction = mta_get_stop_name_and_direction(stop_id)

        graphics.DrawText(canvas, self.font, 1, text_y_top, self.text_colour, f'{stop_name} {direction}')
        if stop_id.startswith('F23'):
            graphics.DrawText(canvas, self.circle_font, 44, text_y_top - 1, self.circle_colour_bdfm, 'F')
            graphics.DrawText(canvas, self.circle_font, 50, text_y_top - 1, self.circle_colour_g, 'G')
        else:
            graphics.DrawText(canvas, self.circle_font, 38, text_y_top - 1, self.circle_colour_nqrw, 'R')
            graphics.DrawText(canvas, self.circle_font, 44, text_y_top - 1, self.circle_colour_nqrw, 'W')
            graphics.DrawText(canvas, self.circle_font, 50, text_y_top - 1, self.circle_colour_nqrw, 'N')
            graphics.DrawText(canvas, self.circle_font, 56, text_y_top - 1, self.circle_colour_bdfm, 'D')

        graphics.DrawText(canvas, self.font, 3, text_y_bottom, self.text_colour, '*no trains*')

    def draw_trains(self, trains, stop_id, canvas, display_time):
        LOG.debug(f'RunMatrix.draw_trains - stop_id {stop_id}')

        if trains is None:
            canvas.Clear()
            self.draw_train_no_data(stop_id, canvas)
            canvas = self.matrix.SwapOnVSync(canvas)
            time.sleep(display_time)
        elif len(trains):
            # check we don't have stale data
            now = datetime.now()
            last_update_time = now - timedelta(minutes=60)
            for train in trains:
                if train.underway and train.last_position_update > last_update_time:
                    last_update_time = train.last_position_update
            # if the latest update was more than 15 minutes ago, the data is stale
            if last_update_time < now - timedelta(minutes=15):
                canvas.Clear()
                self.draw_train_no_data(stop_id, canvas)
                canvas = self.matrix.SwapOnVSync(canvas)
                time.sleep(display_time)
            else:
                if len(trains) == 1:
                    canvas.Clear()
                    self.draw_train(0, 1, trains[0], stop_id, canvas)
                    canvas = self.matrix.SwapOnVSync(canvas)
                    time.sleep(display_time)
                else:
                    swap_time = max(display_time / len(trains) - 1, MIN_DISPLAY_TIME)
                    for i in range(1, len(trains)):
                        canvas.Clear()
                        self.draw_train(0, 1, trains[0], stop_id, canvas)
                        self.draw_train(1, i + 1, trains[i], stop_id, canvas)
                        canvas = self.matrix.SwapOnVSync(canvas)
                        time.sleep(swap_time)
        else:
            canvas.Clear()
            self.draw_trains_none(stop_id, canvas)
            canvas = self.matrix.SwapOnVSync(canvas)
            time.sleep(display_time)

        return True, canvas

    def draw_seasonal(self, seasonal, canvas, display_time):
        LOG.debug(f'RunMatrix.draw_seasonal - seasonal {seasonal}')

        # first pick an image
        im_ind = random.randrange(len(seasonal.images))
        image_file = seasonal.images[im_ind]
        image_behaviour = seasonal.image_behaviour[im_ind]

        if image_behaviour == 'scroll_up':
            canvas = self.draw_seasonal_scroll_up(canvas, image_file, display_time,
                                                  pause=0.)
        elif image_behaviour == 'scroll_up_pause':
            canvas = self.draw_seasonal_scroll_up(canvas, image_file, display_time,
                                                  pause=2.)
        elif image_behaviour == 'scroll_up_animate_centre':
            canvas = self.draw_seasonal_scroll_up_animate_centre(canvas, image_file, display_time)

        return canvas

    def draw_seasonal_scroll_up(self, canvas, image_file, display_time,
                                pause=0.):
        im = Image.open(image_file)

        n_rows_display = 32 * 2 + im.height
        sleep_time = display_time / n_rows_display
        n_center_frames = pause / sleep_time
        center_offset = 16 - int(im.height / 2)

        frame_ind = 0
        is_animated = getattr(im, 'is_animated', False)
        if is_animated:
            im.seek(frame_ind)
        im_disp = im.convert('RGB')
        fstart = datetime.now()
        offset_y = 32
        center_counter = 0
        while offset_y > -(im.height + 32):
            canvas.Clear()
            canvas.SetImage(im_disp, offset_x=0, offset_y=offset_y)
            canvas = self.matrix.SwapOnVSync(canvas)

            if is_animated and (datetime.now() - fstart).total_seconds() * 1000 >= im.info['duration']:
                im.seek(frame_ind)
                im_disp = im.convert('RGB')
                frame_ind = (frame_ind + 1) % im.n_frames
                fstart = datetime.now()

            time.sleep(sleep_time)
            if offset_y == center_offset:
                if center_counter < n_center_frames:
                    offset_y += 1
                center_counter += 1

            offset_y -= 1

        return canvas

    def draw_seasonal_scroll_up_animate_centre(self, canvas, image_file, display_time):
        im = Image.open(image_file)
        is_animated = getattr(im, 'is_animated', False)
        if not is_animated:
            warnings.warn(f'{image_file} is not animated')
            return canvas

        n_rows_display = 32 * 2 + im.height
        start_offset = 32
        center_offset = 16 - int(im.height / 2)
        sleep_time = display_time / n_rows_display

        n_rows_to_centre = start_offset - center_offset
        time_to_centre = n_rows_to_centre * sleep_time
        # count back until we've reached the frame to start from
        time_total = 0
        frame_ind = im.n_frames - 1
        while time_total < time_to_centre:
            im.seek(frame_ind)
            time_total += im.info['duration'] / 1000
            frame_ind = (frame_ind - 1) % im.n_frames
        frame_ind = (frame_ind + 1) % im.n_frames

        offset_y = 32
        im.seek(frame_ind)
        im_disp = im.convert('RGB')
        fstart = datetime.now()
        while offset_y > -(im.height + 32):

            # play the animation when centered
            if offset_y == center_offset:
                for frame_ind in range(im.n_frames):
                    canvas.Clear()
                    im.seek(frame_ind)
                    im_disp = im.convert('RGB')
                    fstart = datetime.now()

                    canvas.SetImage(im_disp, offset_x=0, offset_y=offset_y)
                    canvas = self.matrix.SwapOnVSync(canvas)
                    time.sleep(im.info['duration'] / 1000)
            else:
                canvas.Clear()
                canvas.SetImage(im_disp, offset_x=0, offset_y=offset_y)
                canvas = self.matrix.SwapOnVSync(canvas)
                time.sleep(sleep_time)

                if (datetime.now() - fstart).total_seconds() * 1000 >= im.info['duration']:
                    im.seek(frame_ind)
                    im_disp = im.convert('RGB')
                    frame_ind = (frame_ind + 1) % im.n_frames
                    fstart = datetime.now()

            offset_y -= 1

        return canvas

    def draw_weather(self, canvas, w):
        LOG.debug(f'RunMatrix.draw_weather - w {w}')

        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        max_temp = k_to_c(w.temp['temp_max'])
        min_temp = k_to_c(w.temp['temp_min'])
        icon_file = owm_weather_to_icon(w)

        if icon_file is not None:
            im = Image.open(icon_file)
            im = im.convert('RGB')
            canvas.SetImage(im)

        # get forecast time in local (this automatically happens with from timestamp)
        weather_time = datetime.fromtimestamp(w.ref_time)
        if os.name == 'nt':
            head_str = weather_time.strftime('%#I%p').lower()
        else:
            head_str = weather_time.strftime('%-I%p').lower()

        graphics.DrawText(canvas, self.circle_font, 34, text_y_top, self.text_colour, head_str)
        hot_colour = graphics.Color(247, 92, 92)
        graphics.DrawText(canvas, self.circle_font, 34, text_y_middle, hot_colour,
                          '↑')
        graphics.DrawText(canvas, self.circle_font, 40, text_y_middle, self.text_colour,
                          f'{max_temp}c')
        cold_colour = graphics.Color(92, 172, 247)
        graphics.DrawText(canvas, self.circle_font, 34, text_y_bottom, cold_colour,
                          '↓')
        graphics.DrawText(canvas, self.circle_font, 40, text_y_bottom, self.text_colour,
                          f'{min_temp}c')
        return canvas

    def draw_weather_no_data(self, canvas):
        LOG.debug(f'RunMatrix.draw_weather_no_data')

        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        icon_file = 'icons/32/weather-forecast.png'
        im = Image.open(icon_file)
        im = im.convert('RGB')
        canvas.SetImage(im)

        graphics.DrawText(canvas, self.circle_font, 34, text_y_top, self.text_colour, '***')
        hot_colour = graphics.Color(247, 92, 92)
        graphics.DrawText(canvas, self.circle_font, 34, text_y_middle, hot_colour,
                          '↑')
        graphics.DrawText(canvas, self.circle_font, 40, text_y_middle, self.text_colour,
                          f'--c')
        cold_colour = graphics.Color(92, 172, 247)
        graphics.DrawText(canvas, self.circle_font, 34, text_y_bottom, cold_colour,
                          '↓')
        graphics.DrawText(canvas, self.circle_font, 40, text_y_bottom, self.text_colour,
                          f'--c')
        return canvas

    def draw_weather_summary(self, canvas, w_list, title_str):
        LOG.debug(f'RunMatrix.draw_weather_summary - title_str {title_str}')

        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        max_temp = -100
        min_temp = 100
        codes = []
        for w in w_list:
            max_temp = max(max_temp, k_to_c(w.temp['temp_max']))
            min_temp = min(min_temp, k_to_c(w.temp['temp_min']))
            codes.append(w.weather_code)
        best_code = max(set(codes), key=codes.count)

        icon_file = owm_weather_to_icon(next(w for w in w_list if w.weather_code == best_code))
        if icon_file is not None:
            im = Image.open(icon_file)
            canvas.SetImage(im)

        graphics.DrawText(canvas, self.circle_font, 34, text_y_top, self.text_colour, title_str)
        hot_colour = graphics.Color(247, 92, 92)
        graphics.DrawText(canvas, self.circle_font, 34, text_y_middle, hot_colour,
                          '↑')
        graphics.DrawText(canvas, self.circle_font, 40, text_y_middle, self.text_colour,
                          f'{max_temp}c')
        cold_colour = graphics.Color(92, 172, 247)
        graphics.DrawText(canvas, self.circle_font, 34, text_y_bottom, cold_colour,
                          '↓')
        graphics.DrawText(canvas, self.circle_font, 40, text_y_bottom, self.text_colour,
                          f'{min_temp}c')
        return canvas

    def display_clock(self, canvas, display_time=10):
        LOG.debug(f'RunMatrix.display_clock')

        text_y_top = 13
        text_y_bottom = 28
        clock_pos = 2

        w, _ = owm_get_weather()

        start_time = datetime.now()
        show_colon = True
        while (datetime.now() - start_time).total_seconds() < display_time:
            canvas.Clear()

            current_time = datetime.now()

            # draw time
            graphics.DrawText(canvas, self.font, clock_pos, text_y_top, self.text_colour,
                              current_time.strftime('%H'))
            if show_colon:
                graphics.DrawText(canvas, self.font, clock_pos + 14, text_y_top - 1, self.text_colour, ':')
            graphics.DrawText(canvas, self.font, clock_pos + 17, text_y_top, self.text_colour,
                              current_time.strftime('%M'))

            # draw temp
            temp_c = 0
            if w is not None:
                temp_c = k_to_c(w.temp["temp"])
                if temp_c < 0:
                    icon_file = 'icons/32/thermometer_verycold.png'
                elif temp_c < 10:
                    icon_file = 'icons/32/thermometer_cold.png'
                elif temp_c < 20:
                    icon_file = 'icons/32/thermometer_mid.png'
                elif temp_c < 30:
                    icon_file = 'icons/32/thermometer_hot.png'
                else:
                    icon_file = 'icons/32/thermometer_veryhot.png'
            else:
                icon_file = 'icons/32/thermometer_mid.png'

            im = Image.open(icon_file)
            im = im.convert('RGB')
            canvas.SetImage(im, offset_x=clock_pos + 35, offset_y=2)

            if w is not None:
                graphics.DrawText(canvas, self.circle_font, clock_pos + 44, text_y_top - 1, self.text_colour,
                                  f'{temp_c:d}c')
            else:
                graphics.DrawText(canvas, self.circle_font, clock_pos + 44, text_y_top - 1, self.text_colour,
                                  '--c')

            # draw date
            date_str = current_time.strftime('%a ') + f'{current_time.day} ' + current_time.strftime('%b')
            graphics.DrawText(canvas, self.circle_font, clock_pos, text_y_bottom, self.text_colour, date_str)

            canvas = self.matrix.SwapOnVSync(canvas)
            show_colon = not show_colon
            time.sleep(0.5)

        return canvas

    def display_trains(self, canvas, display_time=10, uptown_only=False):
        LOG.debug(f'RunMatrix.display_trains - uptown_only {uptown_only}')

        mta_update_feeds()
        stop_ids = self.stop_ids
        if uptown_only:
            stop_ids = self.uptown_stop_ids
        for stop_id in stop_ids:
            trains = mta_get_next_trains(stop_id=stop_id, max_num_trains=5, max_arrival_mins=25)
            success, canvas = self.draw_trains(trains, stop_id, canvas, display_time)

        return canvas

    def display_seasonal(self, canvas, display_time=10):
        LOG.debug(f'RunMatrix.display_seasonal')

        # should we display at all
        if random.uniform(0., 1.) > 0.2:  # Only display roughly once every 5 times
            return canvas

        now = datetime.now()
        for seasonal in SEASONAL_DATA:
            start_date = seasonal.date - timedelta(days=seasonal.display_days_before)
            end_date = seasonal.date + timedelta(days=seasonal.display_days_after)
            if start_date < now < end_date:
                canvas = self.draw_seasonal(seasonal, canvas, display_time)

        return canvas

    def display_sports(self, canvas, display_time=10):
        LOG.debug(f'RunMatrix.display_sports')

        games = []
        # games.extend(sgo_get_games())
        games.extend(rapi_football_get_games())
        # games.extend(rapi_rugby_get_games())
        if not len(games):
            return canvas
        games = self._sort_games(games)

        game_time = max(5, round(display_time / len(games)))
        for game in games:
            canvas.Clear()
            canvas = self.draw_game(canvas, game)
            canvas = self.matrix.SwapOnVSync(canvas)
            time.sleep(game_time)
        return canvas

    def display_weather(self, canvas, display_time=10):
        LOG.debug(f'RunMatrix.display_weather')

        timestamp = datetime.now().time()
        if timestamp < dt_time(13, 0):  # before 12 show today's forecast
            title_str = 'Day'
            forecasts = owm_forecasts_today()
        elif timestamp < dt_time(19, 0):  # before 7pm show the evening forecast
            title_str = 'Eve'
            forecasts = owm_forecasts_evening()
        else:
            title_str = 'Tom'
            forecasts = owm_forecasts_tomorrow()

        if len(forecasts):
            weather_time = max(round(display_time / (len(forecasts) + 2)), MIN_DISPLAY_TIME)

            canvas.Clear()
            canvas = self.draw_weather_summary(canvas, forecasts, title_str)
            canvas = self.matrix.SwapOnVSync(canvas)
            time.sleep(weather_time * 2)

            for forecast in forecasts:
                canvas.Clear()
                canvas = self.draw_weather(canvas, forecast)
                canvas = self.matrix.SwapOnVSync(canvas)
                time.sleep(weather_time)

        else:
            canvas.Clear()
            canvas = self.draw_weather_no_data(canvas)
            canvas = self.matrix.SwapOnVSync(canvas)
            time.sleep(display_time)

        return canvas

    @staticmethod
    def what_should_we_display():
        return ['sports'], [5]

        now = datetime.now()
        timestamp = now.time()
        weekday = now.weekday()

        # weekdays
        if weekday < 5:
            # morning between 7am and 10am
            if dt_time(7, 0) <= timestamp < dt_time(10, 0):
                return ['trains_uptown', 'clock', 'weather'], [5, 5, 5]
            # day between 10am and 8pm
            if dt_time(10, 0) <= timestamp < dt_time(20, 0):
                return ['trains', 'clock', 'weather'], [5, 10, 5]
            # evening after 8pm til midnight
            if timestamp > dt_time(19, 30):
                return ['clock', 'weather', 'sports', 'seasonal'], [30, 5, MIN_DISPLAY_TIME, 5]

            # off after midnight
            return ['off'], [600]

        # weekends
        else:
            # all day between 9am and midnight
            if timestamp > dt_time(9, 0):
                return ['trains', 'clock', 'weather', 'sports', 'seasonal'], [5, 30, 5, MIN_DISPLAY_TIME, 5]

            # off after midnight
            return ['off'], [600]

    def run(self):

        canvas = self.matrix.CreateFrameCanvas()

        graceful_killer = GracefulKiller()
        while not graceful_killer.kill_now:
            try:
                display_items, display_times = self.what_should_we_display()
                for display_item, display_time in zip(display_items, display_times):
                    # break out early if required
                    if graceful_killer.kill_now:
                        break
                    if display_item == 'trains':
                        canvas = self.display_trains(canvas, display_time=display_time)
                    elif display_item == 'trains_uptown':
                        canvas = self.display_trains(canvas, display_time=display_time, uptown_only=True)
                    elif display_item == 'clock':
                        canvas = self.display_clock(canvas, display_time=display_time)
                    elif display_item == 'weather':
                        canvas = self.display_weather(canvas, display_time=display_time)
                    elif display_item == 'sports':
                        canvas = self.display_sports(canvas, display_time=display_time)
                    elif display_item == 'seasonal':
                        canvas = self.display_seasonal(canvas, display_time=display_time)
                    else:
                        # nothing
                        canvas.Clear()
                        canvas = self.matrix.SwapOnVSync(canvas)
                        time.sleep(display_time)  # check again in 10 mins
            except TypeError as err:
                LOG.error(f'{err=}')
            except Exception as err:
                print(f'Unexpected {err=}, {type(err)=}')
                raise

    @staticmethod
    def _draw_filled_circle(canvas, x, y, color):
        # Draw circle with lines
        graphics.DrawLine(canvas, x - 1, y - 6, x + 1, y - 6, color)
        graphics.DrawLine(canvas, x - 3, y - 5, x + 3, y - 5, color)
        graphics.DrawLine(canvas, x - 4, y - 4, x + 4, y - 4, color)
        graphics.DrawLine(canvas, x - 5, y - 3, x + 5, y - 3, color)
        graphics.DrawLine(canvas, x - 5, y - 2, x + 5, y - 2, color)
        graphics.DrawLine(canvas, x - 6, y - 1, x + 6, y - 1, color)
        graphics.DrawLine(canvas, x - 6, y, x + 6, y, color)
        graphics.DrawLine(canvas, x - 6, y + 1, x + 6, y + 1, color)
        graphics.DrawLine(canvas, x - 5, y + 2, x + 5, y + 2, color)
        graphics.DrawLine(canvas, x - 5, y + 3, x + 5, y + 3, color)
        graphics.DrawLine(canvas, x - 4, y + 4, x + 4, y + 4, color)
        graphics.DrawLine(canvas, x - 3, y + 5, x + 3, y + 5, color)
        graphics.DrawLine(canvas, x - 1, y + 6, x + 1, y + 6, color)

    @staticmethod
    def _sort_games(games: [Game]):
        games = sorted(games, key=lambda g: g.start_time())
        return games


def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def k_to_c(k):
    return round(k - 273.15)


def logger_setup(args):
    loglevel = args.log

    global LOG
    LOG = logging.getLogger('NYCSubwayDisplay')
    numeric_level = getattr(logging, loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % loglevel)

    # logs to the command (which gets captured if we're a service)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s %(levelname)s:%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def mta_arrival_time(train, stop_id):
    if train.location_status == 'STOPPED_AT' and train.location == stop_id:
        return datetime(9999, 1, 1, 0, 0, 0)
    return next((stu.arrival for stu in train.stop_time_updates
                 if stu.stop_id == stop_id), datetime(9999, 1, 1, 0, 0, 0))


def mta_arrival_minutes(train, stop_id):
    t = mta_arrival_time(train, stop_id)
    tdelta = t - NOW
    arrival_mins = round(tdelta.total_seconds() / 60)
    return arrival_mins


def mta_find_next_trains(trains, max_arrival_mins, max_num_trains, stop_id):
    arrival_mins = [mta_arrival_minutes(train, stop_id) for train in trains]
    train_order = sorted(range(len(arrival_mins)), key=lambda k: arrival_mins[k])
    next_trains = [trains[train_order[i]]
                   for i in range(len(train_order))
                   if arrival_mins[train_order[i]] <= max_arrival_mins]
    if len(next_trains) > max_num_trains:
        next_trains = next_trains[:max_num_trains]
    return next_trains


def mta_get_feeds():
    import requests
    global MTA_FEEDS

    if MTA_FEEDS is None:
        try:
            MTA_FEEDS = [
                NYCTFeed("F"),
                NYCTFeed("G"),
                NYCTFeed("R"),
            ]
        except requests.exceptions.ConnectionError as e:
            LOG.error(f'mta_get_feeds - ConnectionError: {e}')
            return None

    return MTA_FEEDS


def mta_get_next_trains(
        max_arrival_mins=25,
        max_num_trains=9,
        stop_id='F23N'
):
    # time from now
    global NOW
    NOW = datetime.now()
    # get all feeds
    feeds = mta_get_feeds()
    if feeds is not None:
        all_trains = []
        for feed in feeds:
            all_trains.extend(feed.filter_trips(headed_for_stop_id=stop_id))
        return mta_find_next_trains(all_trains, max_arrival_mins, max_num_trains, stop_id)
    else:
        return None


def mta_get_stop_name_and_direction(stop_id):
    # stop_id reference here:
    # https://openmobilitydata-data.s3-us-west-1.amazonaws.com/public/feeds/mta/79/20240103/original/stops.txt

    if stop_id.startswith('F23'):
        stop_name = '4 Av'
    elif stop_id.startswith('R33'):
        stop_name = '9 St'
    else:
        stop_name = '?'

    if stop_id.endswith('N'):
        direction = '↑'
    else:
        direction = '↓'

    return stop_name, direction


def mta_update_feeds():
    global MTA_TIMESTAMP
    import requests

    # update all feeds at the interval specified
    if MTA_TIMESTAMP is None or \
            (datetime.now() - MTA_TIMESTAMP).total_seconds() > MTA_REFRESH_RATE:
        MTA_TIMESTAMP = datetime.now()
        feeds = mta_get_feeds()
        if feeds is not None:
            for feed in feeds:
                try:
                    feed.refresh()
                    LOG.info(f'mta_update_feeds - feed updated {feed}')
                except requests.exceptions.ConnectionError as e:
                    LOG.error(f'mta_update_feeds - ConnectionError: {e}')
                except RuntimeError as e:
                    LOG.error(f'mta_update_feeds - RuntimeError: {e}')


def owm_forecasts_evening():
    # evening forecast is between 7pm and midnight
    start_time = datetime.today().replace(hour=19, minute=0, second=0)
    end_time = datetime.today().replace(hour=0, minute=0, second=0) + timedelta(days=1)
    return owm_forecasts_get(start_time, end_time)


def owm_forecasts_get(time_start, time_end):
    # put time in utc
    time_start = to_utc_tz(time_start)
    time_end = to_utc_tz(time_end)

    w, forecast = owm_get_weather()
    forecasts = []
    if forecast is not None:
        for w in forecast.forecast.weathers:
            if time_start.timestamp() <= w.reference_time() <= time_end.timestamp():
                forecasts.append(w)

    return forecasts


def owm_forecasts_today():
    # today's forecasts are between 9am and 7pm
    start_time = datetime.today().replace(hour=9, minute=0, second=0)
    end_time = datetime.today().replace(hour=19, minute=0, second=0)
    return owm_forecasts_get(start_time, end_time)


def owm_forecasts_tomorrow():
    # tomorrow's forecast is between 6am and 7pm tomorrow
    start_time = datetime.today().replace(hour=6, minute=0, second=0) + timedelta(days=1)
    end_time = datetime.today().replace(hour=19, minute=0, second=0) + timedelta(days=1)
    return owm_forecasts_get(start_time, end_time)


def owm_get_weather():
    global OWM_MGR
    global OWM_WEATHER
    global OWM_FORECAST
    global OWN_TIMESTAMP

    if OWM_MGR is None:
        owm = OWM(os.environ['OWM_API_KEY'])
        OWM_MGR = owm.weather_manager()

    # we only get the weather every 0.5 hours
    if OWM_WEATHER is None or OWN_TIMESTAMP is None or \
            (datetime.now() - OWN_TIMESTAMP).total_seconds() > OWM_REFRESH_RATE:
        LOG.debug(f'owm_get_weather - updating weather')
        OWN_TIMESTAMP = datetime.now()
        try:
            observation = OWM_MGR.weather_at_place('New York')
            OWM_WEATHER = observation.weather
            OWM_FORECAST = OWM_MGR.forecast_at_place('New York', '3h')
            LOG.info(f'owm_get_weather - weather and forecast updated')
        except Exception as e:
            LOG.error(f'owm_get_weather - Failed {type(e)} {e}')
            OWM_WEATHER = None
            OWM_FORECAST = None

    return OWM_WEATHER, OWM_FORECAST


def owm_pick_worst_weather(w1, w2):
    order_of_weather_codes = [
        781,  # tornado
        200, 201, 202, 210, 211, 212, 221, 230, 231, 232,  # thunderstorms!
        615, 602, 616, 601, 600, 621, 611, 613, 620, 612, 622,  # snow
        511, 504, 503, 502, 501, 500, 531, 522, 521, 520,  # rain
        312, 301, 311, 301, 310, 300, 314, 321, 313,  # drizzle
        771, 762, 761, 751, 741, 731, 721, 711, 701,  # atmosphere
        804, 803, 802, 801,  # clouds
        800,  # clear
    ]
    if order_of_weather_codes.index(w1.weather_code) < order_of_weather_codes.index(w2.weather_code):
        return w1
    else:
        return w2


def owm_weather_to_icon(weather):
    # see: https://openweathermap.org/weather-conditions
    # icons from: https://github.com/Dhole/weather-pixel-icons

    # sun and moon: ffaf00
    # light cloud: 9ba0b4
    # dark cloud: 5e616c
    # blue moon: 6a88ff

    is_day = weather.weather_icon_name.endswith('d')

    if weather.weather_code in [200, 201, 202, 230, 231, 232]:
        icon_file = 'icons/32/rain_lightning.png'
    elif weather.weather_code in [210, 211, 212, 221]:
        icon_file = 'icons/32/lightning.png'

    elif weather.weather_code in [300, 301, 302, 310, 311, 312]:
        icon_file = 'icons/32/rain0.png'
    elif weather.weather_code in [313, 314, 321]:
        if is_day:
            icon_file = 'icons/32/rain0_sun.png'
        else:
            icon_file = 'icons/32/rain0.png'

    elif weather.weather_code in [500, ]:
        icon_file = 'icons/32/rain0.png'

    elif weather.weather_code in [501, ]:
        icon_file = 'icons/32/rain1.png'

    elif weather.weather_code in [502, ]:
        icon_file = 'icons/32/rain1.png'

    elif weather.weather_code in [503, 504, ]:
        icon_file = 'icons/32/rain2.png'

    elif weather.weather_code in [511, 611]:
        icon_file = 'icons/32/rain_hail.png'

    elif weather.weather_code in [520, ]:
        if is_day:
            icon_file = 'icons/32/rain0_sun.png'
        else:
            icon_file = 'icons/32/rain0_moon.png'

    elif weather.weather_code in [521, ]:
        if is_day:
            icon_file = 'icons/32/rain1_sun.png'
        else:
            icon_file = 'icons/32/rain1_moon.png'

    elif weather.weather_code in [522, 531]:
        if is_day:
            icon_file = 'icons/32/rain2_sun.png'
        else:
            icon_file = 'icons/32/rain2_moon.png'

    elif weather.weather_code in [600, 601, 602, ]:
        icon_file = 'icons/32/snow.png'

    elif weather.weather_code in [612, 613, 620, 621, 622]:
        if is_day:
            icon_file = 'icons/32/snow_sun.png'
        else:
            icon_file = 'icons/32/snow_moon.png'

    elif weather.weather_code in [615, 616, ]:
        icon_file = 'icons/32/rain_snow.png'

    elif weather.weather_code in [701, 711, 721, 731, 741, 751, 761, 762, 771, 781]:
        icon_file = 'icons/32/fog.png'

    elif weather.weather_code in [781]:
        icon_file = 'icons/32/tornado.png'

    elif weather.weather_code in [800]:
        if is_day:
            icon_file = 'icons/32/sun.png'
        else:
            icon_file = 'icons/32/moon.png'
    elif weather.weather_code in [801, 802, ]:
        if is_day:
            icon_file = 'icons/32/cloud_sun.png'
        else:
            icon_file = 'icons/32/cloud_moon.png'

    elif weather.weather_code in [803, ]:
        icon_file = 'icons/32/cloud.png'

    elif weather.weather_code in [804, ]:
        icon_file = 'icons/32/clouds.png'

    else:
        icon_file = 'icons/32/weather-forecast.png'

    return icon_file


def parse_args():
    parser = argparse.ArgumentParser(
        prog='NYCSubwayDisplay',
        description='Displays subway times and more!',
    )

    parser.add_argument("-r", "--led-rows", action="store",
                        help="Display rows. 16 for 16x32, 32 for 32x32. Default: 32", default=32, type=int)
    parser.add_argument("--led-cols", action="store", help="Panel columns. Typically 32 or 64. (Default: 32)",
                        default=32, type=int)
    parser.add_argument("-c", "--led-chain", action="store", help="Daisy-chained boards. Default: 1.", default=1,
                        type=int)
    parser.add_argument("-P", "--led-parallel", action="store",
                        help="For Plus-models or RPi2: parallel chains. 1..3. Default: 1", default=1, type=int)
    parser.add_argument("-p", "--led-pwm-bits", action="store",
                        help="Bits used for PWM. Something between 1..11. Default: 11", default=11, type=int)
    parser.add_argument("-b", "--led-brightness", action="store",
                        help="Sets brightness level. Default: 100. Range: 1..100", default=100, type=int)
    parser.add_argument("-m", "--led-gpio-mapping",
                        help="Hardware Mapping: regular, adafruit-hat, adafruit-hat-pwm",
                        choices=['regular', 'regular-pi1', 'adafruit-hat', 'adafruit-hat-pwm'], type=str)
    parser.add_argument("--led-scan-mode", action="store",
                        help="Progressive or interlaced scan. 0 Progressive, 1 Interlaced (default)", default=1,
                        choices=range(2), type=int)
    parser.add_argument("--led-pwm-lsb-nanoseconds", action="store",
                        help="Base time-unit for the on-time in the lowest significant bit in nanoseconds. Default: 130",
                        default=130, type=int)
    parser.add_argument("--led-show-refresh", action="store_true",
                        help="Shows the current refresh rate of the LED panel")
    parser.add_argument("--led-slowdown-gpio", action="store",
                        help="Slow down writing to GPIO. Range: 0..4. Default: 1", default=1, type=int)
    parser.add_argument("--led-no-hardware-pulse", action="store", help="Don't use hardware pin-pulse generation")
    parser.add_argument("--led-rgb-sequence", action="store",
                        help="Switch if your matrix has led colors swapped. Default: RGB", default="RGB", type=str)
    parser.add_argument("--led-pixel-mapper", action="store", help="Apply pixel mappers. e.g \"Rotate:90\"",
                        default="", type=str)
    parser.add_argument("--led-row-addr-type", action="store",
                        help="0 = default; 1=AB-addressed panels; 2=row direct; 3=ABC-addressed panels; 4 = ABC Shift + DE direct",
                        default=0, type=int, choices=[0, 1, 2, 3, 4])
    parser.add_argument("--led-multiplexing", action="store",
                        help="Multiplexing type: 0=direct; 1=strip; 2=checker; 3=spiral; 4=ZStripe; 5=ZnMirrorZStripe; 6=coreman; 7=Kaler2Scan; 8=ZStripeUneven... (Default: 0)",
                        default=0, type=int)
    parser.add_argument("--led-panel-type", action="store",
                        help="Needed to initialize special panels. Supported: 'FM6126A'", default="", type=str)
    parser.add_argument("--led-no-drop-privs", dest="drop_privileges",
                        help="Don't drop privileges from 'root' after initializing the hardware.",
                        action='store_false')
    parser.add_argument("--led-limit-refresh", action="store", help="Hz. Default: 0", default=0, type=int)
    parser.add_argument('--log',
                        help='Log Level: DEBUG, INFO, WARNING, ERROR, CRITICAL',
                        default='ERROR')
    parser.set_defaults(drop_privileges=True)

    args = parser.parse_args()
    return args


def rapi_football_get_games():
    global RAPI_FOOTBALL_GAMES, RAPI_FOOTBALL_NEXT_REFRESH, RAPI_FOOTBALL_TIMESTAMP, RAPI_FOOTBALL_GAMES_LAST_UPDATE
    RAPI_FOOTBALL_GAMES, RAPI_FOOTBALL_NEXT_REFRESH, RAPI_FOOTBALL_TIMESTAMP, RAPI_FOOTBALL_GAMES_LAST_UPDATE = \
        sports_get_games('RAPI_FOOTBALL', RAPI_FOOTBALL_GAMES, RAPI_FOOTBALL_NEXT_REFRESH, RAPI_FOOTBALL_TIMESTAMP,
                         RAPI_FOOTBALL_GAMES_LAST_UPDATE, RAPI_FOOTBALL_REFRESH_RATE)
    return RAPI_FOOTBALL_GAMES


def rapi_football_get_games_league(league_id, games_last_update):
    LOG.debug(f'rapi_football_get_games_league - league_id {league_id}')

    now = datetime.now()
    today = datetime.fromordinal(dt_date.today().toordinal())
    starts_after = to_utc_tz(today - timedelta(days=1))
    starts_before = to_utc_tz(today + timedelta(days=3))

    # Championship league id = 40
    # sunderland team id = 746
    querystring = {
        'season': RAPI_FOOTBALL_SEASON_ID,
        'team': RAPI_FOOTBALL_TEAMS[0],  # TODO: support multiple teams
        'from': starts_after.strftime('%Y-%m-%d'),
        'to': starts_before.strftime('%Y-%m-%d'),
    }
    headers = {
        'x-rapidapi-key': f'{os.environ["RPA_API_KEY"]}',
        'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
    }
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    try:
        response = requests.request("GET", url, headers=headers, params=querystring)
        data = response.json()
    except requests.exceptions.ConnectionError as e:
        LOG.error(f'rapi_football_get_games_league - ConnectionError {e}')
        return [], games_last_update

    if response.status_code != 200:
        LOG.error(f'rapi_football_get_games_league - Response returned code {response.status_code} {response.reason}')
        return [], games_last_update

    if int(response.headers['x-ratelimit-requests-remaining']) < 25:
        LOG.warning(f'rapi_football_get_games_league - Remaining requests {response.headers["x-ratelimit-requests-remaining"]}')

    games = []
    for game in data['response']:
        game = GameRAPIFootball(game)
        games.append(game)
        games_last_update[game.id()] = now

    LOG.info(f'rapi_football_get_games_league - Updated {league_id} with {len(games)} games')

    return games, games_last_update


def rapi_rugby_get_games():
    global RAPI_RUGBY_GAMES, RAPI_RUGBY_NEXT_REFRESH, RAPI_RUGBY_TIMESTAMP, RAPI_RUGBY_GAMES_LAST_UPDATE
    RAPI_RUGBY_GAMES, RAPI_RUGBY_NEXT_REFRESH, RAPI_RUGBY_TIMESTAMP, RAPI_RUGBY_GAMES_LAST_UPDATE = \
        sports_get_games('RAPI_RUGBY', RAPI_RUGBY_GAMES, RAPI_RUGBY_NEXT_REFRESH, RAPI_RUGBY_TIMESTAMP,
                         RAPI_RUGBY_GAMES_LAST_UPDATE, RAPI_RUGBY_REFRESH_RATE)
    return RAPI_RUGBY_GAMES


def rapi_rugby_get_games_league(league_id, games_last_update):
    LOG.debug(f'rapi_rugby_get_games_league - league_id {league_id}')

    now = datetime.now()
    today = datetime.fromordinal(dt_date.today().toordinal())
    starts_after = to_utc_tz(today - timedelta(days=1))
    starts_before = to_utc_tz(today + timedelta(days=3))

    def iterate_dates(start_date, end_date):
        current_date = start_date
        while current_date <= end_date:
            yield current_date
            current_date += timedelta(days=1)

    # Super league id = 345
    # wigan team id = 4233
    events = []
    for search_date in iterate_dates(starts_after, starts_before):
        querystring = {
            'year': search_date.strftime('%Y'),
            'month': search_date.strftime('%m'),
            'day': search_date.strftime('%d'),
        }
        headers = {
            'x-rapidapi-key': f'{os.environ["RPA_API_KEY"]}',
            'x-rapidapi-host': 'rugbyapi2.p.rapidapi.com',
        }
        url = f"https://rugbyapi2.p.rapidapi.com/api/rugby/matches/{querystring['day']}/{querystring['month']}/{querystring['year']}"
        try:
            response = requests.request("GET", url, headers=headers)
            data = response.json()
        except requests.exceptions.ConnectionError as e:
            LOG.error(f'rapi_rugby_get_games_league - ConnectionError {e}')
            return [], games_last_update
        except requests.exceptions.JSONDecodeError as e:
            LOG.error(f'rapi_rugby_get_games_league - JSONDecodeError {e}')
            return [], games_last_update

        if response.status_code != 200:
            LOG.error(f'rapi_rugby_get_games_league - Response returned code {response.status_code} {response.reason}')
            return [], games_last_update

        for game in data['events']:
            # discard duplicates
            if any(game['id'] == e['id'] for e in events):
                continue

            # keep only games involving our teams
            if game['homeTeam']['nameCode'] in RAPI_RUGBY_TEAMS or game['awayTeam']['nameCode'] in RAPI_RUGBY_TEAMS:
                events.append(game)

    games = []
    for game in events:
        game = GameRAPIRugby(game)
        games.append(game)
        games_last_update[game.id()] = now

    LOG.info(f'rapi_rugby_get_games_league - Updated {league_id} with {len(games)} games')

    return games, games_last_update


def setup_env():
    if 'SGO_API_KEY' in os.environ:
        return

    if 'SGO_API_KEYS' not in os.environ:
        LOG.error(f'setup_env - SGO_API_KEY and SGO_API_KEYS are not found')
        exit(1)

    LOG.info(f'setup_env - selecting SGO_API_KEY')

    sgo_api_keys = os.environ['SGO_API_KEYS'].split(',')

    # Find the first, active, non-limited API key
    for sgo_api_key in sgo_api_keys:
        try:
            response = requests.get(
                f'https://api.sportsgameodds.com/v2/account/usage',
                headers={'X-Api-Key': sgo_api_key}
            )
            data = response.json()
            if not data['data']['isActive']:
                continue

            is_limited = False
            for limit in data['data']['rateLimits'].values():
                if isinstance(limit['max-entities'], int):
                    if limit['current-entities'] == limit['max-entities']:
                        is_limited = True
                        break

            if not is_limited:
                os.environ['SGO_API_KEY'] = sgo_api_key
                break

        except requests.exceptions.ConnectionError as e:
            LOG.error(f'setup_env - ConnectionError {e}')

    if 'SGO_API_KEY' not in os.environ:
        LOG.error(f'setup_env - SGO_API_KEY is not found')
        exit(1)

    LOG.info(f'setup_env - selected SGO_API_KEY=={os.environ["SGO_API_KEY"]}')


def sgo_get_games():
    global SGO_GAMES, SGO_TIMESTAMP, SGO_NEXT_REFRESH, SGO_GAMES_LAST_UPDATE
    SGO_GAMES, SGO_TIMESTAMP, SGO_NEXT_REFRESH, SGO_GAMES_LAST_UPDATE = \
        sports_get_games('SGO', SGO_GAMES, SGO_TIMESTAMP, SGO_NEXT_REFRESH,
                         SGO_GAMES_LAST_UPDATE, SGO_REFRESH_RATE)
    return SGO_GAMES


def sgo_get_games_league(league_id, games_last_update):
    LOG.debug(f'sgo_get_games_league - league_id {league_id}')

    now = datetime.now()
    today = datetime.fromordinal(dt_date.today().toordinal())

    starts_after = to_utc_tz(today - timedelta(days=1))
    if league_id in ['MLB', 'NHL']:
        starts_before = to_utc_tz(today + timedelta(days=2))
    else:
        starts_before = to_utc_tz(today + timedelta(days=2))

    if league_id == 'MLB':
        league_teams = SGO_MLB_TEAMS
    elif league_id == 'NHL':
        league_teams = SGO_NHL_TEAMS
    elif league_id == 'NFL':
        league_teams = SGO_NFL_TEAMS
    elif league_id == 'MLS':
        league_teams = SGO_MLS_TEAMS
    else:
        league_teams = []

    next_cursor = None
    event_data = []
    while True:
        try:
            response = requests.get(
                'https://api.sportsgameodds.com/v2/events',
                headers={'X-Api-Key': os.environ['SGO_API_KEY']},
                params={
                    'leagueID': league_id,
                    'teamID': ','.join(league_teams),
                    'startsAfter': starts_after.strftime("%Y-%m-%d %H:%M:%S"),
                    'startsBefore': starts_before.strftime("%Y-%m-%d %H:%M:%S"),
                    'oddIDs': 'points-home-game-sp-home',
                    'limit': 10,
                    'cursor': next_cursor
                })

            if response.status_code == 429:
                LOG.warning(f'sgo_get_games_league - Rate limits hit {response.status_code} {response.reason}'
                          f' {response.request.url}')
                setup_env()
                return [], games_last_update

            if response.status_code != 200:
                LOG.error(f'sgo_get_games_league - Response returned code {response.status_code} {response.reason}'
                          f' {response.request.url}')
                return [], games_last_update

            data = response.json()
            if not data['success']:
                LOG.error(f'sgo_get_games_league - Data["success"] == False')
                return [], games_last_update

            event_data.extend(data['data'])

            next_cursor = data.get('nextCursor')
            if not next_cursor:
                break

        except requests.exceptions.ConnectionError as e:
            LOG.error(f'sgo_get_games_league - ConnectionError {e}')
            return [], games_last_update

        except Exception as error:
            print(f'Error fetching events: {error}')
            break

    games = []
    for game in event_data:
        if game['teams']['away']['teamID'] in league_teams or \
                game['teams']['home']['teamID'] in league_teams:
            games_last_update[game['eventID']] = now
            games.append(GameSGO(game))

    LOG.info(f'sgo_get_games_league - Updated {league_id} with {len(games)} games')

    return games, games_last_update


def sports_get_games(type, games, timestamp, next_refresh, games_last_update, refresh_rate):
    LOG.debug(f'sports_get_games - type {type}')

    if timestamp is not None:
        games, timestamp, next_refresh, games_last_update = sports_retrieve_from_cache(
            type, games, timestamp, next_refresh, games_last_update
        )

    # update all feeds when requested but not faster than the refresh rate
    now = datetime.now()
    # update un-initialised data so we update on first request
    if next_refresh is None:
        next_refresh = now - timedelta(days=1)

    if now > next_refresh:
        LOG.debug(f'sports_get_games - refreshing feed')

        timestamp = datetime.now()

        games = []
        if type == 'RAPI_FOOTBALL':
            # league_id is ignored, just gets all sunderland games for the RAPI_FOOTBALL_SEASON_ID season
            games_league, games_last_update = rapi_football_get_games_league(RAPI_FOOTBALL_PREMIER_LEAGUE_ID, games_last_update)
            games.extend(games_league)
        elif type == 'RAPI_RUGBY':
            # league_id is ignored just gets all wigan games between the required dates
            games_league, games_last_update = rapi_rugby_get_games_league(RAPI_RUGBY_SUPER_LEAGUE_ID, games_last_update)
            games.extend(games_league)
        elif type == 'SGO':
            games_league, games_last_update = sgo_get_games_league('MLB', games_last_update)
            games.extend(games_league)
            games_league, games_last_update = sgo_get_games_league('NHL', games_last_update)
            games.extend(games_league)
            games_league, games_last_update = sgo_get_games_league('NFL', games_last_update)
            games.extend(games_league)
            games_league, games_last_update = sgo_get_games_league('MLS', games_last_update)
            games.extend(games_league)

        # update the leagues again tomorrow at 10:00
        next_refresh = datetime.combine(dt_date.today() + timedelta(days=1), dt_time(10, 00))

    # update in progress games
    games, games_last_update = sports_update_games(games, games_last_update, refresh_rate)

    # clean up games_last_update
    game_ids = [game.id() for game in games]
    game_ids_to_remove = list(set(games_last_update.keys()) - set(game_ids))
    for game_id in game_ids_to_remove:
        del games_last_update[game_id]

    # save to cache
    sports_save_to_cache(type, games, timestamp, next_refresh, games_last_update)

    return games, timestamp, next_refresh, games_last_update


def sports_retrieve_from_cache(type, games, timestamp, next_refresh, games_last_update):
    LOG.debug(f'sports_retrieve_from_cache - type {type}')

    temp_dir = tempfile.gettempdir()
    cache_file = os.path.join(temp_dir, f'{type}.pickle')
    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as file:
            games, timestamp, next_refresh, games_last_update = pickle.load(file)
        LOG.info(f'sports_retrieve_from_cache - Retrieved {type} with {len(games)} games')
    else:
        LOG.debug(f'sports_retrieve_from_cache - cache hit failed')

    return games, timestamp, next_refresh, games_last_update


def sports_save_to_cache(type, games, timestamp, next_refresh, games_last_update):
    temp_dir = tempfile.gettempdir()
    cache_file = os.path.join(temp_dir, f'{type}.pickle')
    with open(cache_file, 'wb') as file:
        pickle.dump((games, timestamp, next_refresh, games_last_update), file)

    LOG.info(f'sports_save_to_cache - Saved {type} with {len(games)} games')


def sports_update_games(games: [Game], games_last_update, refresh_rate):
    LOG.debug(f'sports_update_games - updating in progress games')

    now = datetime.now()
    for game_ind, game in enumerate(games):
        has_ended = game.has_ended()
        has_started = game.has_started()
        start_time = game.start_time()
        if not has_started and LOCAL_TZ.localize(now) > start_time:
            has_started = True
        in_progress = has_started and not has_ended

        # if we're in progress, update as soon as possible
        if in_progress:
            LOG.debug(f'sports_update_games - {games[game_ind]} in progress')
            next_refresh = games_last_update[game.id()] + timedelta(seconds=refresh_rate)
            if now > next_refresh:
                LOG.debug(f'sports_update_games - {games[game_ind]} updating')
                games[game_ind], games_last_update = game.update(games_last_update)

    return games, games_last_update


def to_utc_tz(date_time):
    if date_time.tzinfo is None:
        date_time = LOCAL_TZ.localize(date_time, is_dst=None)
    date_time = date_time.astimezone(pytz.utc)
    return date_time


def to_local_tz(date_time):
    if date_time.tzinfo is None:
        date_time = pytz.utc.localize(date_time, is_dst=None)
    date_time = date_time.astimezone(LOCAL_TZ)
    return date_time


def main():
    args = parse_args()
    logger_setup(args)

    setup_env()

    led_display_trains = RunMatrix(
        stop_ids=['F23N', 'F23S', 'R33N', 'R33S'],
        uptown_stop_ids=['F23N', 'R33N'],
        args=args,
    )
    led_display_trains.process()

    pass


if __name__ == '__main__':

    # # A query for SGO rate limiting (costs one object)
    # response = requests.get(
    #     f'https://api.sportsgameodds.com/v2/account/usage',
    #     headers={'X-Api-Key': os.environ['SGO_API_KEY']}
    # )
    # data = response.json()
    # pass
    main()

from collections import namedtuple
from datetime import datetime, time as dt_time, date as dt_date, timedelta
from dateutil.parser import parse
import importlib
import os
import pickle
import random
import requests
import tempfile
import time
import signal
import warnings

from PIL import Image
from nyct_gtfs import NYCTFeed
from pyowm import OWM
import pytz

if os.name == 'nt':
    graphics = importlib.import_module('RGBMatrixEmulator', 'graphics')
else:
    from rgbmatrix import graphics

from samplebase import SampleBase

LOCAL_TZ = pytz.timezone("America/New_York")
NOW = datetime.now()

MTA_FEEDS = None
MTA_TIMESTAMP = None
MTA_TRAINS = None
MTA_REFRESH_RATE = 60

OWM_FORECAST = None
OWM_MGR = None
OWM_REFRESH_RATE = 3600 * 0.5
OWN_TIMESTAMP = None
OWM_WEATHER = None

RAPI_GAMES = None
RAPI_GAMES_LAST_UPDATE = {}
RAPI_TIMESTAMP = None
RAPI_NEXT_REFRESH = None
RAPI_REFRESH_RATE = 360

RAPI_TEAMS = [746, ]
RAPI_TEAM_COLOURS = {
    38: (237, 33, 39),  # Watford
    43: (0, 112, 181),  # Cardiff City
    44: (128, 0, 0),  # Burnley
    56: (226, 26, 35),  # Bristol City
    58: (0, 25, 74),  # Millwall
    59: (0, 33, 86),  # Preston North End
    60: (6, 0, 103),  # West Bromwich Albion
    62: (236, 34, 39),  # Sheffield United
    63: (255, 255, 255),  # Leeds
    64: (241, 138, 1),  # Hull City
    67: (0, 158, 224),  # Blackburn Rovers
    69: (255, 255, 255),  # Derby
    70: (222, 27, 34),  # Middlesbrough
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
    18212: (29, 91, 164),  # Queens Park Rangers
}
RAPI_TEAM_CODES = {
    38: 'WAT',  # Watford
    43: 'CAR',  # Cardiff City
    44: 'BUR',  # Burnley
    56: 'BRC',  # Bristol City
    58: 'MIL',  # Millwall
    59: 'PNE',  # Preston North End
    60: 'WBA',  # West Bromwich Albion
    62: 'SHU',  # Sheffield United
    63: 'LEE',  # Leeds
    64: 'HUL',  # Hull City
    67: 'BBR',  # Blackburn Rovers
    69: 'DER',  # Derby
    70: 'MID',  # Middlesbrough
    71: 'NOR',  # Norwich
    74: 'SHW',  # Sheffield Wednesday
    75: 'STO',  # Stoke City
    76: 'SWA',  # Swansea City
    746: 'SUN',  # Sunderland
    1338: 'OXF',  # Oxford United
    1346: 'COV',  # Coventry City
    1355: 'POR',  # Portsmouth
    1357: 'PLY',  # Plymouth Argyle
    1359: 'LUT',  # Luton Town
    18212: 'QPR',  # Queens Park Rangers
}

Seasonal = namedtuple('Seasonal', ('name', 'start_date', 'end_date', 'images', 'image_behaviour'))
SEASONAL_DATA = [
    Seasonal(
        name='halloween',
        start_date=datetime(year=NOW.year, month=10, day=20),
        end_date=datetime(year=NOW.year, month=11, day=1),
        images=['images/halloween.png', 'images/halloween_anim.gif'],
        image_behaviour=['scroll_up', 'scroll_up_animation']
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


class GracefulKiller:
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True


class RunMatrix(SampleBase):
    def __init__(self, stop_ids, uptown_stop_ids, *args, **kwargs):
        super(RunMatrix, self).__init__(*args, **kwargs)

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

    def draw_game(self, canvas, game):
        if 'fixture' in game:
            canvas = self.draw_game_rapi(canvas, game)
        else:
            canvas = self.draw_game_sgo(canvas, game)

        return canvas

    def draw_game_sgo(self, canvas, game):
        league_id = game['leagueID']
        if league_id == 'MLB':
            league_teams = SGO_MLB_TEAMS
        elif league_id == 'NHL':
            league_teams = SGO_NHL_TEAMS
        elif league_id == 'NFL':
            league_teams = SGO_NFL_TEAMS
        elif league_id == 'MLS':
            league_teams = SGO_MLS_TEAMS
        else:
            return canvas

        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        icon_file = sgo_get_game_icon(game)
        im = Image.open(icon_file)
        canvas.SetImage(im)

        start_time = to_local_tz(parse(game['status']['startsAt']))

        has_started = game['status']['started']
        has_ended = game['status']['ended']
        in_progress = has_started and not has_ended
        score_str = start_time.strftime('%H:%M')
        if game['teams']['away']['teamID'] in league_teams:
            title_symbol = '@'
            title_str = game['teams']['home']['names']['short']
            if has_ended:
                if game['teams']['away']['score'] > game['teams']['home']['score']:
                    score_prefix = 'W'
                elif game['teams']['away']['score'] == game['teams']['home']['score']:
                    score_prefix = 'D'
                else:
                    score_prefix = 'L'
            else:
                score_prefix = ''
            team_colour = graphics.Color(*hex_to_rgb(game['teams']['home']['colors']['primary']))

            if has_started or has_ended:
                score_str = f"{score_prefix}{game['teams']['away']['score']}-{game['teams']['home']['score']}"

        else:
            title_symbol = 'v'
            title_str = game['teams']['away']['names']['short']
            if has_ended:
                if game['teams']['home']['score'] > game['teams']['away']['score']:
                    score_prefix = 'W'
                elif game['teams']['home']['score'] == game['teams']['away']['score']:
                    score_prefix = 'D'
                else:
                    score_prefix = 'L'
            else:
                score_prefix = ''
            team_colour = graphics.Color(*hex_to_rgb(game['teams']['away']['colors']['primary']))

            if has_started or has_ended:
                score_str = f"{score_prefix}{game['teams']['home']['score']}-{game['teams']['away']['score']}"

        today = dt_date.today()
        if in_progress or has_ended:
            if start_time.date() == today:
                date_str = game['status']['displayShort']
                if date_str == 'F':
                    date_str = 'Final'
            else:
                date_str = start_time.strftime('%a')
        else:
            if start_time.date() == today:
                date_str = 'Today'
            else:
                date_str = start_time.strftime('%a')

        graphics.DrawText(canvas, self.circle_font, 34, text_y_top, self.text_colour, title_symbol)
        graphics.DrawText(canvas, self.circle_font, 40, text_y_top, team_colour, title_str)
        graphics.DrawText(canvas, self.sports_font, 34, text_y_middle, self.text_colour, score_str)
        graphics.DrawText(canvas, self.sports_font, 34, text_y_bottom, self.text_colour, date_str)

        return canvas

    def draw_game_rapi(self, canvas, game):

        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        icon_file = rapi_get_game_icon(game)
        im = Image.open(icon_file)
        im = im.convert('RGB')
        canvas.SetImage(im)

        start_time = datetime.fromtimestamp(game['fixture']['timestamp'])

        has_ended = game['fixture']['status']['short'] == 'FT'
        has_started = has_ended or game['fixture']['status']['short'] != 'NS'
        in_progress = has_started and not has_ended
        score_str = start_time.strftime('%H:%M')
        if game['teams']['away']['id'] in RAPI_TEAMS:
            title_symbol = 'A'
            if game['teams']['home']['id'] in RAPI_TEAM_CODES:
                title_str = RAPI_TEAM_CODES[game['teams']['home']['id']]
            else:
                title_str = game['teams']['home']['name'][:3].upper()
            if has_ended:
                if game['goals']['away'] > game['goals']['home']:
                    score_prefix = 'W'
                elif game['goals']['away'] == game['goals']['home']:
                    score_prefix = 'D'
                else:
                    score_prefix = 'L'
            else:
                score_prefix = ''
            if game['teams']['home']['id'] in RAPI_TEAM_COLOURS:
                team_colour = graphics.Color(*RAPI_TEAM_COLOURS[game['teams']['home']['id']])
            else:
                team_colour = self.text_colour

            if has_started or has_ended:
                score_str = f"{score_prefix}{game['goals']['away']}-{game['goals']['home']}"
        else:
            title_symbol = 'H'
            if game['teams']['away']['id'] in RAPI_TEAM_CODES:
                title_str = RAPI_TEAM_CODES[game['teams']['away']['id']]
            else:
                title_str = game['teams']['away']['name'][:3].upper()
            if has_ended:
                if game['goals']['home'] > game['goals']['away']:
                    score_prefix = 'W'
                elif game['goals']['home'] == game['goals']['away']:
                    score_prefix = 'D'
                else:
                    score_prefix = 'L'
            else:
                score_prefix = ''
            if game['teams']['away']['id'] in RAPI_TEAM_COLOURS:
                team_colour = graphics.Color(*RAPI_TEAM_COLOURS[game['teams']['away']['id']])
            else:
                team_colour = self.text_colour

            if has_started or has_ended:
                score_str = f"{score_prefix}{game['goals']['home']}-{game['goals']['away']}"

        today = dt_date.today()
        if in_progress:
            date_str = game['fixture']['status']['short'] + ' ' + str(game['fixture']['status']['elapsed'])
        elif has_ended:
            if start_time.date() == today:
                if game['score']['extratime']['home'] is not None:
                    date_str = 'AET'
                elif game['score']['penalty']['home'] is not None:
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

        graphics.DrawText(canvas, self.circle_font, 34, text_y_top, team_colour, title_str)
        graphics.DrawText(canvas, self.circle_font, 56, text_y_top, self.text_colour, title_symbol)
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

        route_id_offset_width = self.circle_font.CharacterWidth(ord(route_id))
        route_id_offset = int(route_id_offset_width / 2) - 1

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
                self.draw_train_no_data(stop_id, canvas)
            else:
                if len(trains) == 1:
                    canvas.Clear()
                    self.draw_train(0, 1, trains[0], stop_id, canvas)
                    canvas = self.matrix.SwapOnVSync(canvas)
                    time.sleep(display_time)
                else:
                    swap_time = max(display_time / len(trains)-1, 2)
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

        # first pick an image
        im_ind = random.randrange(len(seasonal.images))
        image_file = seasonal.images[im_ind]
        image_behaviour = seasonal.image_behaviour[im_ind]

        if image_behaviour == 'scroll_up':
            canvas = self.draw_seasonal_scroll_up(canvas, image_file, display_time)
        elif image_behaviour == 'scroll_up_animation':
            canvas = self.draw_seasonal_scroll_up_animation(canvas, image_file, display_time)

        return canvas

    def draw_seasonal_scroll_up(self, canvas, image_file, display_time):
        im = Image.open(image_file)
        im = im.convert('RGB')

        n_rows_display = 32*2 + im.height
        sleep_time = display_time / n_rows_display

        offset_y = 32
        while offset_y > -(im.height+32):
            canvas.Clear()
            canvas.SetImage(im, offset_x=0, offset_y=offset_y)
            canvas = self.matrix.SwapOnVSync(canvas)
            time.sleep(sleep_time)
            offset_y -= 1

        return canvas

    def draw_seasonal_scroll_up_animation(self, canvas, image_file, display_time):
        im = Image.open(image_file)

        n_rows_display = 32*2 + im.height
        sleep_time = display_time / n_rows_display
        center_offset = int(im.height / 2) - 16

        if im.is_animated:
            im.seek(0)
        im_disp = im.convert('RGB')

        start_time = datetime.now()
        offset_y = 32
        while offset_y > -(im.height+32):

            # play the animation when centered
            if im.is_animated and offset_y == -center_offset:
                for frame_ind in range(im.n_frames):
                    canvas.Clear()
                    im.seek(frame_ind)
                    im_disp = im.convert('RGB')
                    canvas.SetImage(im_disp, offset_x=0, offset_y=offset_y)

                    canvas = self.matrix.SwapOnVSync(canvas)
                    time.sleep(im.info['duration'] / 1000)
            else:
                canvas.Clear()
                canvas.SetImage(im_disp, offset_x=0, offset_y=offset_y)
                canvas = self.matrix.SwapOnVSync(canvas)
                time.sleep(sleep_time)
            offset_y -= 1

        return canvas

    def draw_weather(self, canvas, w):
        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        max_temp = k_to_c(w.temp['temp_max'])
        min_temp = k_to_c(w.temp['temp_min'])
        icon_file = owm_weather_to_icon(w)

        if icon_file is not None:
            im = Image.open(icon_file)
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
        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        icon_file = 'icons/32/weather-forecast.png'
        im = Image.open(icon_file)
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
        text_y_top = 13
        text_y_bottom = 28
        clock_pos = 1

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

            im = Image.open(icon_file)
            canvas.SetImage(im, offset_x=clock_pos + 35, offset_y=2)

            if w is not None:
                graphics.DrawText(canvas, self.circle_font, clock_pos + 44, text_y_top - 1, self.text_colour,
                                  f'{temp_c:d}c')
            else:
                graphics.DrawText(canvas, self.circle_font, clock_pos + 44, text_y_top - 1, self.text_colour,
                                  '--c')

            # draw date
            date_str = current_time.strftime('%a ') + f'{current_time.day} ' + current_time.strftime('%b')
            graphics.DrawText(canvas, self.circle_font, clock_pos + 1, text_y_bottom, self.text_colour, date_str)

            canvas = self.matrix.SwapOnVSync(canvas)
            show_colon = not show_colon
            time.sleep(0.5)

        return canvas

    def display_trains(self, canvas, display_time=10, uptown_only=False):
        mta_update_feeds()
        stop_ids = self.stop_ids
        if uptown_only:
            stop_ids = self.uptown_stop_ids
        for stop_id in stop_ids:
            trains = mta_get_next_trains(stop_id=stop_id, num_trains=4)
            success, canvas = self.draw_trains(trains, stop_id, canvas, display_time)

        return canvas

    def display_seasonal(self, canvas, display_time=10):

        # should we display at all
        if random.uniform(0., 1.) > 1.:  # TODO: set this to limit the frequency of display
            return canvas

        now = datetime.now()
        for seasonal in SEASONAL_DATA:
            if seasonal.start_date < now < seasonal.end_date:
                canvas = self.draw_seasonal(seasonal, canvas, display_time)

        return canvas

    def display_sports(self, canvas, display_time=10):
        games = []
        games.extend(sgo_get_games())
        games.extend(rapi_get_games())
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
            weather_time = max(3, round(display_time / (len(forecasts) + 2)))

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
        return ['seasonal'], 5

        now = datetime.now()
        timestamp = now.time()
        weekday = now.weekday()

        # weekdays
        if weekday < 5:
            # morning between 7am and 10am
            if dt_time(7, 0) <= timestamp < dt_time(10, 0):
                return ['trains_uptown', 'clock', 'weather'], 5
            # day between 10am and 8pm
            if dt_time(10, 0) <= timestamp < dt_time(20, 0):
                return ['trains', 'clock', 'weather'], 5
            # evening after 8pm til midnight
            if timestamp > dt_time(19, 30):
                return ['clock', 'weather', 'sports'], 5

            # off after midnight
            return ['off'], 600

        # weekends
        else:
            # all day between 9am and midnight
            if timestamp > dt_time(9, 0):
                return ['trains', 'clock', 'weather', 'sports'], 10

            # off after midnight
            return ['off'], 600

    def run(self):
        canvas = self.matrix.CreateFrameCanvas()

        graceful_killer = GracefulKiller()
        while not graceful_killer.kill_now:
            display_items, display_time = self.what_should_we_display()
            for display_item in display_items:
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

        # # Draw circle with lines
        # graphics.DrawLine(canvas, x - 2, y - 5, x + 2, y - 5, color)
        # graphics.DrawLine(canvas, x - 3, y - 4, x + 3, y - 4, color)
        # graphics.DrawLine(canvas, x - 4, y - 3, x + 4, y - 3, color)
        # graphics.DrawLine(canvas, x - 5, y - 2, x + 5, y - 2, color)
        # graphics.DrawLine(canvas, x - 5, y - 1, x + 5, y - 1, color)
        # graphics.DrawLine(canvas, x - 5, y, x + 5, y, color)
        # graphics.DrawLine(canvas, x - 5, y + 1, x + 5, y + 1, color)
        # graphics.DrawLine(canvas, x - 5, y + 2, x + 5, y + 2, color)
        # graphics.DrawLine(canvas, x - 4, y + 3, x + 4, y + 3, color)
        # graphics.DrawLine(canvas, x - 3, y + 4, x + 3, y + 4, color)
        # graphics.DrawLine(canvas, x - 2, y + 5, x + 2, y + 5, color)

    @staticmethod
    def _sort_games(games):

        def start_time(game):
            if 'fixture' in game:
                start_t = to_local_tz(datetime.fromtimestamp(game['fixture']['timestamp']))
            else:
                start_t = to_local_tz(parse(game['status']['startsAt']))
            return start_t

        games = sorted(games, key=start_time)

        return games


def hex_to_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def k_to_c(k):
    return round(k - 273.15)


def mta_arrival_time(train, stop_id):
    if train.location_status == 'STOPPED_AT' and train.location == stop_id:
        return datetime(9999, 1, 1, 0, 0, 0)
    return next((stu.arrival for stu in train.stop_time_updates
                 if stu.stop_id == stop_id), datetime(9999, 1, 1, 0, 0, 0))


def mta_arrival_minutes(train, stop_id):
    t = mta_arrival_time(train, stop_id)
    tdelta = t - NOW
    arrival_mins = int(tdelta.total_seconds() / 60)
    return arrival_mins


def mta_find_next_trains(trains, num_trains, stop_id):
    arrival_times = [mta_arrival_time(train, stop_id) for train in trains]
    train_order = sorted(range(len(arrival_times)), key=lambda k: arrival_times[k])
    return [trains[train_order[i]] for i in range(num_trains) if len(train_order) > i]


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
            warnings.warn(f'ConnectionError: {e}')
            return None

    return MTA_FEEDS


def mta_get_next_trains(
        num_trains=2,
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
        return mta_find_next_trains(all_trains, num_trains, stop_id)
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
                except requests.exceptions.ConnectionError as e:
                    warnings.warn(f'ConnectionError: {e}')
                    pass


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
    # if w is None:
    #     return None, None, 'icons/32/weather-forecast-sign-16552.png'
    #
    # max_temp = k_to_c(w.temp['temp_max'])
    # min_temp = k_to_c(w.temp['temp_min'])
    # icon_weather = w

    forecasts = []
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
    # tomorrow's forecast is between 7am and 7pm tomorrow
    start_time = datetime.today().replace(hour=7, minute=0, second=0) + timedelta(days=1)
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
    if OWN_TIMESTAMP is None or \
            (datetime.now() - OWN_TIMESTAMP).total_seconds() > OWM_REFRESH_RATE:
        OWN_TIMESTAMP = datetime.now()
        try:
            observation = OWM_MGR.weather_at_place('New York')
            OWM_WEATHER = observation.weather
            OWM_FORECAST = OWM_MGR.forecast_at_place('New York', '3h')
        except Exception as e:
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


def rapi_get_game_icon(game):
    icon_file = 'icons/32/SUNDERLAND.png'
    return icon_file


def rapi_get_games():
    global RAPI_GAMES, RAPI_NEXT_REFRESH, RAPI_TIMESTAMP

    if RAPI_TIMESTAMP is None:
        rapi_retrieve_from_cache()

    # update all feeds when requested but not faster than the refresh rate
    now = datetime.now()
    # update un-initialised data so we update on first request
    if RAPI_NEXT_REFRESH is None:
        RAPI_NEXT_REFRESH = now - timedelta(days=1)

    if now > RAPI_NEXT_REFRESH:
        RAPI_TIMESTAMP = datetime.now()

        RAPI_GAMES = []
        RAPI_GAMES.extend(rapi_get_games_league(40))

        # update the leagues again tomorrow
        today = datetime.fromordinal(dt_date.today().toordinal())
        RAPI_NEXT_REFRESH = today + timedelta(days=1)

    # update in progress games
    rapi_update_games(RAPI_GAMES)

    # save to cache
    rapi_save_to_cache()

    return RAPI_GAMES


def rapi_get_games_league(league_id):
    global RAPI_GAMES_LAST_UPDATE

    now = datetime.now()
    today = datetime.fromordinal(dt_date.today().toordinal())
    starts_after = to_utc_tz(today - timedelta(days=1))
    starts_before = to_utc_tz(today + timedelta(days=3))

    # Championship league id = 40
    # sunderland team id = 746
    querystring = {
        # 'league': '40',
        'season': '2024',
        'team': '746',
        'from': starts_after.strftime('%Y-%m-%d'),
        'to': starts_before.strftime('%Y-%m-%d'),
    }
    headers = {
        'x-rapidapi-key': f'{os.environ["RPA_API_KEY"]}',
        'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
    }
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    response = requests.request("GET", url, headers=headers, params=querystring)
    data = response.json()

    games = []
    for game in data['response']:
        games.append(game)
        RAPI_GAMES_LAST_UPDATE[game['fixture']['id']] = now

    return games


def rapi_retrieve_from_cache():
    global RAPI_GAMES, RAPI_TIMESTAMP, RAPI_NEXT_REFRESH, RAPI_GAMES_LAST_UPDATE

    temp_dir = tempfile.gettempdir()
    cache_file = os.path.join(temp_dir, 'rapi.pickle')
    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as file:
            RAPI_GAMES, RAPI_TIMESTAMP, RAPI_NEXT_REFRESH, RAPI_GAMES_LAST_UPDATE = pickle.load(file)

    return


def rapi_save_to_cache():
    temp_dir = tempfile.gettempdir()
    cache_file = os.path.join(temp_dir, 'rapi.pickle')
    with open(cache_file, 'wb') as file:
        pickle.dump((RAPI_GAMES, RAPI_TIMESTAMP, RAPI_NEXT_REFRESH, RAPI_GAMES_LAST_UPDATE), file)


def rapi_update_games(games):
    global RAPI_GAMES_LAST_UPDATE

    now = datetime.now()
    for game_ind, game in enumerate(games):
        has_ended = game['fixture']['status']['short'] == 'FT'
        has_started = has_ended or game['fixture']['status']['short'] != 'NS'
        start_time = to_local_tz(parse(game['fixture']['date']))
        if not has_started and LOCAL_TZ.localize(now) > start_time:
            has_started = True
        in_progress = has_started and not has_ended

        # if we're in progress, update as soon as possible
        if in_progress:
            next_refresh = RAPI_GAMES_LAST_UPDATE[game['fixture']['id']] + timedelta(seconds=RAPI_REFRESH_RATE)
            if now > next_refresh:
                games[game_ind] = rapi_update_game(game)
                RAPI_GAMES_LAST_UPDATE[game['fixture']['id']] = now


def rapi_update_game(game):
    querystring = {
        'id': game['fixture']['id'],
    }
    headers = {
        'x-rapidapi-key': f'{os.environ["RPA_API_KEY"]}',
        'x-rapidapi-host': 'api-football-v1.p.rapidapi.com',
    }
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    response = requests.request("GET", url, headers=headers, params=querystring)
    data = response.json()

    game = data['response'][0]
    return game


def sgo_get_game_icon(game):
    if game['teams']['away']['teamID'] in \
            SGO_MLB_TEAMS + SGO_NHL_TEAMS + SGO_NFL_TEAMS + SGO_MLS_TEAMS:
        icon_file = 'icons/32/' + game['teams']['away']['teamID'] + '.png'
    else:
        icon_file = 'icons/32/' + game['teams']['home']['teamID'] + '.png'

    return icon_file


def sgo_get_games():
    global SGO_GAMES, SGO_TIMESTAMP, SGO_NEXT_REFRESH

    if SGO_TIMESTAMP is None:
        sgo_retrieve_from_cache()

    now = datetime.now()

    # update un-initalised data so we update on first request
    if SGO_NEXT_REFRESH is None:
        SGO_NEXT_REFRESH = now - timedelta(days=1)

    # update all feeds when requested but not faster than the refresh rate
    # update
    if now > SGO_NEXT_REFRESH:
        SGO_TIMESTAMP = datetime.now()

        SGO_GAMES = []
        SGO_GAMES.extend(sgo_get_games_league('MLB'))
        SGO_GAMES.extend(sgo_get_games_league('NHL'))
        SGO_GAMES.extend(sgo_get_games_league('NFL'))
        SGO_GAMES.extend(sgo_get_games_league('MLS'))

        # update the leagues again tomorrow
        today = datetime.fromordinal(dt_date.today().toordinal())
        SGO_NEXT_REFRESH = today + timedelta(days=1)

    # now update games in progress
    sgo_update_games(SGO_GAMES)

    # save to cache
    sgo_save_to_cache()

    return SGO_GAMES


def sgo_get_games_league(league_id):
    global SGO_GAMES_LAST_UPDATE

    now = datetime.now()
    today = datetime.fromordinal(dt_date.today().toordinal())

    starts_after = to_utc_tz(today - timedelta(days=1))
    if league_id in ['MLB', 'NHL']:
        starts_before = to_utc_tz(today + timedelta(days=2))
    else:
        starts_before = to_utc_tz(today + timedelta(days=2))

    response = requests.get(
        f'https://api.sportsgameodds.com/v1/events?leagueID={league_id}&'
        f'startsAfter={starts_after.strftime("%Y-%m-%d %H:%M:%S")}&'
        f'startsBefore={starts_before.strftime("%Y-%m-%d %H:%M:%S")}&'
        f'oddIDs=points-home-game-sp-home',
        headers={'X-Api-Key': os.environ['SGO_API_KEY']}
    )
    data = response.json()
    if not data['success']:
        return []

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

    games = []
    for game in data['data']:
        if game['teams']['away']['teamID'] in league_teams or \
                game['teams']['home']['teamID'] in league_teams:
            SGO_GAMES_LAST_UPDATE[game['eventID']] = now
            games.append(game)

    return games


def sgo_retrieve_from_cache():
    global SGO_GAMES, SGO_TIMESTAMP, SGO_NEXT_REFRESH, SGO_GAMES_LAST_UPDATE

    temp_dir = tempfile.gettempdir()
    cache_file = os.path.join(temp_dir, 'sgo.pickle')
    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as file:
            SGO_GAMES, SGO_TIMESTAMP, SGO_NEXT_REFRESH, SGO_GAMES_LAST_UPDATE = pickle.load(file)

    return


def sgo_save_to_cache():
    temp_dir = tempfile.gettempdir()
    cache_file = os.path.join(temp_dir, 'sgo.pickle')
    with open(cache_file, 'wb') as file:
        pickle.dump((SGO_GAMES, SGO_TIMESTAMP, SGO_NEXT_REFRESH, SGO_GAMES_LAST_UPDATE), file)


def sgo_update_games(games):
    global SGO_GAMES_LAST_UPDATE

    now = datetime.now()
    for game_ind, game in enumerate(games):
        has_started = game['status']['started']
        start_time = to_local_tz(parse(game['status']['startsAt']))
        if not has_started and LOCAL_TZ.localize(now) > start_time:
            has_started = True
        has_ended = game['status']['ended']
        in_progress = has_started and not has_ended

        # if we're in progress, update as soon as possible
        if in_progress:
            next_refresh = SGO_GAMES_LAST_UPDATE[game['eventID']] + timedelta(seconds=SGO_REFRESH_RATE)
            if now > next_refresh:
                games[game_ind] = sgo_update_game(game)
                SGO_GAMES_LAST_UPDATE[game['eventID']] = now


def sgo_update_game(game):
    response = requests.get(
        f'https://api.sportsgameodds.com/v1/events?eventID={game["eventID"]}&'
        f'oddIDs=points-home-game-sp-home',
        headers={'X-Api-Key': os.environ['SGO_API_KEY']}
    )
    data = response.json()
    game = data['data'][0]
    return game


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
    led_display_trains = RunMatrix(['F23N', 'F23S', 'R33N', 'R23S'], ['F23N', 'R33N'])
    led_display_trains.process()

    pass


if __name__ == '__main__':
    # A query for SGO rate limiting (costs one object)
    # response = requests.get(
    #     f'https://api.sportsgameodds.com/v1/account/usage',
    #     headers={'X-Api-Key': os.environ['SGO_API_KEY']}
    # )
    # data = response.json()

    main()

    # script is here:
    # /home/pi/run-matrix.sh
    # configure brightness and other matrix options in here
    #
    # Contents:
    # #!/bin/bash
    #
    # # wait to see if we're online
    # for i in {1..50}; do ping -c1 www.google.com &> /dev/null && break; done
    #
    # # add ssh credentials
    # eval "$(ssh-agent -s)"
    # ssh-add ${HOME}/.ssh/id_github
    #
    # # get latest changes
    # cd ${HOME}/src/NYCSubwayDisplay/
    # git pull
    #
    # # run
    # export PYTHONPATH=${PYTHONPATH}:${HOME}/src/rpi-rgb-led-matrix/bindings/python
    # export OWM_API_KEY=<Key from https://home.openweathermap.org/api_keys>
    # export SGO_API_KEY=<Key from https://sportsgameodds.com/>
    # export RAPI_API_KEY=<Key from https://rapidapi.com/>
    # source ${HOME}/venv/NYCSubwayDisplay/bin/activate
    # sudo --preserve-env=PYTHONPATH,OWM_API_KEY,SGO_API_KEY,RAPI_API_KEY /home/pi/venv/NYCSubwayDisplay/bin/python main.py --led-gpio-mapping=adafruit-hat-pwm --led-rows=32 --led-cols=64 --led-rgb-sequence=RBG --led-brightness=40 --led-slowdown-gpio=1  --led-no-drop-privs

    # systemd setup to auto-run follows this:
    # https://www.dexterindustries.com/howto/run-a-program-on-your-raspberry-pi-at-startup/
    #
    # /lib/systemd/system/matrix.service
    #
    # Contents:
    # [Unit]
    # Description=LED Matrix Runner
    # Wants=network.service
    # Requires=rpcbind.service network-online.target
    # After=multi-user.target network.target network-online.target
    #
    # [Service]
    # Type=idle
    # ExecStart=/home/pi/run-matrix.sh
    # User=pi
    # Group=pi
    # StandardOutput=append:/home/pi/logs/matrix.log
    # StandardError=append:/home/pi/logs/matrix_err.log
    #
    # [Install]
    # WantedBy=multi-user.target
    #
    # to enable
    # sudo systemctl daemon-reload
    # sudo systemctl enable sample.service
    # sudo reboot
    #
    # commands disable, start, stop etc

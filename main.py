from datetime import datetime, time as dt_time, timedelta
import importlib
import os
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

FEEDS = None
NOW = None
LOCAL_TZ = pytz.timezone("America/New_York")
WEATHER_MGR = None
WEATHER = None
FORECAST = None
WEATHER_TIMESTAMP = None


class GracefulKiller:
    def __init__(self):
        self.kill_now = False
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.kill_now = True


class DisplayTrains(SampleBase):
    def __init__(self, stop_ids, uptown_stop_ids, *args, **kwargs):
        super(DisplayTrains, self).__init__(*args, **kwargs)

        self.stop_ids = stop_ids
        self.uptown_stop_ids = uptown_stop_ids
        self.font = graphics.Font()
        # self.font.LoadFont("./fonts/7x13.bdf")
        self.font.LoadFont("./fonts/helvR12.bdf")
        self.circle_font = graphics.Font()
        self.circle_font.LoadFont('./fonts/6x10.bdf')

        # self.text_colour = graphics.Color(0, 110, 0)
        # self.text_colour_arriving = graphics.Color(255, 66, 25)
        self.text_colour = graphics.Color(74, 214, 9)
        self.text_colour_arriving = graphics.Color(247, 75, 25)

        self.circle_colour_bdfm = graphics.Color(255, 99, 25)
        self.circle_colour_g = graphics.Color(108, 190, 69)
        self.circle_colour_nqrw = graphics.Color(252, 204, 10)

    @staticmethod
    def draw_filled_circle(canvas, x, y, color):
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

    def draw_train_row(self,
                       canvas,
                       row_ind,
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

        graphics.DrawText(canvas, self.font, 1, text_y, text_colour, f'{row_ind + 1}')
        graphics.DrawText(canvas, self.font, 7, text_y, text_colour, f'.')
        # graphics.DrawCircle(canvas, 16, circle_y, 5, circle_colour)
        self.draw_filled_circle(canvas, 15, circle_y, circle_colour)
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

    def draw_train(self, row_ind, train, stop_id, canvas):
        arrival_mins = arrival_minutes(train, stop_id)
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

        stop_name, direction = get_stop_name_and_direction(stop_id)

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

        stop_name, direction = get_stop_name_and_direction(stop_id)

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

    def draw_trains(self, trains, stop_id, canvas):
        if trains is None:
            self.draw_train_no_data(stop_id, canvas)
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
                self.draw_train(0, trains[0], stop_id, canvas)
                if len(trains) > 1:
                    self.draw_train(1, trains[1], stop_id, canvas)
        else:
            self.draw_trains_none(stop_id, canvas)

        return True, canvas

    def draw_weather(self, canvas, w):
        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        max_temp = k_to_c(w.temp['temp_max'])
        min_temp = k_to_c(w.temp['temp_min'])
        icon_file = weather_to_icon(w)

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

        icon_file = weather_to_icon(next(w for w in w_list if w.weather_code == best_code))
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

        w, _ = get_weather()

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
            if w is not None:
                graphics.DrawText(canvas, self.circle_font, clock_pos + 44, text_y_top - 1, self.text_colour,
                                  f'{k_to_c(w.temp["temp"]):d}c')
            else:
                graphics.DrawText(canvas, self.circle_font, clock_pos + 44, text_y_top - 1, self.text_colour,
                                  '--c')

            # draw date
            date_str = current_time.strftime('%a ') + f'{current_time.day} ' + current_time.strftime('%b')
            graphics.DrawText(canvas, self.font, 1, text_y_bottom, self.text_colour, date_str)

            canvas = self.matrix.SwapOnVSync(canvas)
            show_colon = not show_colon
            time.sleep(0.5)

        return canvas

    def display_trains(self, canvas, display_time=10, uptown_only=False):
        update_feeds()
        stop_ids = self.stop_ids
        if uptown_only:
            stop_ids = self.uptown_stop_ids
        for stop_id in stop_ids:
            trains = get_next_trains(stop_id=stop_id)

            canvas.Clear()
            success, canvas = self.draw_trains(trains, stop_id, canvas)
            if success:
                time.sleep(0.05)
                canvas = self.matrix.SwapOnVSync(canvas)

            # show display for 10 seconds before update
            time.sleep(display_time)

        return canvas

    def display_weather(self, canvas, display_time=10):

        timestamp = datetime.now().time()
        if timestamp < dt_time(13, 0):  # before 12 show today's forecast
            title_str = 'Day'
            forecasts = forecasts_today()
        elif timestamp < dt_time(19, 0):  # before 7pm show the evening forecast
            title_str = 'Eve'
            forecasts = forecasts_evening()
        else:
            title_str = 'Tom'
            forecasts = forecasts_tomorrow()

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

        timestamp = datetime.now().time()
        # display trains and clock between 7am and 9am
        if dt_time(7, 0) <= timestamp < dt_time(10, 0):
            return ['trains_uptown, clock', 'weather'], 5
        # only trains and weather during the day
        if dt_time(10, 0) <= timestamp < dt_time(20, 0):
            return ['trains', 'weather'], 10
        # only clok after 8
        if timestamp >= dt_time(20, 0):
            return ['clock', 'weather'], 10

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
                else:
                    # nothing
                    canvas.Clear()
                    time.sleep(display_time)  # check again in 10 mins


def arrival_time(train, stop_id):
    if train.location_status == 'STOPPED_AT' and train.location == stop_id:
        return datetime(9999, 1, 1, 0, 0, 0)
    return next((stu.arrival for stu in train.stop_time_updates
                 if stu.stop_id == stop_id), datetime(9999, 1, 1, 0, 0, 0))


def arrival_minutes(train, stop_id):
    t = arrival_time(train, stop_id)
    tdelta = t - NOW
    arrival_mins = int(tdelta.total_seconds() / 60)
    return arrival_mins


def find_next_trains(trains, num_trains, stop_id):
    arrival_times = [arrival_time(train, stop_id) for train in trains]
    train_order = sorted(range(len(arrival_times)), key=lambda k: arrival_times[k])
    return [trains[train_order[i]] for i in range(num_trains) if len(train_order) > i]


def forecasts_evening():
    # evening forecast is between 7pm and midnight
    start_time = datetime.today().replace(hour=19, minute=0, second=0)
    end_time = datetime.today().replace(hour=0, minute=0, second=0) + timedelta(days=1)
    return forecasts_get(start_time, end_time)


def forecasts_get(time_start, time_end):
    # put time in utc
    time_start = to_utc_tz(time_start)
    time_end = to_utc_tz(time_end)

    w, forecast = get_weather()
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


def forecasts_today():
    # today's forecasts are between 9am and 7pm
    start_time = datetime.today().replace(hour=9, minute=0, second=0)
    end_time = datetime.today().replace(hour=19, minute=0, second=0)
    return forecasts_get(start_time, end_time)


def forecasts_tomorrow():
    # tomorrow's forecast is between 7am and 7pm tomorrow
    start_time = datetime.today().replace(hour=7, minute=0, second=0) + timedelta(days=1)
    end_time = datetime.today().replace(hour=19, minute=0, second=0) + timedelta(days=1)
    return forecasts_get(start_time, end_time)


def get_mta_feeds():
    import requests
    global FEEDS

    if FEEDS is None:
        try:
            FEEDS = [
                NYCTFeed("F"),
                NYCTFeed("G"),
                NYCTFeed("R"),
            ]
        except requests.exceptions.ConnectionError as e:
            warnings.warn(f'ConnectionError: {e}')
            return None

    return FEEDS


def get_next_trains(
        num_trains=2,
        stop_id='F23N'
):
    # time from now
    global NOW
    NOW = datetime.now()
    # get all feeds
    feeds = get_mta_feeds()
    if feeds is not None:
        all_trains = []
        for feed in feeds:
            all_trains.extend(feed.filter_trips(headed_for_stop_id=stop_id))
        return find_next_trains(all_trains, num_trains, stop_id)
    else:
        return None


def get_stop_name_and_direction(stop_id):
    # stop_id reference here:
    # https://openmobilitydata-data.s3-us-west-1.amazonaws.com/public/feeds/mta/79/20240103/original/stops.txt

    if stop_id.startswith('F23'):
        stop_name = '4 Av'
    elif stop_id.startswith('R33'):
        stop_name = '9 St'

    if stop_id.endswith('N'):
        direction = '↑'
    else:
        direction = '↓'

    return stop_name, direction


def get_weather():
    global WEATHER_MGR
    global WEATHER
    global FORECAST
    global WEATHER_TIMESTAMP

    if WEATHER_MGR is None:
        owm = OWM(os.environ['OWM_API_KEY'])
        WEATHER_MGR = owm.weather_manager()

    # we only get the weather every 0.5 hours
    if WEATHER_TIMESTAMP is None or \
            (datetime.now() - WEATHER_TIMESTAMP).total_seconds() / 3600 > 0.5:
        WEATHER_TIMESTAMP = datetime.now()
        try:
            observation = WEATHER_MGR.weather_at_place('New York')
            WEATHER = observation.weather
            FORECAST = WEATHER_MGR.forecast_at_place('New York', '3h')
        except Exception as e:
            WEATHER = None
            FORECAST = None

    return WEATHER, FORECAST


def k_to_c(k):
    return round(k - 273.15)


def pick_worst_weather(w1, w2):
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


def to_utc_tz(date_time):
    date_time = LOCAL_TZ.localize(date_time, is_dst=None)
    date_time = date_time.astimezone(pytz.utc)
    return date_time


def to_local_tz(date_time):
    date_time = pytz.utc.localize(date_time, is_dst=None)
    date_time = date_time.astimezone(LOCAL_TZ)
    return date_time


def update_feeds():
    import requests

    # update all feeds
    feeds = get_mta_feeds()
    if feeds is not None:
        for feed in feeds:
            try:
                feed.refresh()
            except requests.exceptions.ConnectionError as e:
                warnings.warn(f'ConnectionError: {e}')
                pass


def weather_to_icon(weather):
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

    elif weather.weather_code in [501, 502, ]:
        icon_file = 'icons/32/rain1.png'

    elif weather.weather_code in [503, 504, ]:
        icon_file = 'icons/32/rain2.png'

    elif weather.weather_code in [511, 611]:
        icon_file = 'icons/32/rain_hail.png'

    elif weather.weather_code in [520, 521, 522, 531]:
        if is_day:
            icon_file = 'icons/32/rain1_sun.png'
        else:
            icon_file = 'icons/32/rain1_moon.png'

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


def main():

    led_display_trains = DisplayTrains(['F23N', 'F23S', 'R33N', 'R23S'], ['F23N', 'R33N'])
    led_display_trains.process()

    pass


if __name__ == '__main__':
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
    # source ${HOME}/venv/NYCSubwayDisplay/bin/activate
    # sudo --preserve-env=PYTHONPATH,OWM_API_KEY /home/pi/venv/NYCSubwayDisplay/bin/python main.py --led-gpio-mapping=adafruit-hat-pwm --led-rows=32 --led-cols=64 --led-rgb-sequence=RBG --led-brightness=40 --led-slowdown-gpio=1  --led-no-drop-privs

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

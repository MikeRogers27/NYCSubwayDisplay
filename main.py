from datetime import datetime, time as dt_time, timedelta
import importlib
import os
import time
import signal
import warnings

from nyct_gtfs import NYCTFeed
from pyowm import OWM

# from PIL import Image

if os.name == 'nt':
    graphics = importlib.import_module('RGBMatrixEmulator', 'graphics')
else:
    from rgbmatrix import graphics

from samplebase import SampleBase

FEEDS = None
NOW = None
# owm = OWM(os.environ['OWM_API_KEY'])
# mgr = owm.weather_manager()
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
    def __init__(self, stop_ids, *args, **kwargs):
        super(DisplayTrains, self).__init__(*args, **kwargs)

        self.stop_ids = stop_ids
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

    def draw_filled_circle(self, canvas, x, y, color):
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

    def draw_row(self,
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

        self.draw_row(canvas,
                      row_ind=row_ind,
                      text_colour=text_colour,
                      circle_colour=circle_colour,
                      route_id=train.route_id,
                      headsign_text=train.headsign_text,
                      direction=direction,
                      arrival_mins=arrival_mins)

    @staticmethod
    def get_stop_name_and_direction( stop_id):
        if stop_id.startswith('F23'):
            stop_name = '4 Av'
        elif stop_id.startswith('R33'):
            stop_name = '9 St'

        if stop_id.endswith('N'):
            direction = '↑'
        else:
            direction = '↓'

        return stop_name, direction

    def draw_no_train_data(self,
                           stop_id,
                           canvas,
                           ):
        # Top line
        text_y_top = 13
        text_y_bottom = 28

        stop_name, direction = self.get_stop_name_and_direction(stop_id)

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

    def draw_no_trains(self,
                       stop_id,
                       canvas,
                       ):
        # Top line
        text_y_top = 13
        text_y_bottom = 28

        stop_name, direction = self.get_stop_name_and_direction(stop_id)

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
            self.draw_no_train_data(stop_id, canvas)
        elif len(trains):
            # check we don't have stale data
            now = datetime.now()
            last_update_time = now - timedelta(minutes=60)
            for train in trains:
                if train.last_position_update > last_update_time:
                    last_update_time = train.last_position_update
            # if the latest update was more than 15 minutes ago, the data is stale
            if last_update_time < now - timedelta(minutes=15):
                self.draw_no_train_data(stop_id, canvas)
            else:
                self.draw_train(0, trains[0], stop_id, canvas)
                if len(trains) > 1:
                    self.draw_train(1, trains[1], stop_id, canvas)
        else:
            self.draw_no_trains(stop_id, canvas)

        return True, canvas

    def what_should_we_display(self):
        # return ['trains']
        # return ['clock', 'trains']

        timestamp = datetime.now().time()
        # display trains and clock between 7am and 9am
        if dt_time(7, 0) <= timestamp < dt_time(9, 0):
            return ['trains, clock']
        # only trains during the day
        if dt_time(9, 0) <= timestamp < dt_time(20, 0):
            return ['trains']
        # only clok after 8
        if timestamp >= dt_time(20, 0):
            return ['clock']

        return ['off']

    def display_trains(self, canvas):
        update_feeds()
        for stop_id in self.stop_ids:
            trains = get_next_trains(stop_id=stop_id)

            canvas.Clear()
            success, canvas = self.draw_trains(trains, stop_id, canvas)
            if success:
                time.sleep(0.05)
                canvas = self.matrix.SwapOnVSync(canvas)

            # show display for 10 seconds before update
            time.sleep(10)

        return canvas

    def display_clock(self, canvas):
        text_y_top = 13
        text_y_bottom = 28
        clock_pos = 1

        w, _ = get_weather()

        start_time = datetime.now()
        show_colon = True
        while (datetime.now() - start_time).total_seconds() < 10:
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

    def display_weather(self, canvas):
        text_y_top = 10
        text_y_middle = 20
        text_y_bottom = 30

        timestamp = datetime.now().time()
        if timestamp < dt_time(13, 0):  # before 12 show today's forecast
            min_temp, max_temp, icon_file = todays_forecast()
            head_str = 'Today'
        elif timestamp < dt_time(19, 0):  # before 7pm show the evening forecast
            min_temp, max_temp, icon_file = evening_forecast()
            head_str = 'Eve'
        else:
            min_temp, max_temp, icon_file = tomorrows_forecast()
            head_str = 'Tom'

        canvas.Clear()

        im = Image.open(icon_file)

        graphics.DrawText(canvas, self.circle_font, 32, text_y_top, self.text_colour, head_str)
        graphics.DrawText(canvas, self.circle_font, 32, text_y_middle, self.text_colour,
                          f'↓{min_temp}c')
        graphics.DrawText(canvas, self.circle_font, 32, text_y_bottom, self.text_colour,
                          f'↑{max_temp}c')
        canvas.SetImage(im)

        canvas = self.matrix.SwapOnVSync(canvas)
        time.sleep(10)
        return canvas

    def run(self):
        canvas = self.matrix.CreateFrameCanvas()

        graceful_killer = GracefulKiller()
        while not graceful_killer.kill_now:
            display_items = self.what_should_we_display()
            for display_item in display_items:
                if display_item == 'trains':
                    canvas = self.display_trains(canvas)
                elif display_item == 'clock':
                    canvas = self.display_clock(canvas)
                elif display_item == 'weather':
                    canvas = self.display_weather(canvas)
                else:
                    # nothing
                    canvas.Clear()
                    time.sleep(600)  # check again in 10 mins


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


def display_trains(trains, stop_id):
    for i, train in enumerate(trains):
        arrival_mins = arrival_minutes(train, stop_id)
        print(f'{i + 1}. {train.route_id} {train.headsign_text: <20s} {arrival_mins:2d}min')
    print()


def k_to_c(k):
    return round(k - 273.15)


def weather_to_icon(weather):
    is_day = weather.weather_icon_name.endswith('d')

    if weather.weather_code in [201, 202]:
        icon_file = 'icons/32/rain_lightning.xbm'
    elif weather.weather_code in [200, 210, 211, 212, 221, 230, 231, 232]:
        icon_file = 'icons/32/lightning.xbm'

    elif weather.weather_code in [300, 301, 302, 310, 311, 312, 313, 314, 321]:
        icon_file = 'icons/32/rain0.xbm'

    elif weather.weather_code in [500, 501, ]:
        icon_file = 'icons/32/rain1.xbm'

    elif weather.weather_code in [502, 503, 504]:
        icon_file = 'icons/32/rain2.xbm'

    elif weather.weather_code in [511, 611, 612, 613, 615, 616, ]:
        icon_file = 'icons/32/rain_snow.xbm'

    elif weather.weather_code in [520, 521, 522, 531]:
        if is_day:
            icon_file = 'icons/32/rain1_sun.xbm'
        else:
            icon_file = 'icons/32/rain1_moon.xbm'

    elif weather.weather_code in [600, 601, 602, ]:
        icon_file = 'icons/32/snow.xbm'

    elif weather.weather_code in [620, 621, 622, ]:
        if is_day:
            icon_file = 'icons/32/snow_sun.xbm'
        else:
            icon_file = 'icons/32/snow_moon.xbm'

    elif weather.weather_code in [701, 711, 721, 731, 741, 751, 761, 762, 771, 781]:
        icon_file = 'icons/32/cloud_wind.xbm.xbm'

    elif weather.weather_code in [800]:
        if is_day:
            icon_file = 'icons/32/sun.xbm'
        else:
            icon_file = 'icons/32/moon.xbm'
    elif weather.weather_code in [801]:
        if is_day:
            icon_file = 'icons/32/cloud_sun.xbm'
        else:
            icon_file = 'icons/32/cloud_moon.xbm'
    elif weather.weather_code in [802]:
        icon_file = 'icons/32/cloud.xbm'
    elif weather.weather_code in [803, 804]:
        icon_file = 'icons/32/clouds.xbm'

    else:
        icon_file = 'icons/32/sun.xbm'

    return icon_file


def get_weather():
    return None, None

    global WEATHER
    global FORECAST
    global WEATHER_TIMESTAMP

    # we only get the weather every 4 hours
    if WEATHER_TIMESTAMP is None or \
            (datetime.now() - WEATHER_TIMESTAMP).total_seconds() / 3600 > 4:
        observation = mgr.weather_at_place('New York')
        WEATHER = observation.weather
        FORECAST = mgr.forecast_at_place('New York', '3h')
        WEATHER_TIMESTAMP = datetime.now()

    return WEATHER, FORECAST


def todays_forecast():
    min_temp = 0
    max_temp = 20
    icon = 'icons/32/sun.xbm'

    w, forecast = get_weather()
    max_temp = k_to_c(w.temp['temp'])
    min_temp = max_temp
    icon = weather_to_icon(w)

    return min_temp, max_temp, icon


def evening_forecast():
    min_temp = 0
    max_temp = 20
    icon = 'icons/32/sun.xbm'

    w, forecast = get_weather()
    max_temp = k_to_c(w.temp['temp'])
    min_temp = max_temp
    icon = weather_to_icon(w)

    return min_temp, max_temp, icon


def tomorrows_forecast():
    min_temp = 0
    max_temp = 20
    icon = 'icons/32/sun.xbm'

    return min_temp, max_temp, icon


def main():
    # stop_id reference here:
    # https://openmobilitydata-data.s3-us-west-1.amazonaws.com/public/feeds/mta/79/20240103/original/stops.txt

    # # Load the realtime feed from the MTA site
    # while True:
    #     fg_trains = get_next_trains(stop_id='F23S')
    #     display_trains(fg_trains, stop_id='F23S')
    #     time.sleep(5)

    # r_trains = get_next_trains(stop_id='R33N')
    # display_trains(r_trains, stop_id='R33N')

    get_mta_feeds()
    led_display_trains = DisplayTrains(['F23N', 'F23S', 'R33N', 'R23S'])
    # led_display_trains = DisplayTrains(['F23S', ])
    led_display_trains.process()

    pass


if __name__ == '__main__':
    main()

    # script is here:
    # /home/pi/run-matrix.sh
    # configure brightness and other matrix options in here

    # systemd setup to auto-run follows this:
    # https://www.dexterindustries.com/howto/run-a-program-on-your-raspberry-pi-at-startup/
    #
    # /lib/systemd/system/matrix.service
    #
    # Contents:
    # [Unit]
    # Description=LED Matrix Runner
    # Wants=network.target network-online.target
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

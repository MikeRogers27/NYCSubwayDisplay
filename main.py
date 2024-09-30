from datetime import datetime
import importlib
import os
import time

from nyct_gtfs import NYCTFeed

if os.name == 'nt':
    graphics = importlib.import_module('RGBMatrixEmulator', 'graphics')
else:
    from rgbmatrix import graphics

from samplebase import SampleBase

FEEDS = [
    NYCTFeed("F"),
    NYCTFeed("G"),
    NYCTFeed("R"),
]
NOW = datetime.now()


class DisplayTrains(SampleBase):
    def __init__(self, stop_ids, *args, **kwargs):
        super(DisplayTrains, self).__init__(*args, **kwargs)

        self.stop_ids = stop_ids
        self.font = graphics.Font()
        # self.font.LoadFont("./fonts/7x13.bdf")
        self.font.LoadFont("./fonts/helvR12.bdf")
        self.circle_font = graphics.Font()
        self.circle_font.LoadFont('./fonts/6x10.bdf')

        self.text_colour = graphics.Color(0, 110, 0)
        self.text_colour_arriving = graphics.Color(255, 66, 25)

        self.circle_colour_bdfm = graphics.Color(255, 66, 25)
        self.circle_colour_g = graphics.Color(108, 190, 69)
        self.circle_colour_nqrw = graphics.Color(252, 204, 10)


    def draw_filled_circle(self, canvas, x, y, color):
        # Draw circle with lines
        graphics.DrawLine(canvas, x - 2, y - 6, x + 2, y - 6, color)
        graphics.DrawLine(canvas, x - 3, y - 5, x + 3, y - 5, color)
        graphics.DrawLine(canvas, x - 4, y - 4, x + 4, y - 4, color)
        graphics.DrawLine(canvas, x - 5, y - 3, x + 5, y - 3, color)
        graphics.DrawLine(canvas, x - 6, y - 2, x + 6, y - 2, color)
        graphics.DrawLine(canvas, x - 6, y - 1, x + 6, y - 1, color)
        graphics.DrawLine(canvas, x - 6, y, x + 6, y, color)
        graphics.DrawLine(canvas, x - 6, y + 1, x + 6, y + 1, color)
        graphics.DrawLine(canvas, x - 6, y + 2, x + 6, y + 2, color)
        graphics.DrawLine(canvas, x - 5, y + 3, x + 5, y + 3, color)
        graphics.DrawLine(canvas, x - 4, y + 4, x + 4, y + 4, color)
        graphics.DrawLine(canvas, x - 3, y + 5, x + 3, y + 5, color)
        graphics.DrawLine(canvas, x - 2, y + 6, x + 2, y + 6, color)

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
            circle_y = 7
            text_y = 12
        else:
            # Bottom line
            circle_y = 23
            text_y = 28

        route_id_offset_width = self.circle_font.CharacterWidth(ord(route_id))
        route_id_offset = int(route_id_offset_width / 2) - 1

        minutes_width = 16
        minutes_text = f'{arrival_mins:2d}'
        # minutes_width = sum(self.font.CharacterWidth(ord(letter)) for letter in minutes_text)
        #
        # graphics.DrawText(canvas, self.font, 1, text_y, text_colour, f'{row_ind+1}')
        # graphics.DrawText(canvas, self.font, 7, text_y, text_colour, f'.')
        # # graphics.DrawCircle(canvas, 16, circle_y, 5, circle_colour)
        # self.draw_filled_circle(canvas, 16, circle_y, circle_colour)
        # graphics.DrawText(canvas, self.circle_font, 16 - route_id_offset, text_y-1, graphics.Color(0, 0, 0), route_id)
        # # graphics.DrawText(canvas, self.font, 26, text_y, text_colour, headsign_text)
        # if direction == 'N':
        #     graphics.DrawText(canvas, self.circle_font, 23, text_y - 1, text_colour, '↑')
        # else:
        #     graphics.DrawText(canvas, self.circle_font, 23, text_y - 1, text_colour, '↓')
        graphics.DrawText(canvas, self.font, 43 - minutes_width, text_y, text_colour, minutes_text)
        graphics.DrawText(canvas, self.font, 43, text_y, text_colour, "min")

    def draw_train(self, row_ind, train, stop_id, canvas):
        arrival_mins = arrival_minutes(train, stop_id)
        # arrival_mins = 0
        text_colour = self.text_colour
        if arrival_mins <= 0:
            text_colour = self.text_colour_arriving

        # see: https://www.6sqft.com/did-you-know-the-mta-uses-pantone-colors-to-distinguish-train-lines/
        if train.route_id in ['B', 'D', 'F', 'M']:
            circle_colour = self.circle_colour_bdfm
        elif train.route_id in ['G', ]:
            circle_colour = self.circle_colour_g
        else:
            circle_colour = self.circle_colour_nqrw

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

    def draw_trains(self, trains, stop_id, canvas):
        if len(trains):
            self.draw_train(0, trains[0], stop_id, canvas)
            # if len(trains) > 1:
            #     self.draw_train(1, trains[1], stop_id, canvas)

            return True, canvas
        else:
            return False, canvas

    def run(self):
        offscreen_canvas = self.matrix.CreateFrameCanvas()
        # font = graphics.Font()
        # font.LoadFont("../../../fonts/7x13.bdf")
        textColor = graphics.Color(0, 255, 0)
        pos = 2  # offscreen_canvas.width
        my_text = 'Test Text'

        while True:
            offscreen_canvas.Clear()
            len = graphics.DrawText(offscreen_canvas, self.font, pos, 10, textColor, my_text)
            # pos -= 1
            if (pos + len < 0):
                pos = offscreen_canvas.width

            time.sleep(0.05)
            offscreen_canvas = self.matrix.SwapOnVSync(offscreen_canvas)

        # trains = get_next_trains(stop_id=self.stop_ids[0])
        # canvas = self.matrix.CreateFrameCanvas()
        # while True:
        #     canvas.Clear()
        #     # success, canvas = self.draw_trains(trains, self.stop_ids[0], canvas)
        #
        #     text_y = 12
        #     arrival_mins = 1
        #     minutes_width = 16
        #     minutes_text = f'{arrival_mins:2d}'
        #     graphics.DrawText(canvas, self.font, 43 - minutes_width, text_y, self.text_colour, minutes_text)
        #     graphics.DrawText(canvas, self.font, 43, text_y, self.text_colour, "min")
        #
        #     time.sleep(0.05)
        #     canvas = self.matrix.SwapOnVSync(canvas)


        # while True:
        #     for stop_id in self.stop_ids:
        #         trains = get_next_trains(stop_id=stop_id)
        #         success, canvas = self.draw_trains(trains, stop_id, canvas)
        #         if success:
        #             time.sleep(10)  # show display for 10 seconds before exit


def arrival_time(train, stop_id):
    if train.location_status == 'STOPPED_AT' and train.location == stop_id:
        return datetime(9999, 1, 1, 0, 0, 0)
    return next((stu.arrival for stu in train.stop_time_updates
                 if stu.stop_id == stop_id), datetime(9999, 1, 1, 0, 0, 0))


def arrival_minutes(train, stop_id):
    t = arrival_time(train, stop_id)
    tdelta = t - NOW
    arrival_mins = max(round(tdelta.total_seconds() / 60), 0)
    return arrival_mins


def find_next_trains(trains, num_trains, stop_id):
    arrival_times = [arrival_time(train, stop_id) for train in trains]
    train_order = sorted(range(len(arrival_times)), key=lambda k: arrival_times[k])
    return [trains[train_order[i]] for i in range(num_trains) if len(train_order) > i]


def get_next_trains(
        num_trains=2,
        stop_id='F23N'
):
    all_trains = []
    for feed in FEEDS:
        feed.refresh()
        all_trains.extend(feed.filter_trips(headed_for_stop_id=stop_id))

    return find_next_trains(all_trains, num_trains, stop_id)


def display_trains(trains, stop_id):
    for i, train in enumerate(trains):
        arrival_mins = arrival_minutes(train, stop_id)
        print(f'{i + 1}. {train.route_id} {train.headsign_text: <20s} {arrival_mins:2d}min')
    print()


def main():
    # stop_id reference here:
    # https://openmobilitydata-data.s3-us-west-1.amazonaws.com/public/feeds/mta/79/20240103/original/stops.txt

    # # Load the realtime feed from the MTA site
    # fg_trains = get_next_trains(stop_id='F23N')
    # display_trains(fg_trains, stop_id='F23N')
    #
    # r_trains = get_next_trains(stop_id='R33N')
    # display_trains(r_trains, stop_id='R33N')

    led_display_trains = DisplayTrains(['F23N', 'F23S', 'R33N', 'R23S'])
    led_display_trains.process()

    pass


if __name__ == '__main__':
    main()

    # cd ~/src/NYCSubwayDisplay/
    # export PYTHONPATH=${PYTHONPATH}:${HOME}/src/rpi-rgb-led-matrix/bindings/python
    # source ~/venv/NYCSubwayDisplay/bin/activate
    # sudo PYTHONPATH=${PYTHONPATH} /home/pi/venv/NYCSubwayDisplay/bin/python main.py --led-gpio-mapping=adafruit-hat --led-rows=32 --led-cols=64 --led-rgb-sequence=RBG --led-brightness=50 --led-slowdown-gpio=2

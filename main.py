from datetime import datetime
import time

from nyct_gtfs import NYCTFeed
from RGBMatrixEmulator import graphics
from samplebase import SampleBase

FEEDS = [
    NYCTFeed("F"),
    NYCTFeed("G"),
    NYCTFeed("R"),
]
NOW = datetime.now()


class DisplayTrains(SampleBase):
    def __init__(self, trains, stop_id, *args, **kwargs):
        super(DisplayTrains, self).__init__(*args, **kwargs)

        self.trains = trains
        self.stop_id = stop_id
        self.font = graphics.Font()
        # self.font.LoadFont("./fonts/7x13.bdf")
        self.font.LoadFont("./fonts/helvR12.bdf")

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

    def draw_row(self,
                 row_ind,
                 text_colour,
                 circle_colour,
                 route_id,
                 headsign_text,
                 arrival_mins):
        # Top line
        if row_ind == 0:
            circle_y = 7
            text_y = 12
        else:
            # Bottom line
            circle_y = 23
            text_y = 28

        graphics.DrawText(self.matrix, self.font, 2, text_y, text_colour, f'{row_ind+1}')
        graphics.DrawText(self.matrix, self.font, 8, text_y, text_colour, f'.')
        # graphics.DrawCircle(self.matrix, 18, circle_y, 7, circle_colour)
        self.draw_filled_circle(self.matrix, 18, circle_y, circle_colour)
        graphics.DrawText(self.matrix, self.font, 14, text_y, graphics.Color(0, 0, 0), route_id)
        graphics.DrawText(self.matrix, self.font, 26, text_y, text_colour, headsign_text)
        graphics.DrawText(self.matrix, self.font, 156, text_y, text_colour, f'{arrival_mins:2d}')
        graphics.DrawText(self.matrix, self.font, 169, text_y, text_colour, "min")

    def draw_train(self, row_ind):
        train = self.trains[row_ind]
        t = arrival_time(train, self.stop_id)
        tdelta = t - NOW
        arrival_mins = max(int(tdelta.total_seconds() // 60), 0)
        text_color = graphics.Color(0, 110, 0)
        if arrival_mins <= 0:
            text_color = graphics.Color(255, 66, 25)

        # see: https://www.6sqft.com/did-you-know-the-mta-uses-pantone-colors-to-distinguish-train-lines/
        if arrival_mins <= 0:
            circle_color = graphics.Color(255, 66, 25)
        elif train.route_id in ['B', 'D', 'F', 'M']:
            circle_color = graphics.Color(255, 66, 25)
        elif train.route_id in ['G', ]:
            circle_color = graphics.Color(108, 190, 69)
        else:
            circle_color = graphics.Color(252, 204, 10)

        self.draw_row(row_ind=row_ind,
                      text_colour=text_color,
                      circle_colour=circle_color,
                      route_id=train.route_id,
                      headsign_text=train.headsign_text,
                      arrival_mins=arrival_mins)

    def run(self):
        self.draw_train(0)
        self.draw_train(1)

        time.sleep(10)  # show display for 10 seconds before exit


def arrival_time(train, stop_id):
    if train.location_status == 'STOPPED_AT' and train.location == stop_id:
        return datetime(9999, 1, 1, 0, 0, 0)
    return next((stu.arrival for stu in train.stop_time_updates
                 if stu.stop_id == stop_id), datetime(9999, 1, 1, 0, 0, 0))


def find_next_trains(trains, num_trains, stop_id):
    arrival_times = [arrival_time(train, stop_id) for train in trains]
    train_order = sorted(range(len(arrival_times)), key=lambda k: arrival_times[k])
    return [trains[train_order[i]] for i in range(num_trains)]


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
        t = arrival_time(train, stop_id)
        tdelta = t - NOW
        arrival_mins = max(int(tdelta.total_seconds() // 60), 0)
        print(f'{i + 1}. {train.route_id} {train.headsign_text: <20s} {arrival_mins:2d}min {t}')
    print()


def main():
    # Load the realtime feed from the MTA site
    fg_trains = get_next_trains(stop_id='F23N')
    display_trains(fg_trains, stop_id='F23N')

    r_trains = get_next_trains(stop_id='R33N')
    display_trains(r_trains, stop_id='R33N')

    led_display_trains = DisplayTrains(fg_trains, 'F23N')
    # led_display_trains = DisplayTrains(r_trains, 'R33N')
    led_display_trains.process()

    pass


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()

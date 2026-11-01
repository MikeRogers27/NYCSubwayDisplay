"""Verify command-driven interruption without a matrix or MQTT broker."""

import unittest
from threading import Event, Thread
from unittest.mock import Mock, patch

import paho.mqtt.client as mqtt

import main
from display_control import DisplayControl, DisplayMode
from mqtt_listener import MQTTListener


class DisplayControlTests(unittest.TestCase):
    def test_command_wakes_a_long_wait_without_waiting_for_timeout(self) -> None:
        control = DisplayControl()
        started = Event()
        results = []

        def wait() -> None:
            started.set()
            results.append(control.wait(600))

        worker = Thread(target=wait, daemon=True)
        worker.start()
        try:
            self.assertTrue(started.wait(timeout=1))
            control.request(DisplayMode("trains"))
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(results, [True])
        finally:
            control.interrupt.set()
            worker.join(timeout=1)

    def test_timeout_and_command_consumption_reset_interrupt(self) -> None:
        control = DisplayControl()
        self.assertFalse(control.wait(0))
        control.request(DisplayMode("clock"))
        control.request(DisplayMode("trains"))
        self.assertTrue(control.wait(0))
        self.assertEqual(control.next_command(), DisplayMode("trains"))
        self.assertFalse(control.wait(0))
        self.assertIsNone(control.next_command())
        control.request(DisplayMode("weather"))
        self.assertTrue(control.wait(0))
        self.assertEqual(control.next_command(), DisplayMode("weather"))

    def test_only_on_messages_queue_a_display_command(self) -> None:
        control = DisplayControl()
        listener = MQTTListener(on_command=control.request)
        for payload in (b"OFF", b"on", b"invalid", b"\xff"):
            message = mqtt.MQTTMessage(topic=b"matrix/display/train/set")
            message.payload = payload
            listener._on_message(listener.client, None, message)
        self.assertIsNone(control.next_command())
        self.assertFalse(control.wait(0))
        message.payload = b"ON"
        listener._on_message(listener.client, None, message)
        self.assertTrue(control.wait(0))
        self.assertEqual(control.next_command(), DisplayMode("trains"))
        self.assertEqual(listener.display_commands.qsize(), 5)


class RenderInterruptionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.display = main.RunMatrix.__new__(main.RunMatrix)
        self.display.display_control = DisplayControl()
        self.display._remaining_rotation = []
        self.display.matrix = Mock()
        self.canvas = Mock()
        self.swapped_canvas = Mock()
        self.display.matrix.CreateFrameCanvas.return_value = self.canvas
        self.display.matrix.SwapOnVSync.return_value = self.swapped_canvas

    def test_requested_mode_is_prepended_to_the_normal_rotation(self) -> None:
        with patch.object(self.display, "scheduled_display", return_value=([DisplayMode("clock")], [30])):
            self.display.display_control.request(DisplayMode("trains"))
            self.display.display_control.request(DisplayMode("trains"))
            self.assertEqual(
                self.display.what_should_we_display(), ([DisplayMode("trains"), DisplayMode("clock")], [5, 30])
            )
            self.assertFalse(self.display.display_control.interrupt.is_set())
            self.assertEqual(self.display._remaining_rotation, [(DisplayMode("trains"), 5), (DisplayMode("clock"), 30)])
            self.display._remaining_rotation.pop(0)
            self.assertEqual(self.display.what_should_we_display(), ([DisplayMode("clock")], [30]))

    def test_repeated_request_does_not_stack_duplicate_entries(self) -> None:
        self.display._remaining_rotation = [(DisplayMode("trains"), 5), (DisplayMode("weather"), 5)]
        self.display.display_control.request(DisplayMode("trains"))
        self.assertEqual(
            self.display.what_should_we_display(), ([DisplayMode("trains"), DisplayMode("weather")], [5, 5])
        )

    def test_stop_selections_are_distinct_and_identical_requests_are_coalesced(self) -> None:
        f_only = DisplayMode("trains", stop_ids=("F23N",))
        r_only = DisplayMode("trains", stop_ids=("R33N",))
        self.display._remaining_rotation = [(DisplayMode("trains"), 5), (DisplayMode("clock"), 30)]
        self.display.display_control.request(f_only)
        self.assertEqual(
            self.display.what_should_we_display(), ([f_only, DisplayMode("trains"), DisplayMode("clock")], [5, 5, 30])
        )
        self.display.display_control.request(f_only)
        self.assertEqual(len(self.display.what_should_we_display()[0]), 3)
        self.display.display_control.request(r_only)
        self.assertEqual(
            self.display.what_should_we_display(),
            ([r_only, f_only, DisplayMode("trains"), DisplayMode("clock")], [5, 5, 5, 30]),
        )

    def test_explicit_stop_selection_overrides_uptown_without_changing_defaults(self) -> None:
        self.display.stop_ids = ["F23N", "F23S", "R33N", "R33S"]
        self.display.uptown_stop_ids = ["F23N", "R33N"]
        with (
            patch.object(main, "mta_update_feeds"),
            patch.object(main, "mta_get_next_trains") as get_trains,
            patch.object(self.display, "draw_trains", return_value=(True, self.swapped_canvas)),
        ):
            for stop in ("F23N", "R33N"):
                with self.subTest(stop=stop):
                    get_trains.reset_mock()
                    self.display.display_trains(self.canvas, uptown_only=True, stop_ids=(stop,))
                    get_trains.assert_called_once_with(stop_id=stop, max_num_trains=5, max_arrival_mins=25)
            get_trains.reset_mock()
            self.display.display_trains(self.canvas)
            self.assertEqual([call.kwargs["stop_id"] for call in get_trains.call_args_list], self.display.stop_ids)
            get_trains.reset_mock()
            self.display.display_trains(self.canvas, uptown_only=True)
            self.assertEqual(
                [call.kwargs["stop_id"] for call in get_trains.call_args_list], self.display.uptown_stop_ids
            )
        self.assertEqual(self.display.stop_ids, ["F23N", "F23S", "R33N", "R33S"])
        self.assertEqual(self.display.uptown_stop_ids, ["F23N", "R33N"])

    def test_mqtt_stop_selection_reaches_renderer_and_preserves_rotation(self) -> None:
        for topic, stop in (("f-trains", "F23N"), ("r-trains", "R33N")):
            with self.subTest(topic=topic):
                self.display._remaining_rotation = []
                killer = Mock(kill_now=False)
                listener = MQTTListener(on_command=self.display.display_control.request)
                rendered = []

                def clock(canvas, display_time, *, rendered=rendered, topic=topic, listener=listener):
                    rendered.append(("clock", None))
                    if len(rendered) == 1:
                        message = mqtt.MQTTMessage(topic=f"matrix/display/{topic}/set".encode())
                        message.payload = b"ON"
                        listener._on_message(listener.client, None, message)
                    return self.swapped_canvas

                def trains(canvas, display_time, stop_ids=None, *, rendered=rendered, killer=killer):
                    rendered.append(("trains", stop_ids))
                    if stop_ids is None:
                        killer.kill_now = True
                    return self.swapped_canvas

                with (
                    patch.object(main, "GracefulKiller", return_value=killer),
                    patch.object(
                        self.display,
                        "scheduled_display",
                        return_value=([DisplayMode("clock"), DisplayMode("trains")], [30, 5]),
                    ),
                    patch.object(self.display, "display_clock", side_effect=clock),
                    patch.object(self.display, "display_trains", side_effect=trains),
                ):
                    self.display.run()
                self.assertEqual(rendered, [("clock", None), ("trains", (stop,)), ("clock", None), ("trains", None)])

    def test_actual_schedule_returns_display_mode_objects(self) -> None:
        modes, durations = self.display.scheduled_display()
        self.assertTrue(modes)
        self.assertEqual(len(modes), len(durations))
        self.assertTrue(all(isinstance(mode, DisplayMode) for mode in modes))

    def test_clock_and_weather_commands_use_rotation_durations_and_preserve_position(self) -> None:
        for mode, duration in (("clock", 10), ("weather", 5)):
            with self.subTest(mode=mode):
                self.display._remaining_rotation = [
                    (DisplayMode("sports"), 3),
                    (DisplayMode("clock"), 10),
                    (DisplayMode("weather"), 5),
                ]
                self.display.display_control.request(DisplayMode(mode))
                items, durations = self.display.what_should_we_display()
                self.assertEqual(
                    items, [DisplayMode(mode), DisplayMode("sports"), DisplayMode("clock"), DisplayMode("weather")]
                )
                self.assertEqual(durations, [duration, 3, 10, 5])
                self.display._remaining_rotation.pop(0)
                self.assertEqual(
                    self.display.what_should_we_display(),
                    ([DisplayMode("sports"), DisplayMode("clock"), DisplayMode("weather")], [3, 10, 5]),
                )

    def test_commands_have_default_durations_when_not_in_current_rotation(self) -> None:
        for mode, duration in (("clock", 30), ("weather", 5)):
            with self.subTest(mode=mode):
                self.display._remaining_rotation = [(DisplayMode("off"), 600)]
                self.display.display_control.request(DisplayMode(mode))
                self.assertEqual(
                    self.display.what_should_we_display(), ([DisplayMode(mode), DisplayMode("off")], [duration, 600])
                )

    def test_overnight_wait_switches_to_trains_then_back_to_schedule(self) -> None:
        killer = Mock(kill_now=False)
        waits = []

        def wait(seconds):
            waits.append(seconds)
            if len(waits) == 1:
                self.display.display_control.request(DisplayMode("trains"))
                return True
            killer.kill_now = True
            return False

        with (
            patch.object(main, "GracefulKiller", return_value=killer),
            patch.object(self.display, "scheduled_display", return_value=([DisplayMode("off")], [600])) as schedule,
            patch.object(self.display, "wait_for_display_interrupt", side_effect=wait),
            patch.object(self.display, "display_trains", return_value=self.swapped_canvas) as trains,
        ):
            self.display.run()
        self.assertEqual(waits, [600, 600])
        schedule.assert_called_once()
        trains.assert_called_once_with(self.swapped_canvas, display_time=5, stop_ids=None)

    def test_interrupt_resumes_current_mode_and_remaining_rotation(self) -> None:
        killer = Mock(kill_now=False)
        rendered = []

        def render(mode, canvas, display_time, **kwargs):
            rendered.append((mode, display_time))
            if rendered == [("clock", 30), ("weather", 5)]:
                self.display.display_control.request(DisplayMode("trains"))
            if mode == "sports":
                killer.kill_now = True
            return self.swapped_canvas

        with (
            patch.object(main, "GracefulKiller", return_value=killer),
            patch.object(
                self.display,
                "scheduled_display",
                return_value=([DisplayMode("clock"), DisplayMode("weather"), DisplayMode("sports")], [30, 5, 3]),
            ) as schedule,
            patch.object(self.display, "display_clock", side_effect=lambda *a, **kw: render("clock", *a, **kw)),
            patch.object(self.display, "display_weather", side_effect=lambda *a, **kw: render("weather", *a, **kw)),
            patch.object(self.display, "display_trains", side_effect=lambda *a, **kw: render("trains", *a, **kw)),
            patch.object(self.display, "display_sports", side_effect=lambda *a, **kw: render("sports", *a, **kw)),
        ):
            self.display.run()
        self.assertEqual(rendered, [("clock", 30), ("weather", 5), ("trains", 5), ("weather", 5), ("sports", 3)])
        self.assertEqual(self.display._remaining_rotation, [])
        schedule.assert_called_once()

    def test_interrupting_command_does_not_replace_saved_rotation(self) -> None:
        killer = Mock(kill_now=False)
        rendered = []

        def render(mode, canvas, display_time, **kwargs):
            rendered.append(mode)
            if len(rendered) in (1, 2):
                self.display.display_control.request(DisplayMode("trains"))
            if mode == "weather":
                killer.kill_now = True
            return self.swapped_canvas

        with (
            patch.object(main, "GracefulKiller", return_value=killer),
            patch.object(
                self.display,
                "scheduled_display",
                return_value=([DisplayMode("clock"), DisplayMode("weather")], [30, 5]),
            ),
            patch.object(self.display, "display_clock", side_effect=lambda *a, **kw: render("clock", *a, **kw)),
            patch.object(self.display, "display_weather", side_effect=lambda *a, **kw: render("weather", *a, **kw)),
            patch.object(self.display, "display_trains", side_effect=lambda *a, **kw: render("trains", *a, **kw)),
        ):
            self.display.run()
        self.assertEqual(rendered, ["clock", "trains", "trains", "clock", "weather"])

    def test_completed_rotation_refreshes_the_time_based_schedule(self) -> None:
        killer = Mock(kill_now=False)
        rendered = []

        def render(mode, canvas, display_time, **kwargs):
            rendered.append(mode)
            if mode == "sports":
                killer.kill_now = True
            return self.swapped_canvas

        with (
            patch.object(main, "GracefulKiller", return_value=killer),
            patch.object(
                self.display,
                "scheduled_display",
                side_effect=[([DisplayMode("clock"), DisplayMode("weather")], [30, 5]), ([DisplayMode("sports")], [3])],
            ) as schedule,
            patch.object(self.display, "display_clock", side_effect=lambda *a, **kw: render("clock", *a, **kw)),
            patch.object(self.display, "display_weather", side_effect=lambda *a, **kw: render("weather", *a, **kw)),
            patch.object(self.display, "display_sports", side_effect=lambda *a, **kw: render("sports", *a, **kw)),
        ):
            self.display.run()
        self.assertEqual(rendered, ["clock", "weather", "sports"])
        self.assertEqual(schedule.call_count, 2)

    def test_nested_train_rendering_preserves_canvas_and_skips_remaining_stations(self) -> None:
        self.display.stop_ids = ["F23N", "R33N"]

        def draw(*args):
            self.display.display_control.request(DisplayMode("trains"))
            return (True, self.swapped_canvas)

        with (
            patch.object(main, "mta_update_feeds"),
            patch.object(main, "mta_get_next_trains"),
            patch.object(self.display, "draw_trains", side_effect=draw) as draw_trains,
        ):
            self.assertIs(self.display.display_trains(self.canvas), self.swapped_canvas)
        draw_trains.assert_called_once()

    def test_train_slides_return_after_first_interrupted_wait(self) -> None:
        with patch.object(main, "DUMMY_DATA", True):
            trains = main.mta_get_next_trains(stop_id="F23N")
        with (
            patch.object(self.display, "draw_train"),
            patch.object(
                self.display,
                "wait_for_display_interrupt",
                side_effect=lambda seconds: self.display.display_control.request(DisplayMode("trains")) or True,
            ),
        ):
            _, canvas = self.display.draw_trains(trains, "F23N", self.canvas, 5)
        self.assertIs(canvas, self.swapped_canvas)
        self.display.matrix.SwapOnVSync.assert_called_once()

    def test_weather_returns_before_forecast_slides_when_interrupted(self) -> None:
        with (
            patch.object(main, "DUMMY_DATA", True),
            patch.object(self.display, "draw_weather_summary"),
            patch.object(self.display, "draw_weather") as draw_weather,
            patch.object(self.display, "wait_for_display_interrupt", return_value=True),
        ):
            canvas = self.display.display_weather(self.canvas)
        self.assertIs(canvas, self.swapped_canvas)
        draw_weather.assert_not_called()
        self.display.matrix.SwapOnVSync.assert_called_once()

    def test_clock_returns_after_first_interrupted_tick(self) -> None:
        self.display.font = Mock()
        self.display.circle_font = Mock()
        self.display.text_colour = Mock()
        with (
            patch.object(main, "DUMMY_DATA", True),
            patch.object(main.graphics, "DrawText"),
            patch.object(self.display, "wait_for_display_interrupt", return_value=True) as wait,
        ):
            canvas = self.display.display_clock(self.canvas, display_time=30)
        self.assertIs(canvas, self.swapped_canvas)
        wait.assert_called_once_with(0.5)
        self.display.matrix.SwapOnVSync.assert_called_once()

    def test_sports_returns_before_remaining_games_when_interrupted(self) -> None:
        with (
            patch.object(main, "DUMMY_DATA", True),
            patch.object(self.display, "draw_game"),
            patch.object(self.display, "wait_for_display_interrupt", return_value=True),
        ):
            canvas = self.display.display_sports(self.canvas)
        self.assertIs(canvas, self.swapped_canvas)
        self.display.matrix.SwapOnVSync.assert_called_once()

    def test_seasonal_animations_return_after_first_interrupted_frame(self) -> None:
        for renderer in (self.display.draw_seasonal_scroll_up, self.display.draw_seasonal_scroll_up_animate_centre):
            with (
                self.subTest(renderer=renderer.__name__),
                patch.object(self.display, "wait_for_display_interrupt", return_value=True),
            ):
                self.display.matrix.SwapOnVSync.reset_mock()
                canvas = renderer(self.canvas, "images/halloween_anim.gif", 5)
                self.assertIs(canvas, self.swapped_canvas)
                self.display.matrix.SwapOnVSync.assert_called_once()


if __name__ == "__main__":
    unittest.main()

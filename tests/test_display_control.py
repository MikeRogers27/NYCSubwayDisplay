"""Verify command-driven interruption without a matrix or MQTT broker."""

import unittest
from threading import Event, Thread
from unittest.mock import Mock, patch

import paho.mqtt.client as mqtt

import main
from display_control import DisplayControl
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
            control.request("trains")
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(results, [True])
        finally:
            control.interrupt.set()
            worker.join(timeout=1)

    def test_timeout_and_command_consumption_reset_interrupt(self) -> None:
        control = DisplayControl()
        self.assertFalse(control.wait(0))
        control.request("clock")
        control.request("trains")
        self.assertTrue(control.wait(0))
        self.assertEqual(control.next_command(), "trains")
        self.assertFalse(control.wait(0))
        self.assertIsNone(control.next_command())
        control.request("weather")
        self.assertTrue(control.wait(0))
        self.assertEqual(control.next_command(), "weather")

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
        self.assertEqual(control.next_command(), "trains")
        self.assertEqual(listener.display_commands.qsize(), 5)


class RenderInterruptionTests(unittest.TestCase):
    def setUp(self) -> None:
        # Avoid fonts, GPIO, and emulator initialization for dispatcher tests.
        self.display = main.RunMatrix.__new__(main.RunMatrix)
        self.display.display_control = DisplayControl()
        self.display._remaining_rotation = []
        self.display.matrix = Mock()
        self.canvas = Mock()
        self.swapped_canvas = Mock()
        self.display.matrix.CreateFrameCanvas.return_value = self.canvas
        self.display.matrix.SwapOnVSync.return_value = self.swapped_canvas

    def test_requested_mode_is_prepended_to_the_normal_rotation(self) -> None:
        with patch.object(self.display, "scheduled_display", return_value=(["clock"], [30])):
            self.display.display_control.request("trains")
            self.display.display_control.request("trains")
            self.assertEqual(self.display.what_should_we_display(), (["trains", "clock"], [5, 30]))
            self.assertFalse(self.display.display_control.interrupt.is_set())
            self.assertEqual(self.display._remaining_rotation, [("trains", 5), ("clock", 30)])
            self.display._remaining_rotation.pop(0)
            self.assertEqual(self.display.what_should_we_display(), (["clock"], [30]))

    def test_repeated_request_does_not_stack_duplicate_entries(self) -> None:
        self.display._remaining_rotation = [("trains", 5), ("weather", 5)]
        self.display.display_control.request("trains")
        self.assertEqual(self.display.what_should_we_display(), (["trains", "weather"], [5, 5]))

    def test_clock_and_weather_commands_use_rotation_durations_and_preserve_position(self) -> None:
        for mode, duration in (("clock", 10), ("weather", 5)):
            with self.subTest(mode=mode):
                self.display._remaining_rotation = [("sports", 3), ("clock", 10), ("weather", 5)]
                self.display.display_control.request(mode)
                items, durations = self.display.what_should_we_display()
                self.assertEqual(items, [mode, "sports", "clock", "weather"])
                self.assertEqual(durations, [duration, 3, 10, 5])
                self.display._remaining_rotation.pop(0)
                self.assertEqual(self.display.what_should_we_display(), (["sports", "clock", "weather"], [3, 10, 5]))

    def test_commands_have_default_durations_when_not_in_current_rotation(self) -> None:
        for mode, duration in (("clock", 30), ("weather", 5)):
            with self.subTest(mode=mode):
                self.display._remaining_rotation = [("off", 600)]
                self.display.display_control.request(mode)
                self.assertEqual(self.display.what_should_we_display(), ([mode, "off"], [duration, 600]))

    def test_overnight_wait_switches_to_trains_then_back_to_schedule(self) -> None:
        killer = Mock(kill_now=False)
        waits = []

        def wait(seconds):
            waits.append(seconds)
            if len(waits) == 1:
                self.display.display_control.request("trains")
                return True
            killer.kill_now = True
            return False

        with (
            patch.object(main, "GracefulKiller", return_value=killer),
            patch.object(self.display, "scheduled_display", return_value=(["off"], [600])) as schedule,
            patch.object(
                self.display,
                "wait_for_display_interrupt",
                side_effect=wait,
            ),
            patch.object(self.display, "display_trains", return_value=self.swapped_canvas) as trains,
        ):
            self.display.run()
        self.assertEqual(waits, [600, 600])
        schedule.assert_called_once()
        trains.assert_called_once_with(self.swapped_canvas, display_time=5)

    def test_interrupt_resumes_current_mode_and_remaining_rotation(self) -> None:
        killer = Mock(kill_now=False)
        rendered = []

        def render(mode, canvas, display_time):
            rendered.append((mode, display_time))
            if rendered == [("clock", 30), ("weather", 5)]:
                self.display.display_control.request("trains")
            if mode == "sports":
                killer.kill_now = True
            return self.swapped_canvas

        with (
            patch.object(main, "GracefulKiller", return_value=killer),
            patch.object(
                self.display, "scheduled_display", return_value=(["clock", "weather", "sports"], [30, 5, 3])
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

        def render(mode, canvas, display_time):
            rendered.append(mode)
            if len(rendered) in (1, 2):
                self.display.display_control.request("trains")
            if mode == "weather":
                killer.kill_now = True
            return self.swapped_canvas

        with (
            patch.object(main, "GracefulKiller", return_value=killer),
            patch.object(self.display, "scheduled_display", return_value=(["clock", "weather"], [30, 5])),
            patch.object(self.display, "display_clock", side_effect=lambda *a, **kw: render("clock", *a, **kw)),
            patch.object(self.display, "display_weather", side_effect=lambda *a, **kw: render("weather", *a, **kw)),
            patch.object(self.display, "display_trains", side_effect=lambda *a, **kw: render("trains", *a, **kw)),
        ):
            self.display.run()
        self.assertEqual(rendered, ["clock", "trains", "trains", "clock", "weather"])

    def test_completed_rotation_refreshes_the_time_based_schedule(self) -> None:
        killer = Mock(kill_now=False)
        rendered = []

        def render(mode, canvas, display_time):
            rendered.append(mode)
            if mode == "sports":
                killer.kill_now = True
            return self.swapped_canvas

        with (
            patch.object(main, "GracefulKiller", return_value=killer),
            patch.object(
                self.display, "scheduled_display", side_effect=[(["clock", "weather"], [30, 5]), (["sports"], [3])]
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
            self.display.display_control.request("trains")
            return True, self.swapped_canvas

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
                side_effect=lambda seconds: self.display.display_control.request("trains") or True,
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
        with patch.object(main, "DUMMY_DATA", True), patch.object(main.graphics, "DrawText"), patch.object(
            self.display, "wait_for_display_interrupt", return_value=True
        ) as wait:
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
        for renderer in (
            self.display.draw_seasonal_scroll_up,
            self.display.draw_seasonal_scroll_up_animate_centre,
        ):
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

"""Verify sample service data works with HTTP requests and API clients forbidden."""

import io
import os
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import main


class DummyDataTests(unittest.TestCase):
    def setUp(self) -> None:
        for patcher in (
            patch.object(main, "DUMMY_DATA", True),
            patch.dict(os.environ, {}, clear=True),
            patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected HTTP request")),
            patch.object(main, "NYCTFeed", side_effect=AssertionError("Unexpected MTA client")),
            patch.object(main, "OWM", side_effect=AssertionError("Unexpected OWM client")),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_startup_needs_no_api_keys_and_enables_dummy_data_before_setup(self) -> None:
        # Simulate startup from the default live configuration.
        main.DUMMY_DATA = False
        with patch("sys.argv", ["main.py", "--dummy-data"]), patch.object(main, "RunMatrix") as display:
            display.return_value.process.side_effect = lambda: self.assertIsNotNone(main.owm_get_weather()[0])
            with redirect_stdout(io.StringIO()) as output:
                main.main()
        self.assertTrue(main.DUMMY_DATA)
        display.return_value.process.assert_called_once()
        self.assertIn("API requests are disabled", output.getvalue())

    def test_mta_arrivals_work_for_both_stations_and_directions(self) -> None:
        main.mta_update_feeds()
        for stop in ("F23N", "F23S", "R33N", "R33S", "CUSTOMN"):
            with self.subTest(stop=stop):
                trains = main.mta_get_next_trains(max_num_trains=3, stop_id=stop)
                self.assertEqual(len(trains), 3)
                for train in trains:
                    self.assertLessEqual(main.mta_arrival_minutes(train, stop), 25)
                    self.assertTrue(train.underway)
                    self.assertLess(
                        datetime.now(tz=main.LOCAL_TZ).replace(tzinfo=None) - train.last_position_update,
                        timedelta(minutes=1),
                    )
        self.assertEqual(main.mta_get_next_trains(max_arrival_mins=2), [])

    def test_owm_current_weather_and_all_forecast_windows(self) -> None:
        weather, forecast = main.owm_get_weather()
        self.assertEqual(main.k_to_c(weather.temp["temp"]), 18)
        self.assertTrue(Path(main.owm_weather_to_icon(weather)).is_file())
        self.assertEqual(len(forecast.forecast.weathers), 40)
        for get_forecasts in (
            main.owm_forecasts_today,
            main.owm_forecasts_evening,
            main.owm_forecasts_tomorrow,
        ):
            with self.subTest(forecast=get_forecasts.__name__):
                self.assertTrue(get_forecasts())

    def test_sports_returns_samples_without_reading_or_writing_live_cache(self) -> None:
        with (
            patch.object(main, "sports_retrieve_from_cache", side_effect=AssertionError("Live cache read")),
            patch.object(main, "sports_save_to_cache", side_effect=AssertionError("Live cache write")),
        ):
            for service in ("RAPI_FOOTBALL", "RAPI_RUGBY", "SGO"):
                with self.subTest(service=service):
                    # Even an already-populated live cache must be ignored.
                    games, _, _, updates = main.sports_get_games(
                        service, [object()], datetime.now(tz=main.LOCAL_TZ), None, {"live-game": None}, 60
                    )
                    self.assertTrue(games)
                    self.assertEqual(set(updates), {game.id() for game in games})
                    self.assertTrue(all(game.id().startswith("dummy-") for game in games))
        self.assertEqual({game.league_id() for game in main.sgo_get_games()}, {"MLB", "NHL", "NFL", "MLS"})

    def test_individual_game_refreshes_and_team_metadata_stay_local(self) -> None:
        games = main.rapi_football_get_games() + main.rapi_rugby_get_games() + main.sgo_get_games()
        updates = {game.id(): datetime.now(tz=main.LOCAL_TZ) - timedelta(days=1) for game in games}
        main.sports_update_games(games, updates, 0)
        for game in games:
            self.assertIs(game.update(updates)[0], game)
            self.assertTrue(Path(game.icon()).is_file())
            self.assertIsInstance(game.home_team_score_str(), str)
            self.assertIsInstance(game.away_team_score_str(), str)
            self.assertIsInstance(game.date_str(), str)
        football = games[0]
        with patch.object(football, "_save_team_info", side_effect=AssertionError("Team cache write")):
            football._update_team_info_from_api(999999, {"name": "Example"})
            self.assertEqual(football._get_team_info(999999, {"name": "Example"})["short_name"], "EXA")

    def test_sample_data_can_be_drawn_with_existing_renderers(self) -> None:
        display = main.RunMatrix([], [], Mock())
        canvas = Mock()
        with patch.object(main.graphics, "DrawText"), patch.object(main.graphics, "DrawLine"):
            for game in main.rapi_football_get_games() + main.rapi_rugby_get_games() + main.sgo_get_games():
                display.draw_game(canvas, game)
            weather, _ = main.owm_get_weather()
            display.draw_weather(canvas, weather)
            display.draw_weather_summary(canvas, main.owm_forecasts_tomorrow(), "Tom")
            display.draw_train(0, 1, main.mta_get_next_trains()[0], "F23N", canvas)
        canvas.SetImage.assert_called()


class LiveDataTests(unittest.TestCase):
    def test_normal_mode_still_queries_sports_apis(self) -> None:
        response = Mock(status_code=200, headers={"x-ratelimit-requests-remaining": "100"})
        response.json.return_value = {"response": [], "success": True, "data": []}
        with (
            patch.object(main, "DUMMY_DATA", False),
            patch.dict(os.environ, {"RPA_API_KEY": "test-key", "SGO_API_KEY": "test-key"}),
            patch.object(main.requests, "request", return_value=response) as request,
            patch.object(main.requests, "get", return_value=response) as get,
        ):
            main.rapi_football_get_games_league(39, {})
            self.assertIn("api-football", request.call_args.args[1])
            response.status_code = 204
            main.rapi_rugby_get_games_league(main.RAPI_RUGBY_LEAGUE_NAMES, {})
            self.assertIn("rugbyapi2", request.call_args.args[1])
            response.status_code = 200
            main.sgo_get_games_league("MLB", {})
            self.assertIn("sportsgameodds", get.call_args.args[0])

    def test_normal_mode_still_constructs_real_service_clients(self) -> None:
        with (
            patch.object(main, "DUMMY_DATA", False),
            patch.object(main, "MTA_FEEDS", None),
            patch.object(main, "NYCTFeed") as feed,
        ):
            self.assertEqual(len(main.mta_get_feeds()), 3)
            self.assertEqual([call.args[0] for call in feed.call_args_list], ["F", "G", "R"])
        with (
            patch.object(main, "DUMMY_DATA", False),
            patch.object(main, "OWM_MGR", None),
            patch.object(main, "OWM_WEATHER", None),
            patch.object(main, "OWM_FORECAST", None),
            patch.object(main, "OWN_TIMESTAMP", None),
            patch.dict(os.environ, {"OWM_API_KEY": "test-key"}),
            patch.object(main, "OWM") as owm,
        ):
            main.owm_get_weather()
            owm.assert_called_once_with("test-key")
            owm.return_value.weather_manager.return_value.weather_at_place.assert_called_once_with("New York")


if __name__ == "__main__":
    unittest.main()

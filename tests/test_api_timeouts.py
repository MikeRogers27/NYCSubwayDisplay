"""Exercise timeout handling without making external API requests."""

import os
import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import requests
from pyowm.utils.config import get_default_config

import dummy_data
import main
from api_clients import HTTP_TIMEOUT, TimedNYCTFeed, weather_config


class APITimeoutTests(unittest.TestCase):
    def setUp(self) -> None:
        for patcher in (
            patch.object(main, "DUMMY_DATA", False),
            patch.dict(
                os.environ,
                {"RPA_API_KEY": "test", "SGO_API_KEY": "test", "OWM_API_KEY": "test"},
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_sports_refreshes_return_after_connect_and_read_timeouts(self) -> None:
        now = datetime.now(tz=main.LOCAL_TZ)
        with patch.object(main.GameRAPIFootball, "RAPI_TEAM_INFO", {}):
            games = [
                main.GameRAPIFootball(dummy_data.football(now, 39, 746)[0]),
                main.GameRAPIRugby(dummy_data.rugby(now)[0]),
                main.GameSGO(dummy_data.sgo(now, "MLB")[0]),
            ]
        for error in (requests.ConnectTimeout, requests.ReadTimeout):
            for game in games:
                with (
                    self.subTest(error=error, game=type(game).__name__),
                    patch(
                        "requests.sessions.Session.send", side_effect=error("timed out")
                    ) as send,
                    self.assertLogs("NYCSubwayDisplay", level="ERROR"),
                ):
                    timestamps = {}
                    self.assertEqual(game.update(timestamps), (game, timestamps))
                    self.assertEqual(send.call_args.kwargs["timeout"], HTTP_TIMEOUT)

    def test_sports_listings_return_after_timeout(self) -> None:
        for fetch, league in (
            (main.rapi_football_get_games_league, 39),
            (main.rapi_rugby_get_games_league, main.RAPI_RUGBY_LEAGUE_NAMES),
            (main.sgo_get_games_league, "MLB"),
        ):
            with (
                self.subTest(fetch=fetch.__name__),
                patch(
                    "requests.sessions.Session.send",
                    side_effect=requests.ReadTimeout("timed out"),
                ) as send,
                self.assertLogs("NYCSubwayDisplay", level="ERROR"),
            ):
                timestamps = {}
                self.assertEqual(fetch(league, timestamps), ([], timestamps))
                self.assertEqual(send.call_args.kwargs["timeout"], HTTP_TIMEOUT)

    def test_mta_constructor_and_refresh_both_use_timeouts(self) -> None:
        response = Mock(status_code=200, content=b"")
        with patch("requests.get", return_value=response) as get:
            feed = TimedNYCTFeed("F")
            feed.refresh()
            self.assertEqual(get.call_count, 2)
            for call in get.call_args_list:
                self.assertEqual(call.kwargs["timeout"], HTTP_TIMEOUT)
            self.assertEqual(feed.trips, [])

    def test_mta_initial_timeout_returns_no_feeds(self) -> None:
        with (
            patch.object(main, "MTA_FEEDS", None),
            patch("requests.get", side_effect=requests.ReadTimeout("timed out")),
            self.assertLogs("NYCSubwayDisplay", level="ERROR"),
        ):
            self.assertIsNone(main.mta_get_feeds())

    def test_mta_refresh_timeout_keeps_existing_feed_and_continues(self) -> None:
        failed, next_feed = Mock(), Mock()
        failed.refresh.side_effect = requests.ReadTimeout("timed out")
        with (
            patch.object(main, "MTA_TIMESTAMP", None),
            patch.object(main, "MTA_FEEDS", [failed, next_feed]),
            self.assertLogs("NYCSubwayDisplay", level="ERROR"),
        ):
            main.mta_update_feeds()
            next_feed.refresh.assert_called_once()
            self.assertIs(main.MTA_FEEDS[0], failed)

    def test_weather_timeout_reaches_http_client_and_is_handled(self) -> None:
        with (
            patch.object(main, "OWM_MGR", None),
            patch.object(main, "OWM_WEATHER", None),
            patch.object(main, "OWM_FORECAST", None),
            patch.object(main, "OWN_TIMESTAMP", None),
            patch(
                "requests.sessions.Session.send",
                side_effect=requests.ReadTimeout("timed out"),
            ) as send,
            self.assertLogs("NYCSubwayDisplay", level="ERROR"),
        ):
            self.assertEqual(main.owm_get_weather(), (None, None))
            self.assertEqual(send.call_args.kwargs["timeout"], 5)

    def test_weather_config_does_not_mutate_library_defaults(self) -> None:
        config = weather_config()
        config["connection"]["timeout_secs"] = None
        self.assertEqual(get_default_config()["connection"]["timeout_secs"], 5)
        self.assertEqual(weather_config()["connection"]["timeout_secs"], 5)

    def test_team_lookup_timeout_uses_default_info(self) -> None:
        with (
            patch.object(main.GameRAPIFootball, "RAPI_TEAM_INFO", {}),
            patch.object(main.GameRAPIFootball, "_save_team_info"),
            patch(
                "requests.sessions.Session.send",
                side_effect=requests.ReadTimeout("timed out"),
            ) as send,
            self.assertLogs("NYCSubwayDisplay", level="ERROR"),
        ):
            game = main.GameRAPIFootball({})
            game._update_team_info_from_api(746, {"name": "Sunderland"})
            self.assertEqual(
                main.GameRAPIFootball.RAPI_TEAM_INFO["746"]["short_name"], "SUN"
            )
            self.assertEqual(send.call_args.kwargs["timeout"], HTTP_TIMEOUT)

    def test_key_selection_continues_after_timeout(self) -> None:
        response = Mock(status_code=200)
        response.json.return_value = {"data": {"isActive": True, "rateLimits": {}}}
        with (
            patch.dict(os.environ, {"SGO_API_KEYS": "first,second"}, clear=True),
            patch(
                "requests.get",
                side_effect=[requests.ReadTimeout("timed out"), response],
            ) as get,
            self.assertLogs("NYCSubwayDisplay", level="ERROR"),
        ):
            main.setup_env()
            self.assertEqual(os.environ["SGO_API_KEY"], "second")
            for call in get.call_args_list:
                self.assertEqual(call.kwargs["timeout"], HTTP_TIMEOUT)

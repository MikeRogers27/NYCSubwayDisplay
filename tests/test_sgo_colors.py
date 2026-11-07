"""Keep SGO games drawable when optional team colors are absent."""

import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import dummy_data
import main
from matrix_backend import graphics


class SGOColorTests(unittest.TestCase):
    def test_missing_or_invalid_colors_do_not_prevent_rendering(self) -> None:
        display = main.RunMatrix([], [], Mock())
        for colors in (None, {}, {"primary": None}, {"primary": ""}, {"primary": "invalid"}):
            for omit_colors in (False, True):
                with self.subTest(colors=colors, omit_colors=omit_colors):
                    event = dummy_data.sgo(datetime.now(tz=main.LOCAL_TZ), "NHL")[0]
                    for team in event["teams"].values():
                        if omit_colors:
                            del team["colors"]
                        else:
                            team["colors"] = colors
                    game = main.GameSGO(event)
                    for color in (game.home_team_colour(), game.away_team_colour()):
                        self.assertEqual((color.red, color.green, color.blue), (255, 255, 255))
                    with patch.object(graphics, "DrawText"), patch.object(graphics, "DrawLine"):
                        display.draw_game(Mock(), game)

    def test_valid_team_colors_are_preserved(self) -> None:
        event = dummy_data.sgo(datetime.now(tz=main.LOCAL_TZ), "NHL")[0]
        game = main.GameSGO(event)
        home = game.home_team_colour()
        away = game.away_team_colour()
        self.assertEqual((home.red, home.green, home.blue), (0, 90, 156))
        self.assertEqual((away.red, away.green, away.blue), (204, 0, 0))

    def test_team_overrides_work_without_api_colors(self) -> None:
        for team_id, expected in (
            ("CHICAGO_WHITE_SOX_MLB", (255, 255, 255)),
            ("SAN_FRANCISCO_GIANTS_MLB", (253, 90, 30)),
            ("PITTSBURGH_PIRATES_MLB", (253, 184, 39)),
        ):
            with self.subTest(team_id=team_id):
                event = dummy_data.sgo(datetime.now(tz=main.LOCAL_TZ), "MLB")[0]
                for team in event["teams"].values():
                    team["teamID"] = team_id
                    del team["colors"]
                game = main.GameSGO(event)
                for color in (game.home_team_colour(), game.away_team_colour()):
                    self.assertEqual((color.red, color.green, color.blue), expected)

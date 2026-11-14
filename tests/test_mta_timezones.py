"""Regression tests for NYCT timestamps across daylight saving transitions."""

import os
import time
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from nyct_gtfs.stop_time_update import StopTimeUpdate

import main


@unittest.skipUnless(hasattr(time, "tzset"), "Requires system timezone switching")
class MTATimezoneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(os.environ, {"TZ": "America/New_York"})
        self.environment.start()
        time.tzset()
        self.addCleanup(self.restore_timezone)

    def restore_timezone(self) -> None:
        self.environment.stop()
        time.tzset()

    def arrival_update(self, instant: datetime) -> StopTimeUpdate:
        """Exercise the installed NYCT parser without downloading a feed."""
        raw = SimpleNamespace(
            stop_id="F23N",
            arrival=SimpleNamespace(time=int(instant.timestamp())),
            HasField=lambda field: field == "arrival",
        )
        return StopTimeUpdate(raw, stops={})

    def test_both_occurrences_of_reported_arrival_keep_their_exact_instant(self) -> None:
        for hour, fold, offset in ((5, 0, -4), (6, 1, -5)):
            with self.subTest(fold=fold):
                instant = datetime(2026, 11, 1, hour, 8, 30, tzinfo=UTC)
                update = self.arrival_update(instant)
                self.assertEqual(update.arrival.fold, fold)
                train = SimpleNamespace(
                    location_status="IN_TRANSIT_TO", stop_time_updates=[update]
                )
                arrival = main.mta_arrival_time(train, "F23N")
                self.assertEqual(arrival.astimezone(UTC), instant)
                self.assertEqual(arrival.utcoffset(), timedelta(hours=offset))
                with patch.object(main, "NOW", instant - timedelta(minutes=3)):
                    self.assertEqual(main.mta_arrival_minutes(train, "F23N"), 3)

    def test_countdown_crosses_autumn_clock_change(self) -> None:
        update = self.arrival_update(datetime(2026, 11, 1, 6, 8, 30, tzinfo=UTC))
        train = SimpleNamespace(location_status="IN_TRANSIT_TO", stop_time_updates=[update])
        now = datetime(2026, 11, 1, 5, 58, 30, tzinfo=UTC)
        with patch.object(main, "NOW", now.astimezone(main.LOCAL_TZ)):
            self.assertEqual(main.mta_arrival_minutes(train, "F23N"), 10)

    def test_spring_change_skips_nonexistent_hour(self) -> None:
        before = datetime(2027, 3, 14, 6, 58, tzinfo=UTC)
        after = datetime(2027, 3, 14, 7, 8, tzinfo=UTC)
        converted = [main.mta_local_time(self.arrival_update(t).arrival) for t in (before, after)]
        self.assertEqual([t.hour for t in converted], [1, 3])
        self.assertEqual(converted[1] - converted[0], timedelta(minutes=10))

    def test_system_timezone_can_differ_from_new_york(self) -> None:
        os.environ["TZ"] = "UTC"
        time.tzset()
        instant = datetime(2026, 11, 1, 6, 8, 30, tzinfo=UTC)
        arrival = main.mta_local_time(self.arrival_update(instant).arrival)
        self.assertEqual(arrival.hour, 1)
        self.assertEqual(arrival.astimezone(UTC), instant)

    def test_aware_fixture_keeps_its_instant(self) -> None:
        for is_dst in (True, False):
            with self.subTest(is_dst=is_dst):
                wall_time = datetime(2026, 11, 1, 1, 8, 30)  # noqa: DTZ001 -- Test both localizations of a naive time.
                aware = main.LOCAL_TZ.localize(wall_time, is_dst=is_dst)
                self.assertEqual(main.mta_local_time(aware).timestamp(), aware.timestamp())

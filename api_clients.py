"""Explicit timeout policies for APIs used by the display."""

from copy import deepcopy
from typing import Any

import requests
from nyct_gtfs import NYCTFeed
from pyowm.utils.config import get_default_config

HTTP_TIMEOUT: tuple[int, int] = (5, 15)


def weather_config() -> dict[str, Any]:
    """Preserve PyOWM's five-second timeout without mutating its defaults."""
    config = deepcopy(get_default_config())
    config["connection"]["timeout_secs"] = 5
    return config


class TimedNYCTFeed(NYCTFeed):
    """Apply timeouts during both construction and later feed refreshes."""

    def refresh(self) -> None:
        """Fetch using NYCTFeed 2.0's URL and public GTFS parsing interface."""
        # The pinned library exposes no timeout option for its own refresh().
        response = requests.get(self._feed_url, timeout=HTTP_TIMEOUT)
        if response.status_code != 200:
            raise RuntimeError(f"Error accessing MTA data feed: {response.content}")
        self.load_gtfs_bytes(response.content)

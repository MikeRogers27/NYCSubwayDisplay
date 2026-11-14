"""Capture stalled display stacks without relying on the Python main thread."""

import faulthandler
import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from time import monotonic

LOG = logging.getLogger("NYCSubwayDisplay")


class DisplayDiagnostics:
    """Dump all thread stacks after two minutes without display progress."""

    def __init__(self, stall_seconds: float = 120) -> None:
        self.stall_seconds = stall_seconds
        self.active = False

    def progress(self, expected_wait: float = 0) -> None:
        """Allow intentional screen holds before starting the stall deadline."""
        if self.active:
            faulthandler.dump_traceback_later(
                self.stall_seconds + expected_wait,
                repeat=True,
                file=sys.stderr,
            )

    @contextmanager
    def mode(self, name: str) -> Iterator[None]:
        """Log mode boundaries and arm a native watchdog until the mode returns."""
        started = monotonic()
        LOG.info("Display mode started: %s (pid=%s)", name, os.getpid())
        self.active = True
        self.progress()
        try:
            yield
        finally:
            self.active = False
            faulthandler.cancel_dump_traceback_later()
            LOG.info("Display mode ended: %s elapsed=%.3fs", name, monotonic() - started)

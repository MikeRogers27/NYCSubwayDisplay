"""Timestamp Python console output captured by the matrix service."""

import logging
import sys
from datetime import datetime
from threading import RLock
from typing import TextIO


class TimestampedStream:
    """Prefix each output line without delaying partial writes or tracebacks."""

    def __init__(self, stream: TextIO) -> None:
        self.stream: TextIO = stream
        self._line_start: bool = True
        self._lock: RLock = RLock()

    def write(self, text: str) -> int:
        """Write immediately, retaining line state across separate print writes."""
        with self._lock:
            for part in text.splitlines(keepends=True):
                if self._line_start:
                    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
                    self.stream.write(f"{timestamp} ")
                self.stream.write(part)
                self._line_start = part.endswith("\n")
            return len(text)

    def flush(self) -> None:
        """Flush the underlying console or redirected log file."""
        with self._lock:
            self.stream.flush()

    @property
    def encoding(self) -> str | None:
        """Expose the wrapped stream's encoding, if it has one."""
        return self.stream.encoding

    def isatty(self) -> bool:
        """Report whether the wrapped stream is connected to a terminal."""
        return self.stream.isatty()

    def fileno(self) -> int:
        """Return the wrapped descriptor, preserving errors for in-memory streams."""
        return self.stream.fileno()

    def __getattr__(self, name: str) -> object:
        """Delegate extra attributes without disabling type checking for callers."""
        return getattr(self.stream, name)


def configure_console_logging(level: int) -> None:
    """Timestamp stdout, stderr, and logging records without duplicate prefixes."""
    if not isinstance(sys.stdout, TimestampedStream):
        sys.stdout = TimestampedStream(sys.stdout)
    if not isinstance(sys.stderr, TimestampedStream):
        sys.stderr = TimestampedStream(sys.stderr)
    logging.basicConfig(
        level=level,
        format="%(levelname)s:%(message)s",
        stream=sys.stderr,
        force=True,
    )

"""Wake the render thread when a queued display command arrives."""

from queue import Empty, SimpleQueue
from threading import Event, Lock


class DisplayControl:
    """Keep commands queued until the scheduler consumes them."""

    def __init__(self) -> None:
        self.commands: SimpleQueue[str] = SimpleQueue()
        self.interrupt = Event()
        self._lock = Lock()

    def request(self, mode: str) -> None:
        """Queue a mode and immediately wake an active display wait."""
        with self._lock:
            self.commands.put(mode)
            self.interrupt.set()

    def next_command(self) -> str | None:
        """Consume pending commands, keeping the latest, and reset the wake signal."""
        with self._lock:
            latest = None
            while True:
                try:
                    latest = self.commands.get_nowait()
                except Empty:
                    break
            self.interrupt.clear()
            return latest

    def wait(self, seconds: float) -> bool:
        """Wait for the duration or return True immediately when interrupted."""
        return self.interrupt.wait(timeout=seconds)

"""Report MQTT messages and optionally forward display commands to the app."""

import argparse
import signal
from collections.abc import Callable
from queue import Empty, SimpleQueue
from threading import Event, Thread
from typing import Any

import paho.mqtt.client as mqtt

from display_control import DisplayMode

DEFAULT_MQTT_TOPIC = "matrix/display/+/set"
TOPIC_MODES = {
    "train": DisplayMode("trains"),
    "f-trains": DisplayMode("trains", stop_ids=("F23N",)),
    "r-trains": DisplayMode("trains", stop_ids=("R33N",)),
    "clock": DisplayMode("clock"),
    "weather": DisplayMode("weather"),
}


class MQTTListener:
    """Receive messages on a network thread and consume them on a console thread."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 1883,
        topic: str = DEFAULT_MQTT_TOPIC,
        on_command: Callable[[DisplayMode], None] | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.topic = topic
        self.on_command = on_command
        self.display_commands: SimpleQueue[mqtt.MQTTMessage] = SimpleQueue()
        self._stop = Event()
        self._reporter = Thread(target=self._report_messages, name="mqtt-console", daemon=True)
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_connect_fail = self._on_connect_fail
        self.client.on_message = self._on_message

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        if reason_code != 0:
            print(f"MQTT connection rejected: {reason_code}", flush=True)
            return
        result, _ = client.subscribe(self.topic)
        if result != mqtt.MQTT_ERR_SUCCESS:
            print(f"MQTT subscription request failed: {mqtt.error_string(result)}", flush=True)
            return
        print(f"MQTT connected; subscription requested: {self.topic}", flush=True)

    def _on_connect_fail(self, client: mqtt.Client, userdata: Any) -> None:
        print(f"MQTT unable to connect to {self.host}:{self.port}; retrying", flush=True)

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        self.display_commands.put(message)
        mode = self._message_mode(message)
        if self.on_command is not None and mode is not None:
            self.on_command(mode)

    def _message_mode(self, message: mqtt.MQTTMessage) -> DisplayMode | None:
        if message.payload != b"ON" or not mqtt.topic_matches_sub(self.topic, message.topic):
            return None
        parts = message.topic.rsplit("/", 2)
        if len(parts) == 3 and parts[-1] == "set":
            return TOPIC_MODES.get(parts[-2])
        # Preserve custom exact-topic aliases previously used for trains.
        return DisplayMode("trains") if message.topic == self.topic else None

    def _report_messages(self) -> None:
        while not self._stop.is_set():
            try:
                message = self.display_commands.get(timeout=0.2)
            except Empty:
                continue
            self._report_message(message)

    def _report_message(self, message: mqtt.MQTTMessage) -> None:
        mode = self._message_mode(message)
        command = f" -> command={mode.name!r}" if mode is not None else ""
        if mode is not None and mode.stop_ids is not None:
            command += f" stop_ids={mode.stop_ids!r}"
        print(f"MQTT topic={message.topic!r} payload={message.payload!r}{command}", flush=True)

    def start(self) -> None:
        """Start background connection retries, message reception, and reporting."""
        self.client.connect_async(self.host, self.port)
        result = self.client.loop_start()
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Unable to start MQTT listener: {mqtt.error_string(result)}")
        self._reporter.start()
        print(f"MQTT listening via {self.host}:{self.port} for {self.topic!r}", flush=True)

    def stop(self) -> None:
        """Disconnect, stop both threads, and report any remaining queued messages."""
        self.client.disconnect()
        self.client.loop_stop()
        self._stop.set()
        if self._reporter.ident is not None:
            self._reporter.join()
        while True:
            try:
                message = self.display_commands.get_nowait()
            except Empty:
                break
            self._report_message(message)


def add_mqtt_arguments(parser: argparse.ArgumentParser) -> None:
    """Add broker connection options shared by the display and standalone listener."""
    parser.add_argument("--mqtt-host", default="127.0.0.1", help="MQTT broker host (default: 127.0.0.1)")
    parser.add_argument("--mqtt-port", default=1883, type=int, help="MQTT broker port (default: 1883)")
    parser.add_argument(
        "--mqtt-topic",
        default=DEFAULT_MQTT_TOPIC,
        help="MQTT subscription filter (default: matrix/display/+/set; + matches train, f-trains, r-trains, clock, or weather)",
    )


def main() -> None:
    """Run the console listener without the matrix or external API keys."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_mqtt_arguments(parser)
    args = parser.parse_args()
    shutdown = Event()
    signal.signal(signal.SIGINT, lambda signum, frame: shutdown.set())
    signal.signal(signal.SIGTERM, lambda signum, frame: shutdown.set())
    listener = MQTTListener(args.mqtt_host, args.mqtt_port, args.mqtt_topic)
    try:
        listener.start()
        shutdown.wait()
    finally:
        listener.stop()


if __name__ == "__main__":
    main()

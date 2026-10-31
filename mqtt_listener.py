"""Report MQTT messages and optionally forward display commands to the app."""

import argparse
import signal
from collections.abc import Callable
from queue import Empty, SimpleQueue
from threading import Event, Thread
from typing import Any

import paho.mqtt.client as mqtt


class MQTTListener:
    """Receive messages on a network thread and consume them on a console thread."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 1883,
        topic: str = "matrix/display/train/set",
        on_command: Callable[[str], None] | None = None,
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
        if self.on_command is not None and message.topic == self.topic and message.payload == b"ON":
            self.on_command("trains")

    def _report_messages(self) -> None:
        while not self._stop.is_set():
            try:
                message = self.display_commands.get(timeout=0.2)
            except Empty:
                continue
            self._report_message(message)

    def _report_message(self, message: mqtt.MQTTMessage) -> None:
        command = " -> command='trains'" if message.topic == self.topic and message.payload == b"ON" else ""
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
        "--mqtt-topic", default="matrix/display/train/set", help="MQTT subscription topic (default: matrix/display/train/set)"
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

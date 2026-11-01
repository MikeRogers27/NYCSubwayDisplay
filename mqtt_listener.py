"""Run the standalone MQTT console listener without the matrix display."""

import argparse
import signal
from threading import Event

from utils.mqtt_listener import MQTTListener, add_mqtt_arguments


def main() -> None:
    """Run the console listener without the matrix or external API keys."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_mqtt_arguments(parser)
    args = parser.parse_args()
    shutdown = Event()
    signal.signal(signal.SIGINT, lambda signum, frame: shutdown.set())
    signal.signal(signal.SIGTERM, lambda signum, frame: shutdown.set())
    listener = MQTTListener(
        args.mqtt_host,
        args.mqtt_port,
        args.mqtt_topic,
        matterbridge=args.matterbridge,
        matterbridge_topic=args.matterbridge_topic,
    )
    try:
        listener.start()
        shutdown.wait()
    finally:
        listener.stop()


if __name__ == "__main__":
    main()

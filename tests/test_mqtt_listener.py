"""Check queue delivery, subscriptions, and listener lifecycle without a broker."""

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import paho.mqtt.client as mqtt

from mqtt_listener import MQTTListener


class MQTTListenerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.listener = MQTTListener()

    def test_subscribes_after_every_successful_connection(self) -> None:
        client = Mock()
        client.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
        with redirect_stdout(io.StringIO()):
            for _ in range(2):
                self.listener._on_connect(client, None, mqtt.ConnectFlags(False), 0, None)
        self.assertEqual(client.subscribe.call_count, 2)
        client.subscribe.assert_called_with("matrix/display/+/set")

    def test_supported_topics_forward_and_report_the_matching_mode(self) -> None:
        callback = Mock()
        listener = MQTTListener(on_command=callback)
        for topic, mode in (("train", "trains"), ("clock", "clock"), ("weather", "weather")):
            with self.subTest(topic=topic):
                message = mqtt.MQTTMessage(topic=f"matrix/display/{topic}/set".encode())
                message.payload = b"ON"
                listener._on_message(listener.client, None, message)
                callback.assert_called_with(mode)
                with redirect_stdout(io.StringIO()) as output:
                    listener._report_message(message)
                self.assertIn(f"command={mode!r}", output.getvalue())

    def test_unsupported_topics_and_off_do_not_forward_commands(self) -> None:
        callback = Mock()
        listener = MQTTListener(on_command=callback)
        for topic in ("matrix/display/clock/set", "matrix/display/weather/set", "matrix/display/sports/set", "other/display/clock/set"):
            for payload in (b"OFF", b"ON"):
                if topic in ("matrix/display/clock/set", "matrix/display/weather/set") and payload == b"ON":
                    continue
                message = mqtt.MQTTMessage(topic=topic.encode())
                message.payload = payload
                listener._on_message(listener.client, None, message)
        callback.assert_not_called()

    def test_custom_subscription_can_restrict_commands(self) -> None:
        callback = Mock()
        listener = MQTTListener(topic="matrix/display/clock/set", on_command=callback)
        for topic in ("train", "clock", "weather"):
            message = mqtt.MQTTMessage(topic=f"matrix/display/{topic}/set".encode())
            message.payload = b"ON"
            listener._on_message(listener.client, None, message)
        callback.assert_called_once_with("clock")

    def test_connection_rejection_does_not_subscribe(self) -> None:
        client = Mock()
        with redirect_stdout(io.StringIO()) as output:
            self.listener._on_connect(client, None, mqtt.ConnectFlags(False), 135, None)
        client.subscribe.assert_not_called()
        self.assertIn("connection rejected", output.getvalue())

    def test_callback_queues_all_messages_in_order_without_printing(self) -> None:
        messages = []
        with redirect_stdout(io.StringIO()) as output:
            for payload in (b"ON", b"OFF", b"\xff"):
                message = mqtt.MQTTMessage(topic=b"matrix/display/train/set")
                message.payload = payload
                messages.append(message)
                self.listener._on_message(self.listener.client, None, message)
        self.assertEqual(output.getvalue(), "")
        for message in messages:
            self.assertIs(self.listener.display_commands.get_nowait(), message)
        self.assertTrue(self.listener.display_commands.empty())

    def test_background_reporting_and_shutdown_drain_queue(self) -> None:
        with patch.object(self.listener, "client") as client, redirect_stdout(io.StringIO()) as output:
            client.loop_start.return_value = mqtt.MQTT_ERR_SUCCESS
            self.listener.start()
            try:
                for payload in (b"ON", b"OFF", b"\xff"):
                    message = mqtt.MQTTMessage(topic=b"matrix/display/train/set")
                    message.payload = payload
                    self.listener._on_message(client, None, message)
            finally:
                self.listener.stop()
        client.connect_async.assert_called_once_with("127.0.0.1", 1883)
        client.disconnect.assert_called_once()
        client.loop_stop.assert_called_once()
        self.assertFalse(self.listener._reporter.is_alive())
        self.assertTrue(self.listener.display_commands.empty())
        self.assertIn("payload=b'ON' -> command='trains'", output.getvalue())
        self.assertIn("payload=b'OFF'", output.getvalue())
        self.assertIn("payload=b'\\xff'", output.getvalue())

    def test_stop_after_failed_start(self) -> None:
        with patch.object(self.listener, "client") as client:
            client.loop_start.return_value = mqtt.MQTT_ERR_INVAL
            with self.assertRaises(RuntimeError):
                self.listener.start()
            self.listener.stop()
        self.assertFalse(self.listener._reporter.is_alive())


if __name__ == "__main__":
    unittest.main()

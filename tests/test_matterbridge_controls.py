"""Verify virtual control registration, activation, and momentary state feedback."""

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import paho.mqtt.client as mqtt

import main
from display_control import DisplayControl, DisplayMode
from matterbridge_controls import CONTROLS, MatterbridgeControls
from mqtt_listener import MQTTListener


class MatterbridgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = Mock()
        self.client.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
        self.client.publish.return_value.rc = mqtt.MQTT_ERR_SUCCESS

    def message(self, device_id: str, payload: bytes, retain: bool = False) -> mqtt.MQTTMessage:
        message = mqtt.MQTTMessage(topic=f"matterbridge/{device_id}/write/root".encode())
        message.payload = payload
        message.retain = retain
        return message

    def test_reconnect_announces_stable_retained_controls_and_restores_subscriptions(self) -> None:
        listener = MQTTListener(matterbridge=True)
        with redirect_stdout(io.StringIO()):
            for _ in range(2):
                listener._on_connect(self.client, None, mqtt.ConnectFlags(False), 0, None)
        subscriptions = [(f"matterbridge/{control.device_id}/write/root", 1) for control in CONTROLS.values()]
        self.assertEqual(self.client.subscribe.call_args_list[1].args[0], subscriptions)
        self.assertEqual(self.client.subscribe.call_args_list[3].args[0], subscriptions)
        calls = self.client.publish.call_args_list
        self.assertEqual(len(calls), 30)
        self.assertEqual(calls[:15], calls[15:])
        retained = {}
        for call in calls[:15]:
            topic, payload = call.args
            self.assertEqual(call.kwargs, {"qos": 1, "retain": True})
            retained[topic] = json.loads(payload)
        for control in CONTROLS.values():
            prefix = f"matterbridge/{control.device_id}"
            config = retained[f"{prefix}/config/root"]
            self.assertEqual(config["deviceTypes"], ["OnOffPlugInUnit"])
            self.assertEqual(config["clusters"]["BridgedDeviceBasicInformation"]["nodeLabel"], control.label)
            self.assertEqual(config["clusters"]["BridgedDeviceBasicInformation"]["serialNumber"], control.device_id)
            self.assertEqual(retained[f"{prefix}/state/root"], {"OnOff": {"onOff": False}})
            self.assertEqual(retained[f"{prefix}/subscribe/root"], {"OnOff": ["onOff"]})

    def test_every_control_can_be_activated_repeatedly_and_resets_without_feedback_loop(self) -> None:
        queue = DisplayControl()
        listener = MQTTListener(matterbridge=True, on_command=queue.request)
        for control in CONTROLS.values():
            with self.subTest(control=control.device_id):
                self.client.publish.reset_mock()
                for _ in range(2):
                    listener._on_message(
                        self.client, None, self.message(control.device_id, b'{"OnOff":{"onOff":true}}')
                    )
                    self.assertTrue(queue.interrupt.is_set())
                    self.assertEqual(queue.next_command(), control.mode)
                    topic, payload = self.client.publish.call_args.args
                    self.assertEqual(topic, f"matterbridge/{control.device_id}/state/root")
                    self.assertEqual(json.loads(payload), {"OnOff": {"onOff": False}})
                    # The plugin can echo the state reset back on the write topic.
                    listener._on_message(self.client, None, self.message(control.device_id, payload.encode()))
                    self.assertIsNone(queue.next_command())
                self.assertEqual(self.client.publish.call_count, 2)

    def test_malformed_false_retained_and_unrelated_messages_do_not_activate(self) -> None:
        callback = Mock()
        listener = MQTTListener(matterbridge=True, on_command=callback)
        payloads = (
            b"",
            b"invalid",
            b"\xff",
            b"null",
            b"[]",
            b"true",
            b"{}",
            b'{"OnOff":null}',
            b'{"OnOff":{"onOff":false}}',
            b'{"OnOff":{"onOff":1}}',
            b'{"OnOff":{"onOff":"true"}}',
        )
        for payload in payloads:
            listener._on_message(self.client, None, self.message("matrix-f-trains", payload))
        listener._on_message(
            self.client, None, self.message("matrix-f-trains", b'{"OnOff":{"onOff":true}}', retain=True)
        )
        listener._on_message(self.client, None, self.message("unknown-device", b'{"OnOff":{"onOff":true}}'))
        callback.assert_not_called()
        self.client.publish.assert_not_called()

    def test_disabled_integration_does_not_register_or_process_plugin_commands(self) -> None:
        callback = Mock()
        listener = MQTTListener(on_command=callback)
        with redirect_stdout(io.StringIO()):
            listener._on_connect(self.client, None, mqtt.ConnectFlags(False), 0, None)
        listener._on_message(self.client, None, self.message("matrix-f-trains", b'{"OnOff":{"onOff":true}}'))
        self.client.subscribe.assert_called_once_with("matrix/display/+/set")
        self.client.publish.assert_not_called()
        callback.assert_not_called()

    def test_custom_prefix_uses_same_control_ids_and_keeps_manual_commands_working(self) -> None:
        callback = Mock()
        listener = MQTTListener(matterbridge=True, matterbridge_topic="home/matrix/", on_command=callback)
        message = mqtt.MQTTMessage(topic=b"home/matrix/matrix-f-trains/write/root")
        message.payload = b'{"OnOff":{"onOff":true}}'
        listener._on_message(self.client, None, message)
        callback.assert_called_with(DisplayMode("trains", stop_ids=("F23N",)))
        self.assertEqual(self.client.publish.call_args.args[0], "home/matrix/matrix-f-trains/state/root")
        message = mqtt.MQTTMessage(topic=b"matrix/display/clock/set")
        message.payload = b"ON"
        listener._on_message(self.client, None, message)
        callback.assert_called_with(DisplayMode("clock"))

    def test_main_matterbridge_flag_enables_mqtt_without_mqtt_flag(self) -> None:
        with (
            patch("sys.argv", ["main.py", "--dummy-data", "--matterbridge"]),
            patch.object(main, "DUMMY_DATA", False),
            patch.object(main, "logger_setup"),
            patch.object(main, "setup_env"),
            patch.object(main, "RunMatrix") as display,
            patch.object(main, "MQTTListener") as listener,
            redirect_stdout(io.StringIO()),
        ):
            main.main()
        self.assertTrue(listener.call_args.kwargs["matterbridge"])
        self.assertEqual(listener.call_args.kwargs["matterbridge_topic"], "matterbridge")
        listener.call_args.kwargs["on_command"](DisplayMode("clock"))
        display.return_value.display_control.request.assert_called_once_with(DisplayMode("clock"))
        listener.return_value.start.assert_called_once()
        listener.return_value.stop.assert_called_once()

    def test_invalid_topic_prefix_is_rejected(self) -> None:
        for topic in ("", "/", "matterbridge/+", "matterbridge/#", "bad\x00topic"):
            with self.subTest(topic=topic), self.assertRaises(ValueError):
                MatterbridgeControls(topic)


if __name__ == "__main__":
    unittest.main()

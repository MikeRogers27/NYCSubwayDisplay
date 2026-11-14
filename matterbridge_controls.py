"""Register momentary display controls with the matterbridge-mqtt plugin."""

import json
from dataclasses import dataclass

import paho.mqtt.client as mqtt

from display_control import DisplayMode


@dataclass(frozen=True)
class VirtualControl:
    """A stable Matter endpoint and the display request it activates."""

    device_id: str
    label: str
    mode: DisplayMode


CONTROLS = {
    "train": VirtualControl("matrix-trains", "All Trains", DisplayMode("trains")),
    "f-trains": VirtualControl(
        "matrix-f-trains", "F Trains", DisplayMode("trains", stop_ids=("F23N",))
    ),
    "r-trains": VirtualControl(
        "matrix-r-trains", "R Trains", DisplayMode("trains", stop_ids=("R33N",))
    ),
    "clock": VirtualControl("matrix-clock", "Pixie Clock", DisplayMode("clock")),
    "weather": VirtualControl(
        "matrix-weather", "Pixie Weather", DisplayMode("weather")
    ),
}


class MatterbridgeControls:
    """Publish retained endpoint definitions and decode non-retained activations."""

    def __init__(self, topic: str = "matterbridge") -> None:
        self.topic = topic.rstrip("/")
        if (
            not self.topic
            or "+" in self.topic
            or "#" in self.topic
            or "\x00" in self.topic
        ):
            raise ValueError(
                "Matterbridge topic must be a nonempty prefix without MQTT wildcards"
            )
        self.write_topics = {
            self.device_topic(control, "write"): control
            for control in CONTROLS.values()
        }

    def device_topic(self, control: VirtualControl, kind: str) -> str:
        """Return the plugin's topic for one endpoint and message kind."""
        return f"{self.topic}/{control.device_id}/{kind}/root"

    def _publish(self, client: mqtt.Client, topic: str, payload: dict) -> None:
        result = client.publish(topic, json.dumps(payload), qos=1, retain=True)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(
                f"Matterbridge publish failed for {topic}: {mqtt.error_string(result.rc)}",
                flush=True,
            )

    def reset(self, client: mqtt.Client, control: VirtualControl) -> None:
        """Report a control as off so another on command can trigger it again."""
        self._publish(
            client, self.device_topic(control, "state"), {"OnOff": {"onOff": False}}
        )

    def register(self, client: mqtt.Client) -> None:
        """Subscribe to controls and announce them on every broker connection."""
        result, _ = client.subscribe([(topic, 1) for topic in self.write_topics])
        if result != mqtt.MQTT_ERR_SUCCESS:
            print(
                f"Matterbridge subscription failed: {mqtt.error_string(result)}",
                flush=True,
            )
            return
        for control in CONTROLS.values():
            config = {
                "deviceTypes": ["OnOffPlugInUnit"],
                "clusters": {
                    "BridgedDeviceBasicInformation": {
                        "nodeLabel": control.label,
                        "serialNumber": control.device_id,
                        "productName": "NYC Subway Display",
                    },
                    "OnOff": {"onOff": False},
                },
            }
            self._publish(client, self.device_topic(control, "config"), config)
            self.reset(client, control)
            self._publish(
                client, self.device_topic(control, "subscribe"), {"OnOff": ["onOff"]}
            )
        print(
            f"Matterbridge announced {len(CONTROLS)} display controls under {self.topic!r}",
            flush=True,
        )

    def message_mode(self, message: mqtt.MQTTMessage) -> DisplayMode | None:
        """Accept only boolean on activations for our controls, never retained commands."""
        control = self.write_topics.get(message.topic)
        if control is None or message.retain:
            return None
        try:
            payload = json.loads(message.payload)
        except (ValueError, UnicodeDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        on_off = payload.get("OnOff")
        if not isinstance(on_off, dict) or on_off.get("onOff") is not True:
            return None
        return control.mode

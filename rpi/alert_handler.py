"""
alert_handler.py
Raspberry Pi alert handler — subscribes to sepsis/status and drives
the GrovePi LED and buzzer based on patient status received from laptop.

Also subscribes to sepsis/acknowledge so the laptop dashboard can
silence the buzzer and switch to blinking amber.

MQTT topics:
  subscribe: sepsis/status       green / yellow / red from laptop
  subscribe: sepsis/acknowledge  clinician ack from dashboard
"""

import json
import time
import paho.mqtt.client as mqtt
from led_controller import apply_status, set_blink_amber, set_off

# ── Config ────────────────────────────────────────────────────────────────────

BROKER_IP    = "172.20.10.4"   # change to laptop's IP on real RPi
BROKER_PORT  = 1883
TOPIC_STATUS = "sepsis/status"
TOPIC_ACK    = "sepsis/acknowledge"

# ── State ─────────────────────────────────────────────────────────────────────

current_status = "green"
acknowledged   = False

# ── MQTT callbacks ────────────────────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to broker at {BROKER_IP}:{BROKER_PORT}")
        client.subscribe(TOPIC_STATUS)
        client.subscribe(TOPIC_ACK)
        print(f"[MQTT] Subscribed to {TOPIC_STATUS} and {TOPIC_ACK}")
        # start green on connect
        apply_status("green")
    else:
        print(f"[MQTT] Connection failed — code {rc}")


def on_message(client, userdata, msg):
    global current_status, acknowledged

    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"[WARN] Could not decode message on {msg.topic}")
        return

    if msg.topic == TOPIC_STATUS:
        status = payload.get("status", "green")
        delta  = payload.get("delta", 0)
        sofa   = payload.get("sofa_total", 0)

        # don't change LED if currently acknowledged and still elevated
        if acknowledged and status == "red":
            print(f"[STATUS] red (acknowledged — LED stays amber)")
            return

        # reset acknowledged flag when patient recovers
        if status != "red":
            acknowledged = False

        current_status = status
        apply_status(status)

        icon = {"green": "[G]", "yellow": "[Y]", "red": "[R!]"}.get(status, "[?]")
        print(f"{icon} Status={status}  SOFA={sofa}  delta={delta:+.1f}")

    elif msg.topic == TOPIC_ACK:
        if payload.get("acknowledged"):
            acknowledged = True
            set_blink_amber()
            print("[ACK] Alert acknowledged — LED switching to blinking amber")


def on_disconnect(client, userdata, rc):
    print("[MQTT] Disconnected — turning LED off")
    set_off()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("[ALERT HANDLER] Starting RPi alert handler")
    print(f"[ALERT HANDLER] Connecting to broker at {BROKER_IP}:{BROKER_PORT}\n")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_disconnect = on_disconnect

    client.connect(BROKER_IP, BROKER_PORT, keepalive=60)

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\n[ALERT HANDLER] Stopped by user")
    finally:
        set_off()
        client.disconnect()


if __name__ == "__main__":
    main()
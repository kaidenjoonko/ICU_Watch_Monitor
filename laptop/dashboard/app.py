"""
app.py
Flask dashboard server.

Exposes the shared state dict from server.py as JSON endpoints
and serves the dashboard HTML. Runs in a background thread
launched from server.py.

Routes:
  GET  /              serve dashboard HTML
  GET  /api/state     current state as JSON (polled every 2s by browser)
  POST /api/override  inject manual vital override
  POST /api/acknowledge  clinician acknowledges alert
"""

from flask import Flask, render_template, jsonify, request
import paho.mqtt.client as mqtt
import json
import threading

# import shared state and helpers from server
from server import (
    state, state_lock,
    set_override,
    BROKER_IP, BROKER_PORT,
    TOPIC_ACK,
)

app = Flask(__name__, template_folder="templates")

# ── MQTT client just for publishing acknowledge ───────────────────────────────
_pub_client      = None
_pub_client_lock = threading.Lock()

def get_pub_client():
    global _pub_client
    with _pub_client_lock:
        if _pub_client is None:
            _pub_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
            _pub_client.connect(BROKER_IP, BROKER_PORT, keepalive=60)
            _pub_client.loop_start()
        return _pub_client

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    """
    Returns the current system state as JSON.
    Called every 2 seconds by the dashboard via fetch().
    """
    with state_lock:
        # build a safe serializable snapshot
        snapshot = {
            "patient_id":    state["patient_id"],
            "session_active": state["session_active"],
            "alert_active":  state["alert_active"],
            "acknowledged":  state["acknowledged"],
            "latest_vitals": state["latest_vitals"],
            "latest_sofa":   state["latest_sofa"],
            "latest_trend":  state["latest_trend"],
            # last 60 readings for the trend chart
            "history": [
                {
                    "reading_num": h["reading_num"],
                    "timestamp":   h["timestamp"],
                    "sofa_total":  h["sofa"]["total"],
                    "status":      h["trend"]["status"],
                    "heart_rate":  h["vitals"].get("heart_rate"),
                    "spo2":        h["vitals"].get("spo2"),
                    "sbp":         h["vitals"].get("sbp"),
                    "resp_rate":   h["vitals"].get("resp_rate"),
                }
                for h in state["history"][-60:]
            ],
        }
    return jsonify(snapshot)


@app.route("/api/override", methods=["POST"])
def api_override():
    """
    Accepts a JSON body with any subset of vital keys.
    Merges into the next SOFA calculation window.
    Example body: { "spo2": 85, "heart_rate": 120 }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    allowed = {"heart_rate", "resp_rate", "sbp", "dbp", "spo2"}
    patch   = {k: float(v) for k, v in data.items() if k in allowed}

    if not patch:
        return jsonify({"error": "No valid vital keys in body"}), 400

    set_override(patch)
    print(f"[OVERRIDE] Queued from dashboard: {patch}")
    return jsonify({"status": "queued", "patch": patch})


@app.route("/api/acknowledge", methods=["POST"])
def api_acknowledge():
    """
    Clinician clicks Acknowledge on dashboard.
    Updates local state and publishes to sepsis/acknowledge so RPi
    can silence buzzer and switch to blinking amber.
    """
    with state_lock:
        state["acknowledged"] = True
        state["alert_active"] = False

    try:
        client = get_pub_client()
        client.publish(TOPIC_ACK, json.dumps({"acknowledged": True}))
        print(f"[ACK] Published to {TOPIC_ACK}")
    except Exception as e:
        print(f"[ACK] Publish error: {e}")

    return jsonify({"status": "acknowledged"})
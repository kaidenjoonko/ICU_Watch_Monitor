#Used Claude for a big portion of front end
from flask import Flask, render_template, jsonify, request
import paho.mqtt.client as mqtt
import json
import threading

from server import (
    state, state_lock,
    set_override,
    BROKER_IP, BROKER_PORT,
    TOPIC_ACK,
)

app = Flask(__name__, template_folder="templates")

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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def api_state():
    with state_lock:
        history_list = []
        for h in state["history"][-60:]:
            entry = {
                "reading_num": h["reading_num"],
                "timestamp":   h["timestamp"],
                "sofa_total":  h["sofa"]["total"],
                "status":      h["trend"]["status"],
                "heart_rate":  h["vitals"].get("heart_rate"),
                "spo2":        h["vitals"].get("spo2"),
                "sbp":         h["vitals"].get("sbp"),
                "resp_rate":   h["vitals"].get("resp_rate"),
            }
            history_list.append(entry)

        snapshot = {
            "patient_id":    state["patient_id"],
            "session_active": state["session_active"],
            "alert_active":  state["alert_active"],
            "acknowledged":  state["acknowledged"],
            "latest_vitals": state["latest_vitals"],
            "latest_sofa":   state["latest_sofa"],
            "latest_trend":  state["latest_trend"],
            "history":       history_list,
        }
    return jsonify(snapshot)


@app.route("/api/override", methods=["POST"])
def api_override():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No JSON body"}), 400

    allowed = {"heart_rate", "resp_rate", "sbp", "dbp", "spo2"}
    patch = {}
    for k in data:
        if k in allowed:
            patch[k] = float(data[k])

    if not patch:
        return jsonify({"error": "No valid vital keys in body"}), 400

    set_override(patch)
    print(f"[OVERRIDE] Queued from dashboard: {patch}")
    return jsonify({"status": "queued", "patch": patch})


@app.route("/api/acknowledge", methods=["POST"])
def api_acknowledge():
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

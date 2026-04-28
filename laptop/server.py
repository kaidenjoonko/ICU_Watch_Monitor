import json
import time
import threading
import paho.mqtt.client as mqtt

from sofa  import compute_sofa
from trend import TrendTracker
from db    import init_db, insert_vital, insert_alert

BROKER_IP    = "localhost"
BROKER_PORT  = 1883
TOPIC_VITALS = "sepsis/vitals"
TOPIC_STATUS = "sepsis/status"
TOPIC_ACK    = "sepsis/acknowledge"

state = {
    "patient_id":    None,
    "latest_vitals": {},
    "latest_sofa":   {},
    "latest_trend":  {},
    "alert_active":  False,
    "acknowledged":  False,
    "history":       [],
    "session_active": False,
}

state_lock = threading.Lock()
tracker    = TrendTracker()

pending_override = {}
override_lock    = threading.Lock()


def set_override(vitals_patch):
    with override_lock:
        pending_override.update(vitals_patch)


def pop_override():
    with override_lock:
        if not pending_override:
            return {}
        snapshot = dict(pending_override)
        pending_override.clear()
        return snapshot


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to broker at {BROKER_IP}:{BROKER_PORT}")
        client.subscribe(TOPIC_VITALS)
        client.subscribe(TOPIC_ACK)
        print(f"[MQTT] Subscribed to {TOPIC_VITALS} and {TOPIC_ACK}")
    else:
        print(f"[MQTT] Connection failed — code {rc}")

#Claude code helped with payload
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        print(f"[WARN] Could not decode message on {msg.topic}")
        return

    if msg.topic == TOPIC_VITALS:
        handle_vitals(client, payload)
    elif msg.topic == TOPIC_ACK:
        handle_acknowledge(client, payload)


def handle_vitals(client, payload):
    if payload.get("session_end"):
        print(f"\n[SESSION] Patient {payload.get('patient_id')} session ended")
        with state_lock:
            state["session_active"] = False
        return

    patient_id = payload.get("patient_id")

    with state_lock:
        if state["patient_id"] != patient_id:
            print(f"\n[SESSION] New patient: {patient_id} — resetting tracker")
            tracker.reset()
            state["patient_id"]     = patient_id
            state["history"]        = []
            state["alert_active"]   = False
            state["acknowledged"]   = False
            state["session_active"] = True

    vitals = {
        "heart_rate": payload.get("heart_rate"),
        "resp_rate":  payload.get("resp_rate"),
        "sbp":        payload.get("sbp"),
        "dbp":        payload.get("dbp"),
        "spo2":       payload.get("spo2"),
    }

    override = pop_override()
    if override:
        vitals.update(override)
        print(f"[OVERRIDE] Applied: {override}")

    valid = {}
    for k in vitals:
        if vitals[k] is not None:
            valid[k] = vitals[k]
    if len(valid) < 2:
        print(f"[SKIP] Reading {payload.get('reading_num')} — insufficient vitals")
        return

    sofa_result  = compute_sofa(vitals)
    trend_result = tracker.update(sofa_result)

    status = trend_result["status"]

    with state_lock:
        was_alert = state["alert_active"]
        new_alert = (status == "red" and not was_alert)

        state["latest_vitals"] = vitals
        state["latest_sofa"]   = sofa_result
        state["latest_trend"]  = trend_result
        state["alert_active"]  = (status == "red")
        if status != "red":
            state["acknowledged"] = False

        state["history"].append({
            "reading_num": payload.get("reading_num"),
            "timestamp":   payload.get("timestamp"),
            "vitals":      vitals,
            "sofa":        sofa_result,
            "trend":       trend_result,
        })

    try:
        insert_vital(patient_id, payload.get("timestamp"), vitals, sofa_result, trend_result)
        if new_alert:
            insert_alert(patient_id, payload.get("timestamp"), sofa_result, trend_result)
    except Exception as e:
        print(f"[DB] Error: {e}")

    status_payload = {
        "patient_id": patient_id,
        "status":     status,
        "sofa_total": sofa_result["total"],
        "delta":      trend_result["delta"],
        "timestamp":  payload.get("timestamp"),
    }
    client.publish(TOPIC_STATUS, json.dumps(status_payload))

    if status == "green":
        icon = "[G]"
    elif status == "yellow":
        icon = "[Y]"
    elif status == "red":
        icon = "[R!]"
    else:
        icon = "[?]"

    reading_num = payload.get("reading_num", "?")
    heart_rate  = vitals.get("heart_rate")
    spo2        = vitals.get("spo2")

    if heart_rate is not None and spo2 is not None:
        sbp = vitals.get("sbp", 0)
        dbp = vitals.get("dbp", 0)
        print(f"{icon} Reading {reading_num}  SOFA={sofa_result['total']}  delta={trend_result['delta']}  HR={int(heart_rate)}  SpO2={int(spo2)}%  MAP={int(sbp)}/{int(dbp)}  {trend_result['message']}")
    else:
        print(f"{icon} Reading {reading_num}  SOFA={sofa_result['total']}  {trend_result['message']}")


def handle_acknowledge(client, payload):
    with state_lock:
        state["acknowledged"] = True
        state["alert_active"] = False
    print(f"[ACK] Alert acknowledged by clinician")
    client.publish(TOPIC_ACK, json.dumps({"acknowledged": True}))


def start_server():
    init_db()

    def run_flask():
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "dashboard"))
        from app import app as flask_app
        flask_app.run(port=5000, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER_IP, BROKER_PORT, keepalive=60)

    print(f"[SERVER] Starting — listening on {TOPIC_VITALS}")
    print(f"[SERVER] Dashboard at http://localhost:5000")
    print(f"[SERVER] Press Ctrl+C to stop\n")

    client.loop_forever()


if __name__ == "__main__":
    start_server()

import csv
import json
import time
import argparse
import paho.mqtt.client as mqtt
from datetime import datetime

BROKER_IP    = "172.20.10.4"
BROKER_PORT  = 1883
TOPIC_VITALS = "sepsis/vitals"
INTERVAL     = 5

DATA_PATH = "data/mimic3-demo/CHARTEVENTS.csv"

ITEM_IDS = {
    220045: "heart_rate",
    220210: "resp_rate",
    220179: "sbp",
    220180: "dbp",
    220277: "spo2",
    223761: "temperature",
}


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to broker at {BROKER_IP}:{BROKER_PORT}")
    else:
        print(f"[MQTT] Connection failed — code {rc}")


def on_disconnect(client, userdata, rc):
    print("[MQTT] Disconnected from broker")


def build_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect
    return client


def load_patients(data_path):
    print(f"[DATA] Loading CHARTEVENTS from {data_path} ...")
    patients = {}

    with open(data_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                item_id = int(float(row["itemid"]))
            except (ValueError, KeyError):
                continue

            if item_id not in ITEM_IDS:
                continue

            try:
                subject_id = int(row["subject_id"])
                value      = float(row["valuenum"])
                charttime  = row["charttime"]
            except (ValueError, KeyError):
                continue

            if subject_id not in patients:
                patients[subject_id] = []

            patients[subject_id].append({
                "timestamp":  charttime,
                "vital_name": ITEM_IDS[item_id],
                "value":      value,
            })

    print(f"[DATA] Loaded data for {len(patients)} patients")
    return patients


def group_by_timestamp(readings):
    buckets = {}

    for r in readings:
        try:
            dt  = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
            key = dt.strftime("%Y-%m-%d %H:00")
        except ValueError:
            key = r["timestamp"][:13]

        if key not in buckets:
            buckets[key] = {}

        buckets[key][r["vital_name"]] = r["value"]

    sorted_keys = sorted(buckets.keys())

    result = []
    for k in sorted_keys:
        result.append((k, buckets[k]))
    return result


def list_patients(patients):
    print("\nAvailable patient IDs:")
    for pid in sorted(patients.keys()):
        count = len(patients[pid])
        print(f"  Subject {pid} — {count} vital readings")
    print()

#Recieved help from Claude to help with the paylaod json
def replay(patient_id, patients, client, interval):
    if patient_id not in patients:
        print(f"[ERROR] Patient {patient_id} not found in dataset")
        print(f"        Run with --list to see available IDs")
        return

    readings  = patients[patient_id]
    snapshots = group_by_timestamp(readings)

    if not snapshots:
        print(f"[ERROR] No usable vitals found for patient {patient_id}")
        return

    print(f"\n[REPLAY] Starting patient {patient_id}")
    print(f"[REPLAY] {len(snapshots)} time windows — publishing every {interval}s")
    print(f"[REPLAY] Press Ctrl+C to stop\n")

    i = 0
    for item in snapshots:
        timestamp = item[0]
        vitals    = item[1]

        if len(vitals) < 2:
            i = i + 1
            continue

        payload = {
            "patient_id":  patient_id,
            "timestamp":   timestamp,
            "reading_num": i + 1,
        }
        for key in vitals:
            payload[key] = vitals[key]

        message = json.dumps(payload)
        result  = client.publish(TOPIC_VITALS, message)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            vitals_str = ""
            for k in vitals:
                if vitals_str != "":
                    vitals_str = vitals_str + "  "
                vitals_str = vitals_str + k + "=" + str(round(vitals[k]))
            print(f"[{i + 1}] {timestamp}  {vitals_str}")
        else:
            print(f"[{i + 1}] Publish failed — rc={result.rc}")

        time.sleep(interval)
        i = i + 1

    client.publish(TOPIC_VITALS, json.dumps({
        "patient_id": patient_id,
        "session_end": True
    }))
    print(f"\n[REPLAY] Session complete for patient {patient_id}")


def main():
    parser = argparse.ArgumentParser(description="MIMIC-III vitals replay — bedside monitor simulator")
    parser.add_argument("--patient", type=int, default=None,     help="Subject ID to replay")
    parser.add_argument("--speed",   type=int, default=INTERVAL, help="Seconds between readings")
    parser.add_argument("--broker",  type=str, default=BROKER_IP, help="MQTT broker IP address")
    parser.add_argument("--list",    action="store_true",         help="List available patient IDs")
    args = parser.parse_args()

    patients = load_patients(DATA_PATH)

    if args.list:
        list_patients(patients)
        return

    patient_id = args.patient
    if patient_id is None:
        patient_id = sorted(patients.keys())[0]
        print(f"[INFO] No patient specified — using subject {patient_id}")

    client = build_client()
    client.connect(args.broker, BROKER_PORT, keepalive=60)
    client.loop_start()

    time.sleep(1)

    try:
        replay(patient_id, patients, client, args.speed)
    except KeyboardInterrupt:
        print("\n[REPLAY] Interrupted by user")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

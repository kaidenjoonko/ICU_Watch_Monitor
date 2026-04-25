"""
replay.py
Raspberry Pi entry point — bedside monitor simulator.

Reads real patient vitals from MIMIC-III CHARTEVENTS.csv and publishes
them over MQTT to the laptop server, one reading every INTERVAL seconds.

Usage:
    python replay.py                         # uses default patient
    python replay.py --patient 10006         # specific subject ID
    python replay.py --speed 5               # seconds between readings
    python replay.py --list                  # list all available patient IDs

MQTT topic published: sepsis/vitals
"""

import csv
import json
import time
import argparse
import paho.mqtt.client as mqtt
from collections import defaultdict
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────

BROKER_IP   = "localhost"   # change to laptop's IP when running on real RPi
BROKER_PORT = 1883
TOPIC_VITALS = "sepsis/vitals"
INTERVAL     = 5            # seconds between readings

DATA_PATH = "data/mimic3-demo/CHARTEVENTS.csv"

# MIMIC item IDs for each vital sign (MetaVision format used in demo dataset)
ITEM_IDS = {
    220045: "heart_rate",
    220210: "resp_rate",
    220179: "sbp",
    220180: "dbp",
    220277: "spo2",
    223761: "temperature",
}

# ── MQTT setup ───────────────────────────────────────────────────────────────

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

# ── MIMIC data loading ───────────────────────────────────────────────────────

def load_patients(data_path):
    """
    Read CHARTEVENTS.csv and group vitals by subject ID.
    Returns a dict: { subject_id: [ {timestamp, vital_name, value}, ... ] }
    Only keeps rows whose ITEMID is one of our vital sign item IDs.
    """
    print(f"[DATA] Loading CHARTEVENTS from {data_path} ...")
    patients = defaultdict(list)

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

            patients[subject_id].append({
                "timestamp":  charttime,
                "vital_name": ITEM_IDS[item_id],
                "value":      value,
            })

    print(f"[DATA] Loaded data for {len(patients)} patients")
    return patients


def group_by_timestamp(readings):
    """
    Group individual vital readings by timestamp window.
    Returns a sorted list of (timestamp, vitals_dict) tuples.
    Merges readings within the same hour into one snapshot.
    """
    buckets = defaultdict(dict)
    for r in readings:
        # round to nearest hour to group simultaneous readings
        try:
            dt  = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
            key = dt.strftime("%Y-%m-%d %H:00")
        except ValueError:
            key = r["timestamp"][:13]   # fallback: first 13 chars

        # keep latest value if multiple readings in same bucket
        buckets[key][r["vital_name"]] = r["value"]

    sorted_keys = sorted(buckets.keys())
    return [(k, buckets[k]) for k in sorted_keys]


def list_patients(patients):
    print("\nAvailable patient IDs:")
    for pid in sorted(patients.keys()):
        count = len(patients[pid])
        print(f"  Subject {pid:6d} — {count} vital readings")
    print()

# ── Main replay loop ─────────────────────────────────────────────────────────

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

    for i, (timestamp, vitals) in enumerate(snapshots):
        # skip snapshots with fewer than 2 vitals — not useful
        if len(vitals) < 2:
            continue

        payload = {
            "patient_id": patient_id,
            "timestamp":  timestamp,
            "reading_num": i + 1,
            **vitals
        }

        message = json.dumps(payload)
        result  = client.publish(TOPIC_VITALS, message)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            vitals_str = "  ".join(
                f"{k}={v:.0f}" for k, v in vitals.items()
            )
            print(f"[{i+1:03d}] {timestamp}  {vitals_str}")
        else:
            print(f"[{i+1:03d}] Publish failed — rc={result.rc}")

        time.sleep(interval)

    # signal session end
    client.publish(TOPIC_VITALS, json.dumps({
        "patient_id": patient_id,
        "session_end": True
    }))
    print(f"\n[REPLAY] Session complete for patient {patient_id}")


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MIMIC-III vitals replay — bedside monitor simulator")
    parser.add_argument("--patient", type=int, default=None,   help="Subject ID to replay")
    parser.add_argument("--speed",   type=int, default=INTERVAL, help="Seconds between readings")
    parser.add_argument("--broker",  type=str, default=BROKER_IP, help="MQTT broker IP address")
    parser.add_argument("--list",    action="store_true",       help="List available patient IDs")
    args = parser.parse_args()

    patients = load_patients(DATA_PATH)

    if args.list:
        list_patients(patients)
        return

    # pick a patient — use first available if none specified
    patient_id = args.patient
    if patient_id is None:
        patient_id = sorted(patients.keys())[0]
        print(f"[INFO] No patient specified — using subject {patient_id}")

    client = build_client()
    client.connect(args.broker, BROKER_PORT, keepalive=60)
    client.loop_start()

    time.sleep(1)   # give connection a moment to establish

    try:
        replay(patient_id, patients, client, args.speed)
    except KeyboardInterrupt:
        print("\n[REPLAY] Interrupted by user")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
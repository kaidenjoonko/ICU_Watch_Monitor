import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "sepsis.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS vitals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id      INTEGER,
            timestamp       TEXT,
            heart_rate      REAL,
            resp_rate       REAL,
            sbp             REAL,
            dbp             REAL,
            spo2            REAL,
            sofa_total      INTEGER,
            sofa_resp       INTEGER,
            sofa_cardio     INTEGER,
            sofa_renal      INTEGER,
            sofa_cns        INTEGER,
            trend_status    TEXT,
            trend_delta     REAL,
            trend_baseline  REAL,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id      INTEGER,
            timestamp       TEXT,
            sofa_total      INTEGER,
            sofa_resp       INTEGER,
            sofa_cardio     INTEGER,
            sofa_renal      INTEGER,
            sofa_cns        INTEGER,
            delta           REAL,
            acknowledged    INTEGER DEFAULT 0,
            acknowledged_at TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")


def insert_vital(patient_id, timestamp, vitals, sofa, trend):
    conn = get_connection()
    conn.execute("""
        INSERT INTO vitals (
            patient_id, timestamp,
            heart_rate, resp_rate, sbp, dbp, spo2,
            sofa_total, sofa_resp, sofa_cardio, sofa_renal, sofa_cns,
            trend_status, trend_delta, trend_baseline
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_id, timestamp,
        vitals.get("heart_rate"), vitals.get("resp_rate"),
        vitals.get("sbp"), vitals.get("dbp"),
        vitals.get("spo2"),
        sofa["total"], sofa["respiration"],
        sofa["cardiovascular"], sofa["renal"], sofa["cns_proxy"],
        trend["status"], trend["delta"], trend.get("baseline"),
    ))
    conn.commit()
    conn.close()


def insert_alert(patient_id, timestamp, sofa, trend):
    conn = get_connection()
    conn.execute("""
        INSERT INTO alerts (
            patient_id, timestamp,
            sofa_total, sofa_resp, sofa_cardio, sofa_renal, sofa_cns,
            delta
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        patient_id, timestamp,
        sofa["total"], sofa["respiration"],
        sofa["cardiovascular"], sofa["renal"],
        sofa["cns_proxy"], trend["delta"],
    ))
    conn.commit()
    conn.close()
    print(f"[DB] Alert logged for patient {patient_id}")


def acknowledge_latest_alert(patient_id):
    conn = get_connection()
    conn.execute("""
        UPDATE alerts
        SET acknowledged = 1,
            acknowledged_at = datetime('now')
        WHERE patient_id = ?
          AND acknowledged = 0
        ORDER BY created_at DESC
        LIMIT 1
    """, (patient_id,))
    conn.commit()
    conn.close()


def get_recent_vitals(patient_id, limit=60):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM vitals
        WHERE patient_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (patient_id, limit)).fetchall()
    conn.close()

    result = []
    for r in reversed(rows):
        result.append(dict(r))
    return result


def get_alerts(patient_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM alerts
        WHERE patient_id = ?
        ORDER BY created_at DESC
    """, (patient_id,)).fetchall()
    conn.close()

    result = []
    for r in rows:
        result.append(dict(r))
    return result


if __name__ == "__main__":
    import os

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    init_db()

    dummy_vitals = {"heart_rate": 95, "resp_rate": 22, "sbp": 100, "dbp": 60, "spo2": 93}
    dummy_sofa   = {"total": 5, "respiration": 2, "cardiovascular": 1, "renal": 1, "cns_proxy": 1}
    dummy_trend  = {"status": "red", "delta": 3.0, "baseline": 2.0, "message": "SEPSIS ALERT"}

    insert_vital(41976, "2198-10-30 06:00", dummy_vitals, dummy_sofa, dummy_trend)
    insert_alert(41976, "2198-10-30 06:00", dummy_sofa, dummy_trend)

    rows = get_recent_vitals(41976)
    print(f"Vitals rows: {len(rows)}")
    print(f"First row:   {rows[0]}")

    alerts = get_alerts(41976)
    print(f"Alerts:      {len(alerts)}")
    print(f"First alert: {alerts[0]}")

    print("\n[DB] All tests passed")

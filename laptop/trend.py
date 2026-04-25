"""
trend.py
Baseline tracker and sepsis status decision engine.

Maintains a rolling history of SOFA scores for a single patient session.
Computes a baseline from the first N readings, then tracks the delta
from that baseline to determine patient status.

Status levels:
  green  - SOFA delta < 1  (stable)
  yellow - SOFA delta 1-2  (deteriorating, watch closely)
  red    - SOFA delta >= 2 (sepsis threshold crossed, alert)
"""

BASELINE_WINDOW  = 5   # number of readings to establish baseline
YELLOW_THRESHOLD = 1   # delta to trigger yellow
RED_THRESHOLD    = 2   # delta to trigger red (clinical sepsis threshold)


class TrendTracker:

    def __init__(self):
        self.history     = []   # list of SOFA total scores over time
        self.baseline    = None # average of first BASELINE_WINDOW scores
        self.last_status = "green"

    def reset(self):
        """Call this when switching to a new patient."""
        self.history     = []
        self.baseline    = None
        self.last_status = "green"

    def update(self, sofa_result):
        """
        Feed in a new SOFA result dict (from compute_sofa).
        Returns a status dict.

        Args:
            sofa_result: dict returned by compute_sofa()

        Returns:
            dict with:
                status   (str)  "green" | "yellow" | "red"
                delta    (int)  current SOFA total minus baseline
                baseline (float) established baseline score
                current  (int)  current SOFA total
                readings (int)  total readings so far
        """
        total = sofa_result["total"]
        self.history.append(total)

        # establish baseline from first N readings
        if self.baseline is None:
            if len(self.history) >= BASELINE_WINDOW:
                self.baseline = sum(self.history[:BASELINE_WINDOW]) / BASELINE_WINDOW
            else:
                # still collecting baseline — return green with no delta yet
                return {
                    "status":   "green",
                    "delta":    0,
                    "baseline": None,
                    "current":  total,
                    "readings": len(self.history),
                    "message":  f"Establishing baseline ({len(self.history)}/{BASELINE_WINDOW})"
                }

        delta = total - self.baseline

        if delta >= RED_THRESHOLD:
            status = "red"
        elif delta >= YELLOW_THRESHOLD:
            status = "yellow"
        else:
            status = "green"

        self.last_status = status

        return {
            "status":   status,
            "delta":    round(delta, 1),
            "baseline": round(self.baseline, 1),
            "current":  total,
            "readings": len(self.history),
            "message":  _status_message(status, delta)
        }

    def get_history(self):
        """Return full SOFA score history for charting."""
        return list(self.history)


def _status_message(status, delta):
    if status == "green":
        return "Patient stable — SOFA within baseline range"
    elif status == "yellow":
        return f"Vitals deteriorating — SOFA delta +{delta:.1f}, monitor closely"
    else:
        return f"SEPSIS ALERT — SOFA delta +{delta:.1f}, threshold exceeded"


# ── Quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from sofa import compute_sofa

    print("=== Trend Tracker Test ===\n")

    tracker = TrendTracker()

    # simulate a patient session: stable for 5 readings, then deteriorates
    session = [
        {"heart_rate": 72,  "resp_rate": 14, "sbp": 118, "dbp": 76, "spo2": 98},
        {"heart_rate": 74,  "resp_rate": 15, "sbp": 116, "dbp": 75, "spo2": 98},
        {"heart_rate": 76,  "resp_rate": 15, "sbp": 115, "dbp": 74, "spo2": 97},
        {"heart_rate": 75,  "resp_rate": 14, "sbp": 117, "dbp": 75, "spo2": 98},
        {"heart_rate": 78,  "resp_rate": 16, "sbp": 114, "dbp": 73, "spo2": 97},
        # baseline established above — now patient starts declining
        {"heart_rate": 85,  "resp_rate": 18, "sbp": 108, "dbp": 68, "spo2": 96},
        {"heart_rate": 94,  "resp_rate": 21, "sbp": 100, "dbp": 62, "spo2": 94},
        {"heart_rate": 104, "resp_rate": 24, "sbp": 92,  "dbp": 57, "spo2": 92},
        {"heart_rate": 112, "resp_rate": 27, "sbp": 85,  "dbp": 52, "spo2": 90},
        {"heart_rate": 122, "resp_rate": 30, "sbp": 78,  "dbp": 46, "spo2": 87},
    ]

    for i, vitals in enumerate(session):
        sofa  = compute_sofa(vitals)
        trend = tracker.update(sofa)
        status_icon = {"green": "[G]", "yellow": "[Y]", "red": "[R]"}[trend["status"]]
        print(f"Reading {i+1:02d}  SOFA={sofa['total']:2d}  delta={trend['delta']:+.1f}  "
              f"{status_icon}  {trend['message']}")
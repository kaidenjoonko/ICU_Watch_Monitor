BASELINE_WINDOW  = 5
YELLOW_THRESHOLD = 1
RED_THRESHOLD    = 2


class TrendTracker:

    def __init__(self):
        self.history     = []
        self.baseline    = None
        self.last_status = "green"

    def reset(self):
        self.history     = []
        self.baseline    = None
        self.last_status = "green"

    def update(self, sofa_result):
        total = sofa_result["total"]
        self.history.append(total)

        if self.baseline is None:
            if len(self.history) >= BASELINE_WINDOW:
                self.baseline = sum(self.history[:BASELINE_WINDOW]) / BASELINE_WINDOW
            else:
                readings_so_far = len(self.history)
                message = "Establishing baseline (" + str(readings_so_far) + "/" + str(BASELINE_WINDOW) + ")"
                result = {}
                result["status"]   = "green"
                result["delta"]    = 0
                result["baseline"] = None
                result["current"]  = total
                result["readings"] = readings_so_far
                result["message"]  = message
                return result

        delta = total - self.baseline

        if delta >= RED_THRESHOLD:
            status = "red"
        elif delta >= YELLOW_THRESHOLD:
            status = "yellow"
        else:
            status = "green"

        self.last_status = status

        result = {}
        result["status"]   = status
        result["delta"]    = round(delta, 1)
        result["baseline"] = round(self.baseline, 1)
        result["current"]  = total
        result["readings"] = len(self.history)
        result["message"]  = get_status_message(status, delta)
        return result

    def get_history(self):
        return list(self.history)


def get_status_message(status, delta):
    if status == "green":
        return "Patient stable — SOFA within baseline range"
    elif status == "yellow":
        return "Vitals deteriorating — SOFA delta +" + str(round(delta, 1)) + ", monitor closely"
    else:
        return "SEPSIS ALERT — SOFA delta +" + str(round(delta, 1)) + ", threshold exceeded"


if __name__ == "__main__":
    from sofa import compute_sofa

    print("=== Trend Tracker Test ===\n")

    tracker = TrendTracker()

    session = [
        {"heart_rate": 72,  "resp_rate": 14, "sbp": 118, "dbp": 76, "spo2": 98},
        {"heart_rate": 74,  "resp_rate": 15, "sbp": 116, "dbp": 75, "spo2": 98},
        {"heart_rate": 76,  "resp_rate": 15, "sbp": 115, "dbp": 74, "spo2": 97},
        {"heart_rate": 75,  "resp_rate": 14, "sbp": 117, "dbp": 75, "spo2": 98},
        {"heart_rate": 78,  "resp_rate": 16, "sbp": 114, "dbp": 73, "spo2": 97},
        {"heart_rate": 85,  "resp_rate": 18, "sbp": 108, "dbp": 68, "spo2": 96},
        {"heart_rate": 94,  "resp_rate": 21, "sbp": 100, "dbp": 62, "spo2": 94},
        {"heart_rate": 104, "resp_rate": 24, "sbp": 92,  "dbp": 57, "spo2": 92},
        {"heart_rate": 112, "resp_rate": 27, "sbp": 85,  "dbp": 52, "spo2": 90},
        {"heart_rate": 122, "resp_rate": 30, "sbp": 78,  "dbp": 46, "spo2": 87},
    ]

    i = 0
    for vitals in session:
        sofa  = compute_sofa(vitals)
        trend = tracker.update(sofa)

        if trend["status"] == "green":
            status_icon = "[G]"
        elif trend["status"] == "yellow":
            status_icon = "[Y]"
        else:
            status_icon = "[R]"

        reading_num = i + 1
        sofa_total  = sofa["total"]
        delta       = trend["delta"]
        message     = trend["message"]
        print(f"Reading {reading_num}  SOFA={sofa_total}  delta={delta}  {status_icon}  {message}")
        i = i + 1

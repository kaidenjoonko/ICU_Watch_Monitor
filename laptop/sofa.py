"""
sofa.py
SOFA (Sequential Organ Failure Assessment) scoring engine.

Computes a simplified 4-organ SOFA score from bedside vitals.
Each organ system scores 0-4, total is 0-16.

Organs evaluated:
  1. Respiration     - SpO2
  2. Cardiovascular  - Mean Arterial Pressure (MAP)
  3. Renal           - Heart rate / MAP ratio (proxy)
  4. CNS proxy       - Heart rate + Respiratory rate combined stress index
"""


def compute_map(sbp, dbp):
    """
    Mean Arterial Pressure from systolic and diastolic BP.
    MAP = DBP + (1/3)(SBP - DBP)
    """
    return dbp + (sbp - dbp) / 3.0


def score_respiration(spo2):
    """
    SpO2-based respiratory subscore.
    Higher score = worse oxygenation.
    """
    if spo2 is None:
        return 0
    if spo2 >= 96:
        return 0
    elif spo2 >= 93:
        return 1
    elif spo2 >= 90:
        return 2
    elif spo2 >= 85:
        return 3
    else:
        return 4


def score_cardiovascular(sbp, dbp):
    """
    MAP-based cardiovascular subscore.
    Lower MAP = worse perfusion.
    """
    if sbp is None or dbp is None:
        return 0
    map_val = compute_map(sbp, dbp)
    if map_val >= 70:
        return 0
    elif map_val >= 65:
        return 1
    elif map_val >= 60:
        return 2
    elif map_val >= 50:
        return 3
    else:
        return 4


def score_renal(heart_rate, sbp, dbp):
    """
    Renal proxy: HR/MAP ratio.
    High HR combined with low MAP suggests renal hypoperfusion.
    """
    if heart_rate is None or sbp is None or dbp is None:
        return 0
    map_val = compute_map(sbp, dbp)
    if map_val == 0:
        return 4
    ratio = heart_rate / map_val
    if ratio < 1.0:
        return 0
    elif ratio < 1.3:
        return 1
    elif ratio < 1.6:
        return 2
    elif ratio < 2.0:
        return 3
    else:
        return 4


def score_cns_proxy(heart_rate, resp_rate):
    """
    CNS/systemic stress proxy: combined HR + RR stress index.
    Both elevated simultaneously signals systemic stress response.
    """
    if heart_rate is None or resp_rate is None:
        return 0
    hr_stressed = heart_rate > 100
    rr_stressed = resp_rate > 20
    if not hr_stressed and not rr_stressed:
        return 0
    elif hr_stressed ^ rr_stressed:
        return 1
    else:
        hr_severity = min(3, max(0, int((heart_rate - 100) / 15)))
        rr_severity = min(3, max(0, int((resp_rate - 20) / 5)))
        return min(4, 1 + max(hr_severity, rr_severity))


def compute_sofa(vitals):
    """
    Compute full SOFA score from a vitals dict.

    Args:
        vitals: dict with keys:
            heart_rate  (bpm)
            resp_rate   (breaths/min)
            sbp         (mmHg, systolic)
            dbp         (mmHg, diastolic)
            spo2        (%, oxygen saturation)

    Returns:
        dict with:
            total       (int, 0-16)
            respiration (int, 0-4)
            cardiovascular (int, 0-4)
            renal       (int, 0-4)
            cns_proxy   (int, 0-4)
    """
    hr  = vitals.get("heart_rate")
    rr  = vitals.get("resp_rate")
    sbp = vitals.get("sbp")
    dbp = vitals.get("dbp")
    spo2 = vitals.get("spo2")

    resp   = score_respiration(spo2)
    cardio = score_cardiovascular(sbp, dbp)
    renal  = score_renal(hr, sbp, dbp)
    cns    = score_cns_proxy(hr, rr)

    total = resp + cardio + renal + cns

    return {
        "total":          total,
        "respiration":    resp,
        "cardiovascular": cardio,
        "renal":          renal,
        "cns_proxy":      cns
    }


# ── Quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":

    print("=== SOFA Score Test ===\n")

    stable_patient = {
        "heart_rate": 72,
        "resp_rate":  14,
        "sbp":        118,
        "dbp":        76,
        "spo2":       98
    }

    deteriorating_patient = {
        "heart_rate": 107,
        "resp_rate":  25,
        "sbp":        88,
        "dbp":        54,
        "spo2":       91
    }

    critical_patient = {
        "heart_rate": 128,
        "resp_rate":  32,
        "sbp":        72,
        "dbp":        40,
        "spo2":       84
    }

    for label, vitals in [
        ("Stable patient",        stable_patient),
        ("Deteriorating patient", deteriorating_patient),
        ("Critical patient",      critical_patient),
    ]:
        result = compute_sofa(vitals)
        print(f"{label}")
        print(f"  Respiration:     {result['respiration']}/4")
        print(f"  Cardiovascular:  {result['cardiovascular']}/4")
        print(f"  Renal:           {result['renal']}/4")
        print(f"  CNS proxy:       {result['cns_proxy']}/4")
        print(f"  TOTAL:           {result['total']}/16")
        print()
def compute_map(sbp, dbp):
    return dbp + (sbp - dbp) / 3.0


def score_respiration(spo2):
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
    if heart_rate is None or resp_rate is None:
        return 0

    hr_stressed = heart_rate > 100
    rr_stressed = resp_rate > 20

    if not hr_stressed and not rr_stressed:
        return 0
    elif (hr_stressed and not rr_stressed) or (rr_stressed and not hr_stressed):
        return 1
    else:
        hr_severity = int((heart_rate - 100) / 15)
        if hr_severity < 0:
            hr_severity = 0
        if hr_severity > 3:
            hr_severity = 3

        rr_severity = int((resp_rate - 20) / 5)
        if rr_severity < 0:
            rr_severity = 0
        if rr_severity > 3:
            rr_severity = 3

        if hr_severity > rr_severity:
            max_severity = hr_severity
        else:
            max_severity = rr_severity

        result = 1 + max_severity
        if result > 4:
            result = 4
        return result


def compute_sofa(vitals):
    hr   = vitals.get("heart_rate")
    rr   = vitals.get("resp_rate")
    sbp  = vitals.get("sbp")
    dbp  = vitals.get("dbp")
    spo2 = vitals.get("spo2")

    resp   = score_respiration(spo2)
    cardio = score_cardiovascular(sbp, dbp)
    renal  = score_renal(hr, sbp, dbp)
    cns    = score_cns_proxy(hr, rr)

    total = resp + cardio + renal + cns

    result = {}
    result["total"]          = total
    result["respiration"]    = resp
    result["cardiovascular"] = cardio
    result["renal"]          = renal
    result["cns_proxy"]      = cns
    return result


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

    result = compute_sofa(stable_patient)
    print("Stable patient")
    print("  Respiration:    " + str(result["respiration"]) + "/4")
    print("  Cardiovascular: " + str(result["cardiovascular"]) + "/4")
    print("  Renal:          " + str(result["renal"]) + "/4")
    print("  CNS proxy:      " + str(result["cns_proxy"]) + "/4")
    print("  TOTAL:          " + str(result["total"]) + "/16")
    print()

    result = compute_sofa(deteriorating_patient)
    print("Deteriorating patient")
    print("  Respiration:    " + str(result["respiration"]) + "/4")
    print("  Cardiovascular: " + str(result["cardiovascular"]) + "/4")
    print("  Renal:          " + str(result["renal"]) + "/4")
    print("  CNS proxy:      " + str(result["cns_proxy"]) + "/4")
    print("  TOTAL:          " + str(result["total"]) + "/16")
    print()

    result = compute_sofa(critical_patient)
    print("Critical patient")
    print("  Respiration:    " + str(result["respiration"]) + "/4")
    print("  Cardiovascular: " + str(result["cardiovascular"]) + "/4")
    print("  Renal:          " + str(result["renal"]) + "/4")
    print("  CNS proxy:      " + str(result["cns_proxy"]) + "/4")
    print("  TOTAL:          " + str(result["total"]) + "/16")
    print()

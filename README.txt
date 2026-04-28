# 🏥 ICU Watch Monitor
### Real-time Sepsis Early Warning System — EE 250 Final Project

A two-node IoT system that simulates an ICU bedside monitoring setup. The Raspberry Pi streams real patient vitals from the MIMIC-III clinical dataset over MQTT to a laptop server, which runs a SOFA scoring algorithm to detect sepsis onset in real time. A GrovePi LED physically reflects patient status — green, yellow, or red — with a buzzer alarm on critical alerts.

---

## 📡 System Architecture

```
┌─────────────────────────────┐         ┌──────────────────────────────────┐
│     Raspberry Pi            │         │           Laptop                 │
│   (Bedside Monitor)         │         │     (Clinical Server)            │
│                             │         │                                  │
│  MIMIC-III CSV              │         │  Mosquitto Broker                │
│       ↓                     │─vitals→ │       ↓                          │
│  replay.py                  │  MQTT   │  server.py                       │
│       ↓                     │         │       ↓                          │
│  alert_handler.py           │←status─ │  sofa.py + trend.py              │
│       ↓                     │  MQTT   │       ↓                          │
│  led_controller.py          │         │  db.py (SQLite)                  │
│       ↓                     │         │       ↓                          │
│  GrovePi LED + Buzzer       │         │  Flask Dashboard                 │
│  🟢 green  stable           │         │  http://localhost:5000           │
│  🟡 yellow deteriorating    │         │                                  │
│  🔴 red    sepsis alert     │         │                                  │
└─────────────────────────────┘         └──────────────────────────────────┘
```

| MQTT Topic | Direction | Purpose |
|---|---|---|
| `sepsis/vitals` | RPi → Laptop | Patient vitals JSON every 5 seconds |
| `sepsis/status` | Laptop → RPi | green / yellow / red status |
| `sepsis/acknowledge` | Laptop → RPi | Clinician ack, silences buzzer |

---

## 🧠 How It Works

1. The RPi reads real ICU patient data from MIMIC-III and publishes timestamped vitals over MQTT
2. The laptop computes a **SOFA score** across 4 organ systems per reading:
   - Respiration (SpO2)
   - Cardiovascular (Mean Arterial Pressure)
   - Renal (HR/MAP ratio proxy)
   - CNS proxy (combined HR + RR stress index)
3. A baseline is established from the first 5 readings. If the SOFA delta rises ≥ 2 from baseline — the clinical sepsis threshold — an alert fires
4. The RPi LED changes color in real time. On red alert, the buzzer fires and the dashboard shows a full alert banner
5. The clinician can **inject manual vital overrides** to test system response, and **acknowledge alerts** to silence the buzzer

---

## 📁 Repository Structure

```
ICU_Watch_Monitor/
├── README.md
├── laptop/
│   ├── server.py              # Entry point — MQTT + Flask launcher
│   ├── app.py                 # Flask routes — /api/state, /override, /acknowledge
│   ├── sofa.py                # SOFA scoring engine
│   ├── trend.py               # Baseline tracker, delta detection
│   ├── db.py                  # SQLite helpers
│   ├── templates/
│   │   └── index.html         # Dashboard UI
│   └── requirements.txt
└── rpi/
    ├── replay.py              # MIMIC data replay, MQTT publisher
    ├── alert_handler.py       # Status subscriber, drives LED + buzzer
    ├── led_controller.py      # GrovePi LED/buzzer abstraction
    └── requirements.txt
```

---

## ⚙️ Setup

### Dataset (required before running)

The MIMIC-III dataset is not included in this repo per PhysioNet's data use agreement.

1. Create a free account at [PhysioNet](https://physionet.org/content/mimiciii-demo/1.4/)
2. Download the demo dataset ZIP (~13 MB)
3. Unzip and place contents at `rpi/data/mimic3-demo/`

> Recommended demo patient: **Subject 41976** — confirmed sepsis deterioration arc

### Install Dependencies

**Laptop:**
```bash
pip install -r laptop/requirements.txt
```

**Raspberry Pi:**
```bash
pip install -r rpi/requirements.txt
```

> If `grovepi` fails to install via pip, use the official installer:
> ```bash
> curl -kL dexterindustries.com/update_grovepi | bash
> ```

### Network Configuration

1. Get your laptop's IP: `ipconfig getifaddr en0` (Mac)
2. In `rpi/replay.py` and `rpi/alert_handler.py`, set:
   ```python
   BROKER_IP = "<your laptop IP>"
   ```
3. In `rpi/led_controller.py`, set:
   ```python
   REAL_HARDWARE = True   # False for laptop-only testing
   ```

### Hardware Wiring (RPi)

| Component | GrovePi Pin |
|---|---|
| RGB LED | D4 |
| Buzzer | D8 |

---

## 🚀 Running the Project

Open **4 terminals**:

**Terminal 1 — Start MQTT broker (laptop)**
```bash
mosquitto
```

**Terminal 2 — Start server + dashboard (laptop)**
```bash
cd laptop/
python server.py
# Dashboard at http://localhost:5000
```

**Terminal 3 — Start alert handler (RPi)**
```bash
cd rpi/
python alert_handler.py
```

**Terminal 4 — Start vitals replay (RPi)**
```bash
cd rpi/
python replay.py --patient 41976 --speed 1
```

Open `http://localhost:5000` and watch the patient deteriorate in real time.

### Replay flags
```bash
python replay.py --patient 41976   # specific patient
python replay.py --speed 1         # 1 second between readings (demo mode)
python replay.py --list            # list all available patient IDs
```

---

## 📊 Dashboard

- **Live vitals** — HR, respiratory rate, blood pressure, SpO2
- **SOFA breakdown** — per-organ subscores with color-coded bars
- **Trend chart** — SOFA score history across the session
- **Manual override panel** — inject custom vital values to test system response
- **Alert log** — timestamped record of all alerts and acknowledgements
- **Acknowledge button** — silences RPi buzzer, switches LED to blinking amber

---

## ⚠️ Known Limitations

- **Simplified SOFA** — uses 4 organ systems from bedside vitals. Full clinical SOFA uses 6 systems including lab values (bilirubin, creatinine, platelets) not available in the vitals stream
- **Demo dataset** — MIMIC-III demo contains 50 patients. Full dataset requires credentialing
- **Replay speed** — default 5s interval is 10x faster than real ICU monitoring cadence. Configurable via `--speed`
- **Vitals grouping** — readings within the same hour window are merged. Some snapshots may be missing vitals if not recorded that hour

---

## 📦 External Libraries

| Library | Purpose |
|---|---|
| `paho-mqtt` | MQTT client — publish and subscribe |
| `flask` | Web framework — dashboard server |
| `numpy` | Numerical computation — SOFA scoring |
| `grovepi` | GrovePi hardware interface (RPi only) |
| `sqlite3` | Built-in — session and alert storage |

---

## 🤖 AI Tool Disclosure

This project was developed with assistance from Claude (Anthropic) for system architecture planning, code structure, and implementation guidance. All design decisions, algorithm choices, hardware wiring, testing, and debugging were completed by the student. Use of AI tools is acknowledged in accordance with EE 250 course policy.

---

*EE 250 — Embedded Systems and the Internet of Things — University of Southern California*
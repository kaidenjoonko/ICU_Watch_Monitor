================================================================================
  EE 250 Final Project — ICU Watch Monitor
  README.txt
================================================================================

Team Member
-----------
  Kaiden Ko

--------------------------------------------------------------------------------
Project Overview
--------------------------------------------------------------------------------

ICU Watch Monitor is a real-time sepsis early warning system that simulates
an ICU bedside monitoring setup using two physical nodes. The Raspberry Pi
acts as a bedside monitor, replaying real patient vitals from the MIMIC-III
Clinical Database Demo over MQTT to a laptop server every 5 seconds. The
laptop receives each transmission, computes a rolling SOFA (Sequential Organ
Failure Assessment) score across 4 organ systems, and tracks whether the
patient's score is rising from their baseline. Based on the current SOFA
delta, the laptop publishes a status back to the RPi — green if stable,
yellow if deteriorating, red if the sepsis threshold is crossed — and the
RPi's GrovePi LED physically changes color to match, with the buzzer firing
on a red alert. A Flask dashboard on the laptop displays live vitals, SOFA
breakdown, trend chart, and alert log. The clinician can manually inject
vital overrides to test system response, and acknowledge alerts to silence
the buzzer and log the response time.

Node roles:
  Node 1 (Raspberry Pi) — MIMIC data replay, MQTT publisher,
                           alert subscriber, GrovePi LED/buzzer output
  Node 2 (Laptop)       — Mosquitto broker, SOFA scoring engine,
                           trend detector, alert publisher, Flask dashboard

MQTT topics:
  sepsis/vitals      RPi -> Laptop    patient vitals JSON every 5 seconds
  sepsis/status      Laptop -> RPi    green / yellow / red status
  sepsis/acknowledge Laptop -> RPi    clinician ack, silences buzzer

--------------------------------------------------------------------------------
Repository Structure
--------------------------------------------------------------------------------

  ICU_Watch_Monitor/
  |-- README.txt
  |-- laptop/
  |   |-- server.py              Main entry point -- MQTT subscriber,
  |   |                          SOFA pipeline orchestrator, Flask launcher
  |   |-- app.py                 Flask routes -- /api/state, /override, /acknowledge
  |   |-- sofa.py                SOFA scoring engine -- 4 organ subscores
  |   |-- trend.py               Baseline tracker -- delta detection, status logic
  |   |-- db.py                  SQLite helpers -- init, insert vitals/alerts
  |   |-- templates/
  |   |   |-- index.html         Dashboard UI
  |   |-- requirements.txt
  |-- rpi/
      |-- replay.py              Reads MIMIC CSV, publishes vitals over MQTT
      |-- alert_handler.py       Subscribes to status, drives LED + buzzer
      |-- led_controller.py      GrovePi LED/buzzer abstraction layer
      |-- requirements.txt

--------------------------------------------------------------------------------
Dataset Setup (required before running)
--------------------------------------------------------------------------------

1. Go to https://physionet.org/content/mimiciii-demo/1.4/
2. Create a free PhysioNet account and accept the data use agreement
3. Download the demo dataset ZIP file (~13 MB)
4. Unzip and place the folder contents at:
     rpi/data/mimic3-demo/
   The replay script expects CHARTEVENTS.csv at that path.

The MIMIC-III demo dataset is not included in this repository in accordance
with PhysioNet's data use agreement. It is freely available to anyone with
a PhysioNet account and requires no special credentialing.

Recommended demo patient: Subject 41976
  Run: python replay.py --patient 41976

--------------------------------------------------------------------------------
Dependencies
--------------------------------------------------------------------------------

LAPTOP (laptop/requirements.txt):
  paho-mqtt       MQTT client -- subscribe/publish
  flask           Web framework -- dashboard server
  numpy           Numerical computation -- SOFA scoring, rolling windows

RASPBERRY PI (rpi/requirements.txt):
  paho-mqtt       MQTT client -- publish vitals, receive alerts
  numpy           Vitals preprocessing
  grovepi         GrovePi hardware interface -- LED, buzzer

Install on laptop:
  pip install -r laptop/requirements.txt

Install on RPi:
  pip install -r rpi/requirements.txt

--------------------------------------------------------------------------------
How to Run
--------------------------------------------------------------------------------

STEP 0 -- Network setup
  Ensure both the laptop and RPi are on the same WiFi network.
  Find the laptop's IP address: run `ipconfig getifaddr en0` on Mac.
  In rpi/replay.py and rpi/alert_handler.py, set:
    BROKER_IP = "<your laptop IP>"

STEP 1 -- Hardware setup (RPi only)
  Wire GrovePi LED to digital pin D4
  Wire GrovePi buzzer to digital pin D8
  In rpi/led_controller.py, set:
    REAL_HARDWARE = True
  (Leave as False if testing on laptop only)

--- ON YOUR LAPTOP (run in separate terminals) ---

STEP 2 -- Start the MQTT broker
  $ mosquitto

STEP 3 -- Start the server and dashboard
  $ cd laptop/
  $ python server.py
  Dashboard available at: http://localhost:5000

--- ON THE RASPBERRY PI ---

STEP 4 -- SSH into RPi
  $ ssh pi@<RPi_IP_address>

STEP 5 -- Start the alert handler
  $ cd rpi/
  $ python alert_handler.py

STEP 6 -- Start the vitals replay
  $ python replay.py --patient 41976 --speed 1

--- DEMO ---

Open http://localhost:5000 in your browser. Vitals update every second.
Watch the SOFA score trend as patient 41976 deteriorates -- the dashboard
will turn red, the alert banner will appear, and the GrovePi LED will
switch to red with the buzzer firing. Click Acknowledge to silence the
buzzer and log the response.

To test the override panel:
  Drag the SpO2 slider to 85% and click Inject -- watch the SOFA
  respiration subscore jump and the total score react immediately.

Additional flags for replay.py:
  --patient <id>    Select a specific MIMIC subject ID
  --speed <sec>     Seconds between readings (default 5, use 1 for demo)
  --list            List all available patient IDs

--------------------------------------------------------------------------------
External Libraries Used
--------------------------------------------------------------------------------

  paho-mqtt         MQTT client library
  flask             Lightweight Python web framework
  numpy             Numerical computing
  grovepi           GrovePi sensor/actuator interface (RPi only)
  sqlite3           Built-in Python -- session and alert storage
  threading         Built-in Python -- concurrent Flask + MQTT loops
  csv               Built-in Python -- MIMIC dataset parsing

--------------------------------------------------------------------------------
AI Tool Disclosure
--------------------------------------------------------------------------------

This project was developed with assistance from Claude (Anthropic) for
system architecture planning, code structure, and implementation guidance.
All design decisions, dataset selection, algorithm choices, hardware wiring,
testing, debugging, and final implementation were completed by the student.
Claude was used as a coding assistant in a manner consistent with the
course policy on transparent AI tool use.

--------------------------------------------------------------------------------
Known Limitations
--------------------------------------------------------------------------------

  - Simplified SOFA model: uses 4 organ systems from bedside vitals only.
    Full clinical SOFA uses 6 systems including lab values (bilirubin,
    creatinine, platelets) not present in the bedside vitals stream.

  - Demo dataset: MIMIC-III demo contains 50 patients with MetaVision
    format vitals. The full MIMIC-III dataset requires credentialing but
    was not necessary for this project scope.

  - Replay speed: default 5-second interval is 10x faster than real ICU
    monitoring cadence. Configurable via --speed flag.

  - Vitals grouping: readings within the same hour window are merged into
    one snapshot. Some snapshots may be missing one or more vitals if the
    sensor was not recorded that hour.

  - GrovePi LED: the led_controller supports any GrovePi RGB LED module.
    If unavailable, set REAL_HARDWARE = False to run in stub/print mode.

================================================================================
================================================================================
  EE 250 Final Project — ICU Watch Monitor
  README.txt
================================================================================

Team Members
------------
  Kaiden Ko, Ramanjot Singh

--------------------------------------------------------------------------------
Instructions to Execute
--------------------------------------------------------------------------------

STEP 1 -- Dataset setup
  Download the MIMIC-III demo dataset from:
  https://physionet.org/content/mimiciii-demo/1.4/
  Place CHARTEVENTS.csv at: rpi/data/mimic3-demo/CHARTEVENTS.csv

STEP 2 -- Network configuration
  Find your laptop IP: ipconfig getifaddr en0 (Mac) or hostname -I (Linux)
  In rpi/replay.py and rpi/alert_handler.py set:
    BROKER_IP = "<your laptop IP>"

STEP 3 -- Start MQTT broker (laptop terminal 1)
  $ mosquitto

STEP 4 -- Start server and dashboard (laptop terminal 2)
  $ cd laptop/
  $ python3 server.py
  Dashboard available at: http://localhost:5000

STEP 5 -- Start alert handler (RPi terminal 1)
  $ cd rpi/
  $ python3 alert_handler.py

STEP 6 -- Start vitals replay (RPi terminal 2)
  $ cd rpi/
  $ python3 replay.py --patient 41976 --speed 1

  Additional flags:
    --list            list all available patient IDs
    --speed <sec>     seconds between readings (default 5)
    --patient <id>    select a specific MIMIC subject ID

--------------------------------------------------------------------------------
External Libraries Used
--------------------------------------------------------------------------------

  paho-mqtt     MQTT client — publish and subscribe between nodes
  flask         Web framework — dashboard server
  numpy         Numerical computation — SOFA scoring
  grovepi       GrovePi hardware interface — LED and buzzer (RPi only)
  sqlite3       Built-in Python — session and alert storage
  threading     Built-in Python — concurrent Flask and MQTT loops
  csv           Built-in Python — MIMIC dataset parsing

================================================================================
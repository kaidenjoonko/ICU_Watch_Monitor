"""
led_controller.py
GrovePi LED and buzzer controller.

Hardware configuration:
  Green LED  -- D4
  White LED  -- D3
  Buzzer     -- D2

LED states:
  green    patient stable        green ON solid, white OFF
  yellow   patient deteriorating green OFF, white ON solid
  red      sepsis alert          both LEDs blinking + buzzer fires once
                                 then both keep blinking until resolved
  off      session ended         all off

Transitions:
  green  -> yellow : green turns off, white turns on
  yellow -> red    : white stops solid, both start blinking, buzzer fires once
  red    -> green  : blink stops, green turns on solid (patient recovered)
  red    -> ack    : blink stops, green turns on solid (clinician acknowledged)

Set REAL_HARDWARE = True when running on the actual RPi with GrovePi.
Set REAL_HARDWARE = False for laptop stub mode (prints to terminal).
"""

import time
import threading

# ── Hardware flag ─────────────────────────────────────────────────────────────
REAL_HARDWARE = True   # flip to False for laptop-only testing

GREEN_PIN  = 4
WHITE_PIN  = 3
BUZZER_PIN = 2

# ── GrovePi import ────────────────────────────────────────────────────────────
if REAL_HARDWARE:
    try:
        import grovepi
        grovepi.pinMode(GREEN_PIN,  "OUTPUT")
        grovepi.pinMode(WHITE_PIN,  "OUTPUT")
        grovepi.pinMode(BUZZER_PIN, "OUTPUT")
        print("[LED] GrovePi hardware initialized")
        print(f"[LED] Green=D{GREEN_PIN}  White=D{WHITE_PIN}  Buzzer=D{BUZZER_PIN}")
    except ImportError:
        print("[LED] WARNING -- grovepi not found, falling back to stub mode")
        REAL_HARDWARE = False
    except Exception as e:
        print(f"[LED] WARNING -- hardware init failed: {e}, falling back to stub mode")
        REAL_HARDWARE = False

# ── Current state tracking ────────────────────────────────────────────────────
_current_status = None   # track last applied status to detect transitions

# ── Blink thread control ──────────────────────────────────────────────────────
_blink_thread = None
_blink_active = False
_blink_lock   = threading.Lock()


def _stop_blink():
    global _blink_active
    with _blink_lock:
        _blink_active = False
    if _blink_thread and _blink_thread.is_alive():
        _blink_thread.join(timeout=1.0)


def _blink_loop(pins, interval):
    """Blink one or more pins simultaneously until stopped."""
    global _blink_active
    state = True
    while True:
        with _blink_lock:
            if not _blink_active:
                break
        for pin in pins:
            _write_pin(pin, 1 if state else 0)
        state = not state
        time.sleep(interval)
    # turn off all blink pins when stopped
    for pin in pins:
        _write_pin(pin, 0)


def _start_blink(pins, interval=0.4):
    global _blink_thread, _blink_active
    _stop_blink()
    time.sleep(0.05)
    with _blink_lock:
        _blink_active = True
    _blink_thread = threading.Thread(
        target=_blink_loop, args=(pins, interval), daemon=True
    )
    _blink_thread.start()


# ── Low level pin writes ──────────────────────────────────────────────────────

def _write_pin(pin, val):
    if REAL_HARDWARE:
        try:
            grovepi.digitalWrite(pin, val)
        except Exception as e:
            print(f"[LED] Pin write error D{pin}={val}: {e}")
    else:
        pin_name = {
            GREEN_PIN:  "GREEN",
            WHITE_PIN:  "WHITE",
            BUZZER_PIN: "BUZZER"
        }.get(pin, f"D{pin}")
        print(f"[STUB] {pin_name} -> {'ON' if val else 'OFF'}")


def _all_off():
    _write_pin(GREEN_PIN,  0)
    _write_pin(WHITE_PIN,  0)
    _write_pin(BUZZER_PIN, 0)


# ── Buzzer (fires once, non-blocking) ─────────────────────────────────────────

def _sound_buzzer(duration=3.0):
    print(f"[BUZZER] Firing for {duration}s")
    _write_pin(BUZZER_PIN, 1)
    time.sleep(duration)
    _write_pin(BUZZER_PIN, 0)
    print(f"[BUZZER] Off")


# ── Public API ────────────────────────────────────────────────────────────────

def set_green():
    """
    Patient stable.
    Green ON solid and stays on until status changes.
    White turns off.
    """
    _stop_blink()
    _write_pin(WHITE_PIN, 0)
    _write_pin(GREEN_PIN, 1)
    print("[STATUS] GREEN -- patient stable, green LED on")


def set_yellow():
    """
    Patient deteriorating.
    White ON solid and stays on until status changes.
    Green turns off.
    """
    _stop_blink()
    _write_pin(GREEN_PIN, 0)
    _write_pin(WHITE_PIN, 1)
    print("[STATUS] YELLOW -- deteriorating, white LED on")


def set_red():
    """
    Sepsis alert.
    Both LEDs start blinking and keep blinking until resolved.
    Buzzer fires once for 3 seconds then stops.
    Blinking continues until set_green() or set_blink_amber() is called.
    """
    # start continuous blink on both LEDs
    _start_blink([GREEN_PIN, WHITE_PIN], interval=0.4)
    # buzzer fires once in background, blinking continues independently
    buzzer_thread = threading.Thread(
        target=_sound_buzzer, args=(3.0,), daemon=True
    )
    buzzer_thread.start()
    print("[STATUS] RED -- SEPSIS ALERT, both LEDs blinking, buzzer firing")


def set_blink_amber():
    """
    Alert acknowledged by clinician.
    Stops blinking, green solid on — patient still elevated but reviewed.
    """
    _stop_blink()
    _write_pin(WHITE_PIN, 0)
    _write_pin(GREEN_PIN, 1)
    print("[STATUS] ACKNOWLEDGED -- green solid, buzzer silenced")


def set_off():
    """Session ended — turn everything off."""
    _stop_blink()
    _all_off()
    print("[STATUS] OFF")


def apply_status(status):
    """
    Main entry point called by alert_handler.py.
    Only applies a new state if status has actually changed —
    avoids flickering LEDs on every repeated message.
    """
    global _current_status

    if status == _current_status:
        return  # no change, do nothing

    _current_status = status

    if status == "green":
        set_green()
    elif status == "yellow":
        set_yellow()
    elif status == "red":
        set_red()
    else:
        set_off()


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== LED Controller Test ===")
    print(f"REAL_HARDWARE = {REAL_HARDWARE}\n")

    print("--- GREEN: patient stable (green stays on) ---")
    set_green()
    time.sleep(3)

    print("\n--- YELLOW: deteriorating (white stays on) ---")
    set_yellow()
    time.sleep(3)

    print("\n--- RED: sepsis alert (both blink, buzzer fires once, keeps blinking) ---")
    set_red()
    time.sleep(6)

    print("\n--- ACKNOWLEDGED: clinician acks (green solid, blinking stops) ---")
    set_blink_amber()
    time.sleep(3)

    print("\n--- OFF: session ended ---")
    set_off()

    print("\n[LED] Test complete")
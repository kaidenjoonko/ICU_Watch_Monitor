"""
led_controller.py
GrovePi LED and buzzer controller.

Controls the RGB LED and buzzer on the GrovePi to reflect patient status.

LED states:
  green       - patient stable
  yellow      - deteriorating, watch closely
  red         - sepsis alert, buzzer fires
  blink_amber - alert acknowledged, still elevated

Hardware:
  LED    wired to D4 (digital pin 4)
  Buzzer wired to D8 (digital pin 8)

Set REAL_HARDWARE = True when running on the actual RPi with GrovePi.
Set REAL_HARDWARE = False to run in stub mode on laptop (prints to terminal).
"""

import time
import threading

# ── Hardware flag ─────────────────────────────────────────────────────────────
# Flip this to True when running on the actual RPi
REAL_HARDWARE = False

LED_PIN    = 4
BUZZER_PIN = 8

# ── GrovePi import (only runs on RPi) ─────────────────────────────────────────
if REAL_HARDWARE:
    try:
        import grovepi
        import grove_rgb_lcd as lcd
        print("[LED] GrovePi hardware initialized")
    except ImportError:
        print("[LED] WARNING — grovepi not found, falling back to stub mode")
        REAL_HARDWARE = False

# ── Blink thread control ──────────────────────────────────────────────────────
_blink_thread  = None
_blink_active  = False
_blink_lock    = threading.Lock()


def _stop_blink():
    """Stop any currently running blink loop."""
    global _blink_active
    with _blink_lock:
        _blink_active = False


def _blink_loop(r, g, b, interval=0.6):
    """Blink the LED at given color. Runs in a background thread."""
    global _blink_active
    on = True
    while _blink_active:
        if on:
            _set_led(r, g, b)
        else:
            _set_led(0, 0, 0)
        on = not on
        time.sleep(interval)
    _set_led(0, 0, 0)


def _start_blink(r, g, b, interval=0.6):
    """Start blinking LED in background thread."""
    global _blink_thread, _blink_active
    _stop_blink()
    time.sleep(0.1)
    with _blink_lock:
        _blink_active = True
    _blink_thread = threading.Thread(
        target=_blink_loop, args=(r, g, b, interval), daemon=True
    )
    _blink_thread.start()


# ── Low-level hardware calls ──────────────────────────────────────────────────

def _set_led(r, g, b):
    if REAL_HARDWARE:
        grovepi.digitalWrite(LED_PIN, 1 if (r or g or b) else 0)
    else:
        color_name = _rgb_to_name(r, g, b)
        if color_name:
            print(f"[LED] {color_name}")


def _sound_buzzer(duration=1.0):
    if REAL_HARDWARE:
        grovepi.digitalWrite(BUZZER_PIN, 1)
        time.sleep(duration)
        grovepi.digitalWrite(BUZZER_PIN, 0)
    else:
        print(f"[BUZZER] ON for {duration}s")
        time.sleep(duration)
        print(f"[BUZZER] OFF")


def _rgb_to_name(r, g, b):
    if r == 0 and g == 0 and b == 0:
        return None
    if r == 0   and g == 255 and b == 0:   return "GREEN  — patient stable"
    if r == 255 and g == 200 and b == 0:   return "YELLOW — deteriorating"
    if r == 255 and g == 0   and b == 0:   return "RED    — SEPSIS ALERT"
    if r == 255 and g == 140 and b == 0:   return "AMBER  — acknowledged"
    return f"RGB({r},{g},{b})"


# ── Public API ────────────────────────────────────────────────────────────────

def set_green():
    """Stable — solid green."""
    _stop_blink()
    _set_led(0, 255, 0)


def set_yellow():
    """Deteriorating — solid yellow."""
    _stop_blink()
    _set_led(255, 200, 0)


def set_red():
    """Sepsis alert — solid red + buzzer."""
    _stop_blink()
    _set_led(255, 0, 0)
    buzzer_thread = threading.Thread(
        target=_sound_buzzer, args=(3.0,), daemon=True
    )
    buzzer_thread.start()


def set_blink_amber():
    """Alert acknowledged — slow blinking amber."""
    _start_blink(255, 140, 0, interval=0.8)


def set_off():
    """Turn everything off."""
    _stop_blink()
    _set_led(0, 0, 0)


def apply_status(status):
    """
    Main entry point — call this with the status string from the server.
    Maps green / yellow / red to the correct LED state.
    """
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
    print("=== LED Controller Test ===\n")
    print("Simulating patient deterioration sequence...\n")

    print("Status: green")
    apply_status("green")
    time.sleep(1)

    print("Status: yellow")
    apply_status("yellow")
    time.sleep(1)

    print("Status: red")
    apply_status("red")
    time.sleep(4)

    print("Status: acknowledged (blink amber)")
    set_blink_amber()
    time.sleep(3)

    print("Status: back to green")
    apply_status("green")
    time.sleep(1)

    set_off()
    print("\n[LED] Test complete")
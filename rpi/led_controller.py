import time
import threading

REAL_HARDWARE = True

GREEN_PIN  = 4
WHITE_PIN  = 3
BUZZER_PIN = 2

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

_current_status = None

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
    global _blink_active
    state = True
    while True:
        with _blink_lock:
            if not _blink_active:
                break
        for pin in pins:
            if state:
                _write_pin(pin, 1)
            else:
                _write_pin(pin, 0)
        state = not state
        time.sleep(interval)
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


def _write_pin(pin, val):
    if REAL_HARDWARE:
        try:
            grovepi.digitalWrite(pin, val)
        except Exception as e:
            print(f"[LED] Pin write error D{pin}={val}: {e}")
    else:
        if pin == GREEN_PIN:
            pin_name = "GREEN"
        elif pin == WHITE_PIN:
            pin_name = "WHITE"
        elif pin == BUZZER_PIN:
            pin_name = "BUZZER"
        else:
            pin_name = "D" + str(pin)

        if val:
            print(f"[STUB] {pin_name} -> ON")
        else:
            print(f"[STUB] {pin_name} -> OFF")


def _all_off():
    _write_pin(GREEN_PIN,  0)
    _write_pin(WHITE_PIN,  0)
    _write_pin(BUZZER_PIN, 0)


def _sound_buzzer(duration=3.0):
    print(f"[BUZZER] Firing for {duration}s")
    _write_pin(BUZZER_PIN, 1)
    time.sleep(duration)
    _write_pin(BUZZER_PIN, 0)
    print(f"[BUZZER] Off")


def set_green():
    _stop_blink()
    _write_pin(WHITE_PIN, 0)
    _write_pin(GREEN_PIN, 1)
    print("[STATUS] GREEN -- patient stable, green LED on")


def set_yellow():
    _stop_blink()
    _write_pin(GREEN_PIN, 0)
    _write_pin(WHITE_PIN, 1)
    print("[STATUS] YELLOW -- deteriorating, white LED on")


def set_red():
    _start_blink([GREEN_PIN, WHITE_PIN], interval=0.4)
    buzzer_thread = threading.Thread(
        target=_sound_buzzer, args=(3.0,), daemon=True
    )
    buzzer_thread.start()
    print("[STATUS] RED -- SEPSIS ALERT, both LEDs blinking, buzzer firing")


def set_blink_amber():
    _stop_blink()
    _write_pin(WHITE_PIN, 0)
    _write_pin(GREEN_PIN, 1)
    print("[STATUS] ACKNOWLEDGED -- green solid, buzzer silenced")


def set_off():
    _stop_blink()
    _all_off()
    print("[STATUS] OFF")


def apply_status(status):
    global _current_status

    if status == _current_status:
        return

    _current_status = status

    if status == "green":
        set_green()
    elif status == "yellow":
        set_yellow()
    elif status == "red":
        set_red()
    else:
        set_off()


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

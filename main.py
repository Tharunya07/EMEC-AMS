# main.py

import time
import signal
import sys
from datetime import datetime
from rfid.validator import RFIDValidator
from relay.controller import RelayController
from config.constants import CARD_POLL_INTERVAL

MACHINE_ID = "lathe-001"
MACHINE_TYPE = "Manual Lathe"

validator = None
relay = None
current_session_id = None
lcd = None

def handle_exit(sig, frame):
    print("\n[SYSTEM] Shutdown triggered.")
    if validator:
        validator.end_session_if_active(current_session_id)
        validator.cleanup()
    if relay:
        try:
            relay.deactivate_relay()
            relay.cleanup()
        except Exception as e:
            print("[RELAY] Cleanup error:", e)
    if lcd:
        try:
            lcd.clear()
            lcd.close()
        except:
            pass
    sys.exit(0)

def main():
    global validator, relay, current_session_id, lcd

    from lcd.lcd import LCD
    lcd = LCD()

    validator = RFIDValidator(machine_id=MACHINE_ID, machine_type=MACHINE_TYPE, lcd=lcd)
    relay = RelayController()

    current_session_id = None
    relay_on = False

    print("[SYSTEM] EMEC Access Control running...")
    lcd.show_message("? EMEC Access\nScan CSU ID card")

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTSTP, handle_exit)

    while True:
        result = validator.scan_and_validate()

        if result:
            uid, csu_id, session_id, status = result

            if status == "authorized" and not relay_on:
                relay.activate_relay(session_id)
                current_session_id = session_id
                relay_on = True
                print(f"[RELAY] ON - Session {session_id}")

        elif relay_on:
            now = datetime.now()

            if validator.should_continue_session(now):
                pass  # Grace countdown shown inside validator
            else:
                print(f"[SYSTEM] Session timeout. Ending session {current_session_id}")
                validator.end_session_if_active(current_session_id)
                relay.deactivate_relay()
                relay_on = False
                current_session_id = None
                lcd.show_message("? Session ended\nMachine idle")

        else:
            lcd.show_message("? Please scan\nCSU ID card")

        time.sleep(CARD_POLL_INTERVAL)

if __name__ == "__main__":
    main()

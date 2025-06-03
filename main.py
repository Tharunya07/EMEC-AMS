# main.py

from utils.startup_check import startup_sequence
from rfid.reader import RFIDReader
from rfid.validator import validate_card
from relay.session_manager import SessionManager
from lcd.lcd import LCD
import time
import signal
import sys
from db.local_db import LocalDB
from config.constants import CARD_POLL_INTERVAL, MACHINE_ID

lcd = LCD()
reader = RFIDReader()
session_mgr = SessionManager()
db = LocalDB()

def exit_handler(sig, frame):
    lcd.display("Shutting down...")
    db.update_machine_status(MACHINE_ID, "offline")
    db.update_machine_heartbeat(MACHINE_ID)
    lcd.clear()
    sys.exit(0)

signal.signal(signal.SIGINT, exit_handler)

def main():
    while True:
        # PHASE 1 ? Startup
        if not startup_sequence():
            time.sleep(5)
            continue

        # PHASE 2 ? Scan for CSU ID
        while True:
            scan = reader.read_card()
            if scan:
                uid_num, csu_id = scan
                validated_csu_id, display_name = validate_card(csu_id)
                if validated_csu_id:
                    break
            time.sleep(CARD_POLL_INTERVAL)

        # PHASE 3 ? Start Session
        session_mgr.start_session(validated_csu_id, display_name)

        # PHASE 4 ? Wait for card removal
        session_mgr.wait_for_card_removal(reader)

        # PHASE 5 ? Grace Period Logic
        outcome = session_mgr.handle_grace_period(reader)

        # PHASE 6 ? Restart loop regardless of outcome
        continue

if __name__ == "__main__":
    main()

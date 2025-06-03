# relay/session_manager.py

import time
import uuid
import logging
import RPi.GPIO as GPIO
from lcd.lcd import LCD
from config.constants import RELAY_PIN, MACHINE_ID, CARD_GRACE_PERIOD_DEFAULT
from db.local_db import LocalDB
from db.azure_sync import sync_session_to_azure, push_user_status, push_machine_status
from relay.controller import RelayController

logger = logging.getLogger("session")
log_file = logging.FileHandler("logs/sync.log")
logger.setLevel(logging.INFO)
logger.addHandler(log_file)

class SessionManager:
    def __init__(self):
        self.db = LocalDB()
        self.lcd = LCD()
        self.relay = RelayController()
        self.active_session_id = None
        self.active_csu_id = None
        self.session_start_time = None
        self.display_name = None

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
        GPIO.output(RELAY_PIN, GPIO.LOW)

    def start_session(self, csu_id, display_name):
        if not self.active_session_id:
            self.active_session_id = str(uuid.uuid4())
            self.session_start_time = time.time()
            self.db.mark_user_active(csu_id)
            self.db.insert_session(self.active_session_id, csu_id, MACHINE_ID)
            logger.info(f"[SESSION] Started: {display_name} ({csu_id}), session_id: {self.active_session_id}")
        else:
            logger.info("[SESSION] Resumed session within grace period.")

        self.active_csu_id = csu_id
        self.display_name = display_name
        self.db.update_machine_status(MACHINE_ID, "in_use")
        self.db.update_machine_heartbeat(MACHINE_ID)
        push_user_status(csu_id)
        push_machine_status(MACHINE_ID)

        self.relay.turn_on()
        self.lcd.clear()
        self.lcd.display(1, f"{display_name[:20]}")
        self.lcd.display(2, "in use")

    def wait_for_card_removal(self, reader):
        absence_start = None
        while True:
            scan = reader.read_card()
            if scan:
                uid, csu_id = scan
                if csu_id == self.active_csu_id:
                    absence_start = None
                else:
                    logger.info("[SESSION] New card detected mid-session.")
                    self.lcd.clear()
                    self.lcd.display(1, "New card detected")
                    self.lcd.display(2, "Resetting...")
                    time.sleep(2)
                    self.force_end_session()
                    break
            else:
                if absence_start is None:
                    absence_start = time.time()
                elif time.time() - absence_start >= 5:
                    self.lcd.clear()
                    self.lcd.display(1, "Card removed")
                    break
            time.sleep(0.5)

    def handle_grace_period(self, reader):
        grace_period = self.db.get_setting("grace_period_seconds", default=CARD_GRACE_PERIOD_DEFAULT)
        end_time = time.time() + grace_period
        while time.time() < end_time:
            remaining = int(end_time - time.time())
            self.lcd.display(2, f"{remaining}s to reinsert")

            scan = reader.read_card()
            if scan:
                uid, csu_id = scan
                if csu_id == self.active_csu_id:
                    self.lcd.clear()
                    self.lcd.display(1, "Continuing session")
                    time.sleep(1)
                    self.start_session(csu_id, self.display_name)
                    return "resumed"
                else:
                    self.lcd.clear()
                    self.lcd.display(1, "New card detected")
                    self.lcd.display(2, "Resetting...")
                    time.sleep(2)
                    self.force_end_session()
                    return "new_card"
            time.sleep(1)

        self.force_end_session()
        logger.info("[SESSION] Ended after grace period.")
        return "timeout"

    def force_end_session(self):
        if not self.active_session_id:
            return

        end_time = time.time()
        duration_sec = int(end_time - self.session_start_time)
        duration_min = max(0, round(duration_sec / 60))

        self.db.end_session(self.active_session_id)
        self.db.mark_user_inactive(self.active_csu_id)
        self.db.update_machine_status(MACHINE_ID, "neutral")
        self.db.update_machine_heartbeat(MACHINE_ID)

        push_user_status(self.active_csu_id)
        push_machine_status(MACHINE_ID)

        sync_session_to_azure(self.active_session_id)
        logger.info(f"[SESSION] Ended: {self.display_name} ({self.active_csu_id}), duration: {duration_min} min")

        self.lcd.clear()
        self.lcd.display(1, "Session ended")
        time.sleep(1)

        self.active_session_id = None
        self.active_csu_id = None
        self.session_start_time = None
        self.display_name = None
        self.relay.turn_off()

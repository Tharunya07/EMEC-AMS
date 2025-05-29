# relay/session_manager.py

import RPi.GPIO as GPIO
import time
import uuid
import signal
import atexit
from datetime import datetime
import db.local_db as local_db
from lcd.lcd import LCD
from db.azure_sync import AzureConnection
from config.constants import STATUS_NEUTRAL

class SessionManager:
    def __init__(self, lcd: LCD, azure: AzureConnection, machine_id: str, pin: int):
        self.lcd = lcd
        self.azure = azure
        self.machine_id = machine_id
        self.relay_pin = pin
        self.session_id = None
        self.csu_id = None
        self.running = False

        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.relay_pin, GPIO.OUT)
        GPIO.output(self.relay_pin, GPIO.LOW)

        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def start_session(self, csu_id):
        self.session_id = str(uuid.uuid4())
        self.csu_id = csu_id
        self.running = True

        now = datetime.now()
        local_db.insert_machine_usage_log(self.session_id, csu_id, self.machine_id, now.strftime("%Y-%m-%d %H:%M:%S"))
        local_db.update_user_active(csu_id, True)
        local_db.update_user_last_used(csu_id, now.strftime("%Y-%m-%d %H:%M:%S"))
        local_db.update_machine_status(self.machine_id, "in_use")
        local_db.update_machine_heartbeat(self.machine_id, now.strftime("%Y-%m-%d %H:%M:%S"))

        GPIO.output(self.relay_pin, GPIO.HIGH)
        name = local_db.get_user_name_by_uid(self._get_uid_from_csu(csu_id)) or csu_id
        self.lcd.show_message(f"{name} in use")

    def stop_session(self):
        if not self.running or not self.session_id or not self.csu_id:
            return

        end_time = datetime.now()
        local_db.close_machine_usage_log(self.csu_id, self.machine_id, end_time)
        local_db.update_user_active(self.csu_id, False)
        local_db.update_machine_status(self.machine_id, STATUS_NEUTRAL)
        local_db.update_machine_heartbeat(self.machine_id, end_time.strftime("%Y-%m-%d %H:%M:%S"))

        GPIO.output(self.relay_pin, GPIO.LOW)
        self.lcd.show_message("Session Ended\nMachine idle")
        self.running = False
        self.session_id = None
        self.csu_id = None

    def _get_uid_from_csu(self, csu_id):
        conn = local_db.get_connection()
        c = conn.cursor()
        c.execute("SELECT uid FROM Users WHERE csu_id = ?", (csu_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else csu_id

    def cleanup(self):
        print("[RELAY] Cleanup triggered")
        self.stop_session()
        self.lcd.clear()
        GPIO.output(self.relay_pin, GPIO.LOW)
        GPIO.cleanup()

    def signal_handler(self, signum, frame):
        self.cleanup()
        exit(0)

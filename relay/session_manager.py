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
from config.constants import STATUS_NEUTRAL, STATUS_OFFLINE

class SessionManager:
    def __init__(self, lcd: LCD, azure: AzureConnection, machine_id: str, pin: int):
        self.lcd = lcd
        self.azure = azure
        self.machine_id = machine_id
        self.pin = pin
        self.session_id = None
        self.csu_id = None
        self.running = False

        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.pin, GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)

        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def start_session(self, csu_id):
        self.session_id = str(uuid.uuid4())
        self.csu_id = csu_id
        self.running = True

        GPIO.output(self.pin, GPIO.HIGH)

    def stop_session(self, csu_id):
        if not self.running:
            return

        end_time = datetime.now()
        local_db.close_machine_usage_log(csu_id, self.machine_id, end_time)
        local_db.update_user_active(csu_id, False)
        local_db.update_machine_status(self.machine_id, STATUS_NEUTRAL)
        local_db.update_machine_heartbeat(self.machine_id, end_time.strftime("%Y-%m-%d %H:%M:%S"))

        GPIO.output(self.pin, GPIO.LOW)
        self.running = False
        self.session_id = None
        self.csu_id = None

    def cleanup(self):
        print("[RELAY] Cleanup triggered")
        GPIO.output(self.pin, GPIO.LOW)
        GPIO.cleanup()

    def signal_handler(self, signum, frame):
        self.cleanup()
        print("[RELAY] OFF")
        exit(0)

    def get_device_id(self):
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("Serial"):
                        return line.strip().split(":")[1].strip()
        except:
            return "UNKNOWN"

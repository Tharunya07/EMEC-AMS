# main.py

import RPi.GPIO as GPIO
import signal
import sys
import time
import uuid
from datetime import datetime

from lcd.lcd import LCD
from rfid.reader import RFIDReader
import db.local_db as local_db
from db.azure_sync import AzureConnection
from relay.session_manager import SessionManager
from config.constants import *
from utils.startup_check import StartupCheck
from rfid.validator import Validator

lcd = LCD()
reader = RFIDReader()
azure = AzureConnection()
machine_id = local_db.get_machine_id()
relay = SessionManager(lcd, azure, machine_id, PIN_RELAY)

uid_active = None
csu_active = None

def cleanup_and_exit():
    print("[MAIN] Shutting down...")
    relay.cleanup()
    lcd.show_message("Session ended\nMachine idle")
    local_db.update_machine_status(machine_id, STATUS_OFFLINE)
    lcd.clear()
    GPIO.cleanup()
    sys.exit(0)

def signal_handler(sig, frame):
    cleanup_and_exit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    lcd.show_message("Booting system...")
    startup = StartupCheck(lcd, azure, machine_id)
    if not startup.run():
        cleanup_and_exit()

    lcd.show_message("All clear.")
    time.sleep(1.5)
    lcd.show_message("Welcome to EMEC!")
    time.sleep(1.5)

    grace_period = local_db.get_grace_period()
    validator = Validator(lcd, reader, azure, machine_id)

    lcd.show_message("Scan your CSU ID")

    while True:
        result = reader.read_card()
        if result is None:
            continue

        uid, csu_id = result
        if uid is None or csu_id is None:
            continue

        print(f"[RFID] Card scanned ? UID: {uid}, CSU ID: {csu_id}")
        print(f"[INFO] Card scanned: UID={uid}, CSU={csu_id}")

        if validator.try_resume_session(uid, csu_id):
            uid_active, csu_active = uid, csu_id
            relay.start_session(csu_id)
            continue

        decision = validator.validate(uid, csu_id)
        if decision == "ALLOW":
            relay.start_session(csu_id)
            uid_active, csu_active = uid, csu_id
        else:
            uid_active = None
            csu_active = None

        while uid_active:
            result_check = reader.read_card()
            if result_check is None:
                continue

            uid_check, _ = result_check
            if uid_check != uid_active:
                lcd.show_message(f"Card removed\n{grace_period}s left")
                countdown = grace_period
                while countdown > 0:
                    time.sleep(1)
                    result_recheck = reader.read_card()
                    if result_recheck is None:
                        countdown -= 1
                        lcd.show_message(f"Reinsert to continue\n{countdown}s left")
                        continue

                    uid_recheck, _ = result_recheck
                    if uid_recheck == uid_active:
                        lcd.show_message("Continuing session")
                        break

                    countdown -= 1
                    lcd.show_message(f"Reinsert to continue\n{countdown}s left")

                else:
                    relay.stop_session()
                    uid_active = None
                    csu_active = None

            time.sleep(0.5)

if __name__ == "__main__":
    main()

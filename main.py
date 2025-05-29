# main.py

import RPi.GPIO as GPIO
import signal
import sys
import time
from datetime import datetime
import uuid

from lcd.lcd import LCD
from rfid.reader import RFIDReader
from db.azure_sync import AzureConnection
import db.local_db as local_db
from relay.session_manager import SessionManager
from rfid.validator import Validator
from config.constants import *

lcd = LCD()
reader = RFIDReader()
azure = AzureConnection()
machine_id = local_db.get_machine_id()

relay = SessionManager(lcd, azure, machine_id, PIN_RELAY)
validator = Validator(reader, local_db, machine_id)
uid_active = None
csu_active = None

def cleanup_and_exit():
    print("[MAIN] Shutting down...")
    if uid_active and csu_active:
        relay.stop_session(csu_active)
        azure.push_machine_status(machine_id, STATUS_OFFLINE)
    else:
        local_db.update_machine_status(machine_id, STATUS_OFFLINE)
        azure.push_machine_status(machine_id, STATUS_OFFLINE)
    lcd.clear()
    GPIO.cleanup()
    sys.exit(0)

def signal_handler(sig, frame):
    cleanup_and_exit()

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    lcd.show_message("Booting system...")
    time.sleep(1)

    # Initial push to Azure on startup
    azure.update_machine_status(machine_id, STATUS_NEUTRAL)
    azure.update_machine_heartbeat(machine_id, relay.get_device_id())
    lcd.show_message("System Ready")
    time.sleep(1.5)

    grace_period = local_db.get_grace_period()
    lcd.show_message("Scan your CSU ID")

    while True:
        uid, csu_id = reader.read_card()
        if not uid or not csu_id:
            continue

        print(f"[RFID] Card scanned ? UID: {uid}, CSU ID: {csu_id}")
        name = local_db.get_user_name_by_uid(uid)
        display_name = name if name else csu_id
        print(f"[INFO] Card scanned: UID={uid}, CSU={csu_id}")

        if validator.try_resume_session(uid, csu_id):
            uid_active, csu_active = uid, csu_id
            relay.lcd.show_message(f"{display_name} in use")
            continue

        decision = validator.validate(uid, csu_id)
        if decision != "ALLOW":
            lcd.show_message("Access Denied")
            time.sleep(2)
            lcd.show_message("Scan your CSU ID")
            continue

        # Start new session
        session_id = str(uuid.uuid4())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        local_db.insert_machine_usage_log(session_id, csu_id, machine_id, now)
        local_db.update_user_active(csu_id, True)
        local_db.update_user_last_used(csu_id, now)
        local_db.update_machine_status(machine_id, STATUS_IN_USE)
        local_db.update_machine_heartbeat(machine_id, now)

        azure.push_user_status(csu_id, True, now)
        azure.push_machine_status(machine_id, STATUS_IN_USE)
        azure.push_machine_heartbeat(machine_id)

        relay.start_session(csu_id)
        lcd.show_message(f"{display_name} in use")
        uid_active, csu_active = uid, csu_id

        # Monitor card presence and handle grace period
        while uid_active:
            time.sleep(0.5)
            uid_check, _ = reader.read_card()
            if uid_check == uid_active:
                continue

            # Start debounce
            absent_count = 0
            for _ in range(5):
                uid_check, _ = reader.read_card()
                if uid_check == uid_active:
                    break
                absent_count += 1
                time.sleep(1)

            if absent_count < 5:
                continue

            lcd.show_message(f"Card removed\n{grace_period}s left")
            countdown = grace_period
            while countdown > 0:
                time.sleep(1)
                uid_check, _ = reader.read_card()
                if uid_check == uid_active:
                    lcd.show_message("Continuing session")
                    time.sleep(1.5)
                    lcd.show_message(f"{display_name} in use")
                    break
                countdown -= 1
                lcd.show_message(f"Reinsert to continue\n{countdown}s left")
            else:
                # Session ends
                relay.stop_session(csu_id)
                azure.push_user_status(csu_id, False, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                azure.push_machine_status(machine_id, STATUS_NEUTRAL)
                azure.push_machine_heartbeat(machine_id)
                uid_active = None
                csu_active = None
                lcd.show_message("Session Ended\nMachine idle")
                time.sleep(2)
                lcd.show_message("Scan your CSU ID")

if __name__ == "__main__":
    main()

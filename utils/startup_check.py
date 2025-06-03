# utils/startup_check.py

import os
import time
import socket
from lcd.lcd import LCD
from config.constants import (
    LCD_MESSAGES,
    STATUS_MAINTENANCE,
    MACHINE_ID,
    DEVICE_ID
)
from db.local_db import LocalDB
from db.azure_sync import sync_local_from_azure, push_machine_status
import logging

logger = logging.getLogger("startup")
log_file = logging.FileHandler("logs/sync.log")
logger.setLevel(logging.INFO)
logger.addHandler(log_file)

def check_internet():
    try:
        return socket.gethostbyname("google.com")
    except:
        return False

def startup_sequence():
    lcd = LCD()
    db = LocalDB()

    logger.info("[STEP] Starting system checks...")

    if not check_internet():
        lcd.show_message("\n".join(LCD_MESSAGES["internet_error"]))
        logger.error("[FAIL] No Internet")
        return False

    logger.info("[PASS] Internet check passed.")

    try:
        lcd.display(1, "Syncing with Azure")
        sync_local_from_azure()
        logger.info("[PASS] Azure sync complete.")
    except Exception as e:
        lcd.show_message("\n".join(LCD_MESSAGES["azure_error"]))
        logger.error(f"[ERROR] Azure sync failed: {e}")
        return False

    machine = db.get_machine(MACHINE_ID)
    if not machine:
        lcd.display(1, f"Machine {MACHINE_ID}")
        lcd.display(2, "not registered")
        db.insert_machine_if_missing(MACHINE_ID)
        logger.warning(f"[WARN] Machine {MACHINE_ID} not found. Inserting default.")

    machine = db.get_machine(MACHINE_ID)
    if machine["machine_status"] == STATUS_MAINTENANCE:
        lcd.show_message("\n".join(LCD_MESSAGES["maintenance"]))
        logger.warning("[HALT] Machine in maintenance mode.")
        return False

    db.update_machine_status(MACHINE_ID, "neutral")
    logger.info("[PASS] Machine status set to neutral.")

    db.update_machine_device(MACHINE_ID, DEVICE_ID)
    db.update_machine_heartbeat(MACHINE_ID)
    logger.info("[PASS] Device ID + Heartbeat updated.")

    push_machine_status(MACHINE_ID)

    lcd.show_message("\n".join(LCD_MESSAGES["start"]))
    time.sleep(2)
    return True

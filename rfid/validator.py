# rfid/validator.py

import time
import logging
from db.local_db import LocalDB
from db.azure_sync import sync_local_from_azure, push_access_requests
from lcd.lcd import LCD
from config.constants import MACHINE_ID
from relay.controller import RelayController
from utils.startup_check import startup_sequence

logger = logging.getLogger("validator")
lcd = LCD()
relay = RelayController()
db = LocalDB()

def validate_card(csu_id):
    logger.info(f"[VALIDATOR] Card scanned: {csu_id}")
    user = db.get_user(csu_id)

    # CASE 1: Unknown or unauthorized user
    if not user or not db.has_permission(csu_id, MACHINE_ID):
        if db.access_request_exists(csu_id, MACHINE_ID):
            lcd.display(1, "Already sent")
            lcd.display(2, "Please wait")
            logger.info(f"[ACCESS] Request already exists for {csu_id}")
        else:
            db.insert_access_request(csu_id, MACHINE_ID)
            push_access_requests()  # sync immediately to Azure
            lcd.display(1, "Request sent")
            lcd.display(2, "Please wait")
            logger.info(f"[ACCESS] Request raised for {csu_id}")
        time.sleep(2)

        # After request sync, re-sync system data
        startup_sequence()
        return None, None

    # CASE 2: Valid user with permission
    display_name = user.get("name") or csu_id
    lcd.display(1, f"{display_name} in use")
    logger.info(f"[ACCESS] Granted to {csu_id} - {display_name}")
    db.mark_user_active(csu_id)
    db.update_machine_status(MACHINE_ID, "in_use")
    db.update_machine_heartbeat(MACHINE_ID)
    relay.turn_on()
    return csu_id, display_name

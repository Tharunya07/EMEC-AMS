# rfid/validator.py

import time
import db.local_db as local_db
from lcd.lcd import LCD
from rfid.reader import RFIDReader
from db.azure_sync import AzureConnection
from config.constants import LCD_MESSAGES

class Validator:
    def __init__(self, lcd: LCD, reader: RFIDReader, azure: AzureConnection, machine_id: str):
        self.lcd = lcd
        self.reader = reader
        self.azure = azure
        self.machine_id = machine_id

    def scan_card(self):
        return self.reader.read_card()

    def is_recent_session(self, csu_id):
        session = local_db.get_latest_session(csu_id, self.machine_id)
        if not session:
            return False
        end_time = session.get('end_time')
        if not end_time:
            return False
        elapsed = (time.time() - end_time.timestamp())
        return elapsed <= 300

    def validate(self, uid, csu_id):
        user = local_db.get_user_by_uid(uid)
        if not user:
            local_db.create_access_request(uid, csu_id, self.machine_id)
            self.lcd.show_message("\n".join(LCD_MESSAGES["unknown_user"]))
            return "DENY"

        if local_db.check_permission(csu_id, self.machine_id):
            return "ALLOW"

        request = local_db.get_access_request(csu_id, self.machine_id)
        if request:
            status = request['status']
            if status == "under_review":
                self.lcd.show_message("\n".join(LCD_MESSAGES["request_pending"]))
            elif status == "rejected":
                self.lcd.show_message("\n".join(LCD_MESSAGES["request_denied"]))
            return "DENY"

        local_db.create_access_request(uid, csu_id, self.machine_id)
        self.lcd.show_message("\n".join(LCD_MESSAGES["request_sent"]))
        return "DENY"

    def try_resume_session(self, uid, csu_id):
        if self.is_recent_session(csu_id):
            self.lcd.show_message("Continuing session")
            time.sleep(2)
            return True
        return False

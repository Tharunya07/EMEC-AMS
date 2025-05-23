# rfid/validator.py

from rfid.reader import RFIDReader
from db.local_db import LocalDB
from config.constants import *
from datetime import datetime
import uuid

class RFIDValidator:
    def __init__(self, machine_id, machine_type, lcd=None):
        self.machine_id = machine_id
        self.machine_type = machine_type
        self.reader = RFIDReader()
        self.db = LocalDB(lcd=lcd)
        self.lcd = lcd

        self.session_id = None
        self.session_uid = None
        self.session_csu_id = None

        self.card_confirmed = False
        self.card_stable_since = None
        self.card_missing_since = None
        self.grace_start_time = None
        self.grace_seconds = self.db.get_setting("grace_period_seconds", default=CARD_GRACE_PERIOD)

        self.last_seen_uid = None
        self.last_seen_csu = None
        self.stable_reads = 0
        self.MIN_STABLE_READS = 2
        self.MAX_MISSES = 3
        self.missed_reads = 0
        self.CONFIRM_REMOVAL_SECONDS = 5

    def scan_and_validate(self):
        now = datetime.now()
        result = self.reader.read_card()

        if result:
            uid, csu_id = result

            # Card debounce logic
            if uid == self.last_seen_uid:
                self.stable_reads += 1
            else:
                self.stable_reads = 1
                self.last_seen_uid = uid
                self.last_seen_csu = csu_id

            if self.stable_reads >= self.MIN_STABLE_READS:
                if not self.card_confirmed:
                    self.card_stable_since = now
                    print(f"[STATE] Card seen stable ? UID: {uid}")
                    self.card_confirmed = True
                    self.grace_start_time = None
                    self.card_missing_since = None

                self.db.update_user_activity(csu_id, active=True)
                name = self.db.get_user_name(csu_id)

                if self.session_uid == uid and self.session_id:
                    print(f"[DEBUG] Continuing session {self.session_id} for {csu_id}")
                else:
                    self.session_id = str(uuid.uuid4())
                    self.session_uid = uid
                    self.session_csu_id = csu_id
                    self.db.log_session_start(self.session_id, csu_id, self.machine_id, self.machine_type)
                    print(f"[DEBUG] Started session {self.session_id} for {name}")

                if self.lcd:
                    self.lcd.show_message(f"{name} in use")

                self.missed_reads = 0
                return uid, csu_id, self.session_id, "authorized"

        else:
            # Missed a read
            self.missed_reads += 1

            if self.card_confirmed and self.missed_reads >= self.MAX_MISSES:
                if not self.card_missing_since:
                    self.card_missing_since = now
                    print("[STATE] Card may be removed... starting watch")
                elif (now - self.card_missing_since).total_seconds() >= self.CONFIRM_REMOVAL_SECONDS:
                    print("[STATE] Card confirmed removed ? relay off, start grace")
                    self.card_confirmed = False
                    self.grace_start_time = now
                    if self.lcd:
                        self.lcd.show_message("? Card removed")
                        self.lcd.update_line(2, f"{self.grace_seconds}s left")

        return None

    def should_continue_session(self, now):
        if self.grace_start_time:
            elapsed = (now - self.grace_start_time).total_seconds()
            if elapsed < self.grace_seconds:
                remaining = int(self.grace_seconds - elapsed)
                print(f"[DEBUG] Grace active ? {remaining}s left")
                if self.lcd:
                    self.lcd.update_line(2, f"{remaining}s left")
                return True
            else:
                print("[DEBUG] Grace expired. Ending session.")
        return False

    def end_session_if_active(self, session_id):
        if session_id:
            self.db.log_session_end(session_id, self.machine_id)
            self.db.update_user_activity(self.session_csu_id, active=False)
            print(f"[DEBUG] Session {session_id} ended and logged.")
        self._reset()

    def _reset(self):
        self.session_id = None
        self.session_uid = None
        self.session_csu_id = None
        self.card_confirmed = False
        self.card_stable_since = None
        self.card_missing_since = None
        self.grace_start_time = None
        self.last_seen_uid = None
        self.last_seen_csu = None
        self.stable_reads = 0
        self.missed_reads = 0

    def cleanup(self):
        if self.session_id:
            self.end_session_if_active(self.session_id)
        if self.lcd:
            self.lcd.clear()
        self.reader.cleanup()
        self.db.close()

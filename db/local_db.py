# db/local_db.py

import sqlite3
import time
from config.constants import LOCAL_DB_PATH

class LocalDB:
    def __init__(self):
        self.conn = sqlite3.connect(LOCAL_DB_PATH)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def get_machine(self, machine_id):
        self.cursor.execute("SELECT * FROM machine WHERE machine_id = ?", (machine_id,))
        return self.cursor.fetchone()

    def insert_machine_if_missing(self, machine_id):
        self.cursor.execute("SELECT * FROM machine WHERE machine_id = ?", (machine_id,))
        if not self.cursor.fetchone():
            self.cursor.execute("""
                INSERT INTO machine (machine_id, machine_name, machine_type, machine_status)
                VALUES (?, ?, ?, 'neutral')
            """, (machine_id, machine_id.upper(), "generic"))
            self.conn.commit()

    def update_machine_status(self, machine_id, status):
        self.cursor.execute("UPDATE machine SET machine_status = ? WHERE machine_id = ?", (status, machine_id))
        self.conn.commit()

    def update_machine_device(self, machine_id, device_id):
        self.cursor.execute("UPDATE machine SET device_id = ? WHERE machine_id = ?", (device_id, machine_id))
        self.conn.commit()

    def update_machine_heartbeat(self, machine_id):
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        self.cursor.execute("UPDATE machine SET last_heartbeat = ? WHERE machine_id = ?", (now, machine_id))
        self.conn.commit()

    def get_setting(self, key, default=None):
        self.cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
        row = self.cursor.fetchone()
        return int(row[0]) if row else default

    def get_user(self, csu_id):
        self.cursor.execute("SELECT * FROM users WHERE csu_id = ?", (csu_id,))
        return self.cursor.fetchone()

    def has_permission(self, csu_id, machine_id):
        self.cursor.execute(
            "SELECT * FROM machine_permissions WHERE csu_id = ? AND machine_id = ?",
            (csu_id, machine_id)
        )
        return self.cursor.fetchone() is not None

    def access_request_exists(self, csu_id, machine_id):
        self.cursor.execute(
            "SELECT * FROM access_requests WHERE csu_id = ? AND machine_id = ?",
            (csu_id, machine_id)
        )
        return self.cursor.fetchone() is not None

    def insert_access_request(self, csu_id, machine_id):
        self.cursor.execute("SELECT uid FROM users WHERE csu_id = ?", (csu_id,))
        user = self.cursor.fetchone()
        uid = user["uid"] if user else None

        self.cursor.execute("SELECT machine_type FROM machine WHERE machine_id = ?", (machine_id,))
        machine = self.cursor.fetchone()
        machine_type = machine["machine_type"] if machine else None

        self.cursor.execute("""
            INSERT INTO access_requests (
            uid, csu_id, machine_id, machine_type,
            status, requested_on
        ) VALUES (?, ?, ?, ?, 'under_review', datetime('now'))
        """, (uid, csu_id, machine_id, machine_type))
        self.conn.commit()

    def mark_user_active(self, csu_id):
        self.cursor.execute("UPDATE users SET is_active = 1, last_used = datetime('now') WHERE csu_id = ?", (csu_id,))
        self.conn.commit()

    def mark_user_inactive(self, csu_id):
        self.cursor.execute("UPDATE users SET is_active = 0 WHERE csu_id = ?", (csu_id,))
        self.conn.commit()

    def insert_session(self, session_id, csu_id, machine_id):
        self.cursor.execute("SELECT machine_type FROM machine WHERE machine_id = ?", (machine_id,))
        result = self.cursor.fetchone()
        machine_type = result["machine_type"] if result and result["machine_type"] else "Unknown"

        self.cursor.execute(
            "INSERT INTO machine_usage (session_id, csu_id, machine_id, machine_type, start_time) VALUES (?, ?, ?, ?, datetime('now'))",
            (session_id, csu_id, machine_id, machine_type)
        )
        self.conn.commit()

    def end_session(self, session_id):
        self.cursor.execute(
            "UPDATE machine_usage SET end_time = datetime('now'), duration = ((strftime('%s','now') - strftime('%s', start_time)) / 60) WHERE session_id = ?",
            (session_id,)
        )
        self.conn.commit()

    def close(self):
        self.conn.close()


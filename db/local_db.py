# db/local_db.py

import sqlite3
import uuid
from datetime import datetime
from config.constants import *
import os

def get_device_id():
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    return line.strip().split(":")[1].strip()
    except:
        return str(uuid.uuid4())[:8]

class LocalDB:
    def __init__(self, db_path=LOCAL_DB_PATH, lcd=None):
        self.device_id = get_device_id()
        self.lcd = lcd
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_tables()
        print(f"[DB] SQLite connected. Device ID: {self.device_id}")

    def _init_tables(self):
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_MACHINE} (
            machine_id TEXT PRIMARY KEY,
            machine_type TEXT,
            machine_name TEXT,
            machine_status TEXT,
            device_id TEXT,
            last_heartbeat TEXT
        )
        """)
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_USERS} (
            uid TEXT PRIMARY KEY,
            csu_id TEXT UNIQUE,
            name TEXT,
            access_level TEXT DEFAULT 'student',
            last_used TEXT,
            is_active INTEGER DEFAULT 0
        )
        """)
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_MACHINE_PERMISSIONS} (
            csu_id TEXT,
            machine_id TEXT,
            machine_type TEXT,
            access TEXT,
            granted_by TEXT,
            granted_at TEXT,
            PRIMARY KEY (csu_id, machine_id)
        )
        """)
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_MACHINE_USAGE} (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            csu_id TEXT,
            machine_id TEXT,
            machine_type TEXT,
            start_time TEXT,
            end_time TEXT,
            duration INTEGER
        )
        """)
        self.cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_ACCESS_REQUESTS} (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            csu_id TEXT,
            machine_id TEXT,
            machine_type TEXT,
            requested_on TEXT,
            status TEXT DEFAULT NULL,
            reviewed_by TEXT,
            reviewed_at TEXT,
            synced_to_cloud INTEGER DEFAULT 0
        )
        """)
        self.conn.commit()
        print("[DB] Tables ensured.")

    def get_setting(self, key, default=None):
        try:
            self.cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
            row = self.cursor.fetchone()
            return int(row[0]) if row else default
        except:
            return default

    def is_authorized(self, csu_id, machine_id):
        self.cursor.execute(f"""
        SELECT 1 FROM {TABLE_MACHINE_PERMISSIONS}
        WHERE csu_id = ? AND machine_id = ? AND access = 'granted'
        """, (csu_id, machine_id))
        return self.cursor.fetchone() is not None

    def add_access_request(self, uid, csu_id, machine_id, machine_type):
        self.cursor.execute(f"""
            SELECT 1 FROM {TABLE_ACCESS_REQUESTS}
            WHERE uid = ? AND machine_id = ? AND status IS NULL
        """, (uid, machine_id))
        if self.cursor.fetchone():
            return "already_requested"

        self.cursor.execute(f"""
            INSERT INTO {TABLE_ACCESS_REQUESTS}
            (uid, csu_id, machine_id, machine_type, requested_on, synced_to_cloud)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (uid, csu_id, machine_id, machine_type, datetime.now()))
        self.conn.commit()
        return "request_sent"

    def log_session_start(self, session_id, csu_id, machine_id, machine_type):
        self.cursor.execute(f"""
            INSERT INTO {TABLE_MACHINE_USAGE}
            (session_id, csu_id, machine_id, machine_type, start_time)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, csu_id, machine_id, machine_type, datetime.now()))
        self.update_machine_status(machine_id, 'in_use')
        self.conn.commit()

    def log_session_end(self, session_id, machine_id):
        self.cursor.execute(f"""
        SELECT start_time FROM {TABLE_MACHINE_USAGE}
        WHERE session_id = ? AND end_time IS NULL
        """, (session_id,))
        row = self.cursor.fetchone()
        if row:
            start = datetime.fromisoformat(row[0])
            end = datetime.now()
            duration = int((end - start).total_seconds() / 60)
            self.cursor.execute(f"""
                UPDATE {TABLE_MACHINE_USAGE}
                SET end_time = ?, duration = ?
                WHERE session_id = ?
            """, (end, duration, session_id))
            self.update_machine_status(machine_id, 'neutral')
            self.conn.commit()

    def update_user_activity(self, csu_id, active=True):
        self.cursor.execute(f"""
            UPDATE {TABLE_USERS}
            SET last_used = ?, is_active = ?
            WHERE csu_id = ?
        """, (datetime.now(), 1 if active else 0, csu_id))
        self.conn.commit()

    def update_machine_status(self, machine_id, status):
        now = datetime.now()
        self.cursor.execute(f"""
            UPDATE {TABLE_MACHINE}
            SET machine_status = ?, last_heartbeat = ?, device_id = ?
            WHERE machine_id = ?
        """, (status, now, self.device_id, machine_id))
        self.conn.commit()

    def get_user_name(self, csu_id):
        self.cursor.execute(f"SELECT name FROM {TABLE_USERS} WHERE csu_id = ?", (csu_id,))
        row = self.cursor.fetchone()
        return row[0] if row and row[0] else csu_id

    def get_unsynced_requests(self):
        self.cursor.execute(f"""
            SELECT uid, csu_id, machine_id, machine_type, requested_on
            FROM {TABLE_ACCESS_REQUESTS}
            WHERE synced_to_cloud = 0
        """)
        return self.cursor.fetchall()

    def mark_requests_synced(self):
        self.cursor.execute(f"""
            UPDATE {TABLE_ACCESS_REQUESTS}
            SET synced_to_cloud = 1
            WHERE synced_to_cloud = 0
        """)
        self.conn.commit()

    def cleanup_local_data(self, current_machine_id):
        print("[DB] Cleaning up local data...")
        self.cursor.execute(f"""
            DELETE FROM {TABLE_MACHINE_USAGE}
            WHERE log_id NOT IN (
                SELECT log_id FROM {TABLE_MACHINE_USAGE}
                ORDER BY start_time DESC LIMIT 1
            )
        """)
        self.cursor.execute(f"""
            DELETE FROM {TABLE_ACCESS_REQUESTS}
            WHERE machine_id != ?
        """, (current_machine_id,))
        self.cursor.execute(f"""
            DELETE FROM {TABLE_MACHINE_PERMISSIONS}
            WHERE machine_id != ?
        """, (current_machine_id,))
        self.cursor.execute(f"""
            DELETE FROM {TABLE_USERS}
            WHERE csu_id NOT IN (
                SELECT csu_id FROM {TABLE_USERS}
                ORDER BY last_used DESC LIMIT 20
            )
        """)
        self.conn.commit()

    def show_on_lcd(self, message):
        if self.lcd:
            self.lcd.show_message(message)

    def close(self):
        self.conn.close()

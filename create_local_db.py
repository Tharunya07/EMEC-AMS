# create_local_db.py

import sqlite3
import os

DB_PATH = "data/local.db"
os.makedirs("data", exist_ok=True)

schema = """
-- USERS
CREATE TABLE IF NOT EXISTS users (
    csu_id TEXT PRIMARY KEY,
    uid TEXT,
    name TEXT,
    email TEXT,
    is_active INTEGER DEFAULT 0,
    last_used TEXT,
    access_level TEXT,
    group_name TEXT
);

-- ACCESS REQUESTS
CREATE TABLE IF NOT EXISTS access_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT,
    csu_id TEXT,
    machine_id TEXT,
    machine_type TEXT,
    requested_on TEXT DEFAULT (datetime('now')),
    status TEXT DEFAULT 'under_review',
    reviewed_by TEXT,
    reviewed_at TEXT
);

-- MACHINE PERMISSIONS
CREATE TABLE IF NOT EXISTS machine_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    csu_id TEXT,
    uid TEXT,
    machine_id TEXT,
    machine_type TEXT,
    access TEXT,
    granted_by TEXT,
    granted_at TEXT
);

-- MACHINE
CREATE TABLE IF NOT EXISTS machine (
    machine_id TEXT PRIMARY KEY,
    machine_name TEXT,
    machine_type TEXT,
    machine_status TEXT DEFAULT 'offline',
    device_id TEXT,
    last_heartbeat TEXT
);

-- SYSTEM SETTINGS
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT
);

-- MACHINE USAGE
CREATE TABLE IF NOT EXISTS machine_usage (
    session_id TEXT PRIMARY KEY,
    csu_id TEXT,
    machine_id TEXT,
    machine_type TEXT,
    start_time TEXT,
    end_time TEXT,
    duration INTEGER
);
"""

def create_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(schema)
    conn.commit()
    conn.close()
    print(f"Local DB created at {DB_PATH}")

if __name__ == "__main__":
    create_db()

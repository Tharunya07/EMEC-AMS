import sqlite3
import logging
from dateutil import parser
from datetime import datetime

DB_PATH = "/home/tharunya/emec-ams/local.db"

logging.basicConfig(
    filename="/home/tharunya/emec-ams/logs/sync.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def get_connection():
    return sqlite3.connect(DB_PATH)

def initialize_local_db():
    conn = get_connection()
    c = conn.cursor()

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            uid TEXT PRIMARY KEY,
            csu_id TEXT,
            name TEXT,
            access_level TEXT,
            last_used TEXT,
            is_active INTEGER DEFAULT 0,
            group_name TEXT
        )
    """)

    # Machine table
    c.execute("""
        CREATE TABLE IF NOT EXISTS Machine (
            machine_id TEXT PRIMARY KEY,
            machine_type TEXT,
            machine_name TEXT,
            machine_status TEXT DEFAULT 'offline',
            device_id TEXT,
            last_heartbeat TEXT
        )
    """)

    # Machine_Permissions table
    c.execute("""
        CREATE TABLE IF NOT EXISTS Machine_Permissions (
            csu_id TEXT,
            machine_id TEXT,
            machine_type TEXT,
            access TEXT NOT NULL,
            granted_by TEXT,
            granted_at TEXT,
            PRIMARY KEY (csu_id, machine_id)
        )
    """)

    # Access_Requests table
    c.execute("""
        CREATE TABLE IF NOT EXISTS Access_Requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            uid TEXT,
            machine_id TEXT,
            machine_type TEXT,
            requested_on TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'under_review',
            reviewed_by TEXT,
            reviewed_at TEXT
        )
    """)

    # Machine_Usage table
    c.execute("""
        CREATE TABLE IF NOT EXISTS Machine_Usage (
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

    # system_settings table
    c.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            description TEXT
        )
    """)

    # azure_synced tracker
    c.execute("""
        CREATE TABLE IF NOT EXISTS azure_synced (
            session_id TEXT PRIMARY KEY
        )
    """)

    conn.commit()
    conn.close()
    logging.info("All local.db tables initialized.")

def replace_table(table_name, rows):
    conn = get_connection()
    c = conn.cursor()
    c.execute(f"DELETE FROM {table_name}")
    if not rows:
        conn.commit()
        conn.close()
        return
    columns = rows[0].keys()
    col_list = ', '.join(columns)
    placeholders = ', '.join(['?'] * len(columns))
    insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"
    for row in rows:
        values = tuple(row[col] for col in columns)
        c.execute(insert_sql, values)
    conn.commit()
    conn.close()

def get_users_with_updates():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT csu_id, is_active, last_used FROM Users WHERE last_used IS NOT NULL")
    rows = [{"csu_id": r[0], "is_active": r[1], "last_used": r[2]} for r in c.fetchall()]
    conn.close()
    return rows

def get_machines_with_updates():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT machine_id, machine_status, last_heartbeat FROM Machine WHERE last_heartbeat IS NOT NULL")
    rows = [{"machine_id": r[0], "machine_status": r[1], "last_heartbeat": r[2]} for r in c.fetchall()]
    conn.close()
    return rows

def get_unsynced_usage_logs():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT session_id, csu_id, machine_id, machine_type, start_time, end_time, duration
        FROM Machine_Usage
        WHERE session_id NOT IN (SELECT session_id FROM azure_synced)
        AND end_time IS NOT NULL
    """)
    rows = [dict(zip([column[0] for column in c.description], row)) for row in c.fetchall()]
    conn.close()
    return rows

def mark_usage_as_synced(session_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO azure_synced (session_id) VALUES (?)", (session_id,))
    conn.commit()
    conn.close()


def get_user_by_uid(uid):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT csu_id, name FROM Users WHERE uid = ?", (uid,))
    row = c.fetchone()
    conn.close()
    if row:
        logging.info(f"User found: {row[1]} (CSU ID: {row[0]})")
        return {"csu_id": row[0], "name": row[1]}
    logging.warning(f"No user found with UID {uid}")
    return None

def get_user_name_by_uid(uid):
    user = get_user_by_uid(uid)
    return user['name'] if user else "Unknown"

def check_permission(csu_id, machine_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM Machine_Permissions WHERE csu_id = ? AND machine_id = ?", (csu_id, machine_id))
    result = c.fetchone()
    conn.close()
    return bool(result)

def get_access_request(csu_id, machine_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT status FROM Access_Requests
        WHERE uid IN (SELECT uid FROM Users WHERE csu_id = ?)
        AND machine_id = ?
        ORDER BY requested_on DESC LIMIT 1
    """, (csu_id, machine_id))
    row = c.fetchone()
    conn.close()
    return {"status": row[0]} if row else None

def create_access_request(uid, csu_id, machine_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO Access_Requests (uid, machine_id, machine_type)
        VALUES (?, ?, (SELECT machine_type FROM Machine WHERE machine_id = ?))
    """, (uid, machine_id, machine_id))
    conn.commit()
    conn.close()
    logging.info(f"Access request created for {csu_id}/{uid} on {machine_id}")

def get_latest_session(csu_id, machine_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT start_time, end_time FROM Machine_Usage 
                 WHERE csu_id = ? AND machine_id = ?
                 ORDER BY start_time DESC LIMIT 1""", (csu_id, machine_id))
    row = c.fetchone()
    conn.close()
    if row:
        end_time = parser.parse(row[1]) if row[1] else None
        return {"start_time": row[0], "end_time": end_time}
    return None

def update_user_active(csu_id, is_active):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE Users SET is_active = ? WHERE csu_id = ?", (int(is_active), csu_id))
    conn.commit()
    conn.close()
    logging.info(f"Set is_active={is_active} for {csu_id}")

def update_user_last_used(csu_id, timestamp):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE Users SET last_used = ? WHERE csu_id = ?", (timestamp, csu_id))
    conn.commit()
    conn.close()
    logging.info(f"Updated last_used for {csu_id} to {timestamp}")

def update_machine_status(machine_id, status):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE Machine SET machine_status = ? WHERE machine_id = ?", (status, machine_id))
    conn.commit()
    conn.close()
    logging.info(f"Updated machine_status for {machine_id} to {status}")

def update_machine_heartbeat(machine_id, timestamp):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE Machine SET last_heartbeat = ? WHERE machine_id = ?", (timestamp, machine_id))
    conn.commit()
    conn.close()
    logging.info(f"Updated heartbeat for {machine_id} to {timestamp}")

def insert_machine_usage_log(session_id, csu_id, machine_id, start_time):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""INSERT INTO Machine_Usage (session_id, csu_id, machine_id, machine_type, start_time)
                 VALUES (?, ?, ?, 
                 (SELECT machine_type FROM Machine WHERE machine_id = ?), ?)""",
              (session_id, csu_id, machine_id, machine_id, start_time))
    conn.commit()
    conn.close()
    logging.info(f"Started session {session_id} for {csu_id} on {machine_id}")

def close_machine_usage_log(csu_id, machine_id, end_time):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""SELECT log_id, start_time FROM Machine_Usage
                 WHERE csu_id = ? AND machine_id = ? AND end_time IS NULL
                 ORDER BY start_time DESC LIMIT 1""", (csu_id, machine_id))
    row = c.fetchone()
    if row:
        log_id, start_time = row
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        duration = int((end_time - start_dt).total_seconds() // 60)
        c.execute("UPDATE Machine_Usage SET end_time = ?, duration = ? WHERE log_id = ?",
                  (end_time.strftime("%Y-%m-%d %H:%M:%S"), duration, log_id))
        conn.commit()
        logging.info(f"Closed session {log_id} for {csu_id}, duration: {duration} mins")
    conn.close()

def is_machine_in_maintenance(machine_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT machine_status FROM Machine WHERE machine_id = ?", (machine_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == "maintenance"

def get_grace_period():
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT value FROM system_settings WHERE key = 'grace_period_seconds'")
        row = c.fetchone()
        return int(row[0]) if row else 10
    except:
        return 10
    finally:
        conn.close()

def get_machine_id():
    return "lathe-001"  

# db/azure_sync.py

import pymysql
import sqlite3
import logging
import os
from config.constants import AZURE_ENV_KEYS, LOCAL_DB_PATH
from db.local_db import LocalDB

logger = logging.getLogger("azure_sync")
logger.setLevel(logging.INFO)
log_path = "logs/sync.log"
os.makedirs("logs", exist_ok=True)
file_handler = logging.FileHandler(log_path)
logger.addHandler(file_handler)

def get_azure_connection():
    return pymysql.connect(
        host=AZURE_ENV_KEYS["host"],
        user=AZURE_ENV_KEYS["user"],
        password=AZURE_ENV_KEYS["password"],
        db=AZURE_ENV_KEYS["database"],
        ssl={"ca": AZURE_ENV_KEYS["ssl_ca"]}
    )

def sync_local_from_azure():
    conn_local = sqlite3.connect(LOCAL_DB_PATH)
    cursor_local = conn_local.cursor()

    conn_azure = get_azure_connection()
    cursor_azure = conn_azure.cursor(pymysql.cursors.DictCursor)

    tables = ['users', 'access_requests', 'machine_permissions', 'system_settings', 'machine']

    for table in tables:
        try:
            cursor_azure.execute(f"SELECT * FROM {table}")
            rows = cursor_azure.fetchall()

            cursor_local.execute(f"DELETE FROM {table}")
            if rows:
                keys = rows[0].keys()
                placeholders = ", ".join(["?"] * len(keys))
                query = f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})"
                for row in rows:
                    cursor_local.execute(query, tuple(row.values()))
            logger.info(f"[SYNC] Pulled {len(rows)} rows from Azure -> {table}")
        except Exception as e:
            logger.error(f"[SYNC] ERROR syncing table {table}: {e}")

    conn_local.commit()
    conn_local.close()
    conn_azure.close()

def sync_session_to_azure(session_id):
    try:
        conn_local = sqlite3.connect(LOCAL_DB_PATH)
        cur = conn_local.cursor()
        cur.execute("SELECT * FROM machine_usage WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if not row:
            return
        values = tuple(row)

        conn_azure = get_azure_connection()
        cursor_az = conn_azure.cursor()
        cursor_az.execute(
            "REPLACE INTO machine_usage (session_id, csu_id, machine_id, machine_type, start_time, end_time, duration) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            values
        )
        conn_azure.commit()
        conn_azure.close()

        cur.execute("DELETE FROM machine_usage WHERE session_id = ?", (session_id,))
        conn_local.commit()
        conn_local.close()
        logger.info(f"[SYNC] Session {session_id} synced and removed locally.")
    except Exception as e:
        logger.error(f"[SYNC] Session sync failed: {e}")

def push_machine_status(machine_id):
    db = LocalDB()
    machine = db.get_machine(machine_id)
    if not machine:
        logger.warning(f"[SYNC] Machine {machine_id} not found locally.")
        return

    try:
        conn = get_azure_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE machine SET device_id=%s, machine_status=%s, last_heartbeat=%s WHERE machine_id=%s",
            (machine["device_id"], machine["machine_status"], machine["last_heartbeat"], machine_id)
        )
        conn.commit()
        conn.close()
        logger.info(f"[SYNC] Machine status pushed for {machine_id}")
    except Exception as e:
        logger.error(f"[SYNC] Machine status push failed: {e}")

def push_user_status(csu_id):
    db = LocalDB()
    user = db.get_user(csu_id)
    if not user:
        logger.warning(f"[SYNC] User {csu_id} not found locally.")
        return

    try:
        conn = get_azure_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET is_active=%s, last_used=%s WHERE csu_id=%s",
            (user["is_active"], user["last_used"], csu_id)
        )
        conn.commit()
        conn.close()
        logger.info(f"[SYNC] User status pushed for {csu_id}")
    except Exception as e:
        logger.error(f"[SYNC] User status push failed: {e}")

def push_access_requests():
    try:
        conn_local = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn_local.cursor()
        cursor.execute("SELECT * FROM access_requests WHERE status = 'under_review'")
        requests = cursor.fetchall()
        if not requests:
            return

        conn_azure = get_azure_connection()
        cur_az = conn_azure.cursor()

        for row in requests:
            cur_az.execute(
                """
                INSERT INTO access_requests (request_id, uid, csu_id, machine_id, machine_type, requested_on, status, reviewed_by, reviewed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                uid=VALUES(uid), machine_id=VALUES(machine_id), machine_type=VALUES(machine_type),
                requested_on=VALUES(requested_on), status=VALUES(status), reviewed_by=VALUES(reviewed_by), reviewed_at=VALUES(reviewed_at)
                """,
                row
            )

        conn_azure.commit()
        conn_azure.close()
        logger.info(f"[SYNC] Access requests synced to Azure")
    except Exception as e:
        logger.error(f"[SYNC] Access request sync failed: {e}")


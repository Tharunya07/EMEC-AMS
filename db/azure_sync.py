# db/azure_sync.py

import os
from dotenv import load_dotenv
import pymysql
from datetime import datetime
import db.local_db as local_db
import logging

# Set up logs
LOG_PATH = "/home/tharunya/emec-ams/logs/sync.log"
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

load_dotenv("/home/tharunya/emec-ams/.env")

class AzureConnection:
    def __init__(self):
        self.conn = None
        self.connect()

    def connect(self):
        self.conn = pymysql.connect(
            host=os.getenv("AZURE_HOST"),
            user=os.getenv("AZURE_USER"),
            password=os.getenv("AZURE_PASSWORD"),
            database=os.getenv("AZURE_DATABASE"),
            ssl={'ca': os.getenv("AZURE_SSL_CA")},
            cursorclass=pymysql.cursors.DictCursor
        )

    def test_connection(self):
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            return True
        except Exception as e:
            logging.error(f"[Azure Test Failed] {e}")
            return False

    def get_machine(self, machine_id):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT * FROM Machine WHERE machine_id = %s", (machine_id,))
            return cursor.fetchone()

    def update_machine_status(self, machine_id, status):
        with self.conn.cursor() as cursor:
            cursor.execute("UPDATE Machine SET machine_status = %s WHERE machine_id = %s", (status, machine_id))
        self.conn.commit()

    def update_machine_heartbeat(self, machine_id, device_id):
        with self.conn.cursor() as cursor:
            cursor.execute("""
                UPDATE Machine SET device_id = %s, last_heartbeat = CURRENT_TIMESTAMP
                WHERE machine_id = %s
            """, (device_id, machine_id))
        self.conn.commit()

    def get_setting(self, key):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT value FROM system_settings WHERE `key` = %s", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    def sync_to_local(self, local):
        try:
            with self.conn.cursor() as cursor:
                for table in ["Users", "Machine", "Machine_Permissions", "system_settings"]:
                    cursor.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    local.replace_table(table, rows)
            return True
        except Exception as e:
            logging.error("[SYNC] Azure ? Local failed: " + str(e))
            return False

    def push_unsynced_logs(self):
        conn = local_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM Machine_Usage WHERE session_id NOT IN (
                SELECT session_id FROM azure_synced
            )
        """)
        unsynced = cursor.fetchall()

        if not unsynced:
            logging.info("[SYNC] No unsynced logs to push")
            return

        with self.conn.cursor() as az_cursor:
            for row in unsynced:
                az_cursor.execute("""
                    INSERT INTO Machine_Usage (session_id, csu_id, machine_id, machine_type, start_time, end_time, duration)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    row[1], row[2], row[3], row[4], row[5], row[6], row[7]
                ))
                cursor.execute("INSERT INTO azure_synced (session_id) VALUES (?)", (row[1],))

        self.conn.commit()
        conn.commit()
        conn.close()
        logging.info(f"[SYNC] {len(unsynced)} logs pushed to Azure")

# If run from CRON
if __name__ == "__main__":
    cron_log_path = "/home/tharunya/emec-ams/logs/cron.log"
    cron_logger = logging.getLogger()
    fh = logging.FileHandler(cron_log_path)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    cron_logger.addHandler(fh)

    logging.info("[CRON] Azure sync job started")
    try:
        azure = AzureConnection()
        if azure.test_connection():
            if azure.sync_to_local(local_db):
                logging.info("[CRON] Sync to Azure completed successfully.")
                azure.push_unsynced_logs()
            else:
                logging.warning("[CRON] Sync to Azure failed.")
        else:
            logging.error("[CRON] Azure DB test failed.")
    except Exception as e:
        logging.exception(f"[CRON] Exception occurred during sync: {e}")

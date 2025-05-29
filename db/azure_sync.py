# db/azure_sync.py

import os
import sys
import logging
from dotenv import load_dotenv
import pymysql
from datetime import datetime

# Allow absolute import when run via crontab
sys.path.append("/home/tharunya/emec-ams")
import db.local_db as local_db

# Load .env
load_dotenv("/home/tharunya/emec-ams/.env")

# Log Setup
LOG_PATH = "/home/tharunya/emec-ams/logs/sync.log"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

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
            ssl={'ca': os.getenv("AZURE_SSL_CA")}
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
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
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
        with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT value FROM system_settings WHERE `key` = %s", (key,))
            row = cursor.fetchone()
            return row["value"] if row else None

    def sync_to_local(self, local):
        try:
            with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                for table in ["Users", "Machine", "Machine_Permissions", "system_settings"]:
                    cursor.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    local.replace_table(table, rows)
            return True
        except Exception as e:
            logging.exception(f"[SYNC] sync_to_local failed: {e}")
            return False

    def push_unsynced_logs(self):
        conn = local_db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT session_id, csu_id, machine_id, machine_type, start_time, end_time, duration
            FROM Machine_Usage
            WHERE session_id NOT IN (SELECT session_id FROM azure_synced)
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
                """, row)
                cursor.execute("INSERT INTO azure_synced (session_id) VALUES (?)", (row[0],))

        self.conn.commit()
        conn.commit()
        conn.close()
        logging.info(f"[SYNC] {len(unsynced)} logs pushed to Azure")

# Entrypoint for CRON
if __name__ == "__main__":
    logging.info("[CRON] Azure sync job started")
    try:
        azure = AzureConnection()
        if azure.test_connection():
            azure.push_unsynced_logs()
            logging.info("[CRON] Sync to Azure completed successfully.")
        else:
            logging.error("[CRON] Azure DB test failed.")
    except Exception as e:
        logging.exception(f"[CRON] Exception occurred during sync: {e}")

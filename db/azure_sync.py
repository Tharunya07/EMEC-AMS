# db/azure_sync.py
import mysql.connector
import sqlite3
from config.constants import *
from db.local_db import LocalDB
import socket
from datetime import datetime
import time

def is_internet_available():
    import urllib.request
    try:
        urllib.request.urlopen("https://www.google.com", timeout=3)
        print("[SYNC] Internet connection available.")
        return True
    except OSError:
        print("[SYNC] No internet connection.")
        return False

def connect_to_azure():
    return mysql.connector.connect(
        host="ams-mysql-server.mysql.database.azure.com",  
        user="pi",                        
        password="Tharunya123",                           
        database="emec_access",                            
        ssl_ca="/etc/ssl/certs/ca-certificates.crt"  
    )

last_online = time.time()

def sync(lcd=None):
    global last_online

    connected = is_internet_available()
    if not connected:
        if lcd:
            lcd.show_message("? No Internet\nSync skipped")
        print("[SYNC] No internet.")
        now = time.time()
        if now - last_online > 60:
            try:
                local_db = LocalDB(lcd=lcd)
                local_db.update_machine_status("lathe-001", "offline")
                local_db.close()
            except Exception as e:
                print("[SYNC] Failed to mark offline:", e)
        return

    last_online = time.time()

    try:
        azure_conn = connect_to_azure()
        az_cursor = azure_conn.cursor()
        local_db = LocalDB(lcd=lcd)
        device_id = local_db.device_id

        print(f"[SYNC] Connected. Device ID: {device_id}")
        local_db.show_on_lcd("? Syncing with cloud...")

        # 1. Upload access requests
        for row in local_db.get_unsynced_requests():
            query = f"""
                INSERT INTO {TABLE_ACCESS_REQUESTS}
                (uid, csu_id, machine_id, machine_type, requested_on)
                VALUES (%s, %s, %s, %s, %s)
            """
            print(query, row)
            az_cursor.execute(query, row)
        local_db.mark_requests_synced()

        # 2. Download granted ? create user/permission
        az_cursor.execute(f"""
            SELECT uid, csu_id, machine_id, machine_type, reviewed_by, reviewed_at
            FROM {TABLE_ACCESS_REQUESTS}
            WHERE status = 'granted'
        """)
        for uid, csu_id, mid, mtype, granted_by, granted_at in az_cursor.fetchall():
            local_db.cursor.execute(f"SELECT 1 FROM {TABLE_USERS} WHERE csu_id = ?", (csu_id,))
            if not local_db.cursor.fetchone():
                local_db.cursor.execute(f"""
                    INSERT INTO {TABLE_USERS}
                    (uid, csu_id, name, access_level, last_used, is_active)
                    VALUES (?, ?, '', 'student', ?, 0)
                """, (uid, csu_id, datetime.now()))
            local_db.cursor.execute(f"""
                INSERT OR REPLACE INTO {TABLE_MACHINE_PERMISSIONS}
                (csu_id, machine_id, machine_type, access, granted_by, granted_at)
                VALUES (?, ?, ?, 'granted', ?, ?)
            """, (csu_id, mid, mtype, granted_by, granted_at))
        local_db.conn.commit()

        # 3. Upload users if missing
        local_db.cursor.execute(f"SELECT uid, csu_id, access_level, last_used, is_active FROM {TABLE_USERS}")
        for uid, csu_id, access, last, active in local_db.cursor.fetchall():
            az_cursor.execute(f"SELECT 1 FROM {TABLE_USERS} WHERE csu_id = %s", (csu_id,))
            if not az_cursor.fetchone():
                az_cursor.execute(f"""
                    INSERT INTO {TABLE_USERS}
                    (uid, csu_id, name, access_level, last_used, is_active)
                    VALUES (%s, %s, '', %s, %s, %s)
                """, (uid, csu_id, access, last, active))

        # 4. Sync updated names from Azure
        az_cursor.execute(f"SELECT csu_id, name FROM {TABLE_USERS} WHERE name IS NOT NULL AND name != ''")
        for csu_id, name in az_cursor.fetchall():
            local_db.cursor.execute("UPDATE users SET name = ? WHERE csu_id = ?", (name, csu_id))
        local_db.conn.commit()

        # 5. Register/Update machine
        local_db.cursor.execute(f"""
            SELECT machine_id, machine_type, machine_name, machine_status
            FROM machine
        """)
        for mid, mtype, mname, mstat in local_db.cursor.fetchall():
            az_cursor.execute("SELECT 1 FROM machine WHERE machine_id = %s", (mid,))
            if not az_cursor.fetchone():
                az_cursor.execute(f"""
                    INSERT INTO machine
                    (machine_id, machine_type, machine_name, machine_status, device_id, last_heartbeat)
                    VALUES (%s, %s, %s, 'neutral', %s, %s)
                """, (mid, mtype, mname, device_id, datetime.now()))
            else:
                az_cursor.execute(f"""
                    UPDATE machine
                    SET device_id = %s, last_heartbeat = %s, machine_status = %s
                    WHERE machine_id = %s
                """, (device_id, datetime.now(), mstat, mid))

        # 6. Push permissions
        local_db.cursor.execute(f"""
            SELECT csu_id, machine_id, machine_type, access, granted_by, granted_at
            FROM machine_permissions
            WHERE access = 'granted'
        """)
        for row in local_db.cursor.fetchall():
            az_cursor.execute(f"""
                INSERT INTO machine_permissions
                (csu_id, machine_id, machine_type, access, granted_by, granted_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                access = VALUES(access),
                granted_by = VALUES(granted_by),
                granted_at = VALUES(granted_at)
            """, row)

        # 7. Upload machine usage logs
        local_db.cursor.execute(f"""
            SELECT session_id, csu_id, machine_id, machine_type, start_time, end_time, duration
            FROM machine_usage
            WHERE end_time IS NOT NULL
        """)
        logs = local_db.cursor.fetchall()
        print(f"[SYNC] Uploading {len(logs)} usage logs...")
        for row in logs:
            az_cursor.execute(f"""
                INSERT IGNORE INTO machine_usage
                (session_id, csu_id, machine_id, machine_type, start_time, end_time, duration)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, row)

        azure_conn.commit()

        # 8. Delete uploaded logs
        local_db.cursor.execute("DELETE FROM machine_usage")
        local_db.conn.commit()

        # 9. Cleanup + reset machine status
        local_db.cleanup_local_data("lathe-001")
        local_db.update_machine_status("lathe-001", "neutral")

        azure_conn.commit()
        local_db.show_on_lcd("? Sync complete")
        print("[SYNC] ? Done")

    except Exception as e:
        print("[SYNC] ERROR:", e)
        if lcd:
            lcd.show_message("? Sync failed")
    finally:
        try:
            az_cursor.close()
            azure_conn.close()
            local_db.close()
        except:
            pass

if __name__ == "__main__":
    sync()

# utils/startup_check.py

import socket
import time
import urllib.request
from lcd.lcd import LCD
import db.local_db as local_db
from db.azure_sync import AzureConnection
from config.constants import *

class StartupCheck:
    def __init__(self, lcd: LCD, azure: AzureConnection, machine_id: str):
        self.lcd = lcd
        self.azure = azure
        self.machine_id = machine_id
        self.device_id = self.get_cpu_serial()

    def get_cpu_serial(self):
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        return line.split(":")[1].strip()
        except Exception:
            return "0000000000000000"

    def check_internet(self):
        try:
            urllib.request.urlopen("https://www.google.com", timeout=3)
            print("[StartupCheck] Internet OK.")
            return True
        except OSError as e:
            print(f"[StartupCheck] Internet failed: {e}")
            return False

    def update_machine_status_and_heartbeat(self):
        machine = self.azure.get_machine(self.machine_id)
        if not machine:
            raise Exception("Machine not found in Azure")

        if machine['machine_status'] == STATUS_MAINTENANCE:
            self.lcd.show_message("\n".join(LCD_MESSAGES["maintenance"]))
            return False

        if machine['machine_status'] == STATUS_OFFLINE:
            self.azure.update_machine_status(self.machine_id, STATUS_NEUTRAL)

        self.azure.update_machine_heartbeat(self.machine_id, self.device_id)
        return True

    def run(self):
        if not self.check_internet():
            self.lcd.show_message("\n".join(LCD_MESSAGES["internet_error"]))
            raise Exception("Internet connection failed")

        if not self.azure.test_connection():
            self.lcd.show_message("\n".join(LCD_MESSAGES["azure_error"]))
            raise Exception("Azure DB connection failed")

        # ? Create tables in local.db
        local_db.initialize_local_db()

        if not self.azure.sync_to_local(local_db):
            self.lcd.show_message("\n".join(LCD_MESSAGES["sync_error"]))
            raise Exception("Azure ? Local sync failed")

        if not self.update_machine_status_and_heartbeat():
            return False

        return True

# config/constants.py

from dotenv import load_dotenv
load_dotenv()
import os
import json
# === Device ID (CPU Serial) ===
def get_cpu_serial():
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("Serial"):
                    return line.strip().split(":")[1].strip()
    except:
        return "0000000000000000"

DEVICE_ID = get_cpu_serial()

# === Machine ID from config.json ===
def get_machine_id():
    try:
        with open("config/config.json", "r") as f:
            data = json.load(f)
            return data.get("machine_id", "UNKNOWN")
    except:
        return "UNKNOWN"

MACHINE_ID = get_machine_id()

# === Relay and Card Constants ===
RELAY_PIN = 11
CARD_POLL_INTERVAL = 0.5  # seconds
CARD_GRACE_PERIOD_DEFAULT = 10  # fallback if not in system_settings
LCD_LINE_DELAY = 2  # seconds
LOCAL_DB_PATH = "data/local.db"

# === Azure Environment Variables ===
AZURE_ENV_KEYS = {
    "host": os.getenv("AZURE_HOST"),
    "user": os.getenv("AZURE_USER"),
    "password": os.getenv("AZURE_PASSWORD"),
    "database": os.getenv("AZURE_DATABASE"),
    "ssl_ca": os.getenv("AZURE_SSL_CA")
}

# === Required Settings from system_settings table ===
REQUIRED_SYSTEM_SETTINGS = [
    "grace_period_seconds"
]

# === Machine Status Enum ===
STATUS_MAINTENANCE = "maintenance"
STATUS_OFFLINE = "offline"
STATUS_NEUTRAL = "neutral"
STATUS_IN_USE = "in_use"

# === LCD Messages ===
LCD_MESSAGES = {
    "start": ["All clear.", "Welcome to EMEC!", "Scan your CSU ID to start"],
    "maintenance": ["Machine out of order"],
    "internet_error": ["No Internet Connection"],
    "azure_error": ["Azure DB Unreachable"],
    "sync_error": ["Sync failed", "Check connection"]
}

LCD_SCAN_PROMPT = "Scan your CSU ID"
LCD_SESSION_CONTINUE = "Continue session"
LCD_CARD_REMOVED = "Card removed"
LCD_GRACE_WAIT = "{}s to reinsert"
LCD_NEW_CARD = "New card detected"
LCD_RESETTING = "Resetting, wait"
LCD_SESSION_ENDED = "Session ended"
LCD_WELCOME = "Welcome to EMEC!"

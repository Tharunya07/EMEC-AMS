# config/constants.py

# === GPIO PIN MAPPINGS ===
RELAY_PIN = 11            # GPIO 17, physical pin 11 (controls power to machine/LED)

# === RFID & Session Timing ===
CARD_POLL_INTERVAL = 1.0      # in seconds (500ms)
CARD_GRACE_PERIOD = 10     # 5 minutes in seconds
SESSION_TIMEOUT_BUFFER = 10   # extra seconds to extend grace check

# === Machine State ===
MACHINE_STATE_NEUTRAL = "neutral"
MACHINE_STATE_IN_USE = "in_use"
MACHINE_STATE_UNAVAILABLE = "offline"

# === Sync Intervals ===
AZURE_SYNC_INTERVAL = 300     # in seconds

# === Database Table Names ===
TABLE_USERS = "users"
TABLE_MACHINE = "machine"
TABLE_MACHINE_USAGE = "machine_usage"
TABLE_MACHINE_PERMISSIONS = "machine_permissions"
TABLE_ACCESS_REQUESTS = "access_requests"

# === Others ===
LOCAL_DB_PATH = "/home/tharunya/emec-ams/emec_local.db"  # adjust path if needed

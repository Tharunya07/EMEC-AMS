# constants.py

CARD_POLL_INTERVAL = 0.5  # seconds
CARD_GRACE_PERIOD_DEFAULT = 10  # fallback if not in system_settings

LCD_LINE_DELAY = 2  # Delay between LCD line transitions
DEVICE_ID_KEY = "device_id"
PIN_RELAY = 11 # GPIO pin for relay control

AZURE_ENV_KEYS = {
    "host": "AZURE_HOST",
    "user": "AZURE_USER",
    "password": "AZURE_PASSWORD",
    "database": "AZURE_DATABASE",
    "ssl_ca": "AZURE_SSL_CA"
}

# MySQL/Azure config keys
REQUIRED_SYSTEM_SETTINGS = [
    "grace_period_seconds"
]

# Machine status states
STATUS_MAINTENANCE = "maintenance"
STATUS_OFFLINE = "offline"
STATUS_NEUTRAL = "neutral"
STATUS_IN_USE = "in_use"

# Default messages
LCD_MESSAGES = {
    "start": ["All clear.", "Welcome to EMEC!", "Scan your CSU ID to start"],
    "maintenance": ["Machine out of order"],
    "internet_error": ["No Internet Connection"],
    "azure_error": ["Azure DB Unreachable"],
    "sync_error": ["Sync failed", "Check connection"]
}

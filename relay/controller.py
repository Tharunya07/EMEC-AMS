# relay/controller.py

import RPi.GPIO as GPIO
from config.constants import RELAY_PIN
import time

class RelayController:
    def __init__(self):
        try:
            GPIO.setmode(GPIO.BOARD)  # Use BOARD to match other devices
        except ValueError:
            # Mode already set ? ignore safely
            pass
        GPIO.setwarnings(False)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
        GPIO.output(RELAY_PIN, GPIO.LOW)
        self.active = False

    def activate_relay(self, session_id=None):
        if not self.active:
            GPIO.output(RELAY_PIN, GPIO.HIGH)
            self.active = True
            print(f"[RELAY] ON - Session {session_id}")

    def deactivate_relay(self):
        if self.active:
            GPIO.output(RELAY_PIN, GPIO.LOW)
            self.active = False
            print("[RELAY] OFF")

    def is_active(self):
        return self.active

    def cleanup(self):
        try:
            GPIO.output(RELAY_PIN, GPIO.LOW)
        except RuntimeError:
            print("[RELAY] Cleanup warning: GPIO not initialized")
        GPIO.cleanup()
        print("[RELAY] GPIO cleaned up")

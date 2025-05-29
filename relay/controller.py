# relay/controller.py

import RPi.GPIO as GPIO
import time
from config.constants import RELAY_PIN

class RelayController:
    def __init__(self):
        GPIO.setmode(GPIO.BOARD) 
        GPIO.setwarnings(False)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
        GPIO.output(RELAY_PIN, GPIO.LOW)
        self.active = False

    def activate_relay(self, session_id=None):
        GPIO.output(RELAY_PIN, GPIO.HIGH)
        self.active = True
        print(f"[RELAY] ON - Session {session_id}")

    def deactivate_relay(self):
        GPIO.output(RELAY_PIN, GPIO.LOW)
        self.active = False
        print("[RELAY] OFF")

    def is_active(self):
        return self.active

    def cleanup(self):
        GPIO.cleanup()
        print("[RELAY] GPIO cleaned up")

# relay/controller.py
"""
File: controller.py
Description:
  Acts as the main hardware controller for EMEC AMS.
  Integrates RFID reading, relay control, and LCD messaging to manage user authentication and machine operation.
"""

import RPi.GPIO as GPIO
from config.constants import RELAY_PIN
import time

class RelayController:
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(RELAY_PIN, GPIO.OUT)
        GPIO.output(RELAY_PIN, GPIO.LOW)

    def turn_on(self):
        GPIO.output(RELAY_PIN, GPIO.HIGH)

    def turn_off(self):
        GPIO.output(RELAY_PIN, GPIO.LOW)

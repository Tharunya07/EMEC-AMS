# lcd/lcd.py

import smbus2 as smbus
import time

I2C_ADDR = 0x27
LCD_WIDTH = 20
LCD_CHR = 1
LCD_CMD = 0
LINE_1 = 0x80
LINE_2 = 0xC0
LINE_3 = 0x94
LINE_4 = 0xD4
E_PULSE = 0.0005
E_DELAY = 0.0005

class LCD:
    def __init__(self):
        self.bus = smbus.SMBus(1)
        self.addr = I2C_ADDR
        self._init_lcd()

    def _init_lcd(self):
        self._write(0x33, LCD_CMD)
        self._write(0x32, LCD_CMD)
        self._write(0x06, LCD_CMD)
        self._write(0x0C, LCD_CMD)
        self._write(0x28, LCD_CMD)
        self.clear()

    def clear(self):
        self._write(0x01, LCD_CMD)
        time.sleep(E_DELAY)

    def display(self, line, text):
        line_map = {1: LINE_1, 2: LINE_2, 3: LINE_3, 4: LINE_4}
        self._write(line_map.get(line, LINE_1), LCD_CMD)
        for char in text.ljust(LCD_WIDTH, " "):
            self._write(ord(char), LCD_CHR)

    def show_message(self, message):
        self.clear()
        lines = message.strip().split("\n")
        for i, text in enumerate(lines[:4]):
            self.display(i+1, text.strip())

    def _write(self, bits, mode):
        high = mode | (bits & 0xF0) | 0x08
        low = mode | ((bits << 4) & 0xF0) | 0x08
        self.bus.write_byte(self.addr, high)
        self._toggle_enable(high)
        self.bus.write_byte(self.addr, low)
        self._toggle_enable(low)

    def _toggle_enable(self, bits):
        time.sleep(E_DELAY)
        self.bus.write_byte(self.addr, bits | 0x04)
        time.sleep(E_PULSE)
        self.bus.write_byte(self.addr, bits & ~0x04)
        time.sleep(E_DELAY)

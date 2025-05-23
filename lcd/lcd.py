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
    def __init__(self, addr=I2C_ADDR):
        """Initialize LCD display at given I2C address."""
        self.addr = addr
        self.bus = smbus.SMBus(1)
        self._last_message = ["", "", "", ""]
        self._init_lcd()

    def _init_lcd(self):
        self._write(0x33, LCD_CMD)  # Initialize
        self._write(0x32, LCD_CMD)  # Set to 4-bit mode
        self._write(0x06, LCD_CMD)  # Cursor move direction
        self._write(0x0C, LCD_CMD)  # Display On, Cursor Off
        self._write(0x28, LCD_CMD)  # 2 line display
        self.clear()

    def clear(self):
        """Clear display and reset last message cache."""
        self._write(0x01, LCD_CMD)
        self._last_message = ["", "", "", ""]
        time.sleep(E_DELAY)

    def show_message(self, message: str):
        """Clear screen and display up to 4 lines of text."""
        lines = message.strip().split("\n")
        display_lines = [line.strip().ljust(LCD_WIDTH)[:LCD_WIDTH] for line in lines[:4]]

        for i in range(4):
            if i < len(display_lines):
                self._display_line(i + 1, display_lines[i])
            else:
                self._display_line(i + 1, " " * LCD_WIDTH)

        self._last_message = display_lines + [""] * (4 - len(display_lines))

    def update_line(self, line: int, text: str):
        """Update a single line without clearing the whole screen."""
        if 1 <= line <= 4:
            formatted = text.strip().ljust(LCD_WIDTH)[:LCD_WIDTH]
            if self._last_message[line - 1] != formatted:
                self._display_line(line, formatted)
                self._last_message[line - 1] = formatted

    def _display_line(self, line: int, text: str):
        """Display text on specified LCD line."""
        line_map = {1: LINE_1, 2: LINE_2, 3: LINE_3, 4: LINE_4}
        self._write(line_map.get(line, LINE_1), LCD_CMD)
        for char in text:
            self._write(ord(char), LCD_CHR)

    def _write(self, bits: int, mode: int):
        high = mode | (bits & 0xF0) | 0x08
        low = mode | ((bits << 4) & 0xF0) | 0x08
        self.bus.write_byte(self.addr, high)
        self._toggle_enable(high)
        self.bus.write_byte(self.addr, low)
        self._toggle_enable(low)

    def _toggle_enable(self, bits: int):
        time.sleep(E_DELAY)
        self.bus.write_byte(self.addr, bits | 0x04)
        time.sleep(E_PULSE)
        self.bus.write_byte(self.addr, bits & ~0x04)
        time.sleep(E_DELAY)

    def close(self):
        """Optional: clean up resources if needed."""
        try:
            self.clear()
            self.bus.close()
        except Exception:
            pass

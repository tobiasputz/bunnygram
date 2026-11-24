# Physical desktop build (USB plugged in, no battery)

The target design is an **ESP32-S3 with Wi-Fi**, a **240×240 ST7789 SPI LCD**, three buttons, an **angled clear acrylic reflector**, and a matte-black laser-cut case. Use a stable 5 V USB power source; power the LCD through the correct 3.3 V rail or specified breakout input and verify display logic levels and LED current from the seller's pinout.

The Python app (`main.py`) is a **PC prototype**; it will not run directly under the microcontroller's MicroPython environment because `pygame` is desktop-only. For the actual ESP32, port `game_rules.py` (pure Python, easy to adapt) and the sprite PNGs to MicroPython/CircuitPython or write the display/game loop using Arduino IDE/C++ with TFT_eSPI/LovyanGFX. A Python-based MicroPython implementation is possible, but 32×32 PNG decoding and a 240×240 color screen require a compatible image decoder/display driver and some RAM planning.

Suggested wiring concept (verify your actual board/display pinout): ESP32-S3 GPIO -> ST7789 SPI SCK, MOSI, CS, DC, RST, backlight; 3 button GPIOs -> GND with internal pullups. There is **no need for a battery or charging circuit**. Feed and pet are two buttons, third toggles sleep; holding the third or adding a fourth button opens mail.

Remote upgrades: on the device, implement signed/authenticated OTA using dual firmware partitions and rollback and a secure HTTPS endpoint. The PC program's `R` key hot-reloads sprite assets; **it is not yet remote ESP32 firmware OTA**.

Security: never expose the unauthenticated local demo server to the Internet, put keys in private configuration, and avoid allowing arbitrary executable Python code from messages.

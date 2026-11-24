"""Minimal ILI9341 SPI driver for Freenove FNK0104B 2.8in IPS.
Hardware reference: Freenove TFT_eSPI / FNK0104B pin map.
MicroPython only; no external display libraries required.
"""
import time
from machine import Pin, SPI, PWM

class Display:
    # Native panel 240x320. Landscape rotations 1 and 3 (320x240).
    def __init__(self, rotation=0, brightness=85):
        self.cs = Pin(10, Pin.OUT, value=1)
        self.dc = Pin(46, Pin.OUT, value=1)
        # LCD RST is tied to the board reset, not a dedicated GPIO.
        self.spi = SPI(2, baudrate=40000000, polarity=0, phase=0,
                       sck=Pin(12), mosi=Pin(11), miso=Pin(13))
        self.bl = None
        try:
            self.bl = PWM(Pin(45), freq=1000, duty_u16=0)
        except Exception:
            self.bl = Pin(45, Pin.OUT, value=0)
        self._zero = bytearray(2048)
        self.rotation = None
        self._init_panel()
        # Required by this Freenove IPS panel: without INVON (0x21),
        # black appears white and red appears blue. Verified on hardware.
        # Keep the existing RGB/BGR register configuration unchanged.
        self.command(0x21)
        self.set_rotation(rotation)
        self.fill(0)
        self.set_brightness(brightness)

    def command(self, cmd, data=None):
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(bytes([cmd]))
        if data is not None and len(data):
            self.dc.value(1)
            self.spi.write(data)
        self.cs.value(1)

    def _init_panel(self):
        self.command(0x01)  # SWRESET
        time.sleep_ms(150)
        self.command(0xEF, b'\x03\x80\x02')
        self.command(0xCF, b'\x00\xc1\x30')
        self.command(0xED, b'\x64\x03\x12\x81')
        self.command(0xE8, b'\x85\x00\x78')
        self.command(0xCB, b'\x39\x2c\x00\x34\x02')
        self.command(0xF7, b'\x20')
        self.command(0xEA, b'\x00\x00')
        self.command(0xC0, b'\x23')
        self.command(0xC1, b'\x10')
        self.command(0xC5, b'\x3e\x28')
        self.command(0xC7, b'\x86')
        self.command(0x3A, b'\x55')  # 16-bit RGB565
        self.command(0xB1, b'\x00\x18')
        self.command(0xB6, b'\x08\x82\x27')
        self.command(0xF2, b'\x00')
        self.command(0x26, b'\x01')
        self.command(0xE0, b'\x0f\x31\x2b\x0c\x0e\x08\x4e\xf1\x37\x07\x10\x03\x0e\x09\x00')
        self.command(0xE1, b'\x00\x0e\x14\x03\x11\x07\x31\xc1\x48\x08\x0f\x0c\x31\x36\x0f')
        self.command(0x11)  # sleep out
        time.sleep_ms(120)
        self.command(0x29)  # display on
        time.sleep_ms(20)

    def set_rotation(self, rotation):
        rotation = int(rotation) % 4
        # ILI9341 MADCTL; bit3 selects BGR color order.
        values = (0x48, 0x28, 0x88, 0xE8)
        self.command(0x36, bytes([values[rotation]]))
        self.rotation = rotation
        self.width, self.height = ((240, 320) if rotation % 2 == 0 else (320, 240))

    def set_brightness(self, level):
        level = max(0, min(100, int(level)))
        if isinstance(self.bl, PWM):
            self.bl.duty_u16(int(level * 65535 / 100))
        else:
            self.bl.value(1 if level else 0)

    def _window(self, x, y, w, h):
        self.command(0x2A, bytes([x >> 8, x & 255, (x+w-1) >> 8, (x+w-1) & 255]))
        self.command(0x2B, bytes([y >> 8, y & 255, (y+h-1) >> 8, (y+h-1) & 255]))
        self.cs.value(0)
        self.dc.value(0)
        self.spi.write(b'\x2C')
        self.dc.value(1)

    def fill_rect(self, x, y, w, h, color=0):
        x, y, w, h = int(x), int(y), int(w), int(h)
        x2, y2 = min(self.width, x+w), min(self.height, y+h)
        x, y = max(0, x), max(0, y)
        w, h = x2-x, y2-y
        if w <= 0 or h <= 0:
            return
        self._window(x, y, w, h)
        nbytes = w*h*2
        if color == 0:
            while nbytes:
                size = min(nbytes, len(self._zero))
                self.spi.write(memoryview(self._zero)[:size])
                nbytes -= size
        else:
            data = bytes([(color>>8)&255, color&255]) * 512
            while nbytes:
                size = min(nbytes, len(data))
                self.spi.write(memoryview(data)[:size])
                nbytes -= size
        self.cs.value(1)

    def fill(self, color=0):
        self.fill_rect(0, 0, self.width, self.height, color)

    def sprite(self, frame, x, y, scale=4, flip_x=False, flip_y=False):
        """Frame is 2048 bytes of big-endian RGB565 pixels on black, 32x32.
        Draw the full rectangular sprite using 32 successive SPI row transfers.
        """
        scale = int(scale)
        dim = 32*scale
        x, y = int(x), int(y)
        if len(frame) != 2048 or x < 0 or y < 0 or x+dim > self.width or y+dim > self.height:
            return
        self._window(x, y, dim, dim)
        row = bytearray(dim*2)
        for sy in range(32):
            src_y = (31-sy) if flip_y else sy
            for sx in range(32):
                src_x = (31-sx) if flip_x else sx
                p = (src_y*32 + src_x)*2
                hi, lo = frame[p], frame[p+1]
                i = sx*scale*2
                for dx in range(scale):
                    row[i+dx*2] = hi
                    row[i+dx*2+1] = lo
            for _ in range(scale):
                self.spi.write(row)
        self.cs.value(1)

    def draw_ip(self, ip):
        """Brief no-dependency 5x7 pixel IP address splash shown at startup."""
        glyphs = {
            'I': ('11111','00100','00100','00100','00100','00100','11111'),
            'P': ('11110','10001','10001','11110','10000','10000','10000'),
            '0': ('01110','10001','10011','10101','11001','10001','01110'),
            '1': ('00100','01100','00100','00100','00100','00100','01110'),
            '2': ('01110','10001','00001','00110','01000','10000','11111'),
            '3': ('11110','00001','00001','01110','00001','00001','11110'),
            '4': ('00010','00110','01010','10010','11111','00010','00010'),
            '5': ('11111','10000','10000','11110','00001','00001','11110'),
            '6': ('01110','10000','10000','11110','10001','10001','01110'),
            '7': ('11111','00001','00010','00100','01000','01000','01000'),
            '8': ('01110','10001','10001','01110','10001','10001','01110'),
            '9': ('01110','10001','10001','01111','00001','00001','01110'),
            '.': ('00000','00000','00000','00000','00000','00110','00110'),
            ' ': ('00000','00000','00000','00000','00000','00000','00000')
        }
        text = 'IP ' + str(ip)
        scale = 2 if len(text)*6*2 <= self.width-8 else 1
        xx = max(0, (self.width-(len(text)*6-1)*scale)//2)
        yy = (self.height-7*scale)//2
        for ch in text:
            glyph = glyphs.get(ch, glyphs[' '])
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit=='1':self.fill_rect(xx+col*scale,yy+row*scale,scale,scale,0xffff)
            xx+=6*scale

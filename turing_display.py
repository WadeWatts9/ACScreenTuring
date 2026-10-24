import time
from enum import IntEnum
from typing import Optional
import numpy as np
import serial
from serial.tools.list_ports import comports
from PIL import Image


class Orientation(IntEnum):
    PORTRAIT = 0
    REVERSE_PORTRAIT = 1
    LANDSCAPE = 2
    REVERSE_LANDSCAPE = 3


class Command(IntEnum):
    RESET = 101
    CLEAR = 102
    TO_BLACK = 103
    SCREEN_OFF = 108
    SCREEN_ON = 109
    SET_BRIGHTNESS = 110
    SET_ORIENTATION = 121
    DISPLAY_BITMAP = 197
    HELLO = 69


class TuringDisplay:
    """
    Controlador para pantallas secundarias USB Turing Smart Screen (CH552/CH572 USB35INCHIPS).
    Soporta resoluciones nativas 320x480 en vertical y 480x320 en horizontal.
    """

    def __init__(self, port: Optional[str] = None, orientation: Orientation = Orientation.LANDSCAPE):
        self.port = port
        self.orientation = orientation
        self.serial: Optional[serial.Serial] = None
        self.base_width = 320
        self.base_height = 480

    @property
    def width(self) -> int:
        if self.orientation in (Orientation.PORTRAIT, Orientation.REVERSE_PORTRAIT):
            return self.base_width
        return self.base_height

    @property
    def height(self) -> int:
        if self.orientation in (Orientation.PORTRAIT, Orientation.REVERSE_PORTRAIT):
            return self.base_height
        return self.base_width

    @staticmethod
    def auto_detect_port() -> Optional[str]:
        for p in comports():
            # Buscar por número de serie o VID/PID del chip USB Turing
            if p.serial_number and "USB35INCHIPS" in p.serial_number:
                return p.device
            if getattr(p, "vid", None) == 0x1A86 and getattr(p, "pid", None) == 0x5722:
                return p.device
            if "CH340" in p.description or "USB-SERIAL" in p.description:
                return p.device
        return None

    def connect(self):
        if not self.port:
            detected = self.auto_detect_port()
            if not detected:
                raise ConnectionError("No se encontró automáticamente el puerto COM de la pantalla Turing.")
            self.port = detected

        print(f"[*] Conectando a pantalla Turing en {self.port}...")
        self.serial = serial.Serial(self.port, baudrate=115200, timeout=1, rtscts=True)
        time.sleep(0.1)

        # Configurar orientación inicial y brillo
        self.set_orientation(self.orientation)
        self.set_brightness(85)
        print(f"[+] Pantalla conectada y lista ({self.width}x{self.height}).")

    def disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.serial = None
            print("[*] Conexión cerrada.")

    def set_orientation(self, orientation: Orientation):
        self.orientation = orientation
        w = self.width
        h = self.height

        buf = bytearray(16)
        buf[5] = Command.SET_ORIENTATION
        buf[6] = orientation + 100
        buf[7] = (w >> 8) & 0xFF
        buf[8] = w & 0xFF
        buf[9] = (h >> 8) & 0xFF
        buf[10] = h & 0xFF
        self._write(bytes(buf))

    def set_brightness(self, level: int = 80):
        """Ajusta el brillo del 0 al 100%."""
        level = max(0, min(100, level))
        # 0 es el máximo brillo y 255 es apagado en este firmware
        val = int(255 - ((level / 100.0) * 255))
        cmd = bytearray(6)
        cmd[0] = (val >> 2) & 0xFF
        cmd[1] = ((val & 3) << 6) & 0xFF
        cmd[5] = Command.SET_BRIGHTNESS
        self._write(bytes(cmd))

    def clear(self):
        cmd = bytearray(6)
        cmd[5] = Command.CLEAR
        self._write(bytes(cmd))

    def _write(self, data: bytes):
        if not self.serial or not self.serial.is_open:
            raise ConnectionError("El puerto serie no está abierto.")
        self.serial.write(data)

    def display_image(self, image: Image.Image, x: int = 0, y: int = 0):
        """
        Envía una imagen PIL/Pillow a la pantalla convirtiéndola a RGB565 little-endian.
        """
        w, h = self.width, self.height

        # Ajustar si el tamaño difiere
        if image.size != (w, h):
            image = image.resize((w, h), Image.Resampling.LANCZOS)

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        # Conversión rápida a RGB565 con NumPy
        rgb_data = np.asarray(image)
        if rgb_data.shape[2] == 4:
            rgb_data = rgb_data[:, :, :3]
        rgb_flat = rgb_data.reshape((-1, 3))

        r = (rgb_flat[:, 0].astype(np.uint16) >> 3)
        g = (rgb_flat[:, 1].astype(np.uint16) >> 2)
        b = (rgb_flat[:, 2].astype(np.uint16) >> 3)
        rgb565 = ((r << 11) | (g << 5) | b).astype("<u2").tobytes()

        # Comando DISPLAY_BITMAP
        x0, y0 = x, y
        x1, y1 = x + w - 1, y + h - 1

        cmd = bytearray(6)
        cmd[0] = (x0 >> 2) & 0xFF
        cmd[1] = (((x0 & 3) << 6) + (y0 >> 4)) & 0xFF
        cmd[2] = (((y0 & 15) << 4) + (x1 >> 6)) & 0xFF
        cmd[3] = (((x1 & 63) << 2) + (y1 >> 8)) & 0xFF
        cmd[4] = y1 & 0xFF
        cmd[5] = Command.DISPLAY_BITMAP

        self._write(bytes(cmd))

        # Enviar bytes por bloques
        chunk_size = w * 8
        for i in range(0, len(rgb565), chunk_size):
            self._write(rgb565[i : i + chunk_size])

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

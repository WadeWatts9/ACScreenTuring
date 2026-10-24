import math
import datetime
import os
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

from config import get_resource_path

class JarvisRenderer:
    """
    Motor gráfico J.A.R.V.I.S. HUD para pantallas secundarias Turing (480x320 y 320x480).
    Soporta 5 pantallas dinámicas con Arc Reactor con iniciales 'AC'.
    """

    def __init__(self, width: int = 480, height: int = 320, logo_path: str = "Logo.png"):
        self.width = width
        self.height = height
        self.is_portrait = height > width
        self.logo_path = get_resource_path(logo_path) if not os.path.isabs(logo_path) else logo_path
        self._logo_image: Optional[Image.Image] = None
        self._logo_dark_enhanced: Optional[Image.Image] = None
        self._load_logo()
        self._load_fonts()

        # Paleta de colores J.A.R.V.I.S.
        self.COLOR_BG = (4, 9, 18)
        self.COLOR_GRID = (8, 22, 38)
        self.COLOR_CYAN = (0, 240, 255)
        self.COLOR_CYAN_DIM = (15, 80, 110)
        self.COLOR_CYAN_GLOW = (0, 140, 180)
        self.COLOR_BLUE_CORE = (10, 160, 255)
        self.COLOR_ORANGE = (255, 170, 20)
        self.COLOR_GREEN = (0, 255, 160)
        self.COLOR_WHITE = (235, 250, 255)
        self.COLOR_MUTED = (60, 105, 130)
        self.COLOR_DARK_CARD = (6, 17, 30)

    def _load_fonts(self):
        font_paths = [
            "C:/Windows/Fonts/bahnschrift.ttf",
            "C:/Windows/Fonts/consolab.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        self.font_xlarge = None
        self.font_large = None
        self.font_title = None
        self.font_mid = None
        self.font_small = None
        self.font_tiny = None
        self.font_core = None

        chosen = None
        for p in font_paths:
            try:
                self.font_xlarge = ImageFont.truetype(p, 36 if not self.is_portrait else 32)
                self.font_large = ImageFont.truetype(p, 28 if not self.is_portrait else 24)
                self.font_title = ImageFont.truetype(p, 20 if not self.is_portrait else 18)
                self.font_mid = ImageFont.truetype(p, 14 if not self.is_portrait else 13)
                self.font_small = ImageFont.truetype(p, 12 if not self.is_portrait else 11)
                self.font_tiny = ImageFont.truetype(p, 10 if not self.is_portrait else 9)
                self.font_core = ImageFont.truetype(p, 16)
                chosen = p
                break
            except Exception:
                continue

        if not chosen:
            default_f = ImageFont.load_default()
            self.font_xlarge = default_f
            self.font_large = default_f
            self.font_title = default_f
            self.font_mid = default_f
            self.font_small = default_f
            self.font_tiny = default_f
            self.font_core = default_f

    def _load_logo(self):
        if os.path.exists(self.logo_path):
            try:
                img = Image.open(self.logo_path)
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                bbox = img.getbbox()
                if bbox:
                    img = img.crop(bbox)
                self._logo_image = img

                # Crear versión mejorada para fondo oscuro HUD
                arr = np.array(img).copy()
                r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
                brightness = (r.astype(int) + g.astype(int) + b.astype(int)) / 3.0
                # Los píxeles oscuros (como el texto "ALAN CANTO" y partes oscuras del monograma)
                # se convierten a blanco nítido para destacar con alto contraste en fondo negro
                dark_mask = (brightness < 75) & (a > 90)
                arr[dark_mask, 0] = 235
                arr[dark_mask, 1] = 250
                arr[dark_mask, 2] = 255
                self._logo_dark_enhanced = Image.fromarray(arr)
            except Exception as e:
                print(f"[!] Error al cargar logo: {e}")
                self._logo_image = None
                self._logo_dark_enhanced = None

    # =========================================================================
    # RENDER PRINCIPAL POR PANTALLA
    # =========================================================================

    def render_screen(
        self,
        screen_type: str,
        frame_count: int,
        metrics: Optional[Dict[str, Any]] = None,
        weather: Optional[Dict[str, Any]] = None,
        custom_names: Optional[Dict[str, str]] = None,
    ) -> Image.Image:
        img = Image.new("RGB", (self.width, self.height), self.COLOR_BG)
        draw = ImageDraw.Draw(img)

        self._draw_grid(draw)
        self._draw_hud_borders(draw)
        self._draw_header(draw, frame_count)

        names = custom_names or {
            "cpu_name": "AMD Ryzen 7 5700G",
            "gpu_name": "NVIDIA GeForce RTX 3070",
            "ram_name": "32 GB DDR4",
            "user_name": "Alan",
        }

        if screen_type == "logo_time":
            self._render_screen_logo_time(draw, img, frame_count)
        elif screen_type == "weather":
            self._render_screen_weather(draw, frame_count, weather or {})
        elif screen_type == "hardware":
            self._render_screen_hardware(draw, frame_count, metrics or {}, names)
        elif screen_type == "greeting":
            self._render_screen_greeting(draw, frame_count, names.get("user_name", "Alan"))
        elif screen_type == "brand":
            self._render_screen_brand(draw, img, frame_count)
        else:
            self._render_screen_brand(draw, img, frame_count)

        self._draw_audio_spectrum(draw, frame_count)
        return img

    # =========================================================================
    # ELEMENTOS GLOBALES DEL HUD
    # =========================================================================

    def _draw_grid(self, draw: ImageDraw.Draw):
        step = 28
        for x in range(0, self.width, step):
            draw.line([(x, 0), (x, self.height)], fill=self.COLOR_GRID, width=1)
        for y in range(0, self.height, step):
            draw.line([(0, y), (self.width, y)], fill=self.COLOR_GRID, width=1)

    def _draw_hud_borders(self, draw: ImageDraw.Draw):
        w, h = self.width, self.height
        margin = 6
        corner = 16

        draw.rectangle([margin, margin, w - margin, h - margin], outline=self.COLOR_CYAN_DIM, width=1)
        c = self.COLOR_CYAN
        draw.line([(margin, margin + corner), (margin, margin), (margin + corner, margin)], fill=c, width=2)
        draw.line([(w - margin - corner, margin), (w - margin, margin), (w - margin, margin + corner)], fill=c, width=2)
        draw.line([(margin, h - margin - corner), (margin, h - margin), (margin + corner, h - margin)], fill=c, width=2)
        draw.line([(w - margin - corner, h - margin), (w - margin, h - margin), (w - margin, h - margin - corner)], fill=c, width=2)

    def _draw_header(self, draw: ImageDraw.Draw, frame_count: int):
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")

        title = "STARK IND. // MARK VII" if not self.is_portrait else "STARK IND."
        draw.text((16, 10), title, fill=self.COLOR_CYAN, font=self.font_small)

        is_pulse_bright = (frame_count // 5) % 2 == 0
        dot_color = self.COLOR_GREEN if is_pulse_bright else self.COLOR_CYAN_DIM
        status_x = 135 if self.is_portrait else 200
        draw.ellipse([status_x, 14, status_x + 6, 20], fill=dot_color)
        draw.text((status_x + 12, 10), "ONLINE", fill=self.COLOR_GREEN, font=self.font_small)

        draw.text((self.width - 72, 10), time_str, fill=self.COLOR_WHITE, font=self.font_small)
        draw.line([(14, 25), (self.width - 14, 25)], fill=self.COLOR_CYAN_DIM, width=1)
        draw.line([(status_x - 8, 25), (status_x + 75, 25)], fill=self.COLOR_CYAN, width=2)

    def _draw_arc_reactor_core(self, draw: ImageDraw.Draw, cx: int, cy: int, base_r: int, frame_count: int):
        """
        Dibuja el Arc Reactor J.A.R.V.I.S. con las iniciales 'AC' en el núcleo central.
        """
        # Anillos exteriores
        draw.ellipse([cx - base_r, cy - base_r, cx + base_r, cy + base_r], outline=self.COLOR_CYAN_DIM, width=1)
        r2 = base_r - 6
        draw.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], outline=self.COLOR_CYAN, width=1)

        # Turbina / rayos giratorios
        angle_offset = (frame_count * 6) % 360
        num_spokes = 8
        for i in range(num_spokes):
            theta = math.radians(angle_offset + i * (360 / num_spokes))
            x1 = cx + int((r2 - 9) * math.cos(theta))
            y1 = cy + int((r2 - 9) * math.sin(theta))
            x2 = cx + int(r2 * math.cos(theta))
            y2 = cy + int(r2 * math.sin(theta))
            draw.line([(x1, y1), (x2, y2)], fill=self.COLOR_CYAN, width=2)

        # Anillo interior intermedio
        r_mid = int(base_r * 0.62)
        draw.ellipse([cx - r_mid, cy - r_mid, cx + r_mid, cy + r_mid], outline=self.COLOR_CYAN_GLOW, width=1)

        # Núcleo interior donde van las iniciales 'AC'
        r_core = int(base_r * 0.44)
        draw.ellipse([cx - r_core, cy - r_core, cx + r_core, cy + r_core], fill=(0, 48, 80), outline=self.COLOR_WHITE, width=2)

        # Iniciales "AC" en el centro
        ac_text = "AC"
        try:
            core_font = self.font_core
            bbox = draw.textbbox((0, 0), ac_text, font=core_font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = cx - (tw // 2)
            ty = cy - (th // 2) - 1

            # Resplandor de las iniciales
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((tx + dx, ty + dy), ac_text, fill=self.COLOR_CYAN_GLOW, font=core_font)
            draw.text((tx, ty), ac_text, fill=self.COLOR_WHITE, font=core_font)
        except Exception:
            draw.text((cx - 10, cy - 8), "AC", fill=self.COLOR_WHITE)

    # =========================================================================
    # PANTALLA 1: LOGO DESTACADO (GRANDE) + HORA ABAJO
    # =========================================================================

    def _render_screen_logo_time(self, draw: ImageDraw.Draw, img: Image.Image, frame_count: int):
        now = datetime.datetime.now()
        time_big = now.strftime("%H:%M:%S")

        dias = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO", "DOMINGO"]
        meses = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        dia_nom = dias[now.weekday()]
        mes_nom = meses[now.month - 1]
        date_str = f"{dia_nom}, {now.day} DE {mes_nom} {now.year}"

        logo_source = self._logo_dark_enhanced or self._logo_image

        if not self.is_portrait:
            # Layout Horizontal (480x320)
            # El logo es el protagonista: ocupa el centro superior con un tamaño destacado (altura ~160px)
            target_h = 160
            if logo_source:
                lw, lh = logo_source.size
                scale = target_h / lh
                target_w = int(lw * scale)
                # Limitar ancho máximo si fuera necesario
                if target_w > 320:
                    target_w = 320
                    target_h = int(lh * (target_w / lw))

                resized_logo = logo_source.resize((target_w, target_h), Image.Resampling.LANCZOS)
                lx = (self.width - target_w) // 2
                ly = 32

                # Resplandor holográfico sutil alrededor del logo
                glow_mask = resized_logo.split()[3].filter(ImageFilter.GaussianBlur(8))
                glow_layer = Image.new("RGBA", (target_w, target_h), (0, 240, 255, 120))
                img.paste(glow_layer, (lx, ly), glow_mask)
                img.paste(resized_logo, (lx, ly), resized_logo)
            else:
                # Marcador si no hay logo
                lx = 100
                ly = 50
                draw.rectangle([lx, ly, lx + 280, ly + 110], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
                draw.text((lx + 65, ly + 40), "ALAN CANTO", fill=self.COLOR_WHITE, font=self.font_large)

            # Tarjeta Sci-Fi debajo del logo con el Reloj Digital Grande y la Fecha
            clock_y = 200
            box_x0 = 45
            box_x1 = self.width - 45
            box_h = 84

            draw.rectangle([box_x0, clock_y, box_x1, clock_y + box_h], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            # Marcas de acento en las esquinas de la tarjeta del reloj
            draw.line([(box_x0, clock_y), (box_x0 + 25, clock_y)], fill=self.COLOR_ORANGE, width=2)
            draw.line([(box_x1 - 25, clock_y), (box_x1, clock_y)], fill=self.COLOR_ORANGE, width=2)
            draw.line([(box_x0, clock_y + box_h), (box_x0 + 25, clock_y + box_h)], fill=self.COLOR_CYAN, width=2)
            draw.line([(box_x1 - 25, clock_y + box_h), (box_x1, clock_y + box_h)], fill=self.COLOR_CYAN, width=2)

            # Reloj digital grande con resplandor holográfico
            bbox = draw.textbbox((0, 0), time_big, font=self.font_xlarge)
            tw = bbox[2] - bbox[0]
            tx = (self.width - tw) // 2
            ty = clock_y + 8

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((tx + dx, ty + dy), time_big, fill=self.COLOR_CYAN_GLOW, font=self.font_xlarge)
            draw.text((tx, ty), time_big, fill=self.COLOR_WHITE, font=self.font_xlarge)

            # Fecha debajo del reloj
            dbbox = draw.textbbox((0, 0), date_str, font=self.font_small)
            dtw = dbbox[2] - dbbox[0]
            draw.text(((self.width - dtw) // 2, clock_y + 54), date_str, fill=self.COLOR_CYAN, font=self.font_small)

        else:
            # Layout Vertical (320x480)
            # En vertical el logo se expande a gran tamaño (ancho 240px)
            target_w = 240
            if logo_source:
                lw, lh = logo_source.size
                scale = target_w / lw
                target_h = int(lh * scale)
                resized_logo = logo_source.resize((target_w, target_h), Image.Resampling.LANCZOS)
                lx = (self.width - target_w) // 2
                ly = 50

                # Resplandor holográfico
                glow_mask = resized_logo.split()[3].filter(ImageFilter.GaussianBlur(10))
                glow_layer = Image.new("RGBA", (target_w, target_h), (0, 240, 255, 120))
                img.paste(glow_layer, (lx, ly), glow_mask)
                img.paste(resized_logo, (lx, ly), resized_logo)
            else:
                ly = 80
                target_h = 160

            # Tarjeta de Reloj debajo
            clock_y = ly + target_h + 30
            draw.rectangle([18, clock_y, self.width - 18, clock_y + 95], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            draw.line([(18, clock_y), (45, clock_y)], fill=self.COLOR_ORANGE, width=2)
            draw.line([(self.width - 45, clock_y), (self.width - 18, clock_y)], fill=self.COLOR_ORANGE, width=2)

            bbox = draw.textbbox((0, 0), time_big, font=self.font_xlarge)
            tw = bbox[2] - bbox[0]
            tx = (self.width - tw) // 2
            ty = clock_y + 12

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((tx + dx, ty + dy), time_big, fill=self.COLOR_CYAN_GLOW, font=self.font_xlarge)
            draw.text((tx, ty), time_big, fill=self.COLOR_WHITE, font=self.font_xlarge)

            dbbox = draw.textbbox((0, 0), date_str, font=self.font_tiny)
            dtw = dbbox[2] - dbbox[0]
            draw.text(((self.width - dtw) // 2, clock_y + 60), date_str, fill=self.COLOR_CYAN, font=self.font_tiny)

    # =========================================================================
    # PANTALLA 2: PRONÓSTICO DEL TIEMPO
    # =========================================================================

    def _render_screen_weather(self, draw: ImageDraw.Draw, frame_count: int, weather: Dict[str, Any]):
        city = weather.get("city", "Santiago")
        country = weather.get("country", "Chile")
        temp = weather.get("temp", 20.0)
        app_temp = weather.get("apparent_temp", 20.0)
        condition = weather.get("condition", "Despejado")
        humidity = weather.get("humidity", 50)
        wind = weather.get("wind_speed", 10.0)
        icon_type = weather.get("icon", "SUNNY")
        updated_at = weather.get("updated_at", "--:--")

        if not self.is_portrait:
            # Horizontal (480x320)
            cx, cy = 76, 142
            self._draw_arc_reactor_core(draw, cx, cy, 48, frame_count)
            draw.text((cx - 28, cy + 54), "ARC CLIMATE", fill=self.COLOR_CYAN_DIM, font=self.font_tiny)

            x = 150
            draw.text((x, 34), "ATMOSPHERIC TELEMETRY", fill=self.COLOR_CYAN, font=self.font_small)
            loc_text = f"{city.upper()} // {country.upper()}"
            draw.text((x, 50), loc_text[:30], fill=self.COLOR_WHITE, font=self.font_title)
            draw.line([(x, 78), (self.width - 20, 78)], fill=self.COLOR_CYAN_DIM, width=1)

            card_y = 86
            draw.rectangle([x, card_y, self.width - 20, card_y + 82], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            draw.line([(x, card_y), (x + 16, card_y)], fill=self.COLOR_ORANGE, width=2)

            self._draw_weather_icon(draw, x + 38, card_y + 40, icon_type, frame_count)

            temp_str = f"{temp:.1f}°C"
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((x + 85 + dx, card_y + 12 + dy), temp_str, fill=self.COLOR_CYAN_GLOW, font=self.font_xlarge)
            draw.text((x + 85, card_y + 12), temp_str, fill=self.COLOR_WHITE, font=self.font_xlarge)

            draw.text((x + 86, card_y + 54), condition.upper(), fill=self.COLOR_GREEN, font=self.font_small)
            draw.text((x + 230, card_y + 54), f"SENS: {app_temp:.1f}°C", fill=self.COLOR_MUTED, font=self.font_tiny)

            bar_y = card_y + 92
            draw.text((x, bar_y), f"HUMIDITY: {humidity}%", fill=self.COLOR_CYAN, font=self.font_tiny)
            draw.rectangle([x, bar_y + 14, x + 135, bar_y + 20], outline=self.COLOR_CYAN_DIM, fill=(10, 20, 30))
            hw = int((humidity / 100.0) * 135)
            if hw > 0:
                draw.rectangle([x, bar_y + 14, x + hw, bar_y + 20], fill=self.COLOR_CYAN)

            draw.text((x + 160, bar_y), f"WIND: {wind:.1f} km/h", fill=self.COLOR_CYAN, font=self.font_tiny)
            draw.rectangle([x + 160, bar_y + 14, x + 295, bar_y + 20], outline=self.COLOR_CYAN_DIM, fill=(10, 20, 30))
            ww = min(135, int((wind / 80.0) * 135))
            if ww > 0:
                draw.rectangle([x + 160, bar_y + 14, x + 160 + ww, bar_y + 20], fill=self.COLOR_ORANGE)

            draw.text((x, bar_y + 28), f"SYNC: {updated_at} // BAROMETRIC PRESSURE: 1014 hPa // UV: LOW", fill=self.COLOR_MUTED, font=self.font_tiny)

        else:
            # Vertical (320x480)
            cx, cy = self.width // 2, 85
            self._draw_arc_reactor_core(draw, cx, cy, 46, frame_count)

            draw.text((20, 145), "ATMOSPHERIC TELEMETRY", fill=self.COLOR_CYAN, font=self.font_tiny)
            draw.text((20, 160), f"{city.upper()}, {country.upper()}"[:28], fill=self.COLOR_WHITE, font=self.font_title)

            draw.rectangle([20, 195, self.width - 20, 295], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            self._draw_weather_icon(draw, 60, 245, icon_type, frame_count)

            temp_str = f"{temp:.1f}°C"
            draw.text((120, 215), temp_str, fill=self.COLOR_WHITE, font=self.font_xlarge)
            draw.text((120, 260), condition.upper(), fill=self.COLOR_GREEN, font=self.font_small)

            draw.text((24, 315), f"HUMIDITY: {humidity}%", fill=self.COLOR_CYAN, font=self.font_tiny)
            draw.rectangle([24, 330, self.width - 24, 336], outline=self.COLOR_CYAN_DIM, fill=(10, 20, 30))
            hw = int((humidity / 100.0) * (self.width - 48))
            draw.rectangle([24, 330, 24 + hw, 336], fill=self.COLOR_CYAN)

            draw.text((24, 350), f"WIND: {wind:.1f} km/h", fill=self.COLOR_CYAN, font=self.font_tiny)
            draw.rectangle([24, 365, self.width - 24, 371], outline=self.COLOR_CYAN_DIM, fill=(10, 20, 30))
            ww = min(self.width - 48, int((wind / 80.0) * (self.width - 48)))
            draw.rectangle([24, 365, 24 + ww, 371], fill=self.COLOR_ORANGE)

    def _draw_weather_icon(self, draw: ImageDraw.Draw, cx: int, cy: int, icon_type: str, frame_count: int):
        c = self.COLOR_CYAN
        if icon_type in ("SUNNY", "MOSTLY_SUNNY"):
            r = 14
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=self.COLOR_ORANGE, outline=self.COLOR_WHITE, width=1)
            for i in range(8):
                angle = math.radians(i * 45 + (frame_count * 2))
                x1 = cx + int((r + 4) * math.cos(angle))
                y1 = cy + int((r + 4) * math.sin(angle))
                x2 = cx + int((r + 8) * math.cos(angle))
                y2 = cy + int((r + 8) * math.sin(angle))
                draw.line([(x1, y1), (x2, y2)], fill=self.COLOR_ORANGE, width=2)
        elif icon_type in ("RAINY", "HEAVY_RAIN", "DRIZZLE", "STORM"):
            draw.ellipse([cx - 18, cy - 8, cx - 2, cy + 8], fill=self.COLOR_CYAN_DIM)
            draw.ellipse([cx - 8, cy - 16, cx + 12, cy + 8], fill=self.COLOR_CYAN_DIM)
            draw.ellipse([cx + 4, cy - 6, cx + 18, cy + 8], fill=self.COLOR_CYAN_DIM)
            draw.rectangle([cx - 14, cy, cx + 14, cy + 8], fill=self.COLOR_CYAN_DIM)
            drop_offset = (frame_count * 3) % 12
            for dx in [-12, -4, 4, 12]:
                dy = cy + 12 + ((dx * 3 + drop_offset) % 10)
                draw.line([(cx + dx, dy), (cx + dx - 2, dy + 5)], fill=self.COLOR_CYAN, width=2)
        else:
            draw.ellipse([cx - 18, cy - 8, cx - 2, cy + 8], fill=self.COLOR_CYAN_DIM, outline=c)
            draw.ellipse([cx - 8, cy - 16, cx + 12, cy + 8], fill=self.COLOR_CYAN_DIM, outline=c)
            draw.ellipse([cx + 4, cy - 6, cx + 18, cy + 8], fill=self.COLOR_CYAN_DIM, outline=c)
            draw.rectangle([cx - 14, cy, cx + 14, cy + 8], fill=self.COLOR_CYAN_DIM)

    # =========================================================================
    # PANTALLA 3: RECURSOS DEL EQUIPO (HARDWARE MONITOR)
    # =========================================================================

    def _render_screen_hardware(
        self, draw: ImageDraw.Draw, frame_count: int, metrics: Dict[str, Any], names: Dict[str, str]
    ):
        cpu_load = metrics.get("cpu_load", 15.0)
        cpu_temp = metrics.get("cpu_temp", 42.0)
        ram_pct = metrics.get("ram_pct", 45.0)
        ram_used = metrics.get("ram_used_gb", 14.5)
        ram_total = metrics.get("ram_total_gb", 31.3)
        gpu_load = metrics.get("gpu_load", 12.0)
        gpu_temp = metrics.get("gpu_temp", 46.0)
        sys_temp = metrics.get("system_temp", 44.0)

        cpu_title = names.get("cpu_name", "AMD Ryzen 7 5700G")
        gpu_title = names.get("gpu_name", "NVIDIA GeForce RTX 3070")
        ram_title = names.get("ram_name", "32 GB DDR4")

        if not self.is_portrait:
            # Horizontal (480x320)
            cx, cy = 76, 142
            self._draw_arc_reactor_core(draw, cx, cy, 48, frame_count)
            draw.text((cx - 30, cy + 54), f"TEMP: {sys_temp:.0f}°C", fill=self.COLOR_GREEN, font=self.font_tiny)

            x = 150
            draw.text((x, 34), "HARDWARE TELEMETRY & DIAGNOSTICS", fill=self.COLOR_CYAN, font=self.font_small)
            draw.line([(x, 50), (self.width - 20, 50)], fill=self.COLOR_CYAN_DIM, width=1)

            # 1. CPU
            y1 = 58
            draw.text((x, y1), cpu_title[:28].upper(), fill=self.COLOR_WHITE, font=self.font_small)
            draw.text((self.width - 120, y1), f"{cpu_load:.1f}% // {cpu_temp:.0f}°C", fill=self.COLOR_CYAN, font=self.font_tiny)
            self._draw_segmented_bar(draw, x, y1 + 16, self.width - 20 - x, 7, cpu_load, self.COLOR_GREEN if cpu_load < 75 else self.COLOR_ORANGE)

            # 2. RAM
            y2 = y1 + 33
            draw.text((x, y2), ram_title[:28].upper(), fill=self.COLOR_WHITE, font=self.font_small)
            draw.text((self.width - 145, y2), f"{ram_used:.1f} / {ram_total:.1f} GB ({ram_pct:.0f}%)", fill=self.COLOR_CYAN, font=self.font_tiny)
            self._draw_segmented_bar(draw, x, y2 + 16, self.width - 20 - x, 7, ram_pct, self.COLOR_CYAN)

            # 3. GPU
            y3 = y2 + 33
            draw.text((x, y3), gpu_title[:28].upper(), fill=self.COLOR_WHITE, font=self.font_small)
            draw.text((self.width - 120, y3), f"{gpu_load:.1f}% // {gpu_temp:.0f}°C", fill=self.COLOR_CYAN, font=self.font_tiny)
            self._draw_segmented_bar(draw, x, y3 + 16, self.width - 20 - x, 7, gpu_load, self.COLOR_GREEN if gpu_load < 75 else self.COLOR_ORANGE)

            # 4. Tarjeta Térmica General
            y4 = y3 + 34
            draw.rectangle([x, y4, self.width - 20, y4 + 40], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            draw.line([(x, y4), (x + 14, y4)], fill=self.COLOR_ORANGE, width=2)
            draw.text((x + 8, y4 + 6), f"> THERMAL SENSORS: SYS {sys_temp:.1f}°C  |  CPU {cpu_temp:.0f}°C  |  GPU {gpu_temp:.0f}°C", fill=self.COLOR_ORANGE, font=self.font_tiny)
            draw.text((x + 8, y4 + 22), "> COOLING PROTOCOL: ACTIVE // STATUS NOMINAL", fill=self.COLOR_GREEN, font=self.font_tiny)

        else:
            # Vertical (320x480)
            cx, cy = self.width // 2, 85
            self._draw_arc_reactor_core(draw, cx, cy, 46, frame_count)

            draw.text((20, 142), "HARDWARE TELEMETRY", fill=self.COLOR_CYAN, font=self.font_tiny)

            y = 165
            draw.text((20, y), cpu_title[:22], fill=self.COLOR_WHITE, font=self.font_small)
            draw.text((self.width - 100, y), f"{cpu_load:.1f}% | {cpu_temp:.0f}°C", fill=self.COLOR_CYAN, font=self.font_tiny)
            self._draw_segmented_bar(draw, 20, y + 18, self.width - 40, 8, cpu_load, self.COLOR_GREEN)

            y += 42
            draw.text((20, y), ram_title[:22], fill=self.COLOR_WHITE, font=self.font_small)
            draw.text((self.width - 110, y), f"{ram_used:.1f}G ({ram_pct:.0f}%)", fill=self.COLOR_CYAN, font=self.font_tiny)
            self._draw_segmented_bar(draw, 20, y + 18, self.width - 40, 8, ram_pct, self.COLOR_CYAN)

            y += 42
            draw.text((20, y), gpu_title[:22], fill=self.COLOR_WHITE, font=self.font_small)
            draw.text((self.width - 100, y), f"{gpu_load:.1f}% | {gpu_temp:.0f}°C", fill=self.COLOR_CYAN, font=self.font_tiny)
            self._draw_segmented_bar(draw, 20, y + 18, self.width - 40, 8, gpu_load, self.COLOR_GREEN)

            y += 45
            draw.rectangle([20, y, self.width - 20, y + 54], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            draw.text((28, y + 8), f"SYS TEMP: {sys_temp:.1f}°C", fill=self.COLOR_ORANGE, font=self.font_small)
            draw.text((28, y + 30), "COOLING PROTOCOL: ACTIVE", fill=self.COLOR_GREEN, font=self.font_tiny)

    def _draw_segmented_bar(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int, pct: float, color: tuple):
        pct = max(0.0, min(100.0, pct))
        draw.rectangle([x, y, x + w, y + h], outline=self.COLOR_CYAN_DIM, fill=(10, 20, 30))
        filled_w = int((pct / 100.0) * w)
        if filled_w > 0:
            draw.rectangle([x, y, x + filled_w, y + h], fill=color)

    # =========================================================================
    # PANTALLA 4: SALUDO CONTEXTUAL SEGÚN HORARIO
    # =========================================================================

    def _render_screen_greeting(self, draw: ImageDraw.Draw, frame_count: int, user_name: str = "Alan"):
        now = datetime.datetime.now()
        hour = now.hour

        if 6 <= hour < 13:
            greeting = f"BUEN DÍA, {user_name.upper()}"
            sub_greeting = "J.A.R.V.I.S. A SU SERVICIO // INICIANDO PROTOCOLOS MATUTINOS"
        elif 13 <= hour < 20:
            greeting = f"BUENAS TARDES, {user_name.upper()}"
            sub_greeting = "J.A.R.V.I.S. EN LÍNEA // MONITOREO ACTIVO Y SISTEMAS NOMINALES"
        else:
            greeting = f"BUENAS NOCHES, {user_name.upper()}"
            sub_greeting = "J.A.R.V.I.S. MODO NOCTURNO // PROTOCOLO DE SEGURIDAD MARK VII"

        if not self.is_portrait:
            # Horizontal (480x320)
            cx, cy = 82, 142
            self._draw_arc_reactor_core(draw, cx, cy, 52, frame_count)
            draw.text((cx - 30, cy + 60), "ARC CORE 100%", fill=self.COLOR_CYAN_DIM, font=self.font_tiny)

            x = 160
            draw.text((x, 42), "STARK INDUSTRIES AI INTERFACE", fill=self.COLOR_CYAN, font=self.font_small)
            draw.line([(x, 60), (self.width - 20, 60)], fill=self.COLOR_CYAN_DIM, width=1)

            y_greet = 72
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((x + dx, y_greet + dy), greeting, fill=self.COLOR_CYAN_GLOW, font=self.font_large)
            draw.text((x, y_greet), greeting, fill=self.COLOR_WHITE, font=self.font_large)

            draw.text((x, y_greet + 40), sub_greeting[:44], fill=self.COLOR_CYAN, font=self.font_tiny)

            card_y = y_greet + 64
            draw.rectangle([x, card_y, self.width - 20, card_y + 48], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            draw.line([(x, card_y), (x + 16, card_y)], fill=self.COLOR_ORANGE, width=2)
            draw.text((x + 10, card_y + 8), f"> USUARIO IDENTIFICADO: {user_name.upper()}", fill=self.COLOR_ORANGE, font=self.font_tiny)
            draw.text((x + 10, card_y + 26), "> INTERFAZ NEURAL LISTA // ENCRIPTACIÓN CUÁNTICA ACTIVA", fill=self.COLOR_GREEN, font=self.font_tiny)

        else:
            # Vertical (320x480)
            cx, cy = self.width // 2, 110
            self._draw_arc_reactor_core(draw, cx, cy, 56, frame_count)

            bbox = draw.textbbox((0, 0), greeting, font=self.font_large)
            tw = bbox[2] - bbox[0]
            tx = (self.width - tw) // 2
            y_greet = 200

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((tx + dx, y_greet + dy), greeting, fill=self.COLOR_CYAN_GLOW, font=self.font_large)
            draw.text((tx, y_greet), greeting, fill=self.COLOR_WHITE, font=self.font_large)

            draw.text((20, y_greet + 44), sub_greeting[:38], fill=self.COLOR_CYAN, font=self.font_tiny)

            draw.rectangle([20, y_greet + 72, self.width - 20, y_greet + 130], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            draw.text((28, y_greet + 84), f"> USUARIO: {user_name.upper()}", fill=self.COLOR_ORANGE, font=self.font_tiny)
            draw.text((28, y_greet + 104), "> J.A.R.V.I.S. MARK VII ONLINE", fill=self.COLOR_GREEN, font=self.font_tiny)

    # =========================================================================
    # PANTALLA 5: "ALAN CANTO TECH"
    # =========================================================================

    def _render_screen_brand(self, draw: ImageDraw.Draw, img: Image.Image, frame_count: int):
        brand_title = "ALAN CANTO TECH"
        sub_title = "ADVANCED ENGINEERING & INNOVATION"

        if not self.is_portrait:
            # Horizontal (480x320)
            cx, cy = 82, 142
            self._draw_arc_reactor_core(draw, cx, cy, 52, frame_count)
            draw.text((cx - 28, cy + 60), "ARC CORE: AC", fill=self.COLOR_CYAN_DIM, font=self.font_tiny)

            x = 160
            draw.text((x, 38), "STARK ENTERPRISES // COLLABORATION", fill=self.COLOR_CYAN, font=self.font_small)
            draw.line([(x, 56), (self.width - 20, 56)], fill=self.COLOR_CYAN_DIM, width=1)

            # Gran título con resplandor holográfico
            y_brand = 66
            for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1)]:
                draw.text((x + dx, y_brand + dy), brand_title, fill=self.COLOR_CYAN_GLOW, font=self.font_xlarge)
            draw.text((x, y_brand), brand_title, fill=self.COLOR_WHITE, font=self.font_xlarge)

            # Subtítulo
            draw.text((x, y_brand + 44), sub_title, fill=self.COLOR_CYAN, font=self.font_small)

            # Cuadro Sci-Fi de proyectos y estado
            card_y = y_brand + 68
            draw.rectangle([x, card_y, self.width - 20, card_y + 46], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            draw.line([(x, card_y), (x + 18, card_y)], fill=self.COLOR_ORANGE, width=2)
            draw.text((x + 10, card_y + 7), "> SYSTEM ARCHITECTURE // HARDWARE CONTROL 3.5\"", fill=self.COLOR_ORANGE, font=self.font_tiny)
            draw.text((x + 10, card_y + 24), "> QUANTUM COMPUTING // AI SENSORS // ACTIVE", fill=self.COLOR_GREEN, font=self.font_tiny)

        else:
            # Vertical (320x480)
            cx, cy = self.width // 2, 110
            self._draw_arc_reactor_core(draw, cx, cy, 56, frame_count)

            y_brand = 205
            bbox = draw.textbbox((0, 0), brand_title, font=self.font_large)
            tw = bbox[2] - bbox[0]
            tx = (self.width - tw) // 2

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw.text((tx + dx, y_brand + dy), brand_title, fill=self.COLOR_CYAN_GLOW, font=self.font_large)
            draw.text((tx, y_brand), brand_title, fill=self.COLOR_WHITE, font=self.font_large)

            sbbox = draw.textbbox((0, 0), sub_title, font=self.font_tiny)
            stx = (self.width - (sbbox[2] - sbbox[0])) // 2
            draw.text((stx, y_brand + 40), sub_title, fill=self.COLOR_CYAN, font=self.font_tiny)

            draw.rectangle([20, y_brand + 70, self.width - 20, y_brand + 130], outline=self.COLOR_CYAN_DIM, fill=self.COLOR_DARK_CARD)
            draw.text((28, y_brand + 82), "> ALAN CANTO TECH LABS", fill=self.COLOR_ORANGE, font=self.font_tiny)
            draw.text((28, y_brand + 104), "> HARDWARE CONTROLLER v2.0", fill=self.COLOR_GREEN, font=self.font_tiny)

    # =========================================================================
    # AUDIO SPECTRUM ANIMADO (PIE DE PÁGINA)
    # =========================================================================

    def _draw_audio_spectrum(self, draw: ImageDraw.Draw, frame_count: int):
        base_x = 20
        base_y = self.height - 18
        bar_width = 6
        spacing = 2
        max_x = self.width - 100
        total_width = max_x - base_x
        num_bars = max(8, total_width // (bar_width + spacing))

        for i in range(num_bars):
            h = int(5 + 8 * math.sin((i * 0.45) + (frame_count * 0.22)) + 4 * math.cos((i * 0.8) - (frame_count * 0.18)))
            h = max(2, min(20, abs(h)))

            bx = base_x + i * (bar_width + spacing)
            by = base_y - h

            color = self.COLOR_CYAN if h < 11 else (self.COLOR_ORANGE if h < 16 else self.COLOR_WHITE)
            draw.rectangle([bx, by, bx + bar_width, base_y], fill=color)

        draw.text((self.width - 80, self.height - 22), "AUDIO HUD", fill=self.COLOR_CYAN_DIM, font=self.font_tiny)

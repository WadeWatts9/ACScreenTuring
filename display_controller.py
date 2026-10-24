import threading
import time
from typing import Callable, Optional, Dict, Any
from PIL import Image

from turing_display import TuringDisplay, Orientation
from jarvis_renderer import JarvisRenderer
from weather_service import WeatherService
from hardware_monitor import HardwareMonitor


class DisplayController:
    """
    Controlador en segundo plano que gestiona la conexión serie con la pantalla Turing,
    la rotación de pantallas (10 segundos por defecto), la recolección de métricas,
    la reconexión automática USB y la previsualización en vivo para la GUI de Windows.
    """

    def __init__(self, config: Dict[str, Any], preview_callback: Optional[Callable[[Image.Image], None]] = None):
        self.config = config.copy()
        self.preview_callback = preview_callback

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._display: Optional[TuringDisplay] = None
        self._renderer: Optional[JarvisRenderer] = None

        self.weather_service = WeatherService(cache_ttl_seconds=900)
        self.hardware_monitor = HardwareMonitor()

        self.last_status_message: str = "Detenido"
        self.current_screen_name: str = ""
        self.is_hardware_connected: bool = False
        self._last_reconnect_attempt: float = 0.0

    @property
    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def _get_orientation_enum(self) -> Orientation:
        orientation_str = self.config.get("orientation", "landscape")
        if orientation_str == "portrait":
            return Orientation.PORTRAIT
        elif orientation_str == "landscape_rev":
            return Orientation.REVERSE_LANDSCAPE
        elif orientation_str == "portrait_rev":
            return Orientation.REVERSE_PORTRAIT
        return Orientation.LANDSCAPE

    def _get_target_dimensions(self) -> tuple[int, int]:
        orient = self._get_orientation_enum()
        if orient in (Orientation.PORTRAIT, Orientation.REVERSE_PORTRAIT):
            return 320, 480
        return 480, 320

    def update_config(self, new_config: Dict[str, Any]):
        old_orient = self.config.get("orientation", "landscape")
        self.config.update(new_config)
        new_orient = self.config.get("orientation", "landscape")

        if old_orient != new_orient:
            w, h = self._get_target_dimensions()
            self._renderer = JarvisRenderer(width=w, height=h)
            if self._display and self.is_hardware_connected:
                try:
                    self._display.set_orientation(self._get_orientation_enum())
                except Exception:
                    pass

        if self._display and self.is_hardware_connected:
            try:
                brightness = int(self.config.get("brightness", 85))
                self._display.set_brightness(brightness)
            except Exception:
                pass

    def _try_connect_hardware(self) -> tuple[bool, str]:
        port = self.config.get("port", "auto")
        if port == "auto":
            detected = TuringDisplay.auto_detect_port()
            if not detected:
                self.is_hardware_connected = False
                return False, "Pantalla USB en espera (Previsualización activa - Auto-detectando puerto COM...)"
            port = detected

        orientation = self._get_orientation_enum()
        try:
            disp = TuringDisplay(port=port, orientation=orientation)
            disp.connect()
            disp.set_brightness(int(self.config.get("brightness", 85)))
            self._display = disp
            self.is_hardware_connected = True
            self.last_status_message = f"Conectado a {port} ({disp.width}x{disp.height})"
            return True, self.last_status_message
        except Exception as e:
            self._display = None
            self.is_hardware_connected = False
            return False, f"Puerto {port} no disponible ({e}). Modo monitor en vivo activo."

    def start(self, allow_virtual_fallback: bool = True) -> tuple[bool, str]:
        if self.is_running:
            return True, "Ya se encuentra en ejecución."

        hw_ok, hw_msg = self._try_connect_hardware()
        self._last_reconnect_attempt = time.time()

        if not hw_ok and not allow_virtual_fallback:
            return False, hw_msg

        w, h = self._get_target_dimensions()
        self._renderer = JarvisRenderer(width=w, height=h)
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        self.last_status_message = hw_msg
        return True, hw_msg

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

        if self._display:
            try:
                self._display.disconnect()
            except Exception:
                pass
            self._display = None

        self.is_hardware_connected = False
        self.last_status_message = "Desconectado"

    def _worker_loop(self):
        frame_count = 0
        current_screen_idx = 0
        last_screen_switch = time.time()

        # Cache de datos climáticos
        city = self.config.get("weather_city", "Santiago")
        country = self.config.get("weather_country", "Chile")
        current_weather = self.weather_service.get_weather(city, country)
        last_weather_fetch = time.time()

        while self._running:
            t0 = time.time()
            fps = float(self.config.get("fps", 6.0))
            frame_delay = 1.0 / max(1.0, min(15.0, fps))

            # Si la pantalla física no está conectada aún, reintentar conexión cada 3 segundos
            if not self.is_hardware_connected and (t0 - self._last_reconnect_attempt >= 3.0):
                self._last_reconnect_attempt = t0
                self._try_connect_hardware()

            # Verificar pantallas activas
            active_screens = self.config.get(
                "active_screens", ["logo_time", "weather", "hardware", "greeting", "brand"]
            )
            if not active_screens:
                active_screens = ["logo_time"]

            # Modo pantalla fija o rotativo
            is_single_mode = self.config.get("single_screen_mode", False)
            if is_single_mode:
                active_screen = self.config.get("selected_single_screen", active_screens[0])
            else:
                rotation_interval = max(3, int(self.config.get("rotation_interval", 10)))
                if t0 - last_screen_switch >= rotation_interval:
                    current_screen_idx = (current_screen_idx + 1) % len(active_screens)
                    last_screen_switch = t0
                if current_screen_idx >= len(active_screens):
                    current_screen_idx = 0
                active_screen = active_screens[current_screen_idx]

            self.current_screen_name = active_screen

            # Actualizar clima cada 5 minutos en segundo plano
            if t0 - last_weather_fetch > 300:
                city = self.config.get("weather_city", "Santiago")
                country = self.config.get("weather_country", "Chile")
                current_weather = self.weather_service.get_weather(city, country)
                last_weather_fetch = t0

            # Obtener telemetría de hardware
            metrics = self.hardware_monitor.get_metrics()

            custom_names = {
                "cpu_name": self.config.get("cpu_name", "AMD Ryzen 7 5700G"),
                "gpu_name": self.config.get("gpu_name", "NVIDIA GeForce RTX 3070"),
                "ram_name": self.config.get("ram_name", "32 GB DDR4"),
                "user_name": self.config.get("user_name", "Alan"),
            }

            try:
                frame = self._renderer.render_screen(
                    screen_type=active_screen,
                    frame_count=frame_count,
                    metrics=metrics,
                    weather=current_weather,
                    custom_names=custom_names,
                )

                if self._display and self.is_hardware_connected:
                    try:
                        self._display.display_image(frame)
                    except Exception as serial_err:
                        print(f"[!] Conexión USB interrumpida: {serial_err}")
                        try:
                            self._display.disconnect()
                        except Exception:
                            pass
                        self._display = None
                        self.is_hardware_connected = False
                        self.last_status_message = "Pantalla USB desconectada. Reintentando conexión..."

                if self.preview_callback:
                    self.preview_callback(frame)

            except Exception as e:
                print(f"[!] Error en ciclo de pantalla: {e}")
                self.last_status_message = f"Error: {e}"
                time.sleep(1.0)

            frame_count += 1
            elapsed = time.time() - t0
            sleep_time = max(0.005, frame_delay - elapsed)
            time.sleep(sleep_time)

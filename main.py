import argparse
import sys
import time

from config import load_config
from turing_display import TuringDisplay, Orientation
from jarvis_renderer import JarvisRenderer
from hardware_monitor import HardwareMonitor
from weather_service import WeatherService


def parse_arguments():
    parser = argparse.ArgumentParser(description="J.A.R.V.I.S. HUD para pantallas secundarias Turing (USB)")
    parser.add_argument(
        "--gui",
        action="store_true",
        default=False,
        help="Lanza la interfaz gráfica de usuario para Windows",
    )
    parser.add_argument(
        "--mode",
        choices=["gui", "static", "live"],
        default="gui",
        help="Modo de ejecución: 'gui' (interfaz de usuario de Windows), 'static' (pantalla fija), 'live' (modo consola rotativo)",
    )
    parser.add_argument(
        "--screen",
        choices=["logo_time", "weather", "hardware", "greeting", "brand", "all"],
        default="all",
        help="Pantalla específica para mostrar en modo consola",
    )
    parser.add_argument(
        "--orientation",
        choices=["landscape", "portrait", "landscape_rev", "portrait_rev"],
        default=None,
        help="Orientación de la pantalla (predeterminado: según config.json o landscape)",
    )
    parser.add_argument(
        "--port",
        type=str,
        default=None,
        help="Puerto COM específico (ej. COM3). Si no se especifica, se detecta automáticamente.",
    )
    parser.add_argument(
        "--brightness",
        type=int,
        default=None,
        help="Nivel de brillo (0-100)",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=6.0,
        help="Cuadros por segundo en modo consola en vivo",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Guarda una captura 'preview.png' localmente al iniciar",
    )
    return parser.parse_args()


def get_orientation_enum(name: str) -> Orientation:
    mapping = {
        "landscape": Orientation.LANDSCAPE,
        "portrait": Orientation.PORTRAIT,
        "landscape_rev": Orientation.REVERSE_LANDSCAPE,
        "portrait_rev": Orientation.REVERSE_PORTRAIT,
    }
    return mapping.get(name, Orientation.LANDSCAPE)


def main():
    args = parse_arguments()
    config = load_config()

    # Si se pide GUI o no se pasaron argumentos de consola, abrir la interfaz gráfica
    if args.gui or (args.mode == "gui" and len(sys.argv) == 1):
        try:
            import gui_app
            gui_app.main()
            return
        except Exception as e:
            print(f"[!] Error al iniciar la interfaz gráfica: {e}")
            print("[*] Pasando a modo consola...")

    # Modo Consola / Terminal
    port = args.port or config.get("port", "auto")
    if port == "auto":
        port = None

    orientation_name = args.orientation or config.get("orientation", "landscape")
    orientation = get_orientation_enum(orientation_name)
    brightness = args.brightness if args.brightness is not None else int(config.get("brightness", 85))

    disp = TuringDisplay(port=port, orientation=orientation)
    try:
        disp.connect()
    except Exception as e:
        print(f"[!] Error al conectar con la pantalla: {e}")
        sys.exit(1)

    disp.set_brightness(brightness)
    renderer = JarvisRenderer(width=disp.width, height=disp.height)
    hw_mon = HardwareMonitor()
    weather_svc = WeatherService()

    active_screens = config.get("active_screens", ["logo_time", "weather", "hardware", "greeting", "brand"])
    if args.screen != "all":
        active_screens = [args.screen]

    custom_names = {
        "cpu_name": config.get("cpu_name", "AMD Ryzen 7 5700G"),
        "gpu_name": config.get("gpu_name", "NVIDIA GeForce RTX 3070"),
        "ram_name": config.get("ram_name", "32 GB DDR4"),
        "user_name": config.get("user_name", "Alan"),
    }

    w_city = config.get("weather_city", "Santiago")
    w_country = config.get("weather_country", "Chile")
    weather_data = weather_svc.get_weather(w_city, w_country)

    if args.preview or args.mode == "static":
        preview_frame = renderer.render_screen(
            screen_type=active_screens[0],
            frame_count=0,
            metrics=hw_mon.get_metrics(),
            weather=weather_data,
            custom_names=custom_names,
        )
        preview_frame.save("preview.png")
        print("[*] Previsualización guardada en 'preview.png'")

    if args.mode == "static":
        print(f"[*] Mostrando pantalla estática: {active_screens[0]}...")
        frame = renderer.render_screen(
            screen_type=active_screens[0],
            frame_count=0,
            metrics=hw_mon.get_metrics(),
            weather=weather_data,
            custom_names=custom_names,
        )
        disp.display_image(frame)
        print("[+] ¡Pantalla actualizada! Desconectando puerto.")
        disp.disconnect()
    else:
        print("[*] Iniciando modo rotativo en vivo (10s por pantalla). Presiona Ctrl+C para salir.")
        frame_delay = 1.0 / max(1.0, args.fps)
        frame_count = 0
        current_scr_idx = 0
        last_switch = time.time()
        rot_interval = int(config.get("rotation_interval", 10))

        try:
            while True:
                t0 = time.time()
                if t0 - last_switch >= rot_interval:
                    current_scr_idx = (current_scr_idx + 1) % len(active_screens)
                    last_switch = t0

                current_scr = active_screens[current_scr_idx]
                metrics = hw_mon.get_metrics()

                frame = renderer.render_screen(
                    screen_type=current_scr,
                    frame_count=frame_count,
                    metrics=metrics,
                    weather=weather_data,
                    custom_names=custom_names,
                )
                disp.display_image(frame)
                frame_count += 1

                elapsed = time.time() - t0
                sleep_time = max(0.001, frame_delay - elapsed)
                time.sleep(sleep_time)
        except KeyboardInterrupt:
            print("\n[*] Deteniendo...")
        finally:
            disp.disconnect()
            print("[+] Desconectado correctamente.")


if __name__ == "__main__":
    main()

import json
import os
import sys
from typing import Dict, Any

CONFIG_FILENAME = "config.json"


def get_app_dir() -> str:
    """Devuelve el directorio donde se ubica el ejecutable (.exe) o el script fuente."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_resource_path(relative_path: str) -> str:
    """
    Resuelve la ruta de recursos (ej. Logo.png, app_icon.ico).
    1. Primero busca junto al ejecutable (.exe) por si el usuario desea personalizar el archivo.
    2. Si está empaquetado con PyInstaller (--onefile), busca en sys._MEIPASS.
    3. Por último, busca en el directorio del código fuente.
    """
    external_path = os.path.join(get_app_dir(), relative_path)
    if os.path.exists(external_path):
        return external_path

    if hasattr(sys, "_MEIPASS"):
        bundled_path = os.path.join(getattr(sys, "_MEIPASS"), relative_path)
        if os.path.exists(bundled_path):
            return bundled_path

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def get_config_path() -> str:
    """Devuelve la ruta de config.json junto al .exe o en %APPDATA% si no hay permisos de escritura."""
    primary_path = os.path.join(get_app_dir(), CONFIG_FILENAME)
    if os.path.exists(primary_path):
        return primary_path

    # Verificar si podemos escribir en el directorio de la aplicación
    try:
        test_file = os.path.join(get_app_dir(), ".write_test")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        return primary_path
    except Exception:
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        cfg_dir = os.path.join(appdata, "JarvisScreenController")
        os.makedirs(cfg_dir, exist_ok=True)
        return os.path.join(cfg_dir, CONFIG_FILENAME)


CONFIG_FILE = get_config_path()

DEFAULT_CONFIG: Dict[str, Any] = {
    "port": "auto",
    "orientation": "landscape",
    "brightness": 85,
    "fps": 6.0,
    "rotation_interval": 10,
    "active_screens": ["logo_time", "weather", "hardware", "greeting", "brand"],
    "single_screen_mode": False,
    "selected_single_screen": "logo_time",
    "weather_city": "Santiago",
    "weather_country": "Chile",
    "cpu_name": "AMD Ryzen 7 5700G",
    "gpu_name": "NVIDIA GeForce RTX 3070",
    "ram_name": "32 GB DDR4",
    "user_name": "Alan",
}


def load_config() -> Dict[str, Any]:
    cfg = DEFAULT_CONFIG.copy()
    cfg_path = get_config_path()
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg.update(data)
        except Exception as e:
            print(f"[!] Error al cargar config.json: {e}")
    return cfg


def save_config(cfg: Dict[str, Any]) -> bool:
    cfg_path = get_config_path()
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[!] Error al guardar config.json: {e}")
        return False

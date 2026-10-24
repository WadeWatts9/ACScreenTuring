import json
import time
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional

WMO_WEATHER_MAP = {
    0: ("Despejado", "SUNNY"),
    1: ("Mayormente Despejado", "MOSTLY_SUNNY"),
    2: ("Parcialmente Nublado", "PARTLY_CLOUDY"),
    3: ("Nublado", "CLOUDY"),
    45: ("Niebla", "FOGGY"),
    48: ("Niebla Escarchada", "FOGGY"),
    51: ("Llovizna Ligera", "DRIZZLE"),
    53: ("Llovizna Moderada", "DRIZZLE"),
    55: ("Llovizna Densa", "RAINY"),
    61: ("Lluvia Ligera", "RAINY"),
    63: ("Lluvia Moderada", "RAINY"),
    65: ("Lluvia Fuerte", "HEAVY_RAIN"),
    71: ("Nieve Ligera", "SNOWY"),
    73: ("Nieve Moderada", "SNOWY"),
    75: ("Nieve Fuerte", "HEAVY_SNOW"),
    80: ("Chubascos Leves", "RAINY"),
    81: ("Chubascos Fuertes", "HEAVY_RAIN"),
    82: ("Torbellino / Chaparrón", "STORM"),
    95: ("Tormenta Eléctrica", "THUNDER"),
    96: ("Tormenta con Granizo", "THUNDER"),
    99: ("Tormenta Severa", "THUNDER"),
}


class WeatherService:
    def __init__(self, cache_ttl_seconds: int = 900):
        self.cache_ttl = cache_ttl_seconds
        self._cached_data: Optional[Dict[str, Any]] = None
        self._last_update_ts: float = 0.0
        self._last_city: str = ""
        self._last_country: str = ""

    def get_weather(self, city: str, country: str = "", force_refresh: bool = False) -> Dict[str, Any]:
        now = time.time()
        city_clean = city.strip()
        country_clean = country.strip()

        if not city_clean:
            city_clean = "Santiago"

        key_changed = (city_clean.lower() != self._last_city.lower()) or (country_clean.lower() != self._last_country.lower())

        if not force_refresh and not key_changed and self._cached_data and (now - self._last_update_ts < self.cache_ttl):
            return self._cached_data

        try:
            coords = self._geocode(city_clean, country_clean)
            if not coords:
                if self._cached_data:
                    return self._cached_data
                return self._fallback_data(city_clean, country_clean, "Ciudad no encontrada")

            lat, lon, resolved_name, resolved_country = coords
            weather_data = self._fetch_open_meteo(lat, lon)
            if weather_data:
                weather_data["city"] = resolved_name
                weather_data["country"] = resolved_country or country_clean
                weather_data["updated_at"] = time.strftime("%H:%M")
                self._cached_data = weather_data
                self._last_update_ts = now
                self._last_city = city_clean
                self._last_country = country_clean
                return weather_data
        except Exception as e:
            print(f"[!] Error al obtener clima: {e}")

        if self._cached_data:
            return self._cached_data

        return self._fallback_data(city_clean, country_clean, "Sin conexión")

    def _geocode(self, city: str, country: str) -> Optional[tuple[float, float, str, str]]:
        encoded_city = urllib.parse.quote(city)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_city}&count=10&language=es&format=json"

        req = urllib.request.Request(url, headers={"User-Agent": "JarvisHUD/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            results = payload.get("results")
            if not results or len(results) == 0:
                return None

            selected = results[0]
            if country:
                c_low = country.lower().strip()
                for r in results:
                    rc = r.get("country", "").lower()
                    rcc = r.get("country_code", "").lower()
                    if c_low in rc or c_low == rcc or rc in c_low:
                        selected = r
                        break

            lat = float(selected["latitude"])
            lon = float(selected["longitude"])
            name = selected.get("name", city)
            c_name = selected.get("country", country)
            return lat, lon, name, c_name

    def _fetch_open_meteo(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat:.5f}&longitude={lon:.5f}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
            f"&timezone=auto"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "JarvisHUD/1.0"})
        with urllib.request.urlopen(req, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
            current = payload.get("current", {})
            code = int(current.get("weather_code", 0))
            condition_desc, condition_icon = WMO_WEATHER_MAP.get(code, ("Despejado", "SUNNY"))

            return {
                "temp": float(current.get("temperature_2m", 20.0)),
                "apparent_temp": float(current.get("apparent_temperature", 20.0)),
                "humidity": int(current.get("relative_humidity_2m", 50)),
                "wind_speed": float(current.get("wind_speed_10m", 0.0)),
                "weather_code": code,
                "condition": condition_desc,
                "icon": condition_icon,
                "is_live": True,
            }

    def _fallback_data(self, city: str, country: str, error_msg: str) -> Dict[str, Any]:
        return {
            "city": city.title(),
            "country": country.title(),
            "temp": 20.0,
            "apparent_temp": 20.0,
            "humidity": 50,
            "wind_speed": 10.0,
            "weather_code": 0,
            "condition": "Despejado (Offline)",
            "icon": "SUNNY",
            "is_live": False,
            "updated_at": "--:--",
            "status_msg": error_msg
        }

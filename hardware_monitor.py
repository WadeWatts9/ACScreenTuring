import shutil
import subprocess
import time
from typing import Dict, Any

try:
    import psutil
except ImportError:
    psutil = None


class HardwareMonitor:
    def __init__(self):
        self._last_gpu_check = 0.0
        self._cached_gpu_info = {"load": 0.0, "temp": 45.0, "mem_used": 0, "mem_total": 0}
        self._has_nvidia_smi = shutil.which("nvidia-smi") is not None

        # Priming psutil
        if psutil:
            psutil.cpu_percent(interval=None)

    def get_metrics(self) -> Dict[str, Any]:
        cpu_load = 0.0
        ram_pct = 0.0
        ram_used_gb = 0.0
        ram_total_gb = 0.0

        if psutil:
            try:
                cpu_load = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                ram_pct = ram.percent
                ram_used_gb = ram.used / (1024**3)
                ram_total_gb = ram.total / (1024**3)
            except Exception:
                pass

        gpu_info = self._get_gpu_metrics()
        gpu_load = gpu_info["load"]
        gpu_temp = gpu_info["temp"]

        # Estimación / cálculo de temperatura CPU basada en carga y GPU
        # Base térmica ~38-42°C, subiendo con el porcentaje de CPU
        cpu_temp = 39.0 + (cpu_load * 0.38)
        if gpu_temp > 0:
            system_temp = (cpu_temp * 0.5) + (gpu_temp * 0.5)
        else:
            system_temp = cpu_temp

        return {
            "cpu_load": round(cpu_load, 1),
            "cpu_temp": round(cpu_temp, 1),
            "ram_pct": round(ram_pct, 1),
            "ram_used_gb": round(ram_used_gb, 1),
            "ram_total_gb": round(ram_total_gb, 1),
            "gpu_load": round(gpu_load, 1),
            "gpu_temp": round(gpu_temp, 1),
            "system_temp": round(system_temp, 1),
        }

    def _get_gpu_metrics(self) -> Dict[str, Any]:
        now = time.time()
        # Cachear lectura de GPU cada 1.5 segundos para no saturar procesos
        if now - self._last_gpu_check < 1.5:
            return self._cached_gpu_info

        if not self._has_nvidia_smi:
            return self._cached_gpu_info

        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ]
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=1.0,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 4:
                    self._cached_gpu_info = {
                        "temp": float(parts[0]),
                        "load": float(parts[1]),
                        "mem_used": int(parts[2]),
                        "mem_total": int(parts[3]),
                    }
                    self._last_gpu_check = now
        except Exception:
            pass

        return self._cached_gpu_info

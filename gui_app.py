import ctypes
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional

from PIL import Image, ImageTk, ImageGrab
from serial.tools.list_ports import comports

from config import load_config, save_config, get_resource_path
from display_controller import DisplayController
from weather_service import WeatherService
from turing_display import TuringDisplay


class JarvisControlApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("J.A.R.V.I.S. Smart Screen Controller - Alan Canto Tech")
        self.root.geometry("980x750")
        self.root.minsize(920, 690)
        self.root.configure(bg="#080e1a")

        # Establecer AppUserModelID e icono de barra de tareas en Windows
        self._setup_window_icon()

        # Cargar configuración persistente
        self.config = load_config()

        # Servicio de clima para pruebas desde la GUI
        self.weather_service = WeatherService()

        # Controlador de pantalla
        self.controller: Optional[DisplayController] = None
        self._preview_image_tk = None
        self._last_preview_pil: Optional[Image.Image] = None

        self._setup_styles()
        self._build_ui()
        self._refresh_ports()
        self._update_ui_state(is_running=False)

        # Actualización periódica de la preview y estado en el hilo principal de Tkinter
        self.root.after(100, self._gui_tick)

        # Al pulsar la [X] de cerrar ventana, minimizar y mantener abierto en la barra de tareas
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_to_taskbar)

        # Iniciar transmisión automáticamente al abrir el programa con la configuración guardada
        self.root.after(250, lambda: self._start_transmission(auto_start=True))

        # Soporte opcional para captura de pantalla automatizada de documentación
        screenshot_target = os.environ.get("JARVIS_AUTO_SCREENSHOT")
        if screenshot_target:
            self.root.after(2200, lambda: self._take_auto_screenshot(screenshot_target))

    def _setup_window_icon(self):
        try:
            if sys.platform == "win32":
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "AlanCantoTech.JarvisScreenController.2.0"
                )
        except Exception:
            pass

        try:
            ico_path = get_resource_path("app_icon.ico")
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
        except Exception:
            pass

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Configurar colores Sci-Fi / JARVIS para ttk
        style.configure("TFrame", background="#080e1a")
        style.configure("Card.TFrame", background="#0d1728", relief="ridge")
        style.configure("TLabel", background="#080e1a", foreground="#d8e8f8", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Bahnschrift", 16, "bold"), foreground="#00f0ff", background="#080e1a")
        style.configure("SubHeader.TLabel", font=("Segoe UI", 9), foreground="#588da8", background="#080e1a")
        style.configure("Section.TLabel", font=("Bahnschrift", 11, "bold"), foreground="#00f0ff", background="#0d1728")
        style.configure("Card.TLabel", background="#0d1728", foreground="#c0d8f0", font=("Segoe UI", 9))

        style.configure("TCheckbutton", background="#0d1728", foreground="#c0d8f0", font=("Segoe UI", 9))
        style.map("TCheckbutton", background=[("active", "#0d1728")], foreground=[("active", "#00f0ff")])

        style.configure(
            "TCombobox",
            fieldbackground="#09121f",
            background="#12253d",
            foreground="#ffffff",
            arrowcolor="#00f0ff",
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#09121f")],
            foreground=[("readonly", "#ffffff")],
        )

        style.configure("TScale", background="#0d1728", troughcolor="#09121f")

    def _build_ui(self):
        # 1. Cabecera principal
        header_frame = tk.Frame(self.root, bg="#080e1a", pady=10, padx=20)
        header_frame.pack(fill="x")

        title_lbl = ttk.Label(header_frame, text="⚡ J.A.R.V.I.S. SMART SCREEN HUD", style="Header.TLabel")
        title_lbl.pack(anchor="w")

        sub_lbl = ttk.Label(
            header_frame,
            text='ALAN CANTO TECH  //  CONTROLADOR DE PANTALLA TURING 3.5" USB  //  AUTO-START & TASKBAR MODE',
            style="SubHeader.TLabel",
        )
        sub_lbl.pack(anchor="w")

        # Barra separadora cian
        sep = tk.Frame(self.root, bg="#00f0ff", height=2)
        sep.pack(fill="x", padx=15, pady=(0, 10))

        # 2. Contenedor dividido en 2 columnas (Izquierda: Opciones, Derecha: Preview y Control)
        main_container = tk.Frame(self.root, bg="#080e1a", padx=15, pady=5)
        main_container.pack(fill="both", expand=True)

        left_col = tk.Frame(main_container, bg="#080e1a", width=520)
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        right_col = tk.Frame(main_container, bg="#080e1a", width=420)
        right_col.pack(side="right", fill="both", expand=False)

        self._build_settings_panel(left_col)
        self._build_preview_panel(right_col)

        # 3. Barra de estado inferior
        status_bar = tk.Frame(self.root, bg="#04070d", height=28, padx=15)
        status_bar.pack(fill="x", side="bottom")

        self.lbl_status = tk.Label(
            status_bar,
            text="Iniciando transmisión automática con la configuración guardada...",
            bg="#04070d",
            fg="#00f0ff",
            font=("Segoe UI", 9),
        )
        self.lbl_status.pack(side="left", pady=4)

        self.lbl_fps_status = tk.Label(
            status_bar,
            text="FIRMWARE: USB35INCHIPSV2",
            bg="#04070d",
            fg="#00f0ff",
            font=("Segoe UI", 9),
        )
        self.lbl_fps_status.pack(side="right", pady=4)

    def _build_settings_panel(self, parent: tk.Frame):
        # Canvas con scrollbar para permitir ver todas las opciones cómodamente
        canvas = tk.Canvas(parent, bg="#080e1a", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#080e1a")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # --- SECCIÓN A: HARDWARE Y CONEXIÓN ---
        f_hw = tk.LabelFrame(
            scrollable_frame,
            text=" [1] CONEXIÓN Y PANTALLA ",
            bg="#0d1728",
            fg="#00f0ff",
            font=("Bahnschrift", 10, "bold"),
            padx=12,
            pady=10,
        )
        f_hw.pack(fill="x", pady=6)

        # Puerto COM
        r1 = tk.Frame(f_hw, bg="#0d1728")
        r1.pack(fill="x", pady=3)
        tk.Label(r1, text="Puerto COM:", bg="#0d1728", fg="#c0d8f0", width=12, anchor="w").pack(side="left")
        self.cb_ports = ttk.Combobox(r1, state="readonly", width=22)
        self.cb_ports.pack(side="left", padx=5)
        btn_refresh = tk.Button(
            r1,
            text="🔄 Refrescar",
            bg="#14263f",
            fg="#00f0ff",
            activebackground="#00f0ff",
            activeforeground="#000000",
            bd=1,
            relief="flat",
            command=self._refresh_ports,
        )
        btn_refresh.pack(side="left", padx=4)

        # Orientación y Brillo
        r2 = tk.Frame(f_hw, bg="#0d1728")
        r2.pack(fill="x", pady=4)
        tk.Label(r2, text="Orientación:", bg="#0d1728", fg="#c0d8f0", width=12, anchor="w").pack(side="left")
        self.var_orientation = tk.StringVar(value=self.config.get("orientation", "landscape"))
        cb_orient = ttk.Combobox(
            r2,
            textvariable=self.var_orientation,
            values=["landscape", "portrait"],
            state="readonly",
            width=14,
        )
        cb_orient.pack(side="left", padx=5)
        cb_orient.bind("<<ComboboxSelected>>", self._on_live_setting_change)

        tk.Label(r2, text="Brillo:", bg="#0d1728", fg="#c0d8f0", padx=10).pack(side="left")
        self.var_brightness = tk.IntVar(value=self.config.get("brightness", 85))
        scale_bright = ttk.Scale(
            r2,
            from_=10,
            to=100,
            variable=self.var_brightness,
            orient="horizontal",
            command=self._on_brightness_change,
        )
        scale_bright.pack(side="left", fill="x", expand=True, padx=5)
        self.lbl_bright_val = tk.Label(
            r2, text=f"{self.var_brightness.get()}%", bg="#0d1728", fg="#00f0ff", width=4
        )
        self.lbl_bright_val.pack(side="left")

        # --- SECCIÓN B: PANTALLAS Y ROTACIÓN (10s) ---
        f_rot = tk.LabelFrame(
            scrollable_frame,
            text=" [2] PANTALLAS EN ROTACIÓN (CADA 10 SEGUNDOS) ",
            bg="#0d1728",
            fg="#00f0ff",
            font=("Bahnschrift", 10, "bold"),
            padx=12,
            pady=10,
        )
        f_rot.pack(fill="x", pady=6)

        r_time = tk.Frame(f_rot, bg="#0d1728")
        r_time.pack(fill="x", pady=2)
        tk.Label(r_time, text="Intervalo de rotación (segundos):", bg="#0d1728", fg="#c0d8f0").pack(side="left")
        self.var_rot_interval = tk.IntVar(value=self.config.get("rotation_interval", 10))
        sp_interval = tk.Spinbox(
            r_time,
            from_=3,
            to=120,
            textvariable=self.var_rot_interval,
            width=5,
            bg="#080e1a",
            fg="#00f0ff",
            bd=1,
            command=self._on_live_setting_change,
        )
        sp_interval.pack(side="left", padx=10)

        # Checkboxes de pantallas activas
        active_list = self.config.get(
            "active_screens", ["logo_time", "weather", "hardware", "greeting", "brand"]
        )
        self.var_scr_logo = tk.BooleanVar(value="logo_time" in active_list)
        self.var_scr_weather = tk.BooleanVar(value="weather" in active_list)
        self.var_scr_hw = tk.BooleanVar(value="hardware" in active_list)
        self.var_scr_greeting = tk.BooleanVar(value="greeting" in active_list)
        self.var_scr_brand = tk.BooleanVar(value="brand" in active_list)

        ttk.Checkbutton(
            f_rot,
            text="1. Logo + Hora Digital y Fecha",
            variable=self.var_scr_logo,
            command=self._on_live_setting_change,
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            f_rot,
            text="2. Pronóstico del Tiempo (Ciudad / País)",
            variable=self.var_scr_weather,
            command=self._on_live_setting_change,
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            f_rot,
            text="3. Recursos del Equipo (CPU, RAM, GPU, Temperatura)",
            variable=self.var_scr_hw,
            command=self._on_live_setting_change,
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            f_rot,
            text="4. Saludo Horario (Buen día / tardes / noches Alan)",
            variable=self.var_scr_greeting,
            command=self._on_live_setting_change,
        ).pack(anchor="w", pady=2)
        ttk.Checkbutton(
            f_rot,
            text="5. Branding 'Alan Canto Tech' // Arc Reactor AC",
            variable=self.var_scr_brand,
            command=self._on_live_setting_change,
        ).pack(anchor="w", pady=2)

        # Modo pantalla fija
        r_single = tk.Frame(f_rot, bg="#0d1728")
        r_single.pack(fill="x", pady=6)
        self.var_single_mode = tk.BooleanVar(value=self.config.get("single_screen_mode", False))
        ttk.Checkbutton(
            r_single,
            text="Fijar solo una pantalla:",
            variable=self.var_single_mode,
            command=self._on_live_setting_change,
        ).pack(side="left")
        self.var_single_screen = tk.StringVar(value=self.config.get("selected_single_screen", "logo_time"))
        cb_single = ttk.Combobox(
            r_single,
            textvariable=self.var_single_screen,
            values=["logo_time", "weather", "hardware", "greeting", "brand"],
            state="readonly",
            width=14,
        )
        cb_single.pack(side="left", padx=8)
        cb_single.bind("<<ComboboxSelected>>", self._on_live_setting_change)

        # --- SECCIÓN C: PRONÓSTICO DEL TIEMPO ---
        f_weather = tk.LabelFrame(
            scrollable_frame,
            text=" [3] CONFIGURACIÓN DE CLIMA ",
            bg="#0d1728",
            fg="#00f0ff",
            font=("Bahnschrift", 10, "bold"),
            padx=12,
            pady=10,
        )
        f_weather.pack(fill="x", pady=6)

        rw1 = tk.Frame(f_weather, bg="#0d1728")
        rw1.pack(fill="x", pady=2)
        tk.Label(rw1, text="Ciudad:", bg="#0d1728", fg="#c0d8f0", width=10, anchor="w").pack(side="left")
        self.entry_city = tk.Entry(rw1, bg="#080e1a", fg="#ffffff", insertbackground="#00f0ff", bd=1, width=20)
        self.entry_city.insert(0, self.config.get("weather_city", "Santiago"))
        self.entry_city.pack(side="left", padx=5)

        tk.Label(rw1, text="País:", bg="#0d1728", fg="#c0d8f0", width=8, anchor="w").pack(
            side="left", padx=(10, 0)
        )
        self.entry_country = tk.Entry(
            rw1, bg="#080e1a", fg="#ffffff", insertbackground="#00f0ff", bd=1, width=16
        )
        self.entry_country.insert(0, self.config.get("weather_country", "Chile"))
        self.entry_country.pack(side="left", padx=5)

        rw2 = tk.Frame(f_weather, bg="#0d1728")
        rw2.pack(fill="x", pady=6)
        btn_test_weather = tk.Button(
            rw2,
            text="⚡ Probar / Actualizar Clima",
            bg="#14263f",
            fg="#00f0ff",
            bd=1,
            relief="flat",
            command=self._test_weather,
        )
        btn_test_weather.pack(side="left")
        self.lbl_weather_result = tk.Label(
            rw2, text="Listo para consultar", bg="#0d1728", fg="#78a0b8", font=("Segoe UI", 9)
        )
        self.lbl_weather_result.pack(side="left", padx=10)

        # --- SECCIÓN D: NOMBRES DE COMPONENTES DE HARDWARE ---
        f_comp = tk.LabelFrame(
            scrollable_frame,
            text=" [4] PERSONALIZACIÓN DE HARDWARE Y USUARIO ",
            bg="#0d1728",
            fg="#00f0ff",
            font=("Bahnschrift", 10, "bold"),
            padx=12,
            pady=10,
        )
        f_comp.pack(fill="x", pady=6)

        def make_row(parent, label_text, default_val):
            r = tk.Frame(parent, bg="#0d1728")
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label_text, bg="#0d1728", fg="#c0d8f0", width=18, anchor="w").pack(side="left")
            entry = tk.Entry(r, bg="#080e1a", fg="#ffffff", insertbackground="#00f0ff", bd=1)
            entry.insert(0, default_val)
            entry.pack(side="left", fill="x", expand=True, padx=5)
            return entry

        self.entry_cpu = make_row(
            f_comp, "Nombre Procesador (CPU):", self.config.get("cpu_name", "AMD Ryzen 7 5700G")
        )
        self.entry_gpu = make_row(
            f_comp, "Tarjeta Gráfica (GPU):", self.config.get("gpu_name", "NVIDIA GeForce RTX 3070")
        )
        self.entry_ram = make_row(f_comp, "Memoria RAM:", self.config.get("ram_name", "32 GB DDR4"))
        self.entry_user = make_row(f_comp, "Nombre de Usuario:", self.config.get("user_name", "Alan"))

    def _build_preview_panel(self, parent: tk.Frame):
        # Panel lateral derecho con visor de la pantalla Turing y botones de acción
        p_frame = tk.LabelFrame(
            parent,
            text=" [ MONITOR EN VIVO DE LA PANTALLA ] ",
            bg="#0d1728",
            fg="#00f0ff",
            font=("Bahnschrift", 10, "bold"),
            padx=10,
            pady=10,
        )
        p_frame.pack(fill="both", expand=True)

        # Indicador de estado de transmisión
        self.lbl_live_badge = tk.Label(
            p_frame,
            text="● INICIANDO TRANSMISIÓN...",
            bg="#092828",
            fg="#00ffaa",
            font=("Bahnschrift", 11, "bold"),
            pady=4,
        )
        self.lbl_live_badge.pack(fill="x", pady=(0, 8))

        # Visor de pantalla (Preview Canvas/Label)
        self.preview_container = tk.Frame(p_frame, bg="#040810", bd=2, relief="solid")
        self.preview_container.pack(fill="both", expand=True, pady=5)

        self.lbl_preview = tk.Label(
            self.preview_container,
            bg="#040810",
            fg="#588da8",
            text="Cargando transmisión J.A.R.V.I.S. HUD...",
        )
        self.lbl_preview.pack(fill="both", expand=True)

        self.lbl_current_screen = tk.Label(
            p_frame, text="Pantalla: [INICIANDO]", bg="#0d1728", fg="#00f0ff", font=("Segoe UI", 9, "bold")
        )
        self.lbl_current_screen.pack(pady=4)

        # Botones principales de acción
        btn_box = tk.Frame(p_frame, bg="#0d1728")
        btn_box.pack(fill="x", pady=6)

        self.btn_start = tk.Button(
            btn_box,
            text="▶ INICIAR TRANSMISIÓN",
            bg="#00f0ff",
            fg="#040d1a",
            font=("Bahnschrift", 11, "bold"),
            activebackground="#80f7ff",
            bd=0,
            padx=15,
            pady=7,
            cursor="hand2",
            command=lambda: self._start_transmission(auto_start=False),
        )
        self.btn_start.pack(fill="x", pady=2)

        self.btn_stop = tk.Button(
            btn_box,
            text="⏹ DETENER TRANSMISIÓN",
            bg="#351a22",
            fg="#ff6666",
            font=("Bahnschrift", 10, "bold"),
            bd=0,
            padx=15,
            pady=6,
            state="disabled",
            cursor="hand2",
            command=self._stop_transmission,
        )
        self.btn_stop.pack(fill="x", pady=2)

        btn_save = tk.Button(
            btn_box,
            text="💾 Guardar y Aplicar Configuración",
            bg="#14263f",
            fg="#c0d8f0",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            pady=6,
            cursor="hand2",
            command=self._save_settings_action,
        )
        btn_save.pack(fill="x", pady=(4, 2))

        btn_exit = tk.Button(
            btn_box,
            text="✖ Salir Completamente del Programa",
            bg="#1a1218",
            fg="#ff8888",
            font=("Segoe UI", 8),
            bd=0,
            pady=4,
            cursor="hand2",
            command=self._exit_application,
        )
        btn_exit.pack(fill="x", pady=(2, 0))

    # =========================================================================
    # ACCIONES Y EVENTOS
    # =========================================================================

    def _refresh_ports(self):
        ports = []
        detected_device = None
        for p in comports():
            desc = f"{p.device} ({p.description})"
            ports.append(desc)
            if p.serial_number and "USB35INCHIPS" in p.serial_number:
                detected_device = desc
            elif getattr(p, "vid", None) == 0x1A86 and getattr(p, "pid", None) == 0x5722:
                detected_device = desc

        options = ["auto (Auto-detectar Turing Smart Screen)"] + ports
        self.cb_ports["values"] = options

        saved_port = self.config.get("port", "auto")
        matching = [opt for opt in options if opt.startswith(saved_port)]
        if matching:
            self.cb_ports.set(matching[0])
        elif detected_device:
            self.cb_ports.set(detected_device)
        else:
            self.cb_ports.set(options[0])

    def _on_brightness_change(self, val):
        try:
            b = int(float(val))
            self.lbl_bright_val.config(text=f"{b}%")
            if self.controller and self.controller.is_running:
                self.config["brightness"] = b
                self.controller.update_config(self.config)
        except Exception:
            pass

    def _on_live_setting_change(self, *args):
        if self.controller and self.controller.is_running:
            cfg = self._collect_current_config()
            self.config.update(cfg)
            self.controller.update_config(self.config)

    def _collect_current_config(self) -> Dict[str, Any]:
        port_raw = self.cb_ports.get()
        if "auto" in port_raw or not port_raw:
            port = "auto"
        else:
            port = port_raw.split(" ")[0]

        active_screens = []
        if self.var_scr_logo.get():
            active_screens.append("logo_time")
        if self.var_scr_weather.get():
            active_screens.append("weather")
        if self.var_scr_hw.get():
            active_screens.append("hardware")
        if self.var_scr_greeting.get():
            active_screens.append("greeting")
        if self.var_scr_brand.get():
            active_screens.append("brand")

        if not active_screens:
            active_screens = ["logo_time"]

        cfg = {
            "port": port,
            "orientation": self.var_orientation.get(),
            "brightness": self.var_brightness.get(),
            "rotation_interval": self.var_rot_interval.get(),
            "fps": float(self.config.get("fps", 6.0)),
            "active_screens": active_screens,
            "single_screen_mode": self.var_single_mode.get(),
            "selected_single_screen": self.var_single_screen.get(),
            "weather_city": self.entry_city.get().strip(),
            "weather_country": self.entry_country.get().strip(),
            "cpu_name": self.entry_cpu.get().strip(),
            "gpu_name": self.entry_gpu.get().strip(),
            "ram_name": self.entry_ram.get().strip(),
            "user_name": self.entry_user.get().strip(),
        }
        return cfg

    def _save_settings_action(self):
        cfg = self._collect_current_config()
        self.config.update(cfg)
        if self.controller and self.controller.is_running:
            self.controller.update_config(self.config)
        if save_config(self.config):
            self.lbl_status.config(
                text="Configuración guardada y aplicada correctamente en config.json.", fg="#00ffaa"
            )
        else:
            messagebox.showerror("Error", "No se pudo guardar la configuración.")

    def _test_weather(self):
        city = self.entry_city.get().strip()
        country = self.entry_country.get().strip()
        self.lbl_weather_result.config(text="Consultando satélites...", fg="#00f0ff")

        def task():
            res = self.weather_service.get_weather(city, country, force_refresh=True)
            t = res.get("temp", 0.0)
            c = res.get("condition", "")
            resolved_city = res.get("city", city)
            self.root.after(
                0,
                lambda: self.lbl_weather_result.config(
                    text=f"{resolved_city}: {t:.1f}°C, {c}",
                    fg="#00ffaa" if res.get("is_live") else "#ffaa00",
                ),
            )

        threading.Thread(target=task, daemon=True).start()

    def _start_transmission(self, auto_start: bool = False):
        cfg = self._collect_current_config()
        self.config.update(cfg)
        if not auto_start:
            save_config(self.config)

        if self.controller and self.controller.is_running:
            self.controller.update_config(self.config)
            return

        self.btn_start.config(state="disabled")
        self.lbl_status.config(text="Iniciando transmisión J.A.R.V.I.S. con configuración guardada...", fg="#00f0ff")

        def preview_cb(img: Image.Image):
            self._last_preview_pil = img

        self.controller = DisplayController(config=self.config, preview_callback=preview_cb)
        ok, msg = self.controller.start(allow_virtual_fallback=True)

        if ok:
            self._update_ui_state(is_running=True)
            self.lbl_status.config(text=f"¡Transmisión activa! {msg}", fg="#00ffaa")
        else:
            self._update_ui_state(is_running=False)
            self.lbl_status.config(text=f"Fallo al iniciar: {msg}", fg="#ff6666")
            if not auto_start:
                messagebox.showerror(
                    "Error de Conexión",
                    f"{msg}\n\nVerifica que el cable USB esté conectado y el puerto COM no esté en uso.",
                )

    def _stop_transmission(self):
        if self.controller:
            self.controller.stop()
            self.controller = None
        self._update_ui_state(is_running=False)
        self.lbl_status.config(text="Transmisión detenida por el usuario.", fg="#6090a8")

    def _update_ui_state(self, is_running: bool = False):
        if is_running:
            self.btn_start.config(state="disabled", bg="#14263f", fg="#507088")
            self.btn_stop.config(state="normal", bg="#b32438", fg="#ffffff")
            self.lbl_live_badge.config(
                text="● TRANSMITIENDO EN VIVO (ACTIVO)", bg="#092828", fg="#00ffaa"
            )
        else:
            self.btn_start.config(state="normal", bg="#00f0ff", fg="#040d1a")
            self.btn_stop.config(state="disabled", bg="#351a22", fg="#ff6666")
            self.lbl_live_badge.config(text="● PANTALLA DETENIDA", bg="#2a1015", fg="#ff5555")

    def _gui_tick(self):
        # Actualizar preview en vivo
        if self._last_preview_pil is not None:
            try:
                img = self._last_preview_pil
                pw = max(240, self.preview_container.winfo_width() - 10)
                ph = max(180, self.preview_container.winfo_height() - 10)
                scale = min(pw / img.width, ph / img.height)
                nw = max(10, int(img.width * scale))
                nh = max(10, int(img.height * scale))

                resized = img.resize((nw, nh), Image.Resampling.BILINEAR)
                self._preview_image_tk = ImageTk.PhotoImage(resized)
                self.lbl_preview.config(image=self._preview_image_tk, text="")
            except Exception:
                pass

        if self.controller and self.controller.is_running:
            scr_name = self.controller.current_screen_name.upper().replace("_", " ")
            hw_state = "USB CONECTADO" if self.controller.is_hardware_connected else "AUTO-DETECT USB"
            self.lbl_current_screen.config(text=f"Pantalla: [{scr_name}]  //  {hw_state}")
        else:
            self.lbl_current_screen.config(text="Pantalla: [EN ESPERA]")

        self.root.after(120, self._gui_tick)

    def _on_close_to_taskbar(self):
        """
        Al pulsar el botón [X] de la ventana, el programa NO se cierra ni detiene la transmisión:
        se minimiza y permanece abierto en la barra de tareas de Windows.
        """
        self.root.iconify()
        self.lbl_status.config(
            text="Programa minimizado en la barra de tareas. La transmisión sigue activa.",
            fg="#00ffaa",
        )

    def _exit_application(self):
        """Cierra completamente el programa cuando el usuario pulsa 'Salir Completamente'."""
        if self.controller:
            self.controller.stop()
        self.root.destroy()

    def _take_auto_screenshot(self, target_path: str):
        try:
            self.root.update_idletasks()
            self.root.lift()
            self.root.focus_force()
            time.sleep(0.2)
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            # Incluir barra de título aproximada de Windows
            bbox = (max(0, x - 8), max(0, y - 32), x + w + 8, y + h + 8)
            shot = ImageGrab.grab(bbox=bbox)
            os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
            shot.save(target_path)
            print(f"[+] Captura guardada en {target_path}")
        except Exception as e:
            print(f"[!] Error al tomar captura automática: {e}")
        finally:
            self._exit_application()


def main():
    root = tk.Tk()
    app = JarvisControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

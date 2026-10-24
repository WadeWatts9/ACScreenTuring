import os
import shutil
import subprocess
import sys


def build():
    print("[*] Iniciando proceso de compilación a un único ejecutable Windows (.exe --onefile)...")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    # 1. Asegurar icono app_icon.ico
    icon_path = os.path.join(base_dir, "app_icon.ico")
    if not os.path.exists(icon_path):
        from PIL import Image

        logo_path = os.path.join(base_dir, "Logo.png")
        if os.path.exists(logo_path):
            img = Image.open(logo_path)
            img.resize((128, 128)).save(
                icon_path,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128)],
            )
            print("[+] Icono app_icon.ico generado.")

    # 2. Configuración PyInstaller en un único archivo (--onefile)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=JarvisScreenController",
        f"--icon={icon_path}",
        "--add-data=Logo.png;.",
        "--add-data=app_icon.ico;.",
        "--collect-all=PIL",
        "--hidden-import=pyserial",
        "--hidden-import=serial",
        "--hidden-import=psutil",
        "--hidden-import=numpy",
        "--hidden-import=tkinter",
        os.path.join(base_dir, "main.py"),
    ]

    print("[*] Ejecutando PyInstaller (--onefile):")
    print(" ".join(cmd))
    res = subprocess.run(cmd)

    if res.returncode != 0:
        print("[!] Error durante la compilación con PyInstaller.")
        sys.exit(1)

    dist_dir = os.path.join(base_dir, "dist")
    exe_file = os.path.join(dist_dir, "JarvisScreenController.exe")

    if os.path.exists(exe_file):
        # Copiar config.json junto al .exe en dist/
        cfg_src = os.path.join(base_dir, "config.json")
        if os.path.exists(cfg_src):
            shutil.copy(cfg_src, os.path.join(dist_dir, "config.json"))
            print("[+] Copiado config.json en dist/")

        size_mb = os.path.getsize(exe_file) / (1024 * 1024)
        print("\n========================================================")
        print(" ¡COMPILACIÓN EN UN SOLO ARCHIVO COMPLETADA EXITOSAMENTE! ")
        print(f" Ejecutable único: {exe_file} ({size_mb:.2f} MB)")
        print("========================================================")
    else:
        print("[!] No se encontró el ejecutable esperado en dist/.")
        sys.exit(1)


if __name__ == "__main__":
    build()

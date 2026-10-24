@echo off
title Instalador JARVIS Screen Controller - Alan Canto Tech
echo ========================================================
echo   J.A.R.V.I.S. SMART SCREEN CONTROLLER - ALAN CANTO TECH
echo ========================================================
echo.
echo Creando acceso directo en tu Escritorio...
set TARGET_DIR=%~dp0dist\
set EXE_PATH=%TARGET_DIR%JarvisScreenController.exe

if not exist "%EXE_PATH%" (
    echo [!] No se encontro el archivo %EXE_PATH%
    echo Ejecutando compilacion en un solo archivo primero...
    python build_exe.py
)

powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop') + '\JARVIS Screen Controller.lnk');$s.TargetPath='%EXE_PATH%';$s.WorkingDirectory='%TARGET_DIR%';$s.IconLocation='%EXE_PATH%,0';$s.Save()"

echo.
echo ========================================================
echo   [EXITO] Acceso directo instalado en tu Escritorio!
echo   Ya puedes abrir "JARVIS Screen Controller" desde tu Escritorio.
echo ========================================================
echo.
pause

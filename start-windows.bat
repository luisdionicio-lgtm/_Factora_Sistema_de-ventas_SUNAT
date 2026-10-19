@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Instala Python 3.12 o superior desde python.org y vuelve a ejecutar este archivo.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo No se pudieron instalar las dependencias. Revisa tu conexion.
  pause
  exit /b 1
)
echo Abre http://localhost:8000 en tu navegador. Para detener: Ctrl+C.
.venv\Scripts\python.exe run.py
pause

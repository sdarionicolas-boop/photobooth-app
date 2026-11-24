# Espejo mágico: instalación y uso

## Instalar en la OptiPlex (o cualquier PC con Windows 10/11)

1. Conectá la webcam y la PC a internet (solo para instalar).
2. Abrí **PowerShell** y ejecutá:

```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://raw.githubusercontent.com/sdarionicolas-boop/photobooth-app/feature/magic-mirror/kiosk/install-optiplex.ps1 -OutFile $env:TEMP\install-optiplex.ps1; & $env:TEMP\install-optiplex.ps1"
```

El instalador pregunta el título del evento y la contraseña de admin, instala `git` y `uv` si faltan,
descarga el programa en `C:\photobooth`, lo configura (webcam, QR, título, tira) y lo deja para que
arranque solo al iniciar sesión. Se puede volver a ejecutar para actualizar.

3. A mano en esa PC (una sola vez):
   - Girar la pantalla a vertical: Configuración → Sistema → Pantalla → Orientación.
   - Inicio de sesión automático (`netplwiz`), para que arranque solo tras un corte de luz.

## Uso diario

- Abrir: `C:\photobooth\photobooth-app\kiosk\start-kiosk.ps1` (o reiniciar la PC, arranca solo).
- Salir del kiosco: **Alt+F4**.
- **Cambiar el título del evento:** botón **Admin** (arriba a la derecha) → Configuración → Uisettings →
  *Frontpage Title*. La fecha de hoy se agrega sola.
- **Fondos:** copiá imágenes (JPG/PNG/WebP) a `userdata\backgrounds\` (Admin → Archivos). El invitado las elige antes de la foto.
- **Mensaje de la tira de 2 fotos:**

```powershell
cd C:\photobooth\photobooth-app
uv run python kiosk/presets/apply_mirror_config.py --title "MIS XV LUCIA♥" --strip-message "Mis XV Lucía" --strip-background "#FFF5E6" --strip-text-color "#7a1f3d"
```

(apagá el programa antes: `Alt+F4` y cerrá la ventana de `uv`/Python desde el Administrador de tareas).

## QR en el salón

El QR apunta a la IP de la PC en la red. La PC y los celulares de los invitados tienen que estar en el **mismo Wi-Fi/router**.
En cada arranque `start-kiosk.ps1` actualiza el QR con la IP actual. Si cambiás de red con el programa ya abierto,
cerralo y volvé a abrirlo.

## Si algo falla

- Registro del kiosco: `log\kiosk.log`. Registro del programa: `log\`.
- Webcam no detectada: probá otro puerto USB; el nombre exacto se pasa con `--camera "Nombre"`.
- Se ve la pantalla de Edge en vez del kiosco: cerrá Edge y ejecutá `start-kiosk.ps1`.

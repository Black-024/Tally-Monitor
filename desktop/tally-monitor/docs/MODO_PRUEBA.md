# Modo prueba y modo normal

## Modo normal
- Con Python: `py -m tally_monitor`
- Con el `.exe`: ejecutá `scripts\crear_release.bat` (una vez); el resultado queda en la carpeta `release`. Para compartir, usá el zip portable o el instalador.
- Sin consola, sin informes. Windows puede mostrar un aviso de SmartScreen porque el .exe no está firmado.

## Modo prueba
- Atajo: doble clic en `scripts\modo_prueba.bat` (usa el .exe de `release` si existe, si no Python).
- O a mano: `py -m tally_monitor --test`  /  `TallyMonitor.exe --test`
- La ventana dice "MODO PRUEBA". Al cerrarla se guarda `%LOCALAPPDATA%\TallyMonitor\informes-prueba\informe-AAAAMMDD-HHMMSS-xxxx.json`
  (se conservan los últimos 20) y se muestra su ruta. Si el programa se cae o Windows lo cierra, queda el informe parcial
  que se fue guardando durante la sesión (`"completo": false`, con las llamadas que estaban en curso).

### Qué trae el informe
`entorno` (versiones) · `salida` (cómo terminó) · `resumen` (llamadas por servicio con ok/error y tiempos, errores con categoría,
HTTP y traza, solicitudes a Tally por código) · `cobertura` (qué puntos de prueba se ejercitaron y cuáles NO) ·
`estado_final` (versión de bases, integridad, conteos, copias de seguridad, ajustes) · `eventos` (línea de tiempo:
pantallas, llamadas, solicitudes, mensajes de log, excepciones, avisos de Qt) · `autorevision`.

### Qué NO trae (garantizado por el código y por pruebas)
API Key, textos de respuestas, nombres de cuentas o encuestas (cuentas = «Cuenta 1», «Cuenta 2»…), identificadores de
encuestados, contenido de las respuestas de Tally, ni el usuario de Windows en las rutas. Al cerrar, el informe se revisa a sí
mismo (`autorevision`). Aun así, mirá el archivo antes de enviármelo si querés.

## Autodiagnóstico del .exe
`TallyMonitor.exe --self-check` escribe `%TEMP%\tally-monitor-autodiagnostico.txt` (PySide6, migraciones incluidas,
DPAPI, bases en carpeta temporal). `crear_release.bat` lo ejecuta solo.

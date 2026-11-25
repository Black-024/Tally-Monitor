# Tally Monitor

Aplicación de escritorio para **Windows**, **Linux** y **macOS** que descarga, guarda en tu equipo, analiza y exporta las respuestas de tus encuestas de [Tally](https://tally.so). Hecha con Python y PySide6.

- **Solo lectura:** únicamente hace consultas `GET` a la API de Tally. Nunca modifica ni borra nada allá.
- **Privada:** sin servidores propios ni cuentas. Tus datos viven en `%LOCALAPPDATA%\TallyMonitor` (Windows) `~/.local/share/TallyMonitor` (Linux) o `~/Library/Application Support/TallyMonitor` (macOS). La API Key se guarda cifrada con Windows DPAPI o en el llavero del sistema (Linux y macOS), aparte de las bases y de las copias de seguridad, y nunca se muestra ni se registra. Ver [PRIVACIDAD.md](PRIVACIDAD.md).
- **Varias cuentas** (una API Key por cuenta), sincronización incremental y copias de seguridad.
- **Análisis:** resumen por pregunta, línea de tiempo y filtros de período.
- **Exportaciones:** Excel, PDF e imagen PNG; resumen o respuestas individuales; estilo oscuro o claro; ocultado de datos personales.
- Tema oscuro y claro.

## Descarga
En la sección *Releases* de este repositorio: instalador (`TallyMonitor-Setup-x.y.z.exe`) o versión portable (`.zip`, descomprimir y abrir `TallyMonitor.exe`). **Linux (x86_64):** `.tar.gz` o `.AppImage`; ver [docs/LINUX.md](docs/LINUX.md). **macOS (Apple Silicon e Intel):** `.dmg`; ver [docs/MACOS.md](docs/MACOS.md). Los archivos no están firmados digitalmente, por lo que Windows puede mostrar un aviso de SmartScreen: verificá la integridad con `SHA256SUMS.txt`.

> En Linux se necesita un llavero activo (GNOME Keyring o KWallet); en Linux Mint y Ubuntu ya viene. Detalles en [docs/LINUX.md](docs/LINUX.md).

## Cómo obtener tu API Key de Tally
Creala en tu cuenta de Tally (sección de claves de API, dentro de *Settings*) y pegala en la app al agregar una cuenta: se pide una sola vez. Nunca la compartas ni la pegues en un chat o un informe.

## Ejecutar desde el código
Requiere Python 3.12 o superior para Windows.
```powershell
py -m pip install -r requirements.txt
$env:PYTHONPATH = "src"
py -m tally_monitor
```
Modo prueba (genera un informe de la sesión **sin** API Key, textos de respuestas ni nombres): `py -m tally_monitor --test`. Ver [docs/MODO_PRUEBA.md](docs/MODO_PRUEBA.md).

## Pruebas
```powershell
py -m pip install -r requirements.txt -r requirements-dev.txt
py -m pytest -q
py tools\auditoria_seguridad.py        # revisión de seguridad del código
```

## Crear el .exe, el instalador y la versión portable
```powershell
py -m pip install -r requirements.txt -r requirements-build.txt
py -m PyInstaller --noconfirm --clean packaging\TallyMonitor.spec     # resultado en dist\TallyMonitor
```
El instalador se compila con [Inno Setup 6](https://jrsoftware.org/isinfo.php) a partir de `packaging\TallyMonitor.iss`.
Para fijar dependencias con hashes: `pip-compile --generate-hashes`.

## Estructura
```
src/tally_monitor/
  core/       errores, SecretStr, redacción de claves, rutas, logging seguro, paletas de color
  security/   DPAPI (Windows), llavero del sistema (Linux/macOS) y almacén de credenciales
  api/        cliente GET-only de Tally y consulta pública de versiones (sin clave)
  storage/    SQLite, migraciones, copias de seguridad
  sync/       normalización, numeración local y sincronización
  analysis/   estadísticas puras
  export/     escritores de Excel y PDF, enmascarado de datos personales
  services/   casos de uso: la interfaz solo habla con esta capa
  ui/         interfaz PySide6
tests/        unit · integration · architecture · security · ui
tools/        auditoría de seguridad
packaging/    PyInstaller e instalador
docs/         API de Tally, estadísticas, modo prueba
```
Las capas están protegidas por una prueba de arquitectura (`ui → services → storage/security/api`).

## Licencia
[MIT](LICENSE). Componentes de terceros: [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

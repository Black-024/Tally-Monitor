# Tally Monitor

**Español** · [English below](#english)

Aplicación **no oficial** para ver, analizar y exportar tus encuestas de [Tally](https://tally.so) desde tu computadora o tu teléfono. Es de **solo lectura**: nunca modifica nada en Tally. No usa servidores propios: la app habla directamente con la API de Tally, con tu API Key.

> Tally Monitor es un proyecto independiente. No está afiliado, respaldado ni patrocinado por Tally.

## Qué hace
- Varias cuentas de Tally, con la API Key cifrada en el almacén seguro de tu sistema (DPAPI en Windows, Keystore en Android). La clave no se muestra, no se registra y no se escribe en ningún archivo.
- Sincronización incremental, estadísticas, filtros de tiempo, respuestas individuales anónimas («Usuario 001…») y exportación a Excel, PDF, CSV y PNG.
- Metas por encuesta, ritmo y tendencias, notas y etiquetas, cruce de preguntas, avisos de respuestas nuevas y widgets (Android).
- Copias de seguridad que **no** incluyen tus credenciales.
- Español e Inglés.

## Descargas
Mirá la sección **[Releases](../../releases)**:
- **Windows 10/11:** instalador o versión portable (`.zip`).
- **Android 10 o superior:** archivo `.apk` (instalación directa; hay que permitir instalar apps de fuentes desconocidas).

Los archivos no están firmados digitalmente por una entidad certificadora: Windows (SmartScreen) puede mostrar un aviso la primera vez. Cada versión incluye un archivo `SHA256SUMS` para verificar la descarga.

## Privacidad
- Solo se hacen pedidos `GET` a la API de Tally. Ninguna otra conexión de red, ninguna estadística de uso.
- Tus datos quedan en tu equipo o teléfono. Los identificadores de personas (`respondentId`, `sessionUuid`) y los enlaces de vista previa/PDF no se guardan.
- Detalle completo: [`desktop/tally-monitor/PRIVACIDAD.md`](desktop/tally-monitor/PRIVACIDAD.md).

## Estructura
| Carpeta | Contenido |
|---|---|
| `desktop/` | Versión de escritorio (Python / PySide6). Windows verificado; Linux y macOS en preparación. |
| `android/` | Versión Android (Kotlin / Jetpack Compose). |

## Compilar desde el código
- **Escritorio:** ver `desktop/tally-monitor/README.md` y `desktop/scripts/`.
- **Android:** abrir `android/` en Android Studio, o `./gradlew :app:assembleRelease`. La firma de release se hace aparte; no hay contraseñas ni llaves en el repositorio.

## Licencia
MIT. Ver [`LICENSE`](LICENSE). Autor: Valentín Mangano.

---

## English

**Unofficial** app to view, analyze and export your [Tally](https://tally.so) surveys from your computer or phone. It is **read-only** — it never changes anything in Tally — and has no servers of its own: it talks straight to Tally's API with your API Key.

> Tally Monitor is an independent project. It is not affiliated with, endorsed by, or sponsored by Tally.

- Multiple accounts; the API Key is encrypted in the system's secure store (DPAPI on Windows, Keystore on Android) and never displayed, logged or written to a file.
- Incremental sync, statistics, time filters, anonymous individual responses, export to Excel / PDF / CSV / PNG.
- Goals, pace and trends, notes and tags, question cross-tabs, new-response alerts and widgets (Android). English and Spanish UI.
- Only `GET` requests to Tally's API; no analytics; backups exclude credentials.
- Downloads: see **[Releases](../../releases)** (Windows 10/11 installer or portable zip; Android 10+ `.apk`). Binaries are not code-signed; verify them with the `SHA256SUMS` file.

License: MIT. Author: Valentín Mangano.

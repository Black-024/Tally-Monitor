# Tally Monitor para Android

Versión Android de Tally Monitor: ver, analizar y exportar tus encuestas de Tally. **Solo lectura**, sin servidores propios, instalación directa por APK. **Requisito: Android 10 o superior.** En Android 8 y 9 la app puede instalarse, pero no está soportada y algunas funciones pueden fallar.

- Idioma: Español e Inglés, se elige en Ajustes (por defecto el del teléfono).
- 7 widgets: Resumen, Semáforo, Meta (elegís la encuesta al agregarlo y podés crear la meta ahí mismo), Ranking, Novedades, Acceso directo y Lista de encuestas. Se quitó el widget Saludo.
- Misma lógica que la versión de Windows (verificada contra vectores generados por la referencia Python: `golden/`).
- La API Key se cifra con el almacén seguro de Android (Keystore, AES-256-GCM) y no se muestra, ni se registra, ni se copia a ningún archivo.
- Permiso de Internet y, solo si activás los avisos, el de notificaciones (`POST_NOTIFICATIONS`). `allowBackup=false`. HTTPS únicamente. Sin redirecciones.

## Estructura
| Módulo | Tipo | Qué contiene |
|---|---|---|
| `core` | Kotlin puro | `Secret`, errores, reloj, JSON, modelos, registro con redacción |
| `credentials` | Kotlin puro | `CredentialStore` (archivo cifrado) |
| `security` | Android | `KeystoreProtector` (único uso de criptografía) |
| `api` | Kotlin puro | `TallyClient` (único módulo con red, solo GET) |
| `storage` | Android | SQLite (mismo esquema que Windows), migraciones, copias de seguridad |
| `sync` | Kotlin puro | sanitizador, normalizador, numeración, `SyncEngine` |
| `analysis` | Kotlin puro | estadísticas, filtros de tiempo, control de coherencia, metas, ritmo, cruce de preguntas, lógica de avisos (con pruebas JUnit: `./gradlew :analysis:test :services:testDebugUnitTest`) |
| `export` | Kotlin puro | enmascarado, Excel y PDF propios (sin librerías) |
| `services` | Android | fachada para la UI (`docs/CONTRATO_BACKEND.md`) |
| `testing` | Android | backend de ejemplo para la UI |
| `verify` | Kotlin puro | comprobaciones contra Python, servidor Tally falso, arquitectura |
| `app` | Android | interfaz Jetpack Compose |

## Compilar
Ver `Pruebas.txt` (sección Android) para el paso a paso completo. Resumen: abrir la carpeta en Android Studio, esperar la sincronización de Gradle, `Build > Build APK`, o `./gradlew :verify:run` para las comprobaciones sin teléfono.

## Licencia
MIT (ver `LICENSE`). Dependencias: ver `THIRD_PARTY_LICENSES.md`.

# Contrato del backend (módulo `:services`)

La interfaz (módulo `:app`) solo habla con `TallyMonitorBackend` (ver `services/.../Contract.kt`, con KDoc de cada método).

## Convenciones
- Todo `suspend` es seguro de llamar desde el hilo principal (trabaja en `Dispatchers.IO`).
- Errores: siempre `TallyMonitorException` con un `code` tipado (`ErrorCode`); los de red de Tally son `ApiException` (con `status` y `retryAfterSeconds`). La UI los traduce con `errorText()`. Ningún mensaje contiene la clave, la URL ni el cuerpo de la respuesta.
- La clave entra como `Secret` (su `toString()` es «***») y **nunca sale**: no existe `getKey()`.
- Operaciones largas (`sync.*`) son `Flow<SyncEvent>`; cancelar la corrutina detiene la sincronización en la siguiente página.
- Paginación por `offset/limit` (no Paging).
- Fechas: ISO-8601 UTC con milisegundos; la UI las muestra en hora local.

## Servicios
| Servicio | Qué hace |
|---|---|
| `accounts` | alta (valida con `GET /users/me` antes de guardar), cambio de clave (si falla se conserva la anterior), renombrar, baja (borra datos y credencial), verificar |
| `surveys` | listado observable con búsqueda (nombre, nota, etiquetas), favoritas, filtro por etiqueta y archivadas, detalle con preguntas, recientes; `setSurveyMeta` (meta, nota, etiquetas; atómico, reglas en `SurveyMetaRules`) y `setArchived` |
| `sync` | `syncForms`, `syncForm(full)`; eventos `Progress`, `FormsDone`, `FormDone` |
| `analysis` | `analyze(filtro, cruce?)` (incluye ritmo), `recentCounts` (últimos 7 días por encuesta), `crosscheck`, `responses(offset, limit)`, `findByLabel("Usuario 012")`, `response(n)` |
| `export` | `exportXlsx`, `exportPdf`, `savePng`, `individualCards` — escriben en el `OutputStream` que abre la UI con el selector de archivos (SAF), de forma atómica |
| `backups` | listar / crear / restaurar / eliminar copias (sin claves) |
| `settings` | `theme`, `auto_backup`, `sync_mode`, `log_level`, `update_check` (mismos valores por defecto que Windows), `notify_mode`, `notify_interval_min`, `notified_new_total` |
| `diagnostics` | solo conteos y estados; jamás claves, textos ni nombres |

## Para desarrollar la UI sin backend real
`:testing` trae `FakeTallyMonitorBackend` (datos inventados, sin red ni disco). La app de depuración lo incluye (`debugImplementation`).

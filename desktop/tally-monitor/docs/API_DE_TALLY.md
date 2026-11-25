# Tally Monitor — Comportamiento verificado de la API de Tally

Resultado de verificar la API contra datos reales (una encuesta de prueba: 27 envíos, 17 preguntas de 3 tipos). Sirve de referencia para quien mantenga el cliente y la sincronización.

Convención:
- **CONFIRMADO** = observado en una respuesta real de Tally.
- **INFERIDO** = deducción razonable; no observada directamente.
- **ABIERTO** = no se sabe; se indica el impacto y cómo se mitiga.

---

## 1. Incertidumbres RESUELTAS (confirmado con datos reales)

### Acceso y formato
| Tema | Resultado |
|---|---|
| Endpoints | `/users/me`, `/workspaces`, `/forms`, `/forms/{id}`, `/forms/{id}/questions`, `/forms/{id}/submissions` y los 5 de analítica responden 200 con una clave válida. |
| `User-Agent` | Obligatorio uno propio: el de `urllib` por defecto recibió **403**. Aplica también al `.exe` empaquetado. |
| Fechas | `startDate` y `endDate` son **inclusivos**; formato ISO 8601 UTC con milisegundos y `Z`. |
| Orden | La lista viene con los envíos **más nuevos primero**. |

### Respuestas y opciones
| Tema | Resultado |
|---|---|
| Forma por tipo | `MULTIPLE_CHOICE` y `CHECKBOXES` → lista de textos; `TEXTAREA` → texto. Sin `formattedAnswer` (0 de 263). |
| IDs vs textos | Las respuestas guardan el **texto** de la opción, **no** su ID. |
| Opciones por pregunta | Las opciones de cada pregunta se obtienen asociando `fields[].blockGroupUuid` de la pregunta con `groupUuid` de los bloques de opción. Funcionó en las **9 de 9** preguntas con opciones. |
| Coincidencia | **226 de 230** etiquetas elegidas están entre las opciones de **su propia pregunta**. Ninguna etiqueta pertenece solo a otra pregunta, aunque 25 bloques de opción comparten 15 textos distintos. |
| Opción "Otro" | Las **4 etiquetas restantes** aparecen todas en las 2 preguntas de casillas que declaran `hasOtherOption`. Es la explicación coherente: son texto libre de "Otro" (no vi sus textos). |
| Respuestas en blanco | Tally registra algunas respuestas vacías (2 de texto, 2 de opción múltiple `[]`). `numberOfResponses` **las cuenta**: coincide en 17 de 17 preguntas contando todas, y en solo 13 de 17 contando únicamente las no vacías. |
| Modificaciones | `submittedAt` = `createdAt` = `updatedAt` en 27 de 27 envíos: no se observó ninguna edición. |

### Paginación, filtros y sincronización
| Tema | Resultado |
|---|---|
| Paginación | 3 páginas de 10 = 27 envíos, sin duplicados, `hasMore` correcto. Una página más allá del final devuelve **200 con lista vacía**. |
| `limit` | Máximo **500**. `501` y `0` devuelven **400** con un error de validación claro. |
| Filtro `partial` | Devuelve 0 envíos (contra 27 sin filtro): el filtro **sí se aplica** a la lista. |
| `afterId` | Con paginación: 13 envíos en 2 páginas, sin duplicados y en orden descendente. Devuelve los **más nuevos** que el pivote, sin incluirlo. |
| Totales | `totalNumberOfSubmissionsPerFilter.all` = envíos recuperados = `numberOfSubmissions` del listado (27). El objeto trae siempre `all`, `completed` y `partial`. |
| Peticiones condicionales | Existe `ETag`, pero reenviarlo en `If-None-Match` da **200, no 304**. No hay `Last-Modified` ni `Cache-Control`. No sirve para ahorrar solicitudes. |

### Analítica de Tally (resuelto en la 0c)
- **Todos los endpoints exigen `period`**, y `startDate/endDate` no lo reemplazan. La documentación oficial no lista los valores; se obtuvieron del mensaje de validación de Tally:
  **`today, yesterday, 24h, 7d, 30d, 3m, 6m, 12m, all`**.
- Con una clave válida, los 5 endpoints respondieron **200** con `period=today`; `metrics` también con `yesterday`, `24h`, `7d`, `30d` y `3m`.

| Endpoint | Forma observada |
|---|---|
| `metrics` | `visits, visitDuration, submissions, uniqueRespondents, totalViews, starts, completions, completionDuration, completionRate` (números) |
| `visits` | `data`: serie por intervalo con `totalVisits`; `interval` |
| `submissions` | `data`: serie por intervalo con `completed` y `partial`; `interval` |
| `dimensions` | Mapas por `source`, `browser`, `os`, `device`, `country`, `city`, `language` con conteos |
| `drop-off` | `stats` (visitantes, inicios, completados, tasa, tiempos en segundos), `dataAvailableSince`, `hasConditionalLogic`, `shouldShowDataCutoffNotice` y `data[]` por pregunta: `views, startedViews, answers, answerRate, drops, dropRate, isRequired, title, type, blockGroupUuid` |

- **`uniqueRespondents`** viene en `metrics`: permite mostrar "participantes únicos" **sin guardar `respondentId`**, lo que mitiga la consecuencia de la decisión de privacidad.
- `drop-off` identifica cada pregunta por `blockGroupUuid`, el mismo valor que `fields[].blockGroupUuid`: se puede cruzar con nuestras preguntas.
- **Zona horaria:** `period=today` devolvió 24 intervalos horarios que empiezan a las 03:00 UTC, es decir, el día **en horario de Argentina (UTC−3)**. Coincide con la zona de tu cuenta. No pude comprobar si Tally toma la zona de la cuenta o de otra fuente.
- **La analítica solo admite esos 9 períodos fijos.** No admite rango personalizado. Los filtros de la app (24 h, 7 d, 30 d, todo, rango personalizado) se calculan localmente sobre `submittedAt`, y solo coinciden con los de Tally en 24 h, 7 d, 30 d y todo.

### Límites de uso
- `x-ratelimit-limit: 100`. El `reset` cayó 60,8 s y 61,2 s después del fin de las corridas 0b y 0c.
- En ambas corridas `x-ratelimit-remaining` bajó en **pasos contiguos de 1, sin huecos, solo por las respuestas 200**, aunque había respuestas 400 intercaladas. Es decir, los 400 no parecen consumir cuota (**inferido**, consistente en 2 corridas).
- 0 respuestas 429 en 72 solicitudes (38 + 34).

---

## 2. Incertidumbres ABIERTAS (ninguna impide usar el programa)

| # | Tema | Impacto | Mitigación en el diseño |
|---|---|---|---|
| 1 | Filtro por defecto de la lista (sin `filter`) | La cuenta no tiene envíos parciales: sin filtro, `all` y `completed` devolvieron lo mismo (27) | La app **siempre envía `filter=all` explícito** (probado) |
| 2 | Envíos **parciales** (forma y campos) | No hay ninguno en la cuenta de prueba | `is_completed` se guarda y se muestra; probar con una encuesta que tenga envíos parciales |
| 3 | Tipos de pregunta no vistos (matriz, ranking, escala, número, fecha, archivos, etc.) | Solo se vieron opción múltiple, casillas y texto largo | Caen en `kind = raw` (JSON legible); sin bloqueo |
| 4 | `afterId` con un pivote **borrado** | Un ID inexistente devuelve 200 con resultados, sin error (inferido: lo ignora) | La sincronización **no depende de `afterId`**: usa `startDate` + deduplicación + control de totales (ver §5) |
| 5 | `startDate` con **varias páginas** | Se probó con una página (14 envíos) | El diseño ya deduplica por ID |
| 6 | Edición de envíos | No se observó ninguna (solo 27 casos) | Reconciliación periódica completa |
| 7 | Unidades de `visitDuration`/`completionDuration` e `interval`; historial de analítica (`dataAvailableSince`) | Solo importa si se construye el módulo de analítica | Módulo opcional; mostrar el aviso `shouldShowDataCutoffNotice` |
| 8 | `period=6m`, `12m`, `all` y los demás períodos en `visits/submissions/dimensions/drop-off` | Tally los declara válidos pero solo probé `today` en esos 4 (y 6 períodos en `metrics`) | Igual que el anterior |
| 9 | Cabecera `tally-version` | No se envió; no se probó cómo cambia el comportamiento | Fijarla recién cuando se conozcan valores válidos |
| 10 | Respuesta en blanco vs pregunta no mostrada por lógica condicional | Tally no los distingue en las respuestas | Se muestran como "Sin respuesta". A futuro se podría calcular con la lógica condicional |
| 11 | Ventana de 60 s del límite y que los 400 no consumen cuota | Inferido | Frenar con `remaining` y `reset` |

---

## 3. Política de privacidad: «JSON original sanitizado»

La capa que guarda lo recibido **no es una copia exacta** de Tally: se le quitan campos antes de guardarlo. Se aplica una **lista blanca**: lo que no esté listado se descarta, y de lo descartado desconocido se registra solo el *nombre* del campo. `sanitizer_version` permite volver a sanear lo guardado.

**Envío (`submission`)**
| Campo | Decisión | Motivo |
|---|---|---|
| `id` | **Conserva** | Sincronización incremental, deduplicación y numeración local |
| `formId`, `isCompleted`, `submittedAt`, `createdAt`, `updatedAt` | Conserva | Pertenencia, estado, filtros temporales y detección de cambios |
| `respondentId` | **Elimina** | Identificador de participante |
| `previewUrl`, `pdfUrl` | **Elimina** | URL firmadas con acceso a la respuesta completa |
| `locale` | Elimina | No se usa |

**Respuesta (`responses[]`)**: conserva `questionId` y `answer`. Elimina `sessionUuid`, `respondentId`, `id`, `submissionId`, `formId`, `createdAt`, `updatedAt`.

**Formulario, preguntas y cuenta**
| Origen | Conserva | Elimina |
|---|---|---|
| `GET /forms` | `id`, `name`, `status`, `isClosed`, `numberOfSubmissions`, `createdAt`, `updatedAt`, `workspaceId` | `createdByUserId`, `organizationId`, `folderId`, `index`, `isNameModifiedByUser`, `hasDraftBlocks` |
| `GET /forms/{id}` | Bloques mínimos: `type`, `groupType`, `uuid`, `groupUuid` y de `payload` solo `text`, `index`, `isHidden`, `isRequired`, `hasOtherOption`, y la lógica condicional (`logicalOperator`, `conditionals`, `actions`) | **Todo `settings`** (destinatarios de correo, contraseña, notificaciones, estilos, metadatos) y el contenido de presentación (`logo`, `placeholder`, `safeHTMLSchema`, `button`) |
| `GET /forms/{id}/questions` | `id`, `type`, `title`, `numberOfResponses`, `isDeleted`, `fields[]` | `formId` |
| `GET /users/me` | Solo el resultado de la conexión | **Todo lo demás** (correo, nombre, plan, SSO, datos del propietario) |
| `GET /workspaces` | `id`, `name` | `members`, `invites`, `createdByUserId` |
| Analítica | Números agregados (opcional, en la caché) | — |

**Respuestas abiertas:** el contenido de `answer` se conserva sin modificar porque es necesario para el análisis. **Pueden contener información personal que los encuestados escribieron voluntariamente** (nombres, correos, teléfonos, relatos personales), incluidas las respuestas de la opción "Otro" de las casillas. Tally Monitor no puede distinguirla ni eliminarla automáticamente, así que las bases locales deben tratarse como datos potencialmente personales. El programa ofrece, al exportar, opciones para **excluir** preguntas abiertas y para **enmascarar** correos, teléfonos y números largos en las exportaciones.

**Participantes únicos:** al no guardar `respondentId`, la app cuenta **envíos**, no personas. La cifra de personas, si se quiere, sale de `uniqueRespondents` de la analítica de Tally.

---

## 4. Almacenamiento aprobado y modelo de datos definitivo

**Decisiones aprobadas**
1. **`library.db`** (SQLite): `raw_` (JSON original sanitizado) + `data_` (normalizado, reconstruible desde `raw_`) + `state_` (numeración "Usuario NNN", favoritos, estado de sincronización; **no reconstruible**). Una sola transacción por sincronización, una sola copia de respaldo consistente y una sola secuencia de migraciones (`PRAGMA user_version`). Copia previa a cada migración y a cada reconciliación completa.
2. **`cache.db`**: estadísticas calculadas (y, si se implementa, analítica de Tally). Descartable, fuera de los backups; se recrea si cambia su versión de esquema.
3. **Credenciales**: almacenamiento **independiente** (archivo propio en `%APPDATA%`, nunca dentro de `library.db` ni de los backups), cifrado con **Windows DPAPI**. Obligatorio: la clave se introduce una vez, se conserva cifrada entre sesiones y se pueden agregar cuentas nuevas en cualquier momento. Exportación/importación cifrada con contraseña para pasar cuentas entre equipos.

Fundamento: en modo WAL, SQLite garantiza atomicidad dentro de cada archivo pero no entre varios archivos adjuntos (documentación de SQLite).

```sql
-- === library.db ===  (PRAGMA user_version; backup con la API de SQLite)

-- raw_: JSON original SANITIZADO (no es una copia exacta de Tally)
raw_form       (account_id, form_id, sanitized_json, sanitizer_version, fetched_at,
                PRIMARY KEY(account_id, form_id));
raw_questions  (account_id, form_id, sanitized_json, sanitizer_version, fetched_at,
                PRIMARY KEY(account_id, form_id));
raw_submission (account_id, submission_id, form_id, sanitized_json, sanitizer_version,
                first_seen_at, last_seen_at, missing_at_source_at,
                PRIMARY KEY(account_id, submission_id));

-- data_: normalizado, reconstruible desde raw_
data_account    (account_id, name, status, last_sync_at, created_at);   -- la API Key NO está aquí
data_form       (account_id, form_id, name, status, is_closed, workspace_id,
                 reported_submissions, created_at, updated_at, last_submission_at, last_synced_at);
data_question   (account_id, form_id, question_id, position, type, title, reported_responses,
                 group_uuid, has_other_option, is_deleted);
data_option     (account_id, form_id, question_id, option_text, position,
                 PRIMARY KEY(account_id, form_id, question_id, option_text));  -- texto, POR pregunta
data_submission (account_id, submission_id, form_id, submitted_at, is_completed,
                 created_at, updated_at, missing_at_source_at);
data_answer     (account_id, submission_id, question_id, kind, text_value, is_blank, raw_json);
                 -- kind: text | single | multi | raw ; is_blank: Tally la cuenta como respuesta
data_choice     (account_id, submission_id, question_id, option_text, origin);
                 -- origin: 'declared' (está en las opciones de su pregunta) | 'other' (texto libre de
                 -- "Otro") | 'unmatched' (opción renombrada o eliminada)

-- state_: NO reconstruible; entra en los backups
state_user_number  (account_id, form_id, submission_id, number,
                    PRIMARY KEY(account_id, submission_id), UNIQUE(account_id, form_id, number));
state_form_counter (account_id, form_id, next_number);
state_favorite     (account_id, form_id);
state_recent       (account_id, form_id, opened_at);
state_sync         (account_id, form_id, newest_submitted_at, newest_submission_id,
                    last_sync_at, last_full_reconcile_at, last_error);

-- === cache.db === (descartable)
stats_cache     (account_id, form_id, range_key, schema_version, computed_at, payload_json);
analytics_cache (account_id, form_id, endpoint, period, fetched_at, payload_json);   -- opcional
```

Reglas de numeración: el número "Usuario NNN" se asigna por `submitted_at` ascendente en la primera sincronización, **en la misma transacción** que inserta el envío, y nunca se reasigna. Un envío tardío recibe el siguiente número libre.

---


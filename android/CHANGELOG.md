# Cambios
## 1.0.0
- Nueva pestaña Inicio (saludo según fecha y hora, resumen de encuestas, aviso de respuestas sin actualizar) y sección «Metas».
- Punto rojo en las encuestas con respuestas sin actualizar y en la pestaña Encuestas.
- Ajuste «Sincronización: Manual / Automática» (igual que en Windows).
- Datos propios por encuesta (base `library`, migración 0003: `survey_meta` y `survey_tags`): meta de respuestas, nota (hasta 500 caracteres) y etiquetas (hasta 8, de hasta 24 caracteres). Entran en las copias de seguridad; restaurar una copia anterior sigue funcionando (la migración se aplica después).
- Pantalla Encuestas: etiquetas en las tarjetas, filtro por etiqueta, barra de meta, archivar/desarchivar y «Mostrar archivadas». La búsqueda también mira etiquetas y notas. Las archivadas no cuentan en Inicio, «Cómo les va», el aviso ni el punto rojo.
- Pantalla de la encuesta: botón «Editar» (meta, nota, etiquetas) y nota bajo el título.
- Resumen: bloque «Meta» con proyección («Al ritmo de los últimos 7 días… se llega el dd/mm/aaaa»), sección «Ritmo» (esta semana contra la anterior, día más activo, hora pico, finalización y gráficos por día y por hora) y «Cruzar preguntas» (todas las estadísticas solo con quienes eligieron una opción; las exportaciones no se ven afectadas).
- Avisos de respuestas nuevas, locales y sin servidores (WorkManager cada 15, 30, 60 o 360 minutos): se pide el permiso de notificaciones (Android 13+) recién al activarlos. Nuevo permiso declarado: `POST_NOTIFICATIONS`. Nueva dependencia: `androidx.work:work-runtime-ktx` 2.9.1.
- 7 widgets para la pantalla de inicio: Resumen (2×1), Semáforo (1×1, círculo redondo: rojo con el número si hay respuestas sin actualizar, verde con ✓ si está todo al día), Meta (2×2; elegís la encuesta al agregarlo y, si ninguna tiene meta, se la ponés ahí mismo), Ranking (3×2: top 3 de encuestas por respuestas, con barras proporcionales), Novedades (2×2: «3 respuestas nuevas» / «Sin nuevas respuestas»), Acceso directo a una encuesta (2×1, se elige al agregarlo) y Lista de encuestas (5×2, achicable a 3×2, con scroll; tocar una abre esa encuesta). Claro/oscuro según el sistema. Los nombres se muestran por defecto y se pueden ocultar en Ajustes › Widgets.
- Idioma: Español e Inglés, se elige en Ajustes (por defecto el del teléfono).
- Widget Meta: elegís la encuesta al agregarlo y podés crear la meta ahí mismo.
- Se quitó el widget Saludo.
- Funciones puras con pruebas JUnit: proyección de metas, ritmo, cruce de preguntas, reglas de meta/etiquetas y lógica de avisos.

- Primera versión para Android (paridad con Windows 1.0): cuentas con API Key cifrada, sincronización incremental, estadísticas, filtros de tiempo, respuestas individuales, exportación a Excel/PDF/PNG con enmascarado, copias de seguridad, tema oscuro/claro.

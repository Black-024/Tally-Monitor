"""Textos de la interfaz. Este archivo tiene el español (rioplatense); `strings_en.py` tiene los mismos nombres en inglés
y los reemplaza al final de este módulo cuando el idioma activo es «en» (ver core/language.py)."""
from ..core import language as _language
from ..core.platform_info import IS_MAC, IS_WINDOWS

# Cómo se protege la API Key según el sistema (los textos de Windows no cambian).
_KEY_STORE = "con Windows" if IS_WINDOWS else "en el llavero de macOS" if IS_MAC else "en el llavero del sistema"
_ABOUT_PROTECTION = (
    "Las API Keys se cifran con Windows (DPAPI) para tu usuario de Windows. Esto protege contra otros "
    "usuarios del equipo y contra copiar los archivos a otra máquina; no protege contra un programa "
    "malicioso que se ejecute con tu mismo usuario. Si Windows recrea tu perfil, las claves se pierden y "
    "hay que reingresarlas." if IS_WINDOWS else
    "Las API Keys se guardan en el llavero del sistema (" + ("Llavero de macOS" if IS_MAC else
                                                             "Secret Service: GNOME Keyring o KWallet") +
    "), asociado a tu usuario. Esto protege contra otros usuarios del equipo y contra copiar los archivos a otra "
    "máquina; no protege contra un programa malicioso que se ejecute con tu mismo usuario. Si el llavero se "
    "reinicia o se borra, hay que reingresar las claves.")
APP_NAME = "Tally Monitor"
TEST_MODE_SUFFIX = " — MODO PRUEBA"
TEST_MODE_BADGE = "Modo prueba: al cerrar se guarda un informe de la sesión."
TEST_REPORT_SAVED = "Informe de la sesión guardado en:\n{path}"

NAV = [("inicio", "Inicio"), ("encuestas", "Encuestas"), ("cuentas", "Cuentas"), ("configuracion", "Ajustes")]
TABS = [("resumen", "Resumen"), ("respuestas", "Respuestas"), ("exportar", "Exportar")]

COMING: dict = {}

# cuentas
ACCOUNTS_TITLE = "Cuentas"
ADD_ACCOUNT = "+ Agregar cuenta"
ADD_FIRST = "Agregar tu primera cuenta"
NO_ACCOUNTS_TITLE = "Todavía no hay cuentas"
NO_ACCOUNTS_TEXT = "Agregá una API Key de Tally para empezar. Se guarda cifrada en este equipo y no se vuelve a mostrar."
KEY_SAVED = "Clave guardada y cifrada"
BTN_VALIDATE, BTN_RENAME, BTN_REPLACE, BTN_DELETE = "Validar", "Renombrar", "Reemplazar clave", "Eliminar"
ADD_TITLE = "Agregar cuenta"
ADD_HELP = ("Pegá la API Key de Tally (empieza con «tly-»). Se valida con Tally y recién entonces se guarda, "
            f"cifrada {_KEY_STORE}. Solo se leen datos: nunca se modifica nada en Tally.")
FIELD_NAME, FIELD_KEY = "Nombre de la cuenta", "API Key"
BTN_CLOSE = "Cerrar"
BTN_SAVE_VALIDATE, BTN_CANCEL, BTN_REPLACE_OK = "Validar y guardar", "Cancelar", "Validar y reemplazar"
REPLACE_TITLE = "Reemplazar clave"
REPLACE_HELP = ("Se valida la clave nueva. Si falla, o si pertenece a otro usuario de Tally, "
                "se conserva la clave actual.")
VALIDATING = "Validando con Tally…"
RENAME_TITLE, RENAME_LABEL = "Renombrar cuenta", "Nuevo nombre:"
DELETE_TITLE = "Eliminar cuenta"
DELETE_TEXT = ("¿Eliminar la cuenta «{name}»?\n\nSe borran su clave cifrada y los datos guardados de esta cuenta "
               "en este equipo. No se toca nada en Tally.")
DELETE_CONFIRM = "Eliminar"
IDENTITY_NOT_VERIFIED = ("La clave se reemplazó, pero no se pudo comprobar que sea del mismo usuario de Tally "
                         "(falta el identificador de uno de los dos).")
KEY_REPLACED = "Clave reemplazada y validada."

# estados
STATUS_LABELS = {"active": "Activa", "key_rejected": "Clave rechazada", "check_failed": "No se pudo verificar",
                 "no_credential": "Sin clave guardada", "unverified": "Sin verificar"}
CHECK_DETAILS = {"network": "Sin conexión con Tally", "rate_limit": "Tally limitó las solicitudes",
                 "server": "El servicio de Tally no respondió", "unexpected": "Respuesta inesperada de Tally",
                 "auth": "Tally rechazó la clave"}
STATUS_HELP = {"key_rejected": "Reemplazá la clave.", "no_credential": "Reemplazá la clave: falta en este equipo.",
               "check_failed": "La clave no se marcó como inválida. Probá validar de nuevo."}

# inicio
HOME_TITLE = "Inicio"
TILE_ACCOUNTS, TILE_ACTIVE, TILE_ATTENTION = "Cuentas", "Activas", "Requieren atención"
ATTENTION_BANNER = "Hay cuentas que requieren atención. Revisalas en «Cuentas»."
OPEN_ACCOUNTS = "Ir a Cuentas"

# configuración
SETTINGS_TITLE = "Configuración"
SEC_DATA, SEC_LOGS, SEC_ABOUT = "Datos y copias de seguridad", "Registro (logs)", "Acerca de"
DATA_FOLDER, OPEN_FOLDER = "Carpeta de datos:", "Abrir carpeta"
BACKUP_NOW, BACKUP_RESTORE, BACKUP_DELETE = "Crear copia ahora", "Restaurar…", "Eliminar copia"
AUTO_BACKUP = "Copia automática diaria al iniciar"
BACKUP_HEADERS = ["Fecha", "Motivo", "Esquema", "Tamaño"]
BACKUP_NOTE = "Las copias no incluyen las API Keys: tras restaurar en otro equipo hay que reingresarlas."
BACKUP_CREATED = "Copia creada."
BACKUP_DELETED = "Copia eliminada."
RESTORE_TITLE = "Restaurar copia"
RESTORE_TEXT = ("¿Restaurar la copia del {date}?\n\nSe reemplaza la base de datos actual (antes se guarda una copia "
                "de seguridad del estado actual). Las claves guardadas no se tocan; las cuentas que no tengan clave "
                "quedarán como «Sin clave guardada».")
RESTORE_OK = "Copia restaurada."
RESTORE_RESTART = "Copia restaurada. Cerrá y volvé a abrir la aplicación."
DELETE_BACKUP_TEXT = "¿Eliminar la copia del {date}? No se puede deshacer."
REASONS = {"auto": "Automática", "manual": "Manual", "pre_migracion": "Previa a migración",
           "pre_restauracion": "Previa a restauración", "pre_reconciliacion": "Previa a reconciliación"}
LOG_LEVEL, LOGS_FOLDER = "Nivel de detalle:", "Abrir carpeta de logs"
ALREADY_RUNNING = "Tally Monitor ya está abierto. Buscalo en la barra de tareas."
COPY_DIAG, DIAG_COPIED = "Copiar informe de diagnóstico", "Informe copiado. Pegalo donde necesites: no incluye API Keys, respuestas ni nombres."
LOG_NOTE = "Los logs nunca incluyen API Keys."
ABOUT_TEXT = "Tally Monitor {version}\nSolo lectura: no modifica nada en Tally.\n\n" + _ABOUT_PROTECTION
LICENSES = "Licencias de terceros"
LICENSES_TEXT = ("PySide6 / Qt for Python — LGPL-3.0 (usado bajo LGPL, enlazado dinámico).\n"
                 "Python y su biblioteca estándar — Python Software Foundation License.\n\n"
                 "Detalle completo en THIRD_PARTY_LICENSES.md.")
DEGRADED = ("La base de datos está dañada. Restaurá una copia de seguridad para continuar; "
            "el resto de las secciones está deshabilitado.")

GENERIC_ERROR = "Ocurrió un error inesperado. Probá de nuevo."
BUSY = "Trabajando…"


# encuestas
SURVEYS_TITLE = "Tus encuestas"
SURVEYS_ACCOUNT = "Cuenta:"
SURVEYS_SEARCH = "Buscar por nombre…"
SURVEYS_FILTERS = [("all", "Todas"), ("fav", "Favoritas"), ("recent", "Recientes")]
SURVEYS_REFRESH = "Actualizar lista"
SURVEYS_NO_ACCOUNTS_TITLE = "Primero agregá una cuenta"
SURVEYS_NO_ACCOUNTS_TEXT = "Las encuestas se leen con la API Key de una cuenta de Tally."
SURVEYS_NO_ACCOUNTS_ACTION = "Ir a Cuentas"
SURVEYS_EMPTY_TITLE = "Todavía no hay encuestas guardadas"
SURVEYS_EMPTY_TEXT = ("Tocá «Actualizar lista» para traer las encuestas de esta cuenta. "
                      "Se guardan en este equipo y se pueden ver sin conexión.")
SURVEYS_EMPTY_FILTER = "No hay encuestas que coincidan con el filtro."
SURVEYS_LISTING = "Actualizando la lista de encuestas…"
SURVEYS_LISTED = "Lista actualizada: {n} encuesta(s)."
OFFLINE_SHOWING_SAVED = "No se pudo conectar. Se muestra lo que ya está guardado."
BTN_OPEN = "Abrir"
FAV_ON, FAV_OFF = "Favorita", "Marcar favorita"
SURVEY_OPEN, SURVEY_CLOSED = "Abierta", "Cerrada"
SURVEY_DRAFT = "Borrador"
NEW_IN_TALLY = "Hay respuestas nuevas en Tally"
NEVER_SYNCED = "Sin sincronizar"

# detalle
BACK_TO_SURVEYS = "Todas las encuestas"
BTN_SYNC, BTN_SYNC_FULL, BTN_CANCEL_SYNC = "Actualizar", "Sincronización completa…", "Cancelar"
SYNC_FULL_TITLE = "Sincronización completa"
SYNC_FULL_TEXT = ("Se vuelven a descargar todas las respuestas de esta encuesta para detectar ediciones y respuestas "
                  "que ya no estén en Tally. Antes se crea una copia de seguridad. Los números de «Usuario» no cambian. "
                  "Puede tardar si hay muchas respuestas.")
SYNC_FULL_CONFIRM = "Sincronizar todo"
SYNCING = "Sincronizando…"
SYNC_PHASES = {"encuestas": "Descargando encuestas", "respuestas": "Descargando respuestas"}
SYNC_CANCELLED = "Sincronización cancelada. Lo ya guardado sigue disponible; podés reanudarla cuando quieras."
RESPONSES_HEADER = "Respuestas"
RESPONSES_SEARCH = "Buscar usuario (p. ej. 012)…"
NO_RESPONSES_TITLE = "Todavía no hay respuestas guardadas"
NO_RESPONSES_TEXT = "Tocá «Sincronizar» para descargarlas desde Tally."
NO_RESPONSES_EMPTY_SURVEY = "Esta encuesta no tiene respuestas en Tally."
SELECT_A_USER = "Elegí un usuario de la lista para ver su respuesta."
LOAD_MORE = "Cargar más"
SHOWING_COUNT = "Mostrando {shown} de {total}"
USER_NOT_FOUND = "No hay un usuario con ese número."
PRIVACY_NOTICE = ("Las respuestas abiertas pueden contener datos personales que los participantes escribieron "
                  "voluntariamente. Tratalas con cuidado y no las compartas sin necesidad.")
ANSWER_BLANK = "(sin respuesta)"
ANSWER_RAW = "(formato de respuesta no interpretado)"
ANSWER_OTHER, ANSWER_UNMATCHED = "(otro)", "(opción que ya no existe en la encuesta)"
INCOMPLETE_RESPONSE = "Respuesta incompleta"
SUBMITTED_AT = "{when}"

# ajustes de sincronización
SEC_SYNC = "Sincronización"
SYNC_MODE_LABEL = "Modo de sincronización:"
SYNC_MODES = [("manual", "Manual (recomendado)"), ("auto", "Automática")]
SYNC_MODE_NOTE = ("Manual: solo se sincroniza cuando tocás el botón. Automática: al abrir Encuestas se actualiza la "
                  "lista y al abrir una encuesta se traen sus respuestas nuevas. En ambos modos se muestra primero "
                  "lo ya guardado.")


# análisis
ANALYSIS_TITLE = "Análisis"
ANALYSIS_SURVEY = "Encuesta:"
ANALYSIS_PERIOD = "Período:"
ANALYSIS_FILTERS = [("all", "Todo el período"), ("24h", "Últimas 24 horas"), ("7d", "Últimos 7 días"),
                    ("30d", "Últimos 30 días"), ("custom", "Rango personalizado")]
ANALYSIS_FROM, ANALYSIS_TO = "Desde:", "Hasta:"
ANALYSIS_INCLUDE_INCOMPLETE = "Incluir envíos incompletos"
ANALYSIS_NO_SURVEYS_TITLE = "Todavía no hay respuestas para analizar"
ANALYSIS_NO_SURVEYS_TEXT = ("Abrí una encuesta en «Encuestas» y tocá «Sincronizar». El análisis usa lo que ya está "
                            "guardado en este equipo; no necesita conexión.")
ANALYSIS_GO_SURVEYS = "Ir a Encuestas"
ANALYSIS_DATA_FROM = "Datos de la última sincronización ({when}). Para actualizarlos, sincronizá la encuesta en «Encuestas»."
ANALYSIS_EMPTY_PERIOD = "No hay respuestas en este período."
ANALYSIS_INVALID_RANGE = "La fecha de inicio es posterior a la de fin."
ANALYSIS_TILES = ("Respuestas", "Completas", "Incompletas", "Promedio por día")
ANALYSIS_SPAN = "Primera respuesta: {first} · Última: {last}"
ANALYSIS_TIMELINE = "Respuestas en el tiempo"
ANALYSIS_BUCKETS = {"hour": "por hora", "day": "por día", "month": "por mes"}
ANALYSIS_QUESTIONS = "Preguntas"
ANALYSIS_ANSWERED = "{n} respondieron"
ANALYSIS_BLANK = "{n} sin respuesta"
ANALYSIS_NOT_ASKED = "{n} no traían esta pregunta (se agregó después)"
ANALYSIS_NOT_INTERPRETED = ("Este tipo de pregunta ({type}) todavía no tiene análisis propio: solo se cuenta cuántas "
                            "personas respondieron.")
ANALYSIS_TEXT_STATS = "Largo promedio: {avg} caracteres · máximo: {max}"
ANALYSIS_TEXT_HINT = "Las respuestas de texto se leen en «Encuestas», por usuario."
ANALYSIS_OTHER_ROW = "Otro (texto escrito)"
ANALYSIS_ORPHAN_ROW = "Opciones que ya no existen en la encuesta"
ANALYSIS_OTHER_VALUES = "Textos de «Otro»: {items}"
ANALYSIS_WARN_NOT_INTERPRETED = "Hay preguntas de un tipo que todavía no se analiza; se muestran solo con su cantidad de respuestas."
ANALYSIS_WARN_LATER_QUESTIONS = "Algunas preguntas se agregaron después de las primeras respuestas; los porcentajes solo cuentan a quienes las vieron."
ANALYSIS_DELETED_QUESTION = "(pregunta eliminada)"


# exportaciones
EXPORT_TITLE = "Exportaciones"
EXPORT_INTRO = "Se exporta lo que ya está guardado en este equipo, con el período y las opciones que elijas acá."
EXPORT_INCLUDE_TEXT = "Incluir respuestas de texto libre"
EXPORT_MASK = "Ocultar posibles datos personales (correos, teléfonos, usuarios, números largos)"
EXPORT_TEXT_WARNING = ("Las respuestas de texto pueden contener datos personales escritos voluntariamente. El ocultado "
                       "automático ayuda pero no garantiza nada: revisá el archivo antes de compartirlo.")
EXPORT_XLSX = "Exportar a Excel"
EXPORT_PDF = "Exportar a PDF"
EXPORT_PNG = "Guardar gráficos como imagen (PNG)"
EXPORT_XLSX_HINT = "Excel: resumen, estadísticas, respuestas en el tiempo y una fila por usuario."
EXPORT_PDF_HINT = "PDF: informe con gráficos. Las respuestas de texto solo si lo tildás arriba."
EXPORT_PNG_HINT = "PNG: una imagen con el gráfico en el tiempo y las barras de cada pregunta de opciones."
EXPORT_SAVE_TITLE = "Guardar como"
EXPORT_FILTERS = {"xlsx": "Libro de Excel (*.xlsx)", "pdf": "Documento PDF (*.pdf)", "png": "Imagen PNG (*.png)"}
EXPORT_BUSY = "Creando el archivo…"
EXPORT_DONE = "Listo. Se guardó en: {path}"
EXPORT_DONE_EXTRA_TEXT = " Incluye respuestas de texto{masked}."
EXPORT_MASKED = " (con datos personales ocultados)"
EXPORT_UNMASKED = " (SIN ocultar datos personales)"
EXPORT_NOTHING = "No hay respuestas en este período para exportar."


# exportaciones y análisis
WALL_SUBTITLE = "Tocá una para ver sus respuestas, el análisis y exportarla. Todo en un solo lugar."
CARD_RESPONSES = "respuestas guardadas"
CARD_RESPONSES_ONE = "respuesta guardada"
CARD_NEVER = "sin descargar"
CARD_NEW = "sin actualizar"
ANALYSIS_CHIPS = [("24h", "24 h"), ("7d", "7 días"), ("30d", "30 días"), ("all", "Todo"), ("custom", "Elegir fechas")]
ANALYSIS_WITH_INCOMPLETE = "Con incompletos"
ANALYSIS_WITHOUT_INCOMPLETE = "Sin incompletos"
EXPORT_SCOPE_SUMMARY = "Resumen de la encuesta"
EXPORT_SCOPE_INDIVIDUAL = "Respuestas individuales"
EXPORT_WHO_ALL = "Todas las personas"
EXPORT_WHO_ONE = "Una sola persona"
EXPORT_WHO_PLACEHOLDER = "Por ejemplo: 7 o Usuario 007"
EXPORT_WHO_NOT_FOUND = "No encontré a esa persona. Probá con su número (por ejemplo 7)."
EXPORT_BIG_XLSX = "Excel\nDatos para calcular"
EXPORT_BIG_PDF = "PDF\nInforme para compartir"
EXPORT_BIG_PNG = "Imagen\nLos gráficos en un PNG"
EXPORT_BIG_PNG_IND = "Imagen\nNo recomendado"
EXPORT_STYLE_LABEL, EXPORT_STYLE_DARK, EXPORT_STYLE_LIGHT = "Estilo del PDF y la imagen:", "Oscuro", "Claro"
EXPORT_BIG_PDF_IND = "PDF\nNo recomendado, puede tardar"
EXPORT_BIG_PDF_TITLE = "PDF con muchas respuestas"
EXPORT_BIG_PDF_TEXT = ("No recomendado: son {n} respuestas y puede tardar demasiado (unos {est} aproximadamente), "
                       "y el archivo será muy pesado. Mientras trabaja podés seguir usando el programa. "
                       "Para algo más ágil, probá Excel o acotá el período. ¿Generarlo igual?")
EXPORT_BIG_PDF_CONFIRM = "Generar el PDF igual"
EXPORT_PNG_IND_TITLE = "Imagen con respuestas individuales"
EXPORT_PNG_IND_TEXT = ("Una imagen con muchas respuestas queda larguísima y difícil de leer o compartir. Para respuestas "
                       "individuales es mejor PDF o Excel. ¿Querés generar la imagen igual?")
EXPORT_PNG_IND_CONFIRM = "Generar la imagen igual"
EXPORT_PNG_IND_TOO_MANY = ("Son {n} personas: demasiadas para una sola imagen (máximo {max}). Elegí una persona, un "
                           "período más corto, o usá PDF o Excel.")
EXPORT_INDIVIDUAL_HINT = "Una ficha por persona con lo que respondió. Las preguntas que no respondió no aparecen."
EXPORT_SUMMARY_HINT = "Estadísticas por pregunta, gráfico en el tiempo y el resumen general."
ANALYSIS_NOTHING_SAVED = "Todavía no hay respuestas guardadas de esta encuesta. Tocá «Actualizar» para descargarlas."
TEST_MODE_TAG = "Modo prueba"


# actualizaciones y acerca de
SEC_UPDATES = "Actualizaciones"
UPDATE_CHECK = "Avisarme si hay una versión nueva"
UPDATE_NOTE = ("Apagado por defecto. Si lo activás, el programa consulta la lista pública de versiones en GitHub "
               "(sin enviar ningún dato tuyo). Solo te avisa: nunca descarga ni instala nada solo.")
UPDATE_NOW, UPDATE_OPEN = "Buscar ahora", "Abrir página de la versión"
UPDATE_STATES = {
    "not_configured": "Todavía no hay un sitio de descargas configurado (se habilita cuando se publique el proyecto).",
    "up_to_date": "Tenés la última versión.",
    "error": "No se pudo consultar ahora. Probá más tarde.",
}
UPDATE_AVAILABLE = "Hay una versión nueva: {version}."
UPDATE_PILL = "Versión {version} disponible"
FOOTER = "Tally Monitor {platform}: {version}. Por: Valentín Mangano"
ABOUT_LICENSE, ABOUT_PRIVACY = "Licencia y terceros", "Privacidad"
PRIVACY_TITLE = "Privacidad"
PRIVACY_SUMMARY = (
    "Todo queda en tu computadora: no hay servidores propios ni cuentas.\n"
    "Solo lectura: el programa únicamente consulta (GET) la API de Tally.\n"
    "Tu API Key se guarda cifrada con " + ("la protección de Windows" if IS_WINDOWS else "el llavero del sistema") + ", en un archivo aparte de las bases y de las copias de seguridad; "
    "nunca se muestra, imprime, registra ni escribe en otro archivo.\n"
    "No se guardan identificadores de respondiente ni de sesión, ni enlaces de vista previa o PDF.\n"
    "Las respuestas abiertas se guardan localmente y pueden contener datos personales que escribió la gente; "
    "las exportaciones pueden ocultarlos.\n"
    "El aviso de actualizaciones está apagado por defecto y nunca descarga ni instala nada solo.")

# apariencia
SEC_APPEARANCE = "Apariencia"
THEME_DARK, THEME_LIGHT = "Oscuro", "Claro"
THEME_NOTE = "Elegí el aspecto de la aplicación. Los PDF y las imágenes tienen su propia opción de estilo al exportar."


# inicio
HOME_PENDING_TITLE = "Hay respuestas sin actualizar"
HOME_PENDING_TEXT = ("Tally informa {n} respuesta(s) más que las guardadas en este equipo, en {s} encuesta(s).")
HOME_PENDING_TEXT_NOCOUNT = "Hay encuestas con respuestas que todavía no se descargaron."
HOME_PENDING_ACTION = "Ir a Encuestas"
HOME_NO_ACCOUNTS_TITLE = "Empecemos"
HOME_NO_ACCOUNTS_TEXT = "Agregá la API Key de tu cuenta de Tally para ver acá cómo van tus encuestas."
HOME_NO_SURVEYS_TITLE = "Todavía no hay encuestas guardadas"
HOME_NO_SURVEYS_TEXT = "Andá a Encuestas y tocá «Actualizar lista» para traerlas."
HOME_TILE_SURVEYS, HOME_TILE_RESPONSES, HOME_TILE_OPEN = "encuestas", "respuestas", "abiertas"
HOME_LAST = "Última respuesta recibida: {when}"
HOME_TOP_TITLE = "Cómo les va"
HOME_TOP_META = "{status} · última: {when}"


# ---------- 1.1: metas, notas, etiquetas, archivadas ----------
BTN_EDIT = "Editar"
EDIT_TITLE = "Editar encuesta"
EDIT_GOAL_LABEL = "Meta de respuestas"
EDIT_GOAL_HELP = "Un número entero entre 1 y 1.000.000. Dejalo vacío si no querés una meta."
EDIT_GOAL_PLACEHOLDER = "Por ejemplo: 200"
EDIT_NOTE_LABEL = "Nota"
EDIT_NOTE_HELP = "Hasta 500 caracteres. Es solo tuya: queda en este equipo y no se sube a Tally."
EDIT_TAGS_LABEL = "Etiquetas"
EDIT_TAGS_HELP = "Hasta 8, de hasta 24 caracteres cada una. Tocá una etiqueta para quitarla."
EDIT_TAG_PLACEHOLDER = "Escribí una etiqueta y tocá Agregar"
EDIT_TAG_ADD = "Agregar"
EDIT_SAVE = "Guardar"
EDIT_GOAL_NOT_NUMBER = "La meta tiene que ser un número entero, sin decimales ni letras."
EDIT_TAG_REMOVE = "Quitar la etiqueta {tag}"
EDIT_SAVED = "Cambios guardados."
ARCHIVE = "Archivar"
UNARCHIVE = "Desarchivar"
ARCHIVED_TAG = "Archivada"
ARCHIVE_DONE = "Encuesta archivada. Ya no cuenta en Inicio ni en los avisos."
UNARCHIVE_DONE = "Encuesta desarchivada."
SHOW_ARCHIVED = "Mostrar archivadas"
TAG_ALL = "Todas"
TAG_FILTER_LABEL = "Etiqueta: {tag}"
SURVEYS_EMPTY_ARCHIVED_HINT = "Hay encuestas archivadas: activá «Mostrar archivadas» para verlas."

GOAL_LINE = "{done} de {goal} ({pct} %)"
GOAL_REACHED = "¡Meta alcanzada!"
GOAL_ETA = "Al ritmo de los últimos 7 días (≈ {per_day} por día) se llega el {date}"
GOAL_NO_PACE_ZERO = "Sin respuestas en los últimos 7 días: no se puede estimar"
GOAL_NO_PACE_ENOUGH = "Sin ritmo suficiente para estimar cuándo se llega"
GOAL_SECTION = "Metas"
GOAL_BLOCK_TITLE = "Meta"
HOME_GOALS_EMPTY = "Todavía no definiste metas. Podés ponerle una a cada encuesta con «Editar»."

# Resumen: ritmo y cruce de preguntas
RHYTHM_TITLE = "Ritmo"
RHYTHM_WEEK = "Esta semana: {n} {word}"
RHYTHM_WEEK_DELTA = " ({delta} vs la anterior)"
RHYTHM_WEEK_NOTE = "La comparación con la semana anterior usa todas las respuestas guardadas, sin importar el período elegido."
RHYTHM_PEAK = "Día más activo: {day} · Hora pico: {hour} h"
RHYTHM_NO_PEAK = "Todavía no hay datos para ver el día y la hora más activos."
RHYTHM_COMPLETION = "Completaron la encuesta: {pct} %"
RHYTHM_WEEKDAYS_TITLE = "Respuestas por día de la semana"
RHYTHM_HOURS_TITLE = "Respuestas por hora del día"
WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

CROSS_TITLE = "Cruzar preguntas"
CROSS_HELP = "Mirá cómo contestaron las demás preguntas quienes eligieron una opción. Funciona con preguntas de opción."
CROSS_QUESTION = "Pregunta"
CROSS_OPTION = "Opción"
CROSS_APPLY = "Aplicar"
CROSS_CLEAR = "Quitar filtro"
CROSS_RIBBON = "Mostrando {matched} de {total} personas que respondieron «{option}» en «{question}»"
CROSS_NOBODY = "Nadie contestó esa opción en este período."
CROSS_EXPORT_NOTE = "Las exportaciones siguen usando todas las respuestas del período."
CROSS_NO_QUESTIONS = "Esta encuesta no tiene preguntas de opción para cruzar."
CROSS_SELF_NOTE = "La pregunta filtrada muestra el 100 % en la opción elegida: es lo esperable."

# Avisos
SEC_NOTIFY = "Avisos"
NOTIFY_CHECK = "Avisarme cuando haya respuestas nuevas"
NOTIFY_INTERVAL_LABEL = "Revisar cada:"
NOTIFY_INTERVALS = [("15", "15 minutos"), ("30", "30 minutos"), ("60", "1 hora"), ("360", "6 horas")]
NOTIFY_NOTE = ("Mientras la app esté abierta (también minimizada), cada tanto se consulta la lista de tus encuestas en "
               "Tally y, si hay respuestas nuevas sin guardar, te llega un aviso del sistema. Solo cuenta encuestas no "
               "archivadas. Si falla la conexión, no se avisa nada y se reintenta en el próximo ciclo.")
NOTIFY_NO_TRAY = "Tu sistema no ofrece bandeja"
NOTIFY_TRAY_OPEN, NOTIFY_TRAY_QUIT = "Abrir", "Salir"
NOTIFY_TRAY_TITLE = "Cerrar a la bandeja"
NOTIFY_TRAY_TEXT = ("La app seguirá abierta en la bandeja para avisarte. Para cerrarla del todo: clic derecho → Salir.")
NOTIFY_TRAY_TOOLTIP = "Tally Monitor"


# ---------- formatos según el idioma (fechas, números, porcentajes) ----------
DATE_FMT = "%d/%m/%Y"
DATETIME_FMT = "%d/%m/%Y %H:%M"
DATETIME_SEC_FMT = "%d/%m/%Y %H:%M:%S"
TL_HOUR_FMT, TL_DAY_FMT, TL_MONTH_FMT = "%d/%m %H:00", "%d/%m", "%m/%Y"      # etiquetas de los gráficos en el tiempo
QT_DATE_FMT = "dd/MM/yyyy"                                                   # selectores de fecha de Qt
DECIMAL_SEP, THOUSANDS_SEP = ",", "."
PCT_FMT = "{value} %"

# ---------- tiempos relativos y duraciones ----------
REL_NEVER, REL_NOW = "nunca", "hace instantes"
REL_MIN, REL_HOUR = "hace {n} min", "hace {n} h"
REL_DAY_ONE, REL_DAY_MANY = "hace {n} día", "hace {n} días"
DUR_SECONDS, DUR_SECOND_ONE = "{n} segundos", "1 segundo"
DUR_MINUTES, DUR_ONE_MINUTE = "{n} minutos", "1 minuto"
DUR_HOUR_ONE, DUR_HOUR_MANY, DUR_AND_MINUTES = "{n} hora", "{n} horas", " y {n} minutos"

# ---------- textos armados por los presentadores ----------
ACCOUNT_DEFAULT_NAME = "Cuenta {n}"
ACCOUNT_VALIDATED_REL = "validada {when}"
ACCOUNT_NOT_VALIDATED = "sin validar todavía"
SURVEY_SAVED_ONE, SURVEY_SAVED_MANY = "{n} respuesta guardada", "{n} respuestas guardadas"
SURVEY_SYNCED_REL = "sincronizada {when}"
SURVEY_REPORTED_ONE, SURVEY_REPORTED_MANY = " · Tally informa {n} respuesta", " · Tally informa {n} respuestas"
SYNC_RESULT_NOCHANGE = "Sin cambios: ya tenías todas las respuestas."
SYNC_RESULT_INITIAL_ONE, SYNC_RESULT_INITIAL_MANY = "Se descargó {n} respuesta.", "Se descargaron {n} respuestas."
SYNC_RESULT_NEW_ONE, SYNC_RESULT_NEW_MANY = "{n} respuesta nueva.", "{n} respuestas nuevas."
SYNC_RESULT_NONE_NEW = "Sin respuestas nuevas."
SYNC_RESULT_FULL = "Sincronización completa: {new} nueva(s), {updated} ya existían."
SYNC_RESULT_FULL_MISSING = "Sincronización completa: {new} nueva(s), {updated} ya existían, {missing} ya no están en Tally."
SYNC_RESULT_MISMATCH = " Atención: hay {local} guardadas y Tally informa {remote}."
OTHER_ITEM, OTHER_ITEM_TIMES, OTHER_MORE = "«{text}»", "«{text}» ×{n}", "y {n} más"
RHYTHM_WORD_ONE, RHYTHM_WORD_MANY = "respuesta", "respuestas"
HOUR_LABEL = "{h} h"
SYNC_PROGRESS, SYNC_PROGRESS_OF = "{label}: {done}…", "{label}: {done} de {total}…"
PERIOD_LABEL = "Período: {label}"
CUSTOM_RANGE = "{start} al {end}"
PERIOD_WITH_INCOMPLETE, PERIOD_WITHOUT_INCOMPLETE = "{label} · con envíos incompletos", "{label} · sin envíos incompletos"

# ---------- mensajes de las cuentas ----------
ACCOUNT_ADDED = "Cuenta «{name}» agregada y validada."
ACCOUNT_VALIDATE_RESULT = "«{name}»: {message}"
ACCOUNT_RENAMED = "Cuenta renombrada a «{name}»."
ACCOUNT_DELETED = "Cuenta «{name}» eliminada."
KEY_FORMAT_ERROR = "La API Key no tiene el formato esperado: debe empezar con «tly-» y no contener espacios."
NAME_LENGTH_ERROR = "El nombre debe tener entre 1 y 60 caracteres."

# ---------- nombres accesibles y rótulos de los widgets ----------
OPEN_SUFFIX = "Abrir"
STATUS_ACCESSIBLE = "Estado: {label}"
THEME_ACCESSIBLE = "Tema {label}"
API_KEY_FIELD = "API Key"
BAR_CHART_NAME = "Gráfico de barras"
RED_DOT_NAME = "Con respuestas sin actualizar"
TIMELINE_NAME = "Gráfico de respuestas en el tiempo"
TIMELINE_DESC = "{total} respuestas en {n} intervalos"

# ---------- exportación (imagen PNG) ----------
EXPORT_PNG_SUBTITLE = "{label} · {n} respuestas"
EXPORT_PNG_IND_SUBTITLE = "{n} respuestas individuales · {period}"
EXPORT_PNG_INCOMPLETE = " · incompleta"

# ---------- idioma ----------
SEC_LANGUAGE = "Idioma / Language"
LANGUAGE_LABEL = "Idioma / Language:"
LANGUAGE_NAMES = [("es", "Español"), ("en", "English")]
LANGUAGE_RESTART = "Reiniciá la aplicación para aplicar el cambio / Restart the app to apply the change"

# ---------- saludos de Inicio ----------
GREET_SPECIAL = {
    (12, 24): ("¡Feliz Navidad!", "¿Encuestas navideñas? Mirá cómo les está yendo."),
    (12, 25): ("¡Feliz Navidad!", "¿Encuestas navideñas? Mirá cómo les está yendo."),
    (12, 31): ("Último día del año", "¿Un balance de las encuestas antes del brindis?"),
    (1, 1): ("¡Feliz año nuevo!", "Empezá el año viendo cómo arrancan tus encuestas."),
    (2, 14): ("Día de los Enamorados", "¿Una encuesta sobre el amor? Preguntar no cuesta nada."),
    (5, 1): ("Día del Trabajador", "Hoy se descansa, pero las respuestas siguen llegando."),
    (5, 25): ("¡Feliz 25 de Mayo!", "Un día patrio para mirar qué opina la gente."),
    (7, 9): ("¡Feliz Día de la Independencia!", "Fecha ideal para una encuesta de opinión."),
    (7, 20): ("¡Feliz Día del Amigo!", "¿Les mandaste la encuesta a tus amigos?"),
    (10, 31): ("¡Feliz Halloween!", "¿Encuestas de terror? Revisá si hay respuestas misteriosas."),
}
GREET_BETWEEN_HOLIDAYS = ("Entre Navidad y Año Nuevo", "Semana lenta: buen momento para revisar resultados.")
GREET_NIGHT, GREET_MORNING = "Trasnochando con las encuestas", "¡Buen día!"
GREET_AFTERNOON, GREET_EVENING = "¡Buenas tardes!", "¡Buenas noches!"
GREET_WEEKDAY = (       # lunes = 0
    "Arrancó la semana: a ver cómo vienen las encuestas.",
    "Martes de números: ¿cuántas respuestas hubo?",
    "Mitad de semana. ¿Cómo van las encuestas?",
    "Jueves: casi llegando al finde. ¿Alguna novedad?",
    "Viernes: una última mirada antes del finde.",
    "Sábado: ¿mirando encuestas igual? Me gusta.",
    "Domingo tranqui. Las encuestas no se cansan.",
)

# ---------- idioma inglés: al final, para que reemplace todo lo anterior ----------
if _language.current() == "en":
    from . import strings_en as _en
    globals().update({_k: _v for _k, _v in vars(_en).items() if _k.isupper() and not _k.startswith("_")})

# Cambios

## 1.0.0
- Idioma Español / English: en Ajustes → «Idioma / Language» se elige y se aplica al reiniciar la app. Sin elegir, se usa el idioma del sistema (español si empieza con «es», si no inglés); también se puede forzar con la variable `TALLY_MONITOR_LANG` (`es` o `en`). La preferencia se guarda en `language.txt` en la carpeta de datos (sin secretos). Cambian los textos, errores, avisos de la bandeja, saludos, fechas (mm/dd/aaaa en inglés), números (1,234 en inglés), las etiquetas de las exportaciones (Excel, PDF, PNG) y el rótulo «Usuario NNN» («User NNN»).
- Metas: a cada encuesta le podés poner una meta de respuestas (1 a 1.000.000). Se ve una barra de progreso en las tarjetas, el bloque «Meta» en el Resumen y la sección «Metas» en Inicio, con una estimación de cuándo se llega según el ritmo de los últimos 7 días.
- Nota propia (hasta 500 caracteres, se muestra bajo el título) y etiquetas (hasta 8 por encuesta) editables con el botón «Editar». Chips para filtrar por etiqueta; la búsqueda también mira notas y etiquetas.
- Archivar y desarchivar encuestas. Las archivadas se ocultan (con «Mostrar archivadas» se ven) y no cuentan en Inicio, en «Cómo les va», en el punto rojo ni en los avisos.
- Resumen: sección «Ritmo» (respuestas de la semana contra la anterior, día más activo, hora pico, porcentaje que completó, gráficos por día de la semana y por hora) y «Cruzar preguntas» (filtra todo el Resumen por quienes eligieron una opción; las exportaciones siguen usando todas las respuestas del período).
- Avisos de respuestas nuevas (apagados por defecto): en Ajustes, cada 15 minutos, 30 minutos, 1 hora o 6 horas, con la app abierta o minimizada, aparece un aviso del sistema desde la bandeja. Con los avisos activos, cerrar la ventana la manda a la bandeja («clic derecho → Salir» para cerrarla del todo). Si el sistema no tiene bandeja, la opción queda desactivada.
- Los datos nuevos (metas, notas, etiquetas, archivadas) quedan en las copias de seguridad; las copias anteriores se siguen pudiendo restaurar.
- Base de datos: migración 3 (se crea una copia previa automática al actualizar).
- Publicación automática de versiones con GitHub Actions (`.github/workflows/release.yml`, sin probar todavía).
- Nueva pestaña Inicio: saludo según la fecha y la hora, mini resumen de las encuestas y aviso con botón cuando hay respuestas sin actualizar.
- Punto rojo en las encuestas con respuestas sin actualizar y en la pestaña Encuestas.
- macOS (Apple Silicon e Intel): app `.app` en `.dmg`; la API Key va al Llavero de macOS.
- Linux x86_64: paquete `.tar.gz` y AppImage. La API Key se guarda en el llavero del sistema (Secret Service). Rutas y tipografías adaptadas.

- Varias cuentas de Tally (API Keys cifradas con Windows DPAPI, nunca visibles ni guardadas en otro lado). Solo lectura.
- Encuestas descargadas y guardadas en tu equipo, con sincronización incremental, copias de seguridad y restauración.
- Respuestas individuales numeradas localmente («Usuario 001»…).
- Análisis: resumen por pregunta, línea de tiempo y filtros (24 h, 7 días, 30 días, todo, rango propio).
- Exportaciones: Excel, PDF e imagen PNG; resumen o respuestas individuales; estilo oscuro o claro; enmascarado de datos personales.
- Temas oscuro y claro.
- Instalador, versión portable, aviso opcional de actualizaciones (apagado por defecto), modo prueba para informes de errores sin datos sensibles.

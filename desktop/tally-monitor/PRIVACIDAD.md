# Privacidad de Tally Monitor

- **Todo queda en tu computadora.** No hay servidores propios ni cuentas. Los datos viven en `%LOCALAPPDATA%\TallyMonitor` (Windows) `~/.local/share/TallyMonitor` (Linux) o `~/Library/Application Support/TallyMonitor` (macOS).
- **Solo lectura.** El programa únicamente hace consultas GET a la API de Tally; no modifica ni borra nada allá.
- **Tu API Key** se guarda cifrada con la protección de Windows (DPAPI) o, en Linux y macOS, en el llavero del sistema (Secret Service / Llavero de macOS), fuera de las bases y de las copias de seguridad; en el archivo `credentials.dat` solo queda una referencia opaca. Nunca se muestra, imprime, registra ni escribe en otro archivo.
- **No se guardan** identificadores de respondiente, de sesión ni enlaces de vista previa o PDF.
- **Respuestas abiertas:** se guardan localmente porque pueden ser lo más valioso de la encuesta, pero pueden contener datos personales que la gente escribió. En las exportaciones se ocultan correos, enlaces, @usuarios y números largos salvo que lo desactives.
- **Registros (logs):** rotan solos y redactan cualquier clave `tly-…`.
- **Informe de diagnóstico:** lo copiás vos y lo pegás donde quieras; no incluye claves, textos de respuestas ni nombres de cuentas o encuestas.
- **Aviso de actualizaciones:** apagado por defecto. Si lo activás, consulta la lista pública de versiones en GitHub (sin enviar datos tuyos) y solo te abre el navegador; nunca descarga ni instala nada solo.
- **Desinstalar:** el instalador te pregunta si querés conservar o borrar tus datos.

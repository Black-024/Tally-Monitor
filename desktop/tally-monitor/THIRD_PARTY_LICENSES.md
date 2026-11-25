# Licencias de terceros

Tally Monitor se distribuye bajo la licencia MIT (ver `LICENSE`). Usa los siguientes componentes de terceros.
Esta lista es informativa; no es asesoramiento jurídico.

| Componente | Uso | Licencia |
|---|---|---|
| Python y biblioteca estándar (`sqlite3`, `ctypes`, `urllib`, `logging`…) | Núcleo | Python Software Foundation License |
| PySide6 / Qt for Python | Interfaz | LGPL-3.0 (también GPL-3.0 o comercial; se usa bajo LGPL) |
| ReportLab | Exportación a PDF | BSD-3-Clause |
| OpenPyXL | Exportación a Excel | MIT |
| keyring (+ SecretStorage, jeepney) | Llavero del sistema (solo Linux y macOS) | MIT (keyring, jeepney) / BSD-3-Clause (SecretStorage) |
| PyInstaller | Empaquetado (solo para generar el .exe) | GPL-2.0 con excepción para el programa empaquetado |
| pytest, pytest-qt | Pruebas (solo desarrollo) | MIT |

No se usa Qt Charts (GPL/comercial): los gráficos son propios.

## Obligaciones de la LGPL de PySide6 / Qt
- Qt va enlazado de forma dinámica: la distribución es una carpeta con sus bibliotecas (no un único .exe que las oculte).
- Podés reemplazar las bibliotecas de Qt de la carpeta por otra versión compatible.
- El texto de la LGPL-3.0 y los avisos de Qt/PySide6 acompañan a la distribución en la carpeta `licenses`.
- Código fuente de Qt y PySide6: https://code.qt.io y https://pypi.org/project/PySide6/

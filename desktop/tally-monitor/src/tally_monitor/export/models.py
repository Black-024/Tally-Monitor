from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ExportOptions:
    kind: str = "all"                      # all | 24h | 7d | 30d | custom
    start_date: date | None = None
    end_date: date | None = None           # inclusivo
    include_incomplete: bool = True
    include_text: bool = False             # respuestas de texto libre (pueden tener datos personales)
    mask_personal: bool = True             # ocultar correos, teléfonos, etc. en esos textos
    scope: str = "summary"                 # summary (estadísticas) | individual (una ficha por persona)
    style: str = "dark"                    # estilo visual de PDF e imagen: dark | light (Excel no cambia)
    only_number: int | None = None         # solo en scope=individual: exportar a una sola persona (n.º de «Usuario»)


@dataclass(frozen=True)
class ExportResult:
    path: str
    format: str                            # xlsx | pdf | png
    responses: int
    questions: int
    text_included: bool
    masked: bool

#!/usr/bin/env python3
"""
Auditoría de seguridad y privacidad de TODO el paquete. Solo biblioteca estándar.

Uso:  py tools\\auditoria_seguridad.py                   # revisa src\\ (código fuente)
      py tools\\auditoria_seguridad.py dist\\TallyMonitor   # además revisa lo empaquetado (busca claves o datos sueltos)

Busca: claves reales (tly-…), métodos HTTP que no sean GET, verificación TLS desactivada, ejecución dinámica
(eval/exec/pickle/shell=True/os.system), URLs http:// que no sean locales, el uso de datos prohibidos
(respondentId, sessionUuid, previewUrl, pdfUrl) fuera de la lista de descarte, y archivos .db/.dat/.log
sueltos en lo empaquetado. Devuelve 0 si está limpio y 1 si hay hallazgos.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = re.compile(r"tly-[A-Za-z0-9]{16,}")
RULES = [
    (re.compile(r"method\s*=\s*['\"](?!GET['\"])[A-Z]+['\"]"), "método HTTP distinto de GET"),
    (re.compile(r"\.(post|put|patch|delete)\(\s*['\"]/"), "posible llamada HTTP de escritura"),
    (re.compile(r"verify\s*=\s*False|_create_unverified_context|CERT_NONE"), "verificación TLS desactivada"),
    (re.compile(r"(?<![.\w])eval\(|(?<![.\w])exec\(|pickle\.load|shell\s*=\s*True|os\.system\("), "ejecución dinámica o shell"),
    (re.compile(r"http://(?!127\.0\.0\.1|localhost)"), "URL http:// no local"),
]
FORBIDDEN_FIELDS = ("respondentId", "sessionUuid", "previewUrl", "pdfUrl")
# solo estos archivos pueden nombrar los campos prohibidos (para descartarlos) y se revisa que no los guarden
FIELDS_ALLOWED = {"sync/sanitizer.py"}
LOOSE = {".db", ".dat", ".log", ".sqlite", ".bak"}


def scan_source(src: Path) -> list[str]:
    bad = []
    for p in sorted(src.rglob("*.py")):
        rel = p.relative_to(src).as_posix()
        text = p.read_text(encoding="utf-8", errors="replace")
        if KEY.search(text):
            bad.append(f"{rel}: parece contener una API Key")
        for rx, why in RULES:
            if rx.search(text):
                bad.append(f"{rel}: {why}")
        if rel not in FIELDS_ALLOWED and any(f in text for f in FORBIDDEN_FIELDS):
            bad.append(f"{rel}: nombra un campo que no debe guardarse ({'/'.join(FORBIDDEN_FIELDS)})")
    return bad


def scan_dist(dist: Path) -> list[str]:
    bad = []
    for p in dist.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() in LOOSE:
            bad.append(f"{p.relative_to(dist)}: archivo de datos suelto en lo empaquetado")
        elif p.suffix.lower() in (".txt", ".json", ".md", ".py", ".ini", ".cfg") and p.stat().st_size < 2_000_000:
            if KEY.search(p.read_text(encoding="utf-8", errors="ignore")):
                bad.append(f"{p.relative_to(dist)}: parece contener una API Key")
    return bad


def main() -> int:
    findings = scan_source(ROOT / "src" / "tally_monitor")
    if len(sys.argv) > 1:
        findings += scan_dist(Path(sys.argv[1]))
    if findings:
        print(f"{len(findings)} hallazgo(s):")
        for f in findings:
            print("  -", f)
        return 1
    print("Auditoría limpia: sin claves, sin escrituras HTTP, sin TLS desactivado, sin ejecución dinámica, "
          "sin campos prohibidos fuera del sanitizador.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

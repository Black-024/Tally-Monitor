#!/usr/bin/env python3
"""
Prueba de carga: mide cuánto tarda la app con encuestas grandes. Funciona en Linux/Mac/Windows.

Uso:   py scripts\\prueba_de_carga.py              # 5.000 y 20.000 respuestas (por defecto)
       py scripts\\prueba_de_carga.py 1000 50000   # tamaños a elección

- NO usa tu API Key ni tus datos ni la red real: levanta un servidor Tally FALSO en tu propio equipo, con
  respuestas generadas SOLO para esta prueba (nunca se mezclan con tus datos reales; todo vive en una carpeta
  temporal que se borra al terminar).
- Mide: sincronización completa, Resumen (análisis), segunda sincronización sin cambios, exportar a Excel y a PDF
  (resumen e individuales), y tamaño de los archivos y de la base.
- Metas (si una falla, lo ves marcado y me pasás el texto):  Resumen < 1 s con 10.000 respuestas.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tally-monitor"
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from support.fake_protector import FakeProtector  # noqa: E402
from support.fake_tally import FakeTally  # noqa: E402
from support.forms import FORM_ID, add_form, big_submission  # noqa: E402
from support.shared import KEY_A  # noqa: E402
from tally_monitor.api.client import TallyClient  # noqa: E402
from tally_monitor.app import build_core  # noqa: E402
from tally_monitor.core.config import AppPaths  # noqa: E402
from tally_monitor.core.secret import SecretStr  # noqa: E402
from tally_monitor.services.export_service import ExportOptions  # noqa: E402

OK = True


def timed(label: str, fn, goal_s: float | None = None):
    global OK
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    mark = ""
    if goal_s is not None:
        good = dt <= goal_s
        OK &= good
        mark = f"   (meta ≤ {goal_s:g} s: {'OK' if good else 'SUPERADA'})"
    print(f"  {label:<46}{dt:8.2f} s{mark}")
    return out


def run(n: int) -> None:
    print(f"\n=== {n:,} respuestas ===".replace(",", "."))
    tmp = Path(tempfile.mkdtemp(prefix="tm-carga-"))
    tally = FakeTally().start()
    try:
        tally.users[KEY_A] = "user-A"
        add_form(tally, [big_submission(i) for i in range(n)], name="Encuesta de carga")
        core = build_core(paths=AppPaths(tmp / "home"), protector=FakeProtector(),
                          client=TallyClient(tally.url, sleep=lambda s: None), configure_logging=False)
        core.startup.run()
        acct = core.accounts.add_account("Prueba", SecretStr(KEY_A)).account_id
        core.sync.sync_forms(acct)
        res = timed("sincronización inicial (descarga + guardado)", lambda: core.sync.sync_form(acct, FORM_ID))
        assert res.new == n, f"se esperaban {n} nuevas y hubo {res.new}"
        timed("sincronización sin cambios", lambda: core.sync.sync_form(acct, FORM_ID))
        goal = 1.0 if n <= 10_000 else 3.0
        a = timed("Resumen (todo el período)", lambda: core.analysis.analyze(acct, FORM_ID, "all"), goal)
        assert a.overview.total == n
        timed("Resumen (últimos 30 días, rango personalizado)",
              lambda: core.analysis.analyze(acct, FORM_ID, "custom", start_date=a.timeline.points[0].start.date(),
                                            end_date=a.timeline.points[-1].start.date()), goal)
        timed("Respuestas: primera página (200)", lambda: core.surveys.responses(acct, FORM_ID, offset=0, limit=200), 0.5)
        out = tmp / "out"
        out.mkdir()
        timed("Excel resumen", lambda: core.export.export_xlsx(acct, FORM_ID, str(out / "r.xlsx")))
        timed("PDF resumen", lambda: core.export.export_pdf(acct, FORM_ID, str(out / "r.pdf")))
        ind = ExportOptions(scope="individual", include_text=True)
        timed("Excel respuestas individuales", lambda: core.export.export_xlsx(acct, FORM_ID, str(out / "i.xlsx"), ind))
        if n <= 5_000:
            timed("PDF respuestas individuales", lambda: core.export.export_pdf(acct, FORM_ID, str(out / "i.pdf"), ind))
        else:
            print("  PDF respuestas individuales                  (omitido: usar una sola persona o un período)")
        for f in sorted(out.iterdir()):
            print(f"  archivo {f.name:<10}{f.stat().st_size / 1_048_576:8.2f} MB")
        db = tmp / "home" / "library.db"
        if db.exists():
            print(f"  base de datos local {db.stat().st_size / 1_048_576:8.2f} MB")
    finally:
        tally.stop()
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    sizes = [int(a) for a in sys.argv[1:]] or [5_000, 20_000]
    for n in sizes:
        run(n)
    print("\nTodo dentro de las metas." if OK else "\nHay metas superadas: copiá este texto y pasámelo.")
    return 0 if OK else 1


if __name__ == "__main__":
    raise SystemExit(main())

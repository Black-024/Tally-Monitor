#!/usr/bin/env python3
"""
Verificación de la sincronización  contra Tally REAL, en Windows.

Uso (PowerShell, desde la carpeta que contiene scripts):
    py scripts\\verify_sync_windows.py                 # te deja elegir la encuesta de la lista
    py scripts\\verify_sync_windows.py --form ID       # o indicás el ID de la encuesta
    py scripts\\verify_sync_windows.py --limpiar       # borra los datos de esta verificación

- Pide la API Key UNA vez con entrada oculta (como verify_core_windows.py). Nunca se muestra ni se guarda en claro.
- Trabaja en %LOCALAPPDATA%\\TallyMonitorVerifySync, NUNCA en tus datos reales.
- Solo hace GET (lectura). No modifica nada en Tally.
- Cantidad de solicitudes: unas 15-25 en total (el límite de Tally es 100 por ventana).
- Imprime OK / FALLO y conteos. NO imprime respuestas de personas. Sí muestra los nombres de tus encuestas
  (en tu propia consola) para que puedas elegir una.
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tally-monitor"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

import verify_core_windows as base   # noqa: E402  (reutiliza la entrada oculta y los helpers)

check, scan_for = base.check, base.scan_for


def pick_form(core, account_id, wanted):
    surveys = core.surveys.list_surveys(account_id)
    if wanted:
        if not any(s.form_id == wanted for s in surveys):
            print("Ese ID no está entre tus encuestas.")
            sys.exit(2)
        return wanted
    if not surveys:
        print("Tu cuenta no tiene encuestas.")
        sys.exit(2)
    print("\nTus encuestas:")
    for i, s in enumerate(surveys, 1):
        print(f"  {i}. {s.name}  [{s.form_id}]  envíos según Tally: {s.reported_submissions}")
    while True:
        raw = input("Número de la encuesta a verificar (con respuestas, idealmente 3 a 100): ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(surveys):
            return surveys[int(raw) - 1].form_id


def run(vdir: Path, protector, client, wanted_form):
    from tally_monitor.app import build_core
    from tally_monitor.core.config import AppPaths
    from tally_monitor.sync.numbering import format_user_label

    print("\n== 1. Preparación ==")
    if vdir.exists():
        shutil.rmtree(vdir)
    core = build_core(paths=AppPaths(vdir), protector=protector, client=client)
    core.startup.run()
    key = base.read_key_hidden()
    acct = core.accounts.add_account("Verificacion", key)
    check("cuenta agregada y validada", acct.status == "active")
    aid = acct.account_id
    needles = [key.reveal().encode(), b"tly-"]

    print("\n== 2. Lista de encuestas ==")
    res = core.sync.sync_forms(aid)
    check("se descargó la lista de encuestas", res.count >= 1, f"{res.count} encuestas")
    print("      campos desconocidos en /forms:", list(res.unknown_fields) or "ninguno")
    form_id = pick_form(core, aid, wanted_form)
    before = core.surveys.get_survey(aid, form_id)
    check("antes de sincronizar la encuesta figura sin copia local", before.never_synced and before.local_submissions == 0)

    print("\n== 3. Primera sincronización de la encuesta ==")
    reqs0 = client.request_count
    r = core.sync.sync_form(aid, form_id, progress=lambda ph, n, t: None)
    print(f"      modo={r.mode} nuevos={r.new} total_local={r.local_total} total_Tally={r.remote_total} "
          f"solicitudes={client.request_count - reqs0}")
    print("      campos desconocidos:", list(r.unknown_fields) or "ninguno", "| avisos:", list(r.warnings) or "ninguno")
    check("el total guardado coincide con el que informa Tally", r.remote_total == r.local_total and not r.warnings)
    views = core.surveys.responses(aid, form_id, limit=100000)
    check("hay tantas respuestas visibles como envíos", len(views) == r.local_total, f"{len(views)}")
    check("numeración 'Usuario' consecutiva sin huecos ni repetidos",
          [v.number for v in views] == list(range(1, len(views) + 1)))
    check("etiquetas correctas", all(v.label == format_user_label(v.number) for v in views))
    dates = [v.submitted_at for v in views]
    check("el Usuario 001 es el envío MÁS ANTIGUO (orden cronológico)", dates == sorted(dates))
    qs = core.surveys.questions(aid, form_id)
    types = sorted({q.type for q in qs})
    print("      tipos de pregunta en esta encuesta:", types)
    print("      envíos incompletos (parciales):", sum(1 for v in views if not v.is_completed))
    raw_kinds = sum(1 for v in views for a in v.answers if a.kind == "raw")
    print("      respuestas guardadas como 'raw' (tipo no interpretado):", raw_kinds)
    unmatched = sum(1 for v in views for a in v.answers for c in a.choices if c.origin == "unmatched")
    print("      opciones que no coinciden con ninguna opción ni 'Otro':", unmatched)
    check("las opciones de las preguntas de selección se leyeron",
          all(q.options for q in qs if q.type in ("MULTIPLE_CHOICE", "CHECKBOXES")))
    survey = core.surveys.get_survey(aid, form_id)
    check("la encuesta ya no marca envíos nuevos pendientes", not survey.has_new_hint)

    print("\n== 4. Segunda sincronización (sin cambios) ==")
    reqs1 = client.request_count
    r2 = core.sync.sync_form(aid, form_id)
    print(f"      modo={r2.mode} solicitudes={client.request_count - reqs1}")
    check("no hay nada nuevo y no se descargó todo de nuevo", r2.mode == "nochange" and r2.new == 0)
    check("la numeración no cambió", [v.number for v in core.surveys.responses(aid, form_id, limit=100000)]
          == [v.number for v in views])

    print("\n== 5. startDate con varias páginas (límite chico) ==")
    from tally_monitor.core.errors import CredentialError  # noqa: F401
    cred = core.sync._store.load(aid)
    full = []
    page = 1
    while True:
        d = client.list_submissions(cred.api_key, form_id, page=page, limit=2)
        full += d["submissions"]
        if not d.get("hasMore"):
            break
        page += 1
    ids_all = [s["id"] for s in full]
    check("la paginación de a 2 recorre todos los envíos sin repetir", len(ids_all) == len(set(ids_all)) == r.local_total,
          f"{len(ids_all)}")
    if len(full) >= 3:
        pivot = full[len(full) // 2]["submittedAt"]
        expected = {s["id"] for s in full if s["submittedAt"] >= pivot}
        got, page = [], 1
        while True:
            d = client.list_submissions(cred.api_key, form_id, page=page, limit=2, start_date=pivot)
            got += [s["id"] for s in d["submissions"]]
            if not d.get("hasMore"):
                break
            page += 1
        check("startDate (inclusivo) con varias páginas devuelve exactamente los esperados",
              set(got) == expected and len(got) == len(set(got)), f"{len(got)} de {len(expected)}")
    else:
        print("      (se omite: la encuesta tiene menos de 3 envíos)")

    print("\n== 6. Sincronización completa forzada (reconciliación) ==")
    r3 = core.sync.sync_form(aid, form_id, full=True)
    check("la completa no marca desaparecidos ni difiere del total", r3.missing == 0 and r3.local_total == r.local_total)
    check("se creó la copia de seguridad previa a la reconciliación",
          any(b.reason == "pre_reconciliacion" for b in core.backups.list_backups()))
    check("la numeración sigue igual tras la completa", [v.number for v in core.surveys.responses(aid, form_id, limit=100000)]
          == [v.number for v in views])

    print("\n== 7. Privacidad: identificadores que NO deben guardarse ==")
    sample = full[0] if full else {}
    secrets_ = [sample.get("respondentId"), sample.get("previewUrl"), sample.get("pdfUrl")]
    for resp in sample.get("responses", [])[:1]:
        secrets_ += [resp.get("sessionUuid"), resp.get("respondentId")]
    secrets_ = [s.encode() for s in secrets_ if isinstance(s, str) and len(s) > 6]
    check("respondentId / sessionUuid / previewUrl / pdfUrl no aparecen en ningún archivo",
          not scan_for(vdir, secrets_) if secrets_ else True, "" if secrets_ else "sin identificadores para comparar")
    check("la API Key no aparece en ningún archivo", not scan_for(vdir, needles))
    check("la API Key no aparece en 'tly-' dentro de las copias de seguridad", not scan_for(vdir / "backups", [b"tly-"]))

    print("\n== 8. Sin conexión ==")
    print("      (manual) Desactivá el wifi y volvé a correr con --leer-local para comprobar que se leen los datos guardados.")
    print("\n  Datos de la verificación guardados en:", vdir)


def read_local(vdir: Path, protector, client):
    from tally_monitor.app import build_core
    from tally_monitor.core.config import AppPaths
    if not vdir.exists():
        print("Corré primero la verificación completa.")
        sys.exit(2)
    core = build_core(paths=AppPaths(vdir), protector=protector, client=client)
    core.startup.run()
    acct = core.accounts.list_accounts()[0]
    surveys = core.surveys.list_surveys(acct.account_id)
    check("la lista de encuestas se lee de la copia local", len(surveys) >= 1)
    for s in surveys:
        if s.local_submissions:
            views = core.surveys.responses(acct.account_id, s.form_id, limit=100000)
            check("las respuestas guardadas se leen sin red", len(views) == s.local_submissions, f"{len(views)}")
            from tally_monitor.api.errors import ApiNetworkError
            try:
                core.sync.sync_form(acct.account_id, s.form_id)
                print("      (había conexión: la sincronización funcionó)")
            except ApiNetworkError:
                check("sin conexión: el error es de red y los datos siguen disponibles", True)
            break


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--form")
    ap.add_argument("--limpiar", action="store_true")
    ap.add_argument("--leer-local", action="store_true")
    args = ap.parse_args()
    if sys.platform != "win32":
        print("Este script es para Windows (usa DPAPI real).")
        return 2
    vdir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TallyMonitorVerifySync"
    if args.limpiar:
        shutil.rmtree(vdir, ignore_errors=True)
        print("Datos de verificación eliminados.")
        return 0
    from tally_monitor.api.client import TallyClient
    from tally_monitor.core.errors import TallyMonitorError
    from tally_monitor.security.dpapi import WindowsDpapiProtector
    protector, client = WindowsDpapiProtector(), TallyClient(min_interval=0.75)
    try:
        if args.leer_local:
            read_local(vdir, protector, TallyClient(timeout=5, max_retries=0))
        else:
            run(vdir, protector, client, args.form)
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        return 130
    except TallyMonitorError as exc:
        print(f"\nSe detuvo por un error: {exc.user_message}")
        return 1
    ok = sum(1 for r, _ in base.RESULTS if r)
    print(f"\nResultado: {ok} de {len(base.RESULTS)} comprobaciones correctas.")
    for r, name in base.RESULTS:
        if not r:
            print("  FALLÓ:", name)
    return 0 if all(r for r, _ in base.RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())

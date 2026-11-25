"""Informe de sesión del «modo prueba»: un JSON que cuenta qué hizo la app, qué no, por qué y qué falló.

Reglas de privacidad (se aplican aquí, en un solo lugar):
- nunca se guarda la API Key ni texto de respuestas, ni nombres de cuentas o encuestas (solo «Cuenta 1», «Encuesta ID»);
- los textos libres se redactan (claves `tly-…`), se recortan y se les quita el nombre de usuario de Windows de las rutas;
- al terminar, el informe se revisa a sí mismo y se anota el resultado en `autorevision`.
"""
from __future__ import annotations

import json
import os
import platform
import re
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .redact import redact

FORMAT = 1
MAX_EVENTS = 6000
MAX_TEXT = 240
KEEP_REPORTS = 20
_TLY = re.compile(r"tly-[A-Za-z0-9_-]{4,}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_WIN_USER = re.compile(r"([A-Za-z]:[\\/]+Users[\\/]+)[^\\/\s\"']+", re.I)
_POSIX_USER = re.compile(r"(/home/|/Users/)[^/\s\"']+")


def scrub_text(value: object, limit: int = MAX_TEXT) -> str:
    s = redact(str(value))
    s = _WIN_USER.sub(r"\1<usuario>", s)
    s = _POSIX_USER.sub(r"\1<usuario>", s)
    s = _EMAIL.sub("<correo>", s)
    return s if len(s) <= limit else s[:limit] + "…"


def safe_value(v: object) -> object:
    """Solo valores simples. Lo demás se reduce a su tipo."""
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return scrub_text(v)
    if isinstance(v, (list, tuple, set, frozenset)):
        return {"len": len(v)}
    if isinstance(v, dict):
        return {"len": len(v)}
    return f"<{type(v).__name__}>"


def describe_exception(exc: BaseException, *, with_traceback: bool = True) -> dict:
    out = {"tipo": type(exc).__name__}
    for attr in ("category", "status", "kind"):
        val = getattr(exc, attr, None)
        if isinstance(val, (str, int)):
            out[{"category": "categoria", "status": "http", "kind": "detalle"}[attr]] = val
    msg = getattr(exc, "user_message", None) or str(exc)
    out["mensaje"] = scrub_text(msg)
    if with_traceback and exc.__traceback__ is not None:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        out["traza"] = scrub_text(tb, 4000)
    return out


# Puntos de verificación que se pueden saber mirando lo que pasó (los visuales no).
def _called(service: str, method: str, *, ok: bool | None = True, category: str | None = None):
    def pred(events):
        for e in events:
            if e.get("kind") == "llamada" and e.get("servicio") == service and e.get("metodo") == method:
                if category is not None and e.get("error", {}).get("categoria") == category:
                    return True
                if category is None and ok is not None and (e.get("resultado") == "ok") == ok:
                    return True
        return False
    return pred


def _sync_mode(mode: str):
    def pred(events):
        return any(e.get("kind") == "llamada" and e.get("metodo") == "sync_form" and
                   isinstance(e.get("resumen"), dict) and e["resumen"].get("mode") == mode for e in events)
    return pred


def _any_error(category: str):
    def pred(events):
        return any(e.get("kind") == "llamada" and e.get("error", {}).get("categoria") == category for e in events)
    return pred


def _visited(page: str):
    return lambda events: any(e.get("kind") == "pantalla" and e.get("pantalla") == page for e in events)


def _filter_used(kind: str):
    return lambda events: any(e.get("kind") == "filtro_analisis" and e.get("filtro") == kind for e in events)


def _clean_exit(events):
    return any(e.get("kind") == "cierre" and e.get("motivo") == "normal" for e in events)


COVERAGE: list[tuple[str, str, Callable[[list[dict]], bool]]] = [
    ("cuenta_agregar", "Agregar una cuenta con una clave válida", _called("accounts", "add_account")),
    ("cuenta_clave_invalida", "Intentar agregar una clave rechazada por Tally (debe dar error de autenticación)",
     _called("accounts", "add_account", category="auth")),
    ("cuenta_validar", "Validar una cuenta", _called("accounts", "validate_account")),
    ("cuenta_renombrar", "Renombrar una cuenta", _called("accounts", "rename_account")),
    ("cuenta_reemplazar", "Reemplazar la clave de una cuenta", _called("accounts", "replace_key")),
    ("cuenta_eliminar", "Eliminar una cuenta", _called("accounts", "delete_account")),
    ("backup_manual", "Crear una copia de seguridad manual", _called("backups", "create_manual")),
    ("backup_restaurar", "Restaurar una copia de seguridad", _called("backups", "restore")),
    ("ajustes", "Cambiar un ajuste", _called("settings", "set")),
    ("sync_lista", "Descargar la lista de encuestas", _called("sync", "sync_forms")),
    ("sync_inicial", "Primera sincronización de una encuesta", _sync_mode("initial")),
    ("sync_sin_cambios", "Sincronizar una encuesta sin cambios (no debe volver a descargar todo)", _sync_mode("nochange")),
    ("sync_incremental", "Sincronizar una encuesta con envíos nuevos", _sync_mode("incremental")),
    ("sync_completa", "Sincronización completa / reconciliación", _sync_mode("full")),
    ("error_red", "Un fallo de red bien clasificado (p. ej. sin Internet)", _any_error("network")),
    ("favoritos", "Marcar o desmarcar un favorito", _called("favorites", "set_favorite")),
    ("pantalla_encuestas", "Ver la pared de encuestas", _visited("encuestas")),
    ("pantalla_cuentas", "Abrir Cuentas", _visited("cuentas")),
    ("pantalla_configuracion", "Abrir Ajustes", _visited("configuracion")),
    ("pantalla_analisis", "Abrir la pestaña Resumen", _visited("analisis")),
    ("pantalla_respuestas", "Abrir la pestaña Respuestas", _visited("respuestas")),
    ("analisis_calculo", "Mostrar el análisis de una encuesta", _called("analysis", "analyze")),
    ("filtro_24h", "Usar el filtro «Últimas 24 horas»", _filter_used("24h")),
    ("filtro_7d", "Usar el filtro «Últimos 7 días»", _filter_used("7d")),
    ("filtro_30d", "Usar el filtro «Últimos 30 días»", _filter_used("30d")),
    ("filtro_rango", "Usar un rango personalizado de fechas", _filter_used("custom")),
    ("filtro_todo", "Volver a «Todo el período»", _filter_used("all")),
    ("pantalla_exportaciones", "Abrir la pestaña Exportar", _visited("exportaciones")),
    ("exportar_individual", "Exportar respuestas individuales", lambda ev: any(e.get("kind") == "exportar_pedida" and e.get("alcance") == "individual" for e in ev)),
    ("exportar_excel", "Exportar a Excel", _called("export", "export_xlsx")),
    ("exportar_pdf", "Exportar a PDF", _called("export", "export_pdf")),
    ("exportar_png", "Guardar los gráficos como PNG", _called("export", "save_png")),
    ("cierre_normal", "Cerrar la aplicación de forma normal", _clean_exit),
]


class SessionRecorder:
    """Acumula eventos (thread-safe) y los vuelca a un archivo JSON, de forma incremental y atómica."""

    def __init__(self, reports_dir: Path, *, app_version: str, frozen: bool = False,
                 flush_every: float = 1.0, monotonic=time.monotonic) -> None:
        self._dir = Path(reports_dir)
        self._lock = threading.RLock()
        self._mono, self._flush_every = monotonic, flush_every
        self._t0 = monotonic()
        self._started = datetime.now(timezone.utc)
        self._events: list[dict] = []
        self._dropped = 0
        self._seq = 0
        self._accounts: dict[str, str] = {}
        self._in_flight: dict[int, dict] = {}
        self._call_id = 0
        self._last_flush = 0.0
        self._closed = False
        self._final: dict = {}
        self._state_provider: Callable[[], dict] | None = None
        self.session_id = uuid.uuid4().hex[:12]
        self._app_version, self._frozen = app_version, frozen
        self.path = self._dir / f"informe-{self._started.strftime('%Y%m%d-%H%M%S')}-{self.session_id[:4]}.json"

    def now(self) -> float:
        return self._mono()

    # ---------- enmascarado ----------
    def mask_account(self, account_id: str) -> str:
        with self._lock:
            return self._accounts.setdefault(account_id, f"Cuenta {len(self._accounts) + 1}")

    def set_state_provider(self, fn: Callable[[], dict]) -> None:
        self._state_provider = fn

    # ---------- eventos ----------
    def event(self, kind: str, **data) -> None:
        with self._lock:
            if self._closed:
                return
            self._seq += 1
            ev = {"n": self._seq, "t": round(self._mono() - self._t0, 3), "kind": kind}
            ev.update({k: (v if isinstance(v, (dict, list)) else safe_value(v)) for k, v in data.items()})
            if len(self._events) >= MAX_EVENTS:
                self._dropped += 1
            else:
                self._events.append(ev)
            urgent = kind in ("error", "excepcion", "llamada") and data.get("resultado") == "error"
        self._maybe_flush(force=urgent or kind == "excepcion")

    def call_started(self, service: str, method: str, args: dict) -> int:
        with self._lock:
            self._call_id += 1
            cid = self._call_id
            self._in_flight[cid] = {"servicio": service, "metodo": method, "desde_s": round(self._mono() - self._t0, 3)}
        return cid

    def call_finished(self, cid: int, service: str, method: str, args: dict, started: float, *,
                      result: object = None, error: BaseException | None = None) -> None:
        with self._lock:
            self._in_flight.pop(cid, None)
        data = {"servicio": service, "metodo": method, "args": args,
                "ms": round((self._mono() - started) * 1000, 1)}
        if error is None:
            data["resultado"] = "ok"
            data["resumen"] = result
        else:
            data["resultado"] = "error"
            data["error"] = describe_exception(error)
        self.event("llamada", **data)

    def request(self, info: dict) -> None:
        """Solicitud a Tally (solo ruta genérica, código, tiempo y límite restante; jamás el contenido)."""
        self.event("solicitud", **{k: v for k, v in info.items() if k in
                                   ("metodo", "ruta", "consulta", "estado", "error", "ms", "restantes", "espera_s")})

    def log(self, level: str, logger: str, message: str) -> None:
        self.event("log", nivel=level, origen=logger, mensaje=message)

    # ---------- archivo ----------
    def _maybe_flush(self, *, force: bool = False) -> None:
        now = self._mono()
        if force or now - self._last_flush >= self._flush_every:
            self._write(complete=False)

    def _snapshot(self, complete: bool) -> dict:
        with self._lock:
            events = list(self._events)
            in_flight = list(self._in_flight.values())
            dropped = self._dropped
        calls: dict[str, dict] = {}
        errors, reqs = [], {"total": 0, "por_estado": {}, "por_error": {}}
        for e in events:
            if e["kind"] == "llamada":
                c = calls.setdefault(f"{e['servicio']}.{e['metodo']}", {"ok": 0, "error": 0, "ms_total": 0.0})
                c["ok" if e["resultado"] == "ok" else "error"] += 1
                c["ms_total"] = round(c["ms_total"] + e.get("ms", 0), 1)
                if e["resultado"] == "error":
                    errors.append({"n": e["n"], "t": e["t"], "donde": f"{e['servicio']}.{e['metodo']}", **e["error"]})
            elif e["kind"] in ("excepcion", "error"):
                errors.append({k: v for k, v in e.items() if k != "kind"} | {"donde": e["kind"]})
            elif e["kind"] == "solicitud":
                reqs["total"] += 1
                if "estado" in e:
                    reqs["por_estado"][str(e["estado"])] = reqs["por_estado"].get(str(e["estado"]), 0) + 1
                if e.get("error"):
                    reqs["por_error"][e["error"]] = reqs["por_error"].get(e["error"], 0) + 1
        coverage, missing = [], []
        for cid, text, pred in COVERAGE:
            try:
                done = bool(pred(events))
            except Exception:  # noqa: BLE001
                done = False
            coverage.append({"id": cid, "descripcion": text, "cubierto": done})
            if not done:
                missing.append(cid)
        state = {}
        if complete and self._state_provider:
            try:
                state = self._state_provider()
            except Exception as exc:  # noqa: BLE001 - el informe nunca debe impedir cerrar
                state = {"error": describe_exception(exc, with_traceback=False)}
        return {
            "formato": FORMAT,
            "modo": "prueba",
            "completo": complete,
            "sesion": self.session_id,
            "aviso": ("Este informe no contiene la API Key, respuestas de personas ni nombres de cuentas o encuestas. "
                      "Las cuentas se llaman «Cuenta N»."),
            "inicio_utc": self._started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fin_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if complete else None,
            "duracion_s": round(self._mono() - self._t0, 1),
            "entorno": self._environment(),
            "salida": self._final or ({"motivo": "en curso o interrumpida"} if not complete else {}),
            "llamadas_en_curso": in_flight,
            "resumen": {"llamadas": calls, "errores": errors, "solicitudes_tally": reqs,
                        "eventos": len(events), "eventos_descartados": dropped},
            "cobertura": {"cubiertos": len(coverage) - len(missing), "total": len(coverage),
                          "no_cubiertos": missing, "detalle": coverage,
                          "nota": "Solo cuenta lo observable por el programa; lo puramente visual lo confirmás vos."},
            "estado_final": state,
            "eventos": events,
        }

    def _environment(self) -> dict:
        env = {"app": self._app_version, "python": platform.python_version(), "sistema": platform.system(),
               "sistema": f"{platform.system()} {platform.version()}", "arquitectura": platform.machine(), "empaquetado": self._frozen,
               "zona_horaria_utc": datetime.now().astimezone().strftime("%z")}
        try:
            import PySide6
            env["pyside6"] = PySide6.__version__
        except Exception:  # noqa: BLE001
            env["pyside6"] = None
        return env

    def _write(self, *, complete: bool) -> None:
        try:
            doc = self._snapshot(complete)
            text = json.dumps(doc, ensure_ascii=False, indent=1)
            check = {"clave_tly": bool(_TLY.search(text)), "correo": bool(_EMAIL.search(text))}
            if check["clave_tly"] or check["correo"]:
                text = _EMAIL.sub("<correo>", redact(text))
            if complete:
                doc["autorevision"] = {"patron_clave_encontrado": check["clave_tly"],
                                       "correo_encontrado": check["correo"],
                                       "accion": "redactado" if any(check.values()) else "ninguna"}
                text = json.dumps(doc, ensure_ascii=False, indent=1)
                text = _EMAIL.sub("<correo>", redact(text))
            self._dir.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, self.path)
            self._last_flush = self._mono()
        except Exception:  # noqa: BLE001 - jamás romper la app por el informe
            pass

    def finish(self, motivo: str, *, error: BaseException | None = None) -> Path:
        """Cierra el informe (idempotente) y devuelve su ruta."""
        with self._lock:
            if self._closed:
                return self.path
        self.event("cierre", motivo=motivo)
        with self._lock:
            self._closed = True
            self._final = {"motivo": motivo}
            if error is not None:
                self._final["error"] = describe_exception(error)
        self._write(complete=True)
        self._prune()
        return self.path

    def _prune(self) -> None:
        try:
            old = sorted(self._dir.glob("informe-*.json"))
            for p in old[:-KEEP_REPORTS]:
                p.unlink()
        except OSError:
            pass


def current_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))

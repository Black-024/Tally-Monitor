"""Conteos y comprobaciones para el informe del modo prueba. Solo cifras: nunca nombres ni respuestas."""
from __future__ import annotations

from .database import Database

_TABLES = ("data_account", "data_form", "data_question", "data_submission", "data_answer", "state_user_number",
           "state_favorite", "state_recent", "state_sync", "raw_form", "raw_submission")


class DiagnosticsRepository:
    def __init__(self, library: Database, cache: Database) -> None:
        self._lib, self._cache = library, cache

    def snapshot(self) -> dict:
        out: dict = {}
        for name, db in (("library", self._lib), ("cache", self._cache)):
            info: dict = {"existe": db.path.exists()}
            if info["existe"]:
                info["tamano_bytes"] = db.path.stat().st_size
                info["version_esquema"] = db.user_version()
                info["integridad_ok"] = db.quick_check() == []
            out[name] = info
        if out["library"].get("integridad_ok"):
            with self._lib.connection() as c:
                counts = {}
                for t in _TABLES:
                    try:
                        counts[t] = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    except Exception:  # noqa: BLE001 - tabla aún no creada en un esquema antiguo
                        counts[t] = None
                out["library"]["filas"] = counts
                out["library"]["cuentas_por_estado"] = {
                    r[0]: r[1] for r in c.execute("SELECT status, COUNT(*) FROM data_account GROUP BY status")}
                try:
                    out["library"]["envios_desaparecidos_del_origen"] = c.execute(
                        "SELECT COUNT(*) FROM data_submission WHERE missing_at_source_at IS NOT NULL").fetchone()[0]
                    out["library"]["envios_sin_numero"] = c.execute(
                        "SELECT COUNT(*) FROM data_submission s LEFT JOIN state_user_number n ON "
                        "n.account_id=s.account_id AND n.submission_id=s.submission_id WHERE n.number IS NULL"
                        " AND s.missing_at_source_at IS NULL").fetchone()[0]
                except Exception:  # noqa: BLE001
                    pass
        return out

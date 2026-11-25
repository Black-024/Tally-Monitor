"""Aviso de respuestas nuevas (solo local): decide si hay que notificar y evita repetir el mismo aviso.
Sin Qt: el reloj y los servicios se inyectan, así se prueba sin interfaz. La interfaz solo agenda y muestra."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..api.errors import ApiAuthError, ApiError
from ..core.clock import Clock
from ..core.errors import TallyMonitorError
from ..core.language import pick as _t
from .settings_service import SettingsService

log = logging.getLogger(__name__)

INTERVALS = (15, 30, 60, 360)
DEFAULT_INTERVAL = 60
_SKIP_STATUS = ("no_credential", "key_rejected")        # sin clave utilizable no hay nada que consultar


@dataclass(frozen=True)
class CheckOutcome:
    total: int                   # respuestas de Tally que todavía no están guardadas (encuestas no archivadas)
    surveys: int                 # en cuántas encuestas
    notify: bool
    title: str = ""
    body: str = ""
    errors: int = 0              # cuentas que fallaron (red/401/429/…): si hay, no se avisa ni se toca el estado
    checked_at: str = ""


def notification_text(total: int, surveys: int) -> tuple[str, str]:
    if _t("es", "en") == "es":
        t = f"{total} respuesta" + ("" if total == 1 else "s") + (" nueva" if total == 1 else " nuevas")
        s = f"{surveys} encuesta" + ("" if surveys == 1 else "s")
        return f"{t} en {s}", "Tocá para abrir Tally Monitor"
    t = f"{total} new response" + ("" if total == 1 else "s")
    s = f"{surveys} survey" + ("" if surveys == 1 else "s")
    return f"{t} in {s}", "Tap to open Tally Monitor"


class NewResponsesChecker:
    def __init__(self, accounts, sync, surveys, settings: SettingsService, clock: Clock | None = None) -> None:
        self._accounts, self._sync, self._surveys, self._settings = accounts, sync, surveys, settings
        self._clock = clock or Clock()

    # ---------- ajustes ----------
    def is_enabled(self) -> bool:
        return self._settings.get("notify_mode") == "on"

    def interval_minutes(self) -> int:
        try:
            v = int(self._settings.get("notify_interval_min"))
        except ValueError:
            return DEFAULT_INTERVAL
        return v if v in INTERVALS else DEFAULT_INTERVAL

    def set_enabled(self, on: bool) -> None:
        self._settings.set("notify_mode", "on" if on else "off")

    def set_interval(self, minutes: int) -> None:
        if minutes not in INTERVALS:
            raise ValueError("Intervalo inválido")
        self._settings.set("notify_interval_min", str(minutes))

    def notified_total(self) -> int:
        try:
            return max(0, int(self._settings.get("notified_new_total")))
        except ValueError:
            return 0

    # ---------- chequeo ----------
    def check(self) -> CheckOutcome:
        """Trae solo el listado de encuestas de cada cuenta con clave y suma lo que falta guardar.
        Se notifica solo si el total subió respecto del último guardado y es > 0. Los errores son silenciosos."""
        errors = 0
        per_account: list[str] = []
        for acc in self._accounts.list_accounts():
            if acc.status in _SKIP_STATUS:
                continue
            try:
                self._sync.sync_forms(acc.account_id)
                per_account.append(acc.account_id)
            except ApiAuthError:
                errors += 1
                try:
                    self._accounts.validate_account(acc.account_id)      # igual que hoy: queda «Clave rechazada»
                except TallyMonitorError:
                    pass
            except (ApiError, TallyMonitorError) as exc:
                errors += 1
                log.info("Chequeo de respuestas nuevas: %s", type(exc).__name__)
        now = self._clock.iso()
        if errors:
            return CheckOutcome(0, 0, False, errors=errors, checked_at=now)
        total = surveys = 0
        for aid in per_account:
            for s in self._surveys.list_surveys(aid):
                if s.archived:
                    continue
                gap = max(0, (s.reported_submissions or 0) - s.local_submissions)
                if gap:
                    total += gap
                    surveys += 1
        previous = self.notified_total()
        notify = total > 0 and total > previous
        self._settings.set("notified_new_total", str(total))
        title, body = notification_text(total, surveys) if notify else ("", "")
        return CheckOutcome(total, surveys, notify, title, body, 0, now)

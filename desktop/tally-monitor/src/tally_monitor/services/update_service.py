"""Aviso opcional de versión nueva. Apagado por defecto; nunca descarga ni instala nada."""
from __future__ import annotations

from dataclasses import dataclass

from ..api.update_client import UpdateClient
from ..core.versioning import is_newer
from .settings_service import SettingsService


@dataclass(frozen=True)
class UpdateStatus:
    state: str                     # disabled | not_configured | up_to_date | available | error
    latest: str | None = None
    url: str | None = None


class UpdateService:
    def __init__(self, client: UpdateClient, settings: SettingsService, current_version: str, repo: str) -> None:
        self._client, self._settings, self._current, self._repo = client, settings, current_version, repo

    def enabled(self) -> bool:
        return self._settings.get("update_check") == "1"

    def set_enabled(self, on: bool) -> None:
        self._settings.set("update_check", "1" if on else "0")

    def check(self, *, force: bool = False) -> UpdateStatus:
        """`force` = el usuario apretó «Buscar ahora». Sin eso, solo consulta si el aviso está activado."""
        if not force and not self.enabled():
            return UpdateStatus("disabled")
        if not self._repo:
            return UpdateStatus("not_configured")
        try:
            rel = self._client.latest_release(self._repo)
        except Exception:  # noqa: BLE001 - un aviso nunca debe romper ni molestar
            return UpdateStatus("error")
        if is_newer(rel.tag, self._current):
            return UpdateStatus("available", rel.tag.lstrip("v"), rel.url)
        return UpdateStatus("up_to_date", rel.tag.lstrip("v"))

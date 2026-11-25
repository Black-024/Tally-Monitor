"""Consulta pública de la última versión en GitHub. Un único GET, SIN API Key ni datos del usuario."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from .errors import ApiNetworkError, ApiUnexpectedError

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}/[A-Za-z0-9_.-]{1,100}$")
_MAX_BODY = 262_144


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401
        return None


@dataclass(frozen=True)
class LatestRelease:
    tag: str
    url: str


class UpdateClient:
    def __init__(self, base_url: str = "https://api.github.com", *, timeout: float = 8.0) -> None:
        self._base, self._timeout = base_url.rstrip("/"), timeout
        self._opener = urllib.request.build_opener(_NoRedirect)

    def latest_release(self, repo: str) -> LatestRelease:
        if not _REPO_RE.match(repo or ""):
            raise ValueError("Repositorio inválido")
        req = urllib.request.Request(f"{self._base}/repos/{repo}/releases/latest", method="GET",
                                     headers={"Accept": "application/vnd.github+json", "User-Agent": "TallyMonitor-update-check"})
        try:
            with self._opener.open(req, timeout=self._timeout) as resp:
                body = resp.read(_MAX_BODY + 1)
                status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            raise ApiUnexpectedError(status) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise ApiNetworkError(type(exc).__name__) from None
        if len(body) > _MAX_BODY:
            raise ApiUnexpectedError(status)
        try:
            obj = json.loads(body)
        except ValueError:
            raise ApiUnexpectedError(status) from None
        tag, url = (obj.get("tag_name"), obj.get("html_url")) if isinstance(obj, dict) else (None, None)
        if not isinstance(tag, str) or not isinstance(url, str):
            raise ApiUnexpectedError(status)
        # solo se acepta un enlace de GitHub a ese mismo repositorio (es lo único que luego se abre en el navegador)
        if not url.startswith(f"https://github.com/{repo}/"):
            raise ApiUnexpectedError(status)
        return LatestRelease(tag[:40], url)

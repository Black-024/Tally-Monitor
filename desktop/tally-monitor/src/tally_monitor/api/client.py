"""Cliente de Tally de SOLO LECTURA. Único módulo de la aplicación que usa la red."""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse

from ..core.secret import SecretStr
from .errors import (ApiAuthError, ApiNetworkError, ApiRateLimitError, ApiServerError,
                     ApiUnexpectedError)

log = logging.getLogger(__name__)

BASE_URL = "https://api.tally.so"
USER_AGENT = "TallyMonitor/0.1 (lectura; escritorio)"   # Tally rechaza el User-Agent por defecto de Python
_RETRY_5XX = {500, 502, 503, 504}
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")     # los IDs de Tally; evita inyectar rutas o parámetros
_MAX_BODY = 25_000_000
MAX_PAGE_SIZE = 500


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """No seguir redirecciones: urllib reenvía cabeceras (incluida Authorization) al nuevo destino."""
    def redirect_request(self, *args, **kwargs):  # noqa: D401
        return None


@dataclass(frozen=True)
class TallyUser:
    """Lo único que se conserva de /users/me: el id opaco (puede faltar)."""
    tally_user_id: str | None


@dataclass(frozen=True)
class RateInfo:
    limit: int | None
    remaining: int | None
    reset_epoch: float | None


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


_ROUTE_ID = re.compile(r"^(/forms/)[^/]+")


def describe_request(path: str) -> tuple[str, dict]:
    """Ruta genérica (sin IDs) y parámetros de consulta no sensibles, para el informe del modo prueba."""
    base, _, query = path.partition("?")
    params = {}
    for part in query.split("&") if query else []:
        k, _, v = part.partition("=")
        if k in ("page", "limit", "filter"):
            params[k] = v[:12]
        elif k in ("startDate", "endDate"):
            params[k] = True
    return _ROUTE_ID.sub(r"\1{id}", base), params


def _check_id(value: str, what: str = "id") -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValueError(f"Identificador de {what} inválido")
    return value


class TallyClient:
    def __init__(self, base_url: str = BASE_URL, *, timeout: float = 20.0, max_retries: int = 2,
                 max_wait: float = 30.0, sleep=time.sleep, min_interval: float = 0.0,
                 wall_clock=time.time, monotonic=time.monotonic, on_event=None) -> None:
        u = urlparse(base_url)
        if u.scheme != "https" and not (u.scheme == "http" and u.hostname in _LOCAL_HOSTS):
            raise ValueError("La API Key solo se envía por HTTPS (HTTP solo hacia localhost en pruebas).")
        self._base = base_url.rstrip("/")
        self._timeout, self._max_retries, self._max_wait, self._sleep = timeout, max_retries, max_wait, sleep
        self._opener = urllib.request.build_opener(_NoRedirect)
        # Ritmo de solicitudes: separación mínima y respeto de x-ratelimit-* (límite ~100 por ventana).
        self._min_interval, self._wall, self._mono = min_interval, wall_clock, monotonic
        self._last_request = None
        self.rate = RateInfo(None, None, None)
        self.request_count = 0
        self._on_event = on_event        # solo para el modo prueba: recibe datos genéricos, nunca claves ni cuerpos

    # ---------- operaciones ----------
    def get_current_user(self, api_key: SecretStr) -> TallyUser:
        obj = self._get_json("/users/me", api_key)
        uid = obj.get("id")
        return TallyUser(uid if isinstance(uid, str) and uid else None)

    def list_forms(self, api_key: SecretStr, *, page: int = 1) -> dict:
        return self._get_json(f"/forms?{urlencode({'page': int(page)})}", api_key)

    def get_form(self, api_key: SecretStr, form_id: str) -> dict:
        return self._get_json(f"/forms/{_check_id(form_id, 'formulario')}", api_key)

    def get_questions(self, api_key: SecretStr, form_id: str) -> dict:
        return self._get_json(f"/forms/{_check_id(form_id, 'formulario')}/questions", api_key)

    def list_submissions(self, api_key: SecretStr, form_id: str, *, page: int = 1, limit: int = MAX_PAGE_SIZE,
                         start_date: str | None = None, end_date: str | None = None,
                         filter: str = "all") -> dict:
        if filter not in ("all", "completed", "partial"):
            raise ValueError("Filtro inválido")
        params = {"page": int(page), "limit": max(1, min(int(limit), MAX_PAGE_SIZE)), "filter": filter}
        for key, val in (("startDate", start_date), ("endDate", end_date)):
            if val is not None:
                if not isinstance(val, str) or not re.match(r"^[0-9T:.\-]+Z$", val):
                    raise ValueError("Fecha inválida (se espera ISO UTC terminada en Z)")
                params[key] = val
        return self._get_json(f"/forms/{_check_id(form_id, 'formulario')}/submissions?{urlencode(params)}", api_key)

    # ---------- núcleo ----------
    def _get_json(self, path: str, api_key: SecretStr) -> dict:
        status, body = self._get(path, api_key)
        try:
            obj = json.loads(body)
        except ValueError as exc:
            raise ApiUnexpectedError(status) from exc
        if not isinstance(obj, dict):
            raise ApiUnexpectedError(status)
        return obj

    def _pace(self) -> None:
        """Espera antes de pedir: separación mínima y, si la ventana está agotada, hasta su reinicio."""
        r = self.rate
        if r.remaining is not None and r.remaining <= 2 and r.reset_epoch is not None:
            wait = min(max(0.0, r.reset_epoch - self._wall()), self._max_wait)
            if wait > 0:
                log.info("Ventana de solicitudes agotada; esperando %.1fs", wait)
                if self._on_event:
                    self._on_event({"espera_s": round(wait, 1), "ruta": "(ventana agotada)"})
                self._sleep(wait)
            self.rate = RateInfo(r.limit, None, None)
        if self._min_interval and self._last_request is not None:
            gap = self._min_interval - (self._mono() - self._last_request)
            if gap > 0:
                self._sleep(gap)

    def _note_rate(self, headers) -> None:
        if headers is None:
            return
        self.rate = RateInfo(_int(headers.get("x-ratelimit-limit")), _int(headers.get("x-ratelimit-remaining")),
                             float(headers["x-ratelimit-reset"]) if _int(headers.get("x-ratelimit-reset"))
                             is not None else None)

    def _get(self, path: str, api_key: SecretStr) -> tuple[int, bytes]:
        """GET con reintentos para 429 y 5xx. No existe ningún otro método HTTP en este cliente."""
        attempt = 0
        while True:
            try:
                return self._single_get(path, api_key)
            except (ApiRateLimitError, ApiServerError) as exc:
                if attempt >= self._max_retries:
                    raise
                wait = getattr(exc, "retry_after", None)
                wait = min(wait if wait is not None else 2.0 * (attempt + 1), self._max_wait)
                log.info("Reintentando en %.1fs (%s)", wait, exc.category)
                self._sleep(wait)
                attempt += 1

    def _single_get(self, path: str, api_key: SecretStr) -> tuple[int, bytes]:
        req = urllib.request.Request(
            self._base + path, method="GET",
            headers={"Authorization": f"Bearer {api_key.reveal()}", "Accept": "application/json",
                     "User-Agent": USER_AGENT})
        self._pace()
        self._last_request = self._mono()
        self.request_count += 1
        t0 = self._mono()
        try:
            status, body = self._open(req)
            self._emit(path, t0, estado=status)
            return status, body
        except BaseException as exc:
            self._emit(path, t0, estado=getattr(exc, "status", None),
                       error=getattr(exc, "category", type(exc).__name__))
            raise

    def _emit(self, path: str, t0: float, **extra) -> None:
        if self._on_event is None:
            return
        try:
            ruta, consulta = describe_request(path)
            self._on_event({"metodo": "GET", "ruta": ruta, "consulta": consulta,
                            "ms": round((self._mono() - t0) * 1000, 1), "restantes": self.rate.remaining,
                            **{k: v for k, v in extra.items() if v is not None}})
        except Exception:  # noqa: BLE001 - observar nunca debe romper una solicitud
            pass

    def _open(self, req) -> tuple[int, bytes]:
        try:
            with self._opener.open(req, timeout=self._timeout) as resp:
                self._note_rate(resp.headers)
                body = resp.read(_MAX_BODY + 1)
                if len(body) > _MAX_BODY:
                    raise ApiUnexpectedError(resp.status)
                return resp.status, body
        except urllib.error.HTTPError as exc:
            status = exc.code
            self._note_rate(exc.headers)
            retry_after = self._parse_retry_after(exc.headers.get("Retry-After") if exc.headers else None)
            exc.close()
            if status in (401, 403):
                raise ApiAuthError(status) from None
            if status == 429:
                raise ApiRateLimitError(retry_after) from None
            if status in _RETRY_5XX or status >= 500:
                raise ApiServerError(status) from None
            raise ApiUnexpectedError(status) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            # Solo el nombre de la clase: nunca el mensaje (podría incluir la URL o cabeceras).
            raise ApiNetworkError(type(exc).__name__) from None

    @staticmethod
    def _parse_retry_after(value: str | None) -> float | None:
        try:
            return max(0.0, float(value)) if value is not None else None
        except ValueError:
            return None

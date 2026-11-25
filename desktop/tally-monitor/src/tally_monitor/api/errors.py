"""Errores del cliente de Tally, separados por causa. Ninguno contiene la clave ni el cuerpo de la respuesta."""
from __future__ import annotations

from ..core.errors import TallyMonitorError
from ..core.language import pick as _t


class ApiError(TallyMonitorError):
    category = "unexpected"
    default_message = _t("Tally respondió de forma inesperada.", "Tally responded unexpectedly.")


class ApiAuthError(ApiError):
    """401/403 con el User-Agent correcto: Tally rechazó la clave."""
    category = "auth"
    default_message = _t("Tally rechazó la API Key (no autorizada o sin permisos).", "Tally rejected the API Key (unauthorized or insufficient permissions).")

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(_t(f"Tally rechazó la API Key (HTTP {status}).", f"Tally rejected the API Key (HTTP {status})."))


class ApiNetworkError(ApiError):
    category = "network"
    default_message = _t("No se pudo conectar con Tally. Revisá tu conexión a Internet.", "Could not connect to Tally. Check your Internet connection.")

    def __init__(self, kind: str = "") -> None:
        self.kind = kind  # solo el nombre de la clase de la excepción
        super().__init__()


class ApiRateLimitError(ApiError):
    category = "rate_limit"
    default_message = _t("Tally limitó las solicitudes (demasiadas en poco tiempo). Probá de nuevo en un minuto.", "Tally limited the requests (too many in a short time). Try again in a minute.")

    def __init__(self, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__()


class ApiServerError(ApiError):
    category = "server"

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(_t(f"El servicio de Tally no está disponible ahora (HTTP {status}). Probá más tarde.", f"The Tally service is not available right now (HTTP {status}). Try again later."))


class ApiUnexpectedError(ApiError):
    category = "unexpected"

    def __init__(self, status: int | None = None) -> None:
        self.status = status
        msg = _t("Tally respondió de forma inesperada", "Tally responded unexpectedly") + (f" (HTTP {status})." if status else ".")
        super().__init__(msg)

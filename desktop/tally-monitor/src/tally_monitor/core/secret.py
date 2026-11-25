"""Valor secreto que no se imprime, no se serializa y no aparece en trazas."""
from __future__ import annotations

import hmac


class SecretStr:
    """Envuelve una cadena secreta (p. ej. una API Key).

    str(), repr(), format() y f-strings devuelven '***'. No se puede serializar
    con pickle ni copiar por accidente a un JSON. Para usar el valor hay que
    llamar a reveal() de forma explícita.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError("SecretStr requiere una cadena")
        object.__setattr__(self, "_value", value)

    def __setattr__(self, name, value):  # inmutable
        raise AttributeError("SecretStr es inmutable")

    def reveal(self) -> str:
        return self._value

    def __len__(self) -> int:
        return len(self._value)

    def __bool__(self) -> bool:
        return bool(self._value)

    def matches(self, other: "SecretStr") -> bool:
        """Comparación en tiempo constante."""
        return hmac.compare_digest(self._value.encode("utf-8"), other._value.encode("utf-8"))

    def __str__(self) -> str:
        return "***"

    def __repr__(self) -> str:
        return "SecretStr('***')"

    def __format__(self, spec: str) -> str:
        return "***"

    def __eq__(self, other: object) -> bool:  # evita comparar por accidente con ==
        return NotImplemented

    __hash__ = None  # type: ignore[assignment]

    def __reduce__(self):
        raise TypeError("SecretStr no se puede serializar")

    def __copy__(self):
        raise TypeError("SecretStr no se puede copiar")

    def __deepcopy__(self, memo):
        raise TypeError("SecretStr no se puede copiar")

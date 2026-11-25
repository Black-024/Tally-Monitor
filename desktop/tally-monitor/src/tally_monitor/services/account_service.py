"""Gestión de cuentas: alta, validación, renombrado, reemplazo de clave y baja."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from ..api.client import TallyClient
from ..api.errors import ApiError
from ..core.clock import Clock
from ..core.language import pick as _t
from ..core.keyformat import looks_like_api_key
from ..core.errors import (AccountNameTakenError, CredentialError, DuplicateKeyError,
                           InvalidAccountNameError, InvalidKeyFormatError,
                           KeyBelongsToOtherAccountError)
from ..core.secret import SecretStr
from ..security.credential_store import CredentialStore
from ..storage.accounts_repo import Account, AccountsRepository  # noqa: F401  (Account se re-exporta a la interfaz)

log = logging.getLogger(__name__)
MAX_NAME = 60

_CATEGORY_STATUS = {"ok": "active", "auth": "key_rejected"}   # el resto: check_failed


@dataclass(frozen=True)
class ValidationOutcome:
    account: Account
    result: str                  # ok | auth | network | rate_limit | server | unexpected | no_credential
    message: str


@dataclass(frozen=True)
class ReplaceResult:
    account: Account
    identity_verified: bool      # False si no se pudo comparar el usuario de Tally (falta el id anterior o el nuevo)


class AccountService:
    def __init__(self, repo: AccountsRepository, store: CredentialStore, client: TallyClient,
                 clock: Clock | None = None) -> None:
        self._repo, self._store, self._client = repo, store, client
        self._clock = clock or Clock()

    # ---------- consultas ----------
    def list_accounts(self) -> list[Account]:
        return self._repo.list()

    def get_account(self, account_id: str) -> Account:
        return self._repo.get(account_id)

    # ---------- validaciones internas ----------
    @staticmethod
    def _clean_name(name: str) -> str:
        n = (name or "").strip()
        if not 1 <= len(n) <= MAX_NAME:
            raise InvalidAccountNameError()
        return n

    def _check_duplicate_key(self, api_key: SecretStr, *, exclude_id: str | None = None) -> None:
        for aid, cred in self._store.iter_credentials():
            if aid != exclude_id and cred.api_key.matches(api_key):
                raise DuplicateKeyError()

    @staticmethod
    def _check_key_shape(api_key: SecretStr) -> None:
        # Se rechaza ANTES de llamar a la red: una clave mal pegada (vacía, con espacios o
        # caracteres de control) no debe llegar a Tally ni confundirse con una clave rechazada.
        if not looks_like_api_key(api_key.reveal()):
            raise InvalidKeyFormatError()

    # ---------- alta ----------
    def add_account(self, name: str, api_key: SecretStr) -> Account:
        """Valida contra Tally y recién entonces guarda (clave cifrada primero, cuenta después).
        Si algo falla no queda ningún residuo. Los errores de Tally (ApiError) se propagan."""
        name = self._clean_name(name)
        self._check_key_shape(api_key)
        if self._repo.name_exists(name):
            raise AccountNameTakenError()
        self._check_duplicate_key(api_key)
        user = self._client.get_current_user(api_key)          # puede lanzar ApiError
        account = self._repo.add(name, status="active", last_check_result="ok", validated=True)
        try:
            self._store.save(account.account_id, api_key, user.tally_user_id)
        except Exception:
            self._repo.delete(account.account_id)               # deshacer
            raise
        log.info("Cuenta agregada")
        return account

    # ---------- validación ----------
    def validate_account(self, account_id: str) -> ValidationOutcome:
        """Comprueba la clave guardada. Solo un rechazo de autenticación marca 'Clave rechazada';
        red, límites y errores del servidor dejan 'No se pudo verificar' sin tocar la clave."""
        self._repo.get(account_id)  # existe
        try:
            cred = self._store.load(account_id)
        except CredentialError:
            cred = None
        if cred is None:
            acct = self._repo.set_status(account_id, "no_credential")
            return ValidationOutcome(acct, "no_credential", _t("Falta la clave de esta cuenta: reemplazala.", "This account has no key: replace it."))
        try:
            user = self._client.get_current_user(cred.api_key)
        except ApiError as exc:
            status = _CATEGORY_STATUS.get(exc.category, "check_failed")
            acct = self._repo.set_check(account_id, status=status, result=exc.category)
            return ValidationOutcome(acct, exc.category, exc.user_message)
        if cred.tally_user_id is None and user.tally_user_id is not None:
            self._store.save(account_id, cred.api_key, user.tally_user_id)   # completar la identidad
        acct = self._repo.set_check(account_id, status="active", result="ok")
        return ValidationOutcome(acct, "ok", _t("La clave es válida.", "The key is valid."))

    def validate_all(self) -> list[ValidationOutcome]:
        return [self.validate_account(a.account_id) for a in self._repo.list()]

    # ---------- renombrar ----------
    def rename_account(self, account_id: str, new_name: str) -> Account:
        return self._repo.rename(account_id, self._clean_name(new_name))

    # ---------- reemplazar clave ----------
    def replace_key(self, account_id: str, new_key: SecretStr) -> ReplaceResult:
        """La clave anterior se conserva si la nueva falla la validación, si ya está en otra
        cuenta o si pertenece a otro usuario de Tally."""
        account = self._repo.get(account_id)
        self._check_key_shape(new_key)
        self._check_duplicate_key(new_key, exclude_id=account_id)
        try:
            old = self._store.load(account_id)
        except CredentialError:
            old = None
        user = self._client.get_current_user(new_key)          # si falla, no se toca nada
        verified = False
        if old is not None and old.tally_user_id and user.tally_user_id:
            if old.tally_user_id != user.tally_user_id:
                raise KeyBelongsToOtherAccountError()
            verified = True
        self._store.save(account_id, new_key, user.tally_user_id or (old.tally_user_id if old else None))
        account = self._repo.set_check(account_id, status="active", result="ok")
        log.info("Clave reemplazada")
        return ReplaceResult(account, verified)

    # ---------- eliminar ----------
    def delete_account(self, account_id: str) -> None:
        """Primero la clave cifrada y después la fila: nunca queda una clave huérfana tras una baja."""
        self._repo.get(account_id)
        self._store.delete(account_id)
        self._repo.delete(account_id)
        log.info("Cuenta eliminada")

    # ---------- coherencia ----------
    def reconcile_credentials(self) -> dict[str, list[str]]:
        """Claves sin cuenta → se eliminan. Cuentas sin clave legible → 'Sin credencial'."""
        accounts = self._repo.list()
        orphans = self._store.purge_orphans({a.account_id for a in accounts})
        flagged = []
        for a in accounts:
            try:
                ok = self._store.load(a.account_id) is not None
            except CredentialError:
                ok = False
            if not ok and a.status != "no_credential":
                self._repo.set_status(a.account_id, "no_credential")
                flagged.append(a.account_id)
        return {"orphans_removed": orphans, "marked_no_credential": flagged}

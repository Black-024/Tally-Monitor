"""Errores de la aplicación. Todos llevan un mensaje seguro (sin claves) para el usuario."""
from __future__ import annotations

from .language import pick as _t
from .redact import redact


class TallyMonitorError(Exception):
    """Base. `user_message` es apto para mostrarse en la interfaz."""

    default_message = _t("Ocurrió un error inesperado.",
        "An unexpected error occurred.")

    def __init__(self, user_message: str | None = None) -> None:
        self.user_message = redact(user_message or self.default_message)
        super().__init__(self.user_message)


# --- almacenamiento ---
class StorageError(TallyMonitorError):
    default_message = _t("Error en el almacenamiento local.",
        "Local storage error.")


class DatabaseTooNewError(StorageError):
    default_message = _t(("La base de datos fue creada por una versión más nueva de Tally Monitor. "
                       "Actualizá la aplicación; no se modificó nada."),
        "The database was created by a newer version of Tally Monitor. Update the app; nothing was changed.")


class MigrationError(StorageError):
    default_message = _t("Falló la actualización de la base de datos. Se conservó la copia previa.",
        "The database update failed. The previous copy was kept.")


class BackupError(StorageError):
    default_message = _t("No se pudo crear o usar la copia de seguridad.",
        "The backup could not be created or used.")


class BackupTooNewError(BackupError):
    default_message = _t("La copia de seguridad es de una versión más nueva de la aplicación.",
        "The backup comes from a newer version of the app.")


class RestoreFailedError(BackupError):
    default_message = _t("La restauración falló; se volvió al estado anterior.",
        "The restore failed; the previous state was recovered.")


# --- credenciales ---
class CredentialError(TallyMonitorError):
    default_message = _t("Error con el almacén de credenciales.",
        "Credential store error.")


class ProtectionUnavailableError(CredentialError):
    default_message = _t(("No hay un almacenamiento seguro disponible para la API Key en este sistema; "
                       "no se guardan claves sin cifrar."),
        "No secure storage is available for the API Key on this system; keys are never stored unencrypted.")


class CredentialUnreadableError(CredentialError):
    default_message = _t("No se pudo descifrar la clave guardada (¿otro usuario o equipo, o se borró del llavero?).",
        "The stored key could not be decrypted (different user or computer, or removed from the keychain?).")


# --- cuentas ---
class AccountError(TallyMonitorError):
    default_message = _t("Error en la gestión de cuentas.",
        "Account management error.")


class InvalidAccountNameError(AccountError):
    default_message = _t("El nombre debe tener entre 1 y 60 caracteres.",
        "The name must be between 1 and 60 characters.")


class AccountNameTakenError(AccountError):
    default_message = _t("Ya existe una cuenta con ese nombre.",
        "An account with that name already exists.")


class AccountNotFoundError(AccountError):
    default_message = _t("La cuenta no existe.",
        "The account does not exist.")


class DuplicateKeyError(AccountError):
    default_message = _t("Esa API Key ya está guardada en otra cuenta.",
        "That API Key is already saved in another account.")


class KeyBelongsToOtherAccountError(AccountError):
    default_message = _t(("La nueva clave pertenece a otro usuario de Tally. "
                       "Se conservó la clave anterior."),
        "The new key belongs to a different Tally user. The previous key was kept.")


class InvalidKeyFormatError(AccountError):
    default_message = _t(("La API Key no tiene el formato esperado: debe empezar con «tly-» y no "
                       "contener espacios ni caracteres de control."),
        "The API Key does not have the expected format: it must start with \"tly-\" and contain no spaces or control characters.")


class SyncCancelled(TallyMonitorError):
    default_message = _t("La sincronización se canceló.",
        "The sync was cancelled.")


class InvalidSurveyMetaError(TallyMonitorError):
    default_message = _t("Los datos de la encuesta no son válidos.",
        "The survey data is not valid.")


class InvalidFilterError(TallyMonitorError):
    default_message = _t("Ese filtro por respuesta no se puede aplicar a esa pregunta.",
        "That answer filter cannot be applied to that question.")


class SurveyNotFoundError(TallyMonitorError):
    default_message = _t("No se encontró esa encuesta en la copia local. Sincronizá la cuenta primero.",
        "That survey was not found in the local copy. Sync the account first.")


class ExportError(TallyMonitorError):
    default_message = _t("No se pudo crear el archivo de exportación.",
        "The export file could not be created.")

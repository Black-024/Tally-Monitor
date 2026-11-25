#!/usr/bin/env python3
"""
Verificación del núcleo de Tally Monitor en Windows (DPAPI real + Tally real).

Uso (PowerShell, desde la carpeta que contiene scripts):
    py scripts\\verify_core_windows.py                       # etapa 1: pruebas completas
    (reiniciar Windows)
    py scripts\\verify_core_windows.py --despues-de-reiniciar # etapa 2: ¿sigue guardada la clave?
    py scripts\\verify_core_windows.py --limpiar              # borra los datos de esta verificación

- Pide la API Key UNA vez con entrada oculta (no se muestra, no se guarda en claro, no va por argumentos).
- Trabaja en %LOCALAPPDATA%\\TallyMonitorVerify, NUNCA en tus datos reales.
- Solo hace GET /users/me (solo lectura). No modifica nada en Tally.
- Imprime únicamente OK / FALLO y categorías de error; nunca la clave.
"""
import argparse
import getpass
import os
import secrets
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "tally-monitor"
sys.path.insert(0, str(ROOT / "src"))

RESULTS: list[tuple[bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    RESULTS.append((bool(ok), name))
    print(f"  [{'OK' if ok else 'FALLO'}] {name}" + (f"  ({detail})" if detail else ""))
    return bool(ok)


def scan_for(vdir: Path, needles: list[bytes]) -> list[str]:
    found = []
    for p in vdir.rglob("*"):
        if p.is_file():
            data = p.read_bytes()
            if any(n in data for n in needles):
                found.append(str(p.relative_to(vdir)))
    return found


def read_key_hidden():
    from tally_monitor.core.keyformat import looks_like_api_key
    from tally_monitor.core.secret import SecretStr
    if not sys.stdin.isatty() or sys.stdin is not sys.__stdin__:
        print("Este script necesita una consola interactiva para pedir la clave de forma oculta.")
        sys.exit(2)
    print("Pegá tu API Key y presioná Enter. No se va a ver nada mientras pegás.")
    print("En Windows, pegá con CLIC DERECHO o Shift+Insert (Ctrl+V puede no funcionar en este tipo de entrada).")
    for attempt in range(1, 4):
        value = getpass.getpass("API Key: ").strip()
        if looks_like_api_key(value):
            print(f"  Clave recibida ({len(value)} caracteres, formato correcto).")
            return SecretStr(value)
        has_ctrl = any(ord(ch) < 32 for ch in value)
        print(f"  La clave no tiene el formato esperado (recibidos {len(value)} caracteres; "
              f"empieza con 'tly-': {'sí' if value.startswith('tly-') else 'no'}; "
              f"caracteres de control: {'sí' if has_ctrl else 'no'}).")
        if has_ctrl or len(value) <= 3:
            print("  Parece que el pegado no funcionó (Ctrl+V). Probá con clic derecho o Shift+Insert.")
        print(f"  Intento {attempt} de 3.")
    print("No se recibió una clave con formato válido.")
    sys.exit(2)


def stage_all(vdir: Path, protector, client, get_key) -> None:
    from tally_monitor.api.errors import ApiAuthError, ApiError
    from tally_monitor.app import build_core
    from tally_monitor.core.config import AppPaths
    from tally_monitor.core.errors import CredentialUnreadableError, DuplicateKeyError
    from tally_monitor.core.secret import SecretStr

    print("\n== 1. Cifrado de Windows (DPAPI) ==")
    sample = b'{"api_key": "tly-PRUEBA-NO-ES-UNA-CLAVE"}'
    blob = protector.protect(sample)
    check("DPAPI cifra (el texto original no aparece en el resultado)", b"PRUEBA" not in blob)
    check("DPAPI descifra al mismo valor", protector.unprotect(blob) == sample)
    try:
        protector.unprotect(b"datos-que-no-son-dpapi" * 3)
        check("DPAPI rechaza datos ajenos", False)
    except CredentialUnreadableError:
        check("DPAPI rechaza datos ajenos", True)

    print("\n== 2. Arranque, bases y migraciones ==")
    if vdir.exists():
        shutil.rmtree(vdir)
    core = build_core(paths=AppPaths(vdir), protector=protector, client=client)
    rep = core.startup.run()
    check("library.db y cache.db creadas", (vdir / "library.db").exists() and (vdir / "cache.db").exists())
    check("integridad correcta y sin necesidad de restaurar", rep.library_ok and not rep.needs_restore)
    check("backup automático creado al primer arranque", rep.daily_backup_created)

    print("\n== 3. Clave inválida (clasificación real de Tally) ==")
    fake = SecretStr("tly-" + secrets.token_hex(16))
    try:
        core.accounts.add_account("Prueba invalida", fake)
        check("una clave inventada NO se acepta", False)
    except ApiError as exc:
        print(f"      Tally respondió: categoría = {exc.category}, HTTP = {getattr(exc, 'status', '-')}")
        check("una clave inventada se clasifica como rechazo de autenticación", isinstance(exc, ApiAuthError))
    check("no quedó ninguna cuenta ni credencial tras el rechazo",
          core.accounts.list_accounts() == [] and core.accounts._store.ids() == set())

    print("\n== 4. Tu clave real ==")
    key = get_key()
    acct = core.accounts.add_account("Verificacion", key)
    check("cuenta agregada y validada contra Tally", acct.status == "active")
    stored = core.accounts._store.load(acct.account_id)
    has_id = stored is not None and stored.tally_user_id is not None
    check("Tally devolvió un id de usuario (se guarda solo cifrado)", has_id,
          "si falla, el reemplazo de clave no podrá comparar usuarios")
    check("la clave se descifra igual a la ingresada", stored is not None and stored.api_key.matches(key))
    try:
        core.accounts.add_account("Duplicada", key)
        check("la misma clave no se puede agregar dos veces", False)
    except DuplicateKeyError:
        check("la misma clave no se puede agregar dos veces", True)
    check("validar la cuenta devuelve 'ok'", core.accounts.validate_account(acct.account_id).result == "ok")

    print("\n== 5. Reemplazo de clave ==")
    try:
        core.accounts.replace_key(acct.account_id, fake)
        check("una clave inválida no reemplaza a la anterior", False)
    except ApiError:
        check("una clave inválida no reemplaza a la anterior", True)
    check("la clave anterior sigue funcionando", core.accounts.validate_account(acct.account_id).result == "ok")
    res = core.accounts.replace_key(acct.account_id, key)
    check("reemplazo con una clave válida del mismo usuario", res.account.status == "active")
    check("identidad verificada (mismo usuario de Tally)", res.identity_verified is True)

    print("\n== 6. Backups y restauración (sin credenciales) ==")
    b = core.backups.create_manual()
    needles = [key.reveal().encode(), key.reveal()[4:].encode()]
    check("el backup no contiene la clave ni el prefijo 'tly-'",
          not scan_for(vdir / "backups", needles + [b"tly-"]))
    core.accounts.delete_account(acct.account_id)
    check("eliminar la cuenta borra la fila y la clave cifrada",
          core.accounts.list_accounts() == [] and core.accounts._store.ids() == set())
    core.backups.restore(b.filename)
    rec = core.accounts.reconcile_credentials()
    restored = core.accounts.list_accounts()
    check("restaurar devuelve la cuenta SIN clave (queda 'Sin credencial')",
          len(restored) == 1 and restored[0].status == "no_credential" and len(rec["marked_no_credential"]) == 1)
    core.accounts.replace_key(restored[0].account_id, key)
    check("reemplazar la clave la deja activa otra vez",
          core.accounts.get_account(restored[0].account_id).status == "active")

    print("\n== 7. Búsqueda de la clave en todos los archivos ==")
    leaks = scan_for(vdir, needles)
    check("la clave NO aparece en ningún archivo (bases, credenciales, backups, logs)", not leaks, ", ".join(leaks))
    check("no aparece ningún texto 'tly-' en los archivos", not scan_for(vdir, [b"tly-"]))
    print("\n  Datos de la verificación guardados en:", vdir)


def stage_after_reboot(vdir: Path, protector, client) -> None:
    from tally_monitor.app import build_core
    from tally_monitor.core.config import AppPaths
    if not vdir.exists():
        print("No existe la carpeta de verificación: corré primero la etapa 1.")
        sys.exit(2)
    print("\n== Después del reinicio ==")
    core = build_core(paths=AppPaths(vdir), protector=protector, client=client)
    rep = core.startup.run()
    accounts = core.accounts.list_accounts()
    check("la cuenta sigue guardada", len(accounts) == 1)
    check("la clave se pudo descifrar (no quedó 'Sin credencial')", not rep.marked_no_credential)
    if accounts:
        out = core.accounts.validate_account(accounts[0].account_id)
        check("sigue validando contra Tally sin volver a ingresar la clave", out.result == "ok", out.result)
    check("ningún texto 'tly-' en los archivos", not scan_for(vdir, [b"tly-"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--despues-de-reiniciar", action="store_true")
    ap.add_argument("--limpiar", action="store_true")
    args = ap.parse_args()
    if sys.platform != "win32":
        print("Este script es para Windows (usa DPAPI real).")
        return 2
    vdir = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TallyMonitorVerify"
    if args.limpiar:
        shutil.rmtree(vdir, ignore_errors=True)
        print("Datos de verificación eliminados.")
        return 0
    from tally_monitor.api.client import TallyClient
    from tally_monitor.core.errors import TallyMonitorError
    from tally_monitor.security.dpapi import WindowsDpapiProtector
    protector, client = WindowsDpapiProtector(), TallyClient()
    try:
        if args.despues_de_reiniciar:
            stage_after_reboot(vdir, protector, client)
        else:
            stage_all(vdir, protector, client, read_key_hidden)
    except KeyboardInterrupt:
        print("\nInterrumpido.")
        return 130
    except TallyMonitorError as exc:                 # error esperado: mensaje seguro, sin traza
        print(f"\nSe detuvo por un error: {exc.user_message}")
        print("Resultados hasta ahora:", f"{sum(1 for r, _ in RESULTS if r)} de {len(RESULTS)} correctas.")
        return 1
    ok = sum(1 for r, _ in RESULTS if r)
    print(f"\nResultado: {ok} de {len(RESULTS)} comprobaciones correctas.")
    for r, name in RESULTS:
        if not r:
            print("  FALLÓ:", name)
    if not args.despues_de_reiniciar and all(r for r, _ in RESULTS):
        print("\nSiguiente paso: reiniciá Windows y ejecutá:\n  py scripts\\verify_core_windows.py --despues-de-reiniciar")
        print("Luego limpiá el portapapeles (PowerShell):  Set-Clipboard -Value ' '")
    return 0 if all(r for r, _ in RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())

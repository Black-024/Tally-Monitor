"""Idioma Español / English: detección, prioridad, persistencia, paridad de textos y arranque en inglés."""
import inspect
import os
import string
import subprocess
import sys
from pathlib import Path

import pytest

from tally_monitor.core import language
from tally_monitor.ui import strings as S_es
from tally_monitor.ui import strings_en as S_en

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def clean(monkeypatch):
    """Sin variables de idioma ni de carpeta de datos, y sin API de Windows."""
    for var in ("TALLY_MONITOR_LANG", "LC_ALL", "LC_MESSAGES", "LANGUAGE", "LANG", "TALLY_MONITOR_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("tally_monitor.core.windows_shell.user_ui_language", lambda: None)
    monkeypatch.setattr(language.locale, "getlocale", lambda *a, **k: (None, None))
    return monkeypatch


# ---------- detección ----------
@pytest.mark.parametrize("value,expected", [("es_AR.UTF-8", "es"), ("es", "es"), ("es_ES", "es"), ("en_US.UTF-8", "en"),
                                            ("fr_FR", "en"), ("pt_BR", "en"), ("C", "en"), ("POSIX", "en")])
def test_detect_system_from_env(clean, value, expected):
    clean.setenv("LANG", value)
    assert language.detect_system() == expected


def test_detect_system_priority_and_fallbacks(clean):
    assert language.detect_system() == "en"                      # nada configurado -> inglés
    clean.setattr(language.locale, "getlocale", lambda *a, **k: ("es_AR", "UTF-8"))
    assert language.detect_system() == "es"                      # locale de Python
    clean.setenv("LANG", "en_US.UTF-8")
    assert language.detect_system() == "en"                      # la variable de entorno gana al locale
    clean.setenv("LANGUAGE", "es:en")
    assert language.detect_system() == "es"                      # LANGUAGE puede traer una lista


def test_detect_system_windows_ui_language(clean):
    clean.setattr("tally_monitor.core.windows_shell.user_ui_language", lambda: "es")
    clean.setenv("LANG", "en_US")
    assert language.detect_system() == "es"
    clean.setattr("tally_monitor.core.windows_shell.user_ui_language", lambda: "other")
    clean.setenv("LANG", "es_AR")
    assert language.detect_system() == "en"


def test_detect_system_survives_broken_locale(clean):
    def boom(*a, **k):
        raise ValueError("locale roto")
    clean.setattr(language.locale, "getlocale", boom)
    assert language.detect_system() == "en"


# ---------- persistencia y prioridad ----------
def test_set_language_persists_in_given_dir(clean, tmp_path):
    home = tmp_path / "datos"
    assert language.stored(home) is None
    language.set_language("en", home)
    assert (home / "language.txt").read_text(encoding="utf-8").strip() == "en"
    assert language.stored(home) == "en"
    language.set_language("ES", home)
    assert language.stored(home) == "es"
    assert [p.name for p in home.iterdir()] == ["language.txt"]   # sin temporales; no toca otros archivos


def test_set_language_rejects_unknown(clean, tmp_path):
    with pytest.raises(ValueError):
        language.set_language("fr", tmp_path)
    assert not (tmp_path / "language.txt").exists()


def test_stored_ignores_garbage(clean, tmp_path):
    (tmp_path / "language.txt").write_text("klingon\n", encoding="utf-8")
    assert language.stored(tmp_path) is None
    (tmp_path / "language.txt").write_bytes(b"\xff\xfe\x00")
    assert language.stored(tmp_path) is None


def test_resolve_priority_env_over_file_over_system(clean, tmp_path):
    clean.setenv("LANG", "es_AR")
    assert language.resolve(tmp_path) == "es"                     # sistema
    language.set_language("en", tmp_path)
    assert language.resolve(tmp_path) == "en"                     # archivo > sistema
    clean.setenv("TALLY_MONITOR_LANG", "es")
    assert language.resolve(tmp_path) == "es"                     # entorno > archivo
    clean.setenv("TALLY_MONITOR_LANG", "xx")
    assert language.resolve(tmp_path) == "en"                     # entorno inválido se ignora


def test_language_file_is_not_a_secret_store(clean, tmp_path):
    language.set_language("en", tmp_path)
    assert (tmp_path / "language.txt").read_text(encoding="utf-8") in ("en\n", "en")


def test_tests_run_in_spanish():
    assert language.current() == "es" and S_es.NAV[0][1] == "Inicio"


# ---------- paridad strings / strings_en ----------
def _public(mod):
    return {k: v for k, v in vars(mod).items() if k.isupper() and not k.startswith("_")
            and k not in ("IS_MAC", "IS_WINDOWS")}


def _fields(text):
    return sorted(f[1] for f in string.Formatter().parse(text) if f[1] is not None)


def _check_same(name, a, b):
    assert type(a) is type(b), f"{name}: distinto tipo"
    if isinstance(a, str):
        assert _fields(a) == _fields(b), f"{name}: placeholders distintos ({_fields(a)} vs {_fields(b)})"
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b), f"{name}: distinta cantidad de elementos"
        for i, (x, y) in enumerate(zip(a, b)):
            _check_same(f"{name}[{i}]", x, y)
    elif isinstance(a, dict):
        assert set(a) == set(b), f"{name}: distintas claves"
        for k in a:
            _check_same(f"{name}[{k!r}]", a[k], b[k])
    elif callable(a):
        assert inspect.signature(a) == inspect.signature(b), f"{name}: distinta firma"


def test_strings_en_has_same_names():
    es, en = _public(S_es), _public(S_en)
    assert set(es) - set(en) == set(), "faltan en strings_en.py"
    assert set(en) - set(es) == set(), "sobran en strings_en.py"


def test_strings_en_same_shape_and_placeholders():
    es, en = _public(S_es), _public(S_en)
    for name in es:
        _check_same(name, es[name], en[name])


def test_structural_keys_are_not_translated():
    """Las claves internas (estados, filtros, pestañas) deben coincidir: solo cambia el texto visible."""
    for name in ("NAV", "TABS", "SURVEYS_FILTERS", "ANALYSIS_FILTERS", "ANALYSIS_CHIPS", "SYNC_MODES", "NOTIFY_INTERVALS"):
        assert [k for k, _ in getattr(S_es, name)] == [k for k, _ in getattr(S_en, name)], name


def test_english_has_no_spanish_leftovers():
    """Heurística: ningún texto en inglés lleva letras acentuadas ni signos de apertura del español (salvo el selector)."""
    allowed = {"SEC_LANGUAGE", "LANGUAGE_LABEL", "LANGUAGE_NAMES", "LANGUAGE_RESTART", "FOOTER"}
    bad = []

    def walk(name, v):
        if isinstance(v, str):
            if any(c in v for c in "áéíóúñ¿¡«»"):
                bad.append(name)
        elif isinstance(v, (list, tuple)):
            [walk(name, x) for x in v]
        elif isinstance(v, dict):
            [walk(name, x) for x in list(v.keys()) + list(v.values())]
    for name, v in _public(S_en).items():
        if name not in allowed:
            walk(name, v)
    assert not bad, bad


# ---------- arranque real en inglés (proceso aparte) ----------
def _run_en(code: str, home=None) -> str:
    env = {k: v for k, v in os.environ.items() if k != "TALLY_MONITOR_HOME"}
    env.update(TALLY_MONITOR_LANG="en", PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf-8")
    res = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


def test_subprocess_english_ui_texts():
    out = _run_en(
        "from tally_monitor.ui import strings as S, presenters as P, greeting\n"
        "from datetime import datetime\n"
        "print(S.NAV[0][1], '|', S.ACCOUNTS_TITLE, '|', S.THEME_ACCESSIBLE.format(label='Dark'))\n"
        "print(P.format_count(1234), '|', P.format_pct(12.5), '|', P.format_decimal(1.5))\n"
        "print(P.format_local_naive(datetime(2026, 11, 25, 13, 5)))\n"
        "print(P.format_duration(4800), '|', P.suggest_account_name([]))\n"
        "print(greeting.greeting_for(datetime(2026, 12, 25, 10, 0))[0])\n"
        "print(greeting.greeting_for(datetime(2026, 11, 25, 10, 0)))\n")
    lines = out.splitlines()
    assert lines[0] == "Home | Accounts | Dark theme"
    assert lines[1] == "1,234 | 12.5% | 1.5"
    assert lines[2] == "11/25/2026 13:05"
    assert lines[3] == "1 hour and 20 minutes | Account 1"
    assert lines[4] == "Merry Christmas!"
    assert lines[5].startswith("('Good morning!'")


def test_subprocess_english_errors_services_and_exports():
    out = _run_en(
        "from tally_monitor.core.errors import AccountNotFoundError\n"
        "from tally_monitor.api.errors import ApiNetworkError\n"
        "from tally_monitor.sync.numbering import format_user_label, parse_user_label\n"
        "from tally_monitor.services.notify_service import notification_text\n"
        "from tally_monitor.export import format as F\n"
        "from tally_monitor.analysis.timefilter import resolve_filter\n"
        "from datetime import datetime, timezone\n"
        "print(AccountNotFoundError().user_message)\n"
        "print(ApiNetworkError().user_message)\n"
        "print(format_user_label(7), parse_user_label('User 007'), parse_user_label('Usuario 007'))\n"
        "print(notification_text(2, 1))\n"
        "print(F.dec(1.5), F.pct(12.5), F.dt(datetime(2026, 11, 25, 13, 5)))\n"
        "print(resolve_filter('7d', datetime.now(timezone.utc), timezone.utc).label)\n")
    lines = out.splitlines()
    assert lines[0] == "The account does not exist."
    assert lines[1].startswith("Could not connect to Tally")
    assert lines[2] == "User 007 7 7"
    assert lines[3] == "('2 new responses in 1 survey', 'Tap to open Tally Monitor')"
    assert lines[4] == "1.5 12.5% 11/25/2026 13:05"
    assert lines[5] == "Last 7 days"


def test_subprocess_stored_language_file_is_used(tmp_path):
    env = {k: v for k, v in os.environ.items() if k not in ("TALLY_MONITOR_LANG",)}
    env.update(PYTHONPATH=str(ROOT / "src"), TALLY_MONITOR_HOME=str(tmp_path), LANG="es_AR.UTF-8")
    (tmp_path / "language.txt").write_text("en\n", encoding="utf-8")
    res = subprocess.run([sys.executable, "-c", "from tally_monitor.ui import strings as S; print(S.NAV[0][1])"],
                         env=env, capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "Home"

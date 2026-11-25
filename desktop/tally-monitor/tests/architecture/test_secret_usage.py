"""La clave solo se «revela» en los pocos lugares que la necesitan; nunca en export, analysis, sync ni logs."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "tally_monitor"
ALLOWED = {"api/client.py", "core/secret.py", "security/credential_store.py", "ui/dialogs/key_dialogs.py",
           "services/account_service.py"}


def test_reveal_only_in_allowed_modules():
    bad = []
    for p in SRC.rglob("*.py"):
        rel = p.relative_to(SRC).as_posix()
        if ".reveal(" in p.read_text(encoding="utf-8") and rel not in ALLOWED:
            bad.append(rel)
    assert not bad, bad


def test_no_print_outside_cli_entrypoints():
    allowed = {"selfcheck.py", "__main__.py", "core/session_report.py"}
    bad = [p.relative_to(SRC).as_posix() for p in SRC.rglob("*.py")
           if re.search(r"^\s*print\(", p.read_text(encoding="utf-8"), re.M) and p.relative_to(SRC).as_posix() not in allowed]
    assert not bad, bad

"""`keyring` y los módulos de llavero solo se tocan desde security/keyring_protector.py."""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "tally_monitor"


def test_keyring_is_imported_only_by_its_protector():
    bad = []
    for f in SRC.rglob("*.py"):
        rel = f.relative_to(SRC).as_posix()
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            if any(n == "keyring" or n.startswith("keyring.") for n in names) and rel != "security/keyring_protector.py":
                bad.append(rel)
    assert not bad, bad

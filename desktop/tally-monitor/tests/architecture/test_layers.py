"""Reglas de capas verificadas leyendo los imports del código (sin ejecutarlo)."""
import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "tally_monitor"
PKG = "tally_monitor"

NETWORK = {"urllib.request", "http", "http.client", "socket", "ssl", "httpx", "requests", "urllib3", "aiohttp"}
UI_FORBIDDEN_EXTERNAL = NETWORK | {"sqlite3", "ctypes", "urllib", "shutil"}
LAYER_RULES = {            # capa -> capas internas que NO puede importar
    "ui": {"storage", "security", "api", "app", "sync", "analysis", "export"},
    "services": {"ui", "app"},
    "storage": {"ui", "services", "api", "security", "app", "export"},
    "security": {"ui", "services", "api", "storage", "app", "sync", "analysis", "export"},
    "api": {"ui", "services", "storage", "security", "app", "sync", "analysis", "export"},
    "core": {"ui", "services", "api", "storage", "security", "app", "sync", "analysis", "export"},
    "sync": {"ui", "services", "api", "storage", "security", "app", "analysis", "export"},   # lógica pura: solo puede usar core
    "analysis": {"ui", "services", "api", "storage", "security", "app", "sync", "export"},   # cálculo puro: solo puede usar core
    "export": {"ui", "services", "api", "storage", "security", "app", "sync"},     # escritores puros: core + analysis.models
}


NETWORK_FILES = {"api/client.py", "api/update_client.py"}     # Tally (con clave) y avisos de versión (sin clave)


def imports_of(source: str) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:                       # relativo: from ..storage import x
                base = "." * node.level + base
            out.add(base)
            out |= {f"{base}.{a.name}" for a in node.names}
    return out


def resolve(mod: str, file_rel: Path) -> str:
    """Convierte imports relativos en absolutos (tally_monitor.xxx)."""
    if not mod.startswith("."):
        return mod
    level = len(mod) - len(mod.lstrip("."))
    parts = [PKG] + list(file_rel.parent.parts)
    base = parts[: len(parts) - (level - 1)]
    rest = mod.lstrip(".")
    return ".".join(base + ([rest] if rest else []))


def layer_of(rel: Path) -> str:
    return rel.parts[0] if len(rel.parts) > 1 else "app"


def violations(files: dict[str, str]) -> list[str]:
    bad = []
    for name, source in files.items():
        rel = Path(name)
        layer = layer_of(rel)
        for raw in imports_of(source):
            mod = resolve(raw, rel)
            top = mod.split(".")
            # 1) dependencias entre capas internas
            if top[0] == PKG and len(top) > 1 and top[1] in LAYER_RULES.get(layer, set()):
                bad.append(f"{name}: la capa '{layer}' no puede importar '{mod}'")
            # 2) red solo en api/client.py
            if any(mod == n or mod.startswith(n + ".") for n in NETWORK) and name not in NETWORK_FILES:
                bad.append(f"{name}: usa red ('{mod}') fuera de {sorted(NETWORK_FILES)}")
            # 3) sqlite3 solo en storage/
            if (mod == "sqlite3" or mod.startswith("sqlite3.")) and layer != "storage":
                bad.append(f"{name}: usa sqlite3 fuera de storage/")
            # 4) ctypes solo en security/dpapi.py
            if (mod == "ctypes" or mod.startswith("ctypes.")) and name not in ("security/dpapi.py", "core/windows_shell.py"):
                bad.append(f"{name}: usa ctypes fuera de security/dpapi.py")
            # 5) la interfaz no toca bases, red, ctypes ni el sistema de archivos a bajo nivel
            if layer == "ui" and mod.split(".")[0] in UI_FORBIDDEN_EXTERNAL:
                bad.append(f"{name}: la interfaz no puede importar '{mod}'")
    return bad


def load_real() -> dict[str, str]:
    return {p.relative_to(SRC).as_posix(): p.read_text(encoding="utf-8") for p in SRC.rglob("*.py")}


def test_real_code_respects_layers():
    files = load_real()
    assert len(files) > 20
    assert violations(files) == []


# --- el verificador debe detectar violaciones (si no, la prueba anterior no vale nada) ---
def test_checker_detects_violations():
    bad = violations({
        "ui/pages/accounts.py": "import sqlite3\nfrom tally_monitor.storage import database\n",
        "ui/x.py": "from ...api import client\nimport urllib.request\n",
        "services/a.py": "import urllib.request\nimport ctypes\n",
        "storage/b.py": "from ..services import account_service\n",
        "api/errors.py": "from ..storage.database import Database\n",
        "core/z.py": "from ..security import protector\n",
        "sync/n.py": "from ..storage import database\nimport sqlite3\n",
        "ui/y.py": "from tally_monitor.sync import numbering\n",
        "analysis/a.py": "from ..storage import database\nimport sqlite3\n",
        "ui/z.py": "from tally_monitor.analysis import stats\n",
    })
    text = "\n".join(bad)
    for needle in ("ui/pages/accounts.py: la capa 'ui' no puede importar 'tally_monitor.storage",
                   "ui/pages/accounts.py: usa sqlite3 fuera de storage/",
                   "ui/x.py: usa red", "ui/x.py: la interfaz no puede importar 'urllib",
                   "services/a.py: usa red", "services/a.py: usa ctypes",
                   "storage/b.py: la capa 'storage' no puede importar",
                   "api/errors.py: la capa 'api'", "core/z.py: la capa 'core'",
                   "sync/n.py: la capa 'sync' no puede importar", "sync/n.py: usa sqlite3",
                   "ui/y.py: la capa 'ui' no puede importar 'tally_monitor.sync",
                   "analysis/a.py: la capa 'analysis' no puede importar", "analysis/a.py: usa sqlite3",
                   "ui/z.py: la capa 'ui' no puede importar 'tally_monitor.analysis"):
        assert needle in text, needle


def test_checker_allows_legit_imports():
    assert violations({
        "ui/pages/accounts.py": "from tally_monitor.services.account_service import AccountService\nfrom PySide6 import QtWidgets\n",
        "api/client.py": "import urllib.request\nfrom ..core.secret import SecretStr\n",
        "security/dpapi.py": "import ctypes\n",
        "storage/db.py": "import sqlite3\nfrom ..sync.models import FormRow\n",
        "services/s.py": "from ..sync import normalizer\nfrom ..storage import surveys_repo\n",
        "sync/n.py": "from ..core.errors import TallyMonitorError\n",
        "storage/r.py": "from ..analysis.models import AnswerPoint\n",
        "services/a.py": "from ..analysis import stats\nfrom ..storage import analytics_repo\n",
        "analysis/ok.py": "from ..core.errors import TallyMonitorError\n",
    }) == []


def test_no_print_and_no_env_key_in_source():
    for name, source in load_real().items():
        tree = ast.parse(source)
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "print"]
        assert not calls, f"{name}: usa print()"
        assert "TALLY_API_KEY" not in source, f"{name}: lee la clave de una variable de entorno"


def test_only_get_in_client():
    src = (SRC / "api" / "client.py").read_text(encoding="utf-8")
    assert 'method="GET"' in src
    for verb in ("POST", "PUT", "PATCH", "DELETE"):
        assert f'"{verb}"' not in src and f"'{verb}'" not in src

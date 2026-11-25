"""Fixtures compartidas. Se importan explícitamente en cada módulo de pruebas (sin conftest.py)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")     # Qt sin ventana real (solo afecta a las pruebas de UI)
import pytest

from support.fake_protector import FakeProtector
from support.fake_tally import FakeTally
from support.shared import FakeClock, KEY_A, KEY_B, KEY_C  # noqa: F401
from tally_monitor.api.client import TallyClient
from tally_monitor.app import build_core
from tally_monitor.core.config import AppPaths

@pytest.fixture
def tally():
    s = FakeTally().start()
    s.users.update({KEY_A: "user-A", KEY_B: "user-B", KEY_C: "user-A"})  # C = otra clave del mismo usuario A
    yield s
    s.stop()


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def paths(tmp_path):
    return AppPaths(tmp_path / "home")


@pytest.fixture
def protector():
    return FakeProtector()


@pytest.fixture
def make_core(paths, protector, tally, clock):
    """Construye un núcleo nuevo sobre la misma carpeta (permite simular reinicios)."""
    def _make(*, prot=None, logging=False):
        client = TallyClient(tally.url, sleep=lambda s: None)
        return build_core(paths=paths, protector=prot or protector, client=client, clock=clock,
                          configure_logging=logging)
    return _make


@pytest.fixture
def core(make_core):
    c = make_core()
    c.startup.run()
    return c

@pytest.fixture
def ctx(core, paths):
    from tally_monitor.ui.context import AppContext
    return AppContext(core.accounts, core.backups, core.settings, str(paths.home), str(paths.logs_dir), "0.1.0",
                      sync=core.sync, surveys=core.surveys, favorites=core.favorites, analysis=core.analysis, export=core.export,
                      notifier=core.notifier)


@pytest.fixture
def runner(qtbot):          # solo lo usan las pruebas con Qt real
    from tally_monitor.ui.workers import TaskRunner
    return TaskRunner()

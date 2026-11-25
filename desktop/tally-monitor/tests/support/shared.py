"""Constantes y utilidades compartidas por las pruebas (fuera de conftest para evitar choques de nombre)."""
from tally_monitor.core.clock import Clock

KEY_A = "tly-AAAA1111bbbb2222cccc3333dddd4444eeee"
KEY_B = "tly-BBBB1111aaaa2222cccc3333dddd4444ffff"
KEY_C = "tly-CCCC1111aaaa2222bbbb3333dddd4444gggg"


class FakeClock(Clock):
    def __init__(self):
        from datetime import datetime, timezone
        self.t = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)

    def now(self):
        return self.t

    def advance(self, **kw):
        from datetime import timedelta
        self.t += timedelta(**kw)

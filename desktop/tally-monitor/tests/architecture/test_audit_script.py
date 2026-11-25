import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "auditoria_seguridad.py"
spec = importlib.util.spec_from_file_location("auditoria", SCRIPT)
aud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aud)


def test_real_source_is_clean():
    assert aud.scan_source(aud.ROOT / "src" / "tally_monitor") == []


def test_auditor_detects_problems(tmp_path):
    (tmp_path / "a.py").write_text('k = "tly-' + "A" * 20 + '"\nr = Request(u, method="POST")\nx = eval(s)\n'
                                   'u = "http://example.com"\nf = "respondentId"\n')
    found = " | ".join(aud.scan_source(tmp_path))
    for expected in ("API Key", "distinto de GET", "ejecución dinámica", "http://", "campo que no debe"):
        assert expected in found
    (tmp_path / "x.db").write_bytes(b"x")
    assert any("suelto" in f for f in aud.scan_dist(tmp_path))

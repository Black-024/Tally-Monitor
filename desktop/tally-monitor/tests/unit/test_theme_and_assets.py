import re

from support.fixtures import *  # noqa: F401,F403
from tally_monitor.core import assets
from tally_monitor.core.palette import DARK, LIGHT, THEMES, palette
from tally_monitor.ui import presenters as P

HEX = re.compile(r"^#[0-9a-f]{6}$")


def test_palettes_have_same_keys_and_valid_colors():
    assert DARK.keys() == LIGHT.keys()
    for name, pal in THEMES.items():
        assert all(HEX.match(v) for v in pal.values()), name


def test_palettes_follow_the_requested_design():
    assert DARK["bg"] == "#0b0b0f" and DARK["accent"] == "#8b7bff" and DARK["action"] == "#e6b84a"   # negro / violeta / dorado
    assert LIGHT["bg"] == "#ffffff" and LIGHT["accent"] == "#12a198" and LIGHT["action"] == "#8a5a3b"  # blanco / aqua / café
    assert palette("raro") == DARK


def _luminance(h: str) -> float:
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_text_is_readable_in_both_themes():
    for pal in (DARK, LIGHT):
        assert _contrast(pal["text"], pal["bg"]) >= 7
        assert _contrast(pal["muted"], pal["bg"]) >= 4.5
        assert _contrast(pal["action_text"], pal["action"]) >= 4.5      # texto de los botones dorado / café
        assert _contrast(pal["text"], pal["surface"]) >= 7


def test_no_gradients_left_in_ui_or_exports():
    import pathlib
    src = pathlib.Path(__file__).resolve().parents[2] / "src" / "tally_monitor"
    for p in list(src.glob("ui/**/*.py")) + list(src.glob("export/*.py")):
        text = p.read_text(encoding="utf-8")
        assert "qlineargradient" not in text and "QLinearGradient" not in text and "GRADIENT" not in text, p.name


def test_no_emoji_in_ui_strings():
    import pathlib
    import unicodedata
    text = (pathlib.Path(__file__).resolve().parents[2] / "src" / "tally_monitor" / "ui" / "strings.py").read_text(encoding="utf-8")
    bad = {c for c in text if unicodedata.category(c) == "So"}
    assert not bad, bad


def test_theme_setting_roundtrip(core):
    assert core.settings.get("theme") == "dark"
    core.settings.set("theme", "light")
    assert core.settings.get("theme") == "light"


def test_logo_is_optional(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, "ASSETS_DIR", tmp_path)
    assert assets.find_logo("dark") is None and assets.find_icon() is None
    (tmp_path / "logo.png").write_bytes(b"x")
    assert assets.find_logo("dark").name == "logo.png"
    (tmp_path / "logo_dark.png").write_bytes(b"x")
    assert assets.find_logo("dark").name == "logo_dark.png" and assets.find_logo("light").name == "logo.png"


def test_count_and_duration_formatting():
    assert P.format_count(12345) == "12.345"
    assert P.format_duration(10) == "10 segundos" and P.format_duration(180) == "3 minutos"
    assert P.format_duration(4800) == "1 hora y 20 minutos"


def test_legal_texts_are_found_from_the_source_tree():
    from tally_monitor.core.assets import read_legal
    assert "MIT License" in read_legal("LICENSE")
    assert "API Key" in read_legal("PRIVACIDAD.md")
    assert "PySide6" in read_legal("THIRD_PARTY_LICENSES.md")
    assert read_legal("no-existe.md") is None


def test_pyinstaller_spec_bundles_legal_texts_and_logos():
    import pathlib
    spec = (pathlib.Path(__file__).resolve().parents[2] / "packaging" / "TallyMonitor.spec").read_text(encoding="utf-8")
    for needle in ("PRIVACIDAD.md", "THIRD_PARTY_LICENSES.md", "LICENSE", '"legal"', "assets"):
        assert needle in spec


def test_privacy_fallback_text_never_empty():
    from tally_monitor.ui import strings as S
    assert "solo lectura" in S.PRIVACY_SUMMARY.lower() and "API Key" in S.PRIVACY_SUMMARY

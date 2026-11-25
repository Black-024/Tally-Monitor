from datetime import timezone

import openpyxl
import pytest

from support.fixtures import *  # noqa: F401,F403
from support.forms import FORM_ID, add_form, submission
from support.shared import KEY_A
from tally_monitor.core.errors import ExportError, SurveyNotFoundError
from tally_monitor.core.secret import SecretStr
from tally_monitor.export.models import ExportOptions


@pytest.fixture
def acct(core, tally):
    core.analysis._tz = timezone.utc
    a = core.accounts.add_account("Cuenta", SecretStr(KEY_A))
    add_form(tally, [submission(800, single="Sí", multi=("Rojo", "Verde"), text="mail: a@b.com"),
                     submission(810, single="No", multi=("Azul",), text="=SUM(1+1)"),
                     submission(820, single=None, multi=None, text="x", completed=False)])
    core.sync.sync_form(a.account_id, FORM_ID)
    return a


def load(path):
    return openpyxl.load_workbook(path)


def test_xlsx_default_has_no_free_text_and_matches_counts(core, acct, tmp_path):
    out = tmp_path / "e.xlsx"
    res = core.export.export_xlsx(acct.account_id, FORM_ID, str(out))
    assert res.responses == 3 and res.text_included is False
    wb = load(out)
    assert wb.sheetnames == ["Resumen", "Estadísticas", "En el tiempo", "Respuestas"]
    ws = wb["Respuestas"]
    heads = [c.value for c in ws[1]]
    full = tmp_path / "f.xlsx"
    core.export.export_xlsx(acct.account_id, FORM_ID, str(full), ExportOptions(include_text=True))
    assert len(load(full)["Respuestas"][1]) == len(heads) + 1       # con texto aparece una columna más
    assert ws.cell(2, 1).value == "Usuario 001" and ws.cell(2, 3).value == "Completa"
    assert ws.cell(4, 3).value == "Incompleta"
    blob = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value is not None)
    assert "a@b.com" not in blob and "SUM" not in blob            # el texto libre no sale por defecto
    assert "Rojo | Verde" in blob


def test_xlsx_text_masked_and_formula_stays_text(core, acct, tmp_path):
    out = tmp_path / "t.xlsx"
    res = core.export.export_xlsx(acct.account_id, FORM_ID, str(out), ExportOptions(include_text=True))
    assert res.text_included and res.masked
    ws = load(out)["Respuestas"]
    values = [c.value for row in ws.iter_rows(min_row=2) for c in row if isinstance(c.value, str)]
    assert not any("a@b.com" in v for v in values) and any("[oculto]" in v for v in values)
    cell = next(c for row in ws.iter_rows(min_row=2) for c in row if c.value == "=SUM(1+1)")
    assert cell.data_type == "s"                                   # nunca se evalúa como fórmula
    out2 = tmp_path / "u.xlsx"
    core.export.export_xlsx(acct.account_id, FORM_ID, str(out2), ExportOptions(include_text=True, mask_personal=False))
    assert "a@b.com" in " ".join(str(c.value) for row in load(out2)["Respuestas"].iter_rows() for c in row)


def test_excluding_incomplete_and_filters(core, acct, tmp_path):
    res = core.export.export_xlsx(acct.account_id, FORM_ID, str(tmp_path / "a.xlsx"),
                                  ExportOptions(include_incomplete=False))
    assert res.responses == 2


def test_target_checks_and_no_overwrite(core, acct, tmp_path):
    p = tmp_path / "x.xlsx"
    core.export.export_xlsx(acct.account_id, FORM_ID, str(p))
    with pytest.raises(ExportError, match="Ya existe"):
        core.export.export_xlsx(acct.account_id, FORM_ID, str(p))
    core.export.export_xlsx(acct.account_id, FORM_ID, str(p), overwrite=True)
    with pytest.raises(ExportError, match="terminar en"):
        core.export.export_xlsx(acct.account_id, FORM_ID, str(tmp_path / "x.csv"))
    with pytest.raises(ExportError, match="no existe"):
        core.export.export_xlsx(acct.account_id, FORM_ID, str(tmp_path / "nada" / "x.xlsx"))
    with pytest.raises(SurveyNotFoundError):
        core.export.export_xlsx(acct.account_id, "zzzzzz", str(tmp_path / "y.xlsx"))
    assert sorted(f.name for f in tmp_path.iterdir() if f.name != "home") == ["x.xlsx"]       # sin temporales sobrantes


def test_suggested_name_is_windows_safe(core, acct):
    name = core.export.suggested_name(acct.account_id, FORM_ID, "xlsx")
    assert name.endswith(".xlsx") and not any(c in name for c in '<>:"/\\|?*')


def test_pdf_and_png_exports(core, acct, tmp_path):
    out = tmp_path / "i.pdf"
    res = core.export.export_pdf(acct.account_id, FORM_ID, str(out))
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and res.format == "pdf" and res.responses == 3
    out2 = tmp_path / "t.pdf"
    core.export.export_pdf(acct.account_id, FORM_ID, str(out2), ExportOptions(include_text=True, kind="30d"))
    assert out2.read_bytes().startswith(b"%PDF")
    png = tmp_path / "g.png"
    core.export.save_png(str(png), b"\x89PNG\r\n\x1a\n" + b"0" * 10)
    assert png.exists()
    with pytest.raises(ExportError, match="no es válida"):
        core.export.save_png(str(tmp_path / "h.png"), b"nope")
    with pytest.raises(ExportError, match="Ya existe"):
        core.export.save_png(str(png), b"\x89PNG\r\n\x1a\n")


def test_individual_exports(core, acct, tmp_path):
    opts = ExportOptions(scope="individual", include_text=True)
    x = tmp_path / "ind.xlsx"
    res = core.export.export_xlsx(acct.account_id, FORM_ID, str(x), opts)
    wb = load(x)
    assert wb.sheetnames == ["Resumen", "Respuestas", "Detalle"] and res.responses == 3
    detalle = [[c.value for c in r] for r in wb["Detalle"].iter_rows(min_row=2)]
    assert any(r[0] == "Usuario 001" and "Rojo, Verde" in str(r[4]) for r in detalle)
    assert not any("a@b.com" in str(c) for r in detalle for c in r)          # enmascarado
    p = tmp_path / "ind.pdf"
    core.export.export_pdf(acct.account_id, FORM_ID, str(p), opts)
    assert p.read_bytes().startswith(b"%PDF")
    one = tmp_path / "uno.pdf"
    r1 = core.export.export_pdf(acct.account_id, FORM_ID, str(one), ExportOptions(scope="individual", only_number=2))
    assert r1.responses == 1
    with pytest.raises(ExportError, match="No se encontró"):
        core.export.export_pdf(acct.account_id, FORM_ID, str(tmp_path / "z.pdf"),
                               ExportOptions(scope="individual", only_number=999))


def test_individual_cards_hide_text_by_default_and_skip_blank(core, acct):
    name, label, cards = core.export.individual_cards(acct.account_id, FORM_ID, ExportOptions(scope="individual"))
    assert len(cards) == 3 and cards[0].label == "Usuario 001"
    notes = [i for c in cards for i in c.items if i.is_note]
    assert notes and all("no incluida" in n.text for n in notes)
    third = next(c for c in cards if c.label == "Usuario 003")
    assert all(i.text for i in third.items)                                   # las preguntas en blanco no aparecen


@pytest.mark.parametrize("style", ["dark", "light"])
@pytest.mark.parametrize("scope", ["summary", "individual"])
def test_pdf_both_styles_and_scopes(core, acct, tmp_path, style, scope):
    out = tmp_path / f"{scope}-{style}.pdf"
    res = core.export.export_pdf(acct.account_id, FORM_ID, str(out), ExportOptions(scope=scope, style=style))
    assert out.read_bytes().startswith(b"%PDF") and res.responses == 3


def test_pdf_palettes_follow_the_design():
    from tally_monitor.export.pdf_writer import Pal
    dark, light = Pal("dark"), Pal("light")
    assert dark.bg.hexval() == "0x0b0b0f" and light.bg.hexval() == "0xffffff"
    assert dark.action.hexval() == "0xe6b84a" and light.action.hexval() == "0x8a5a3b"     # dorado / café
    assert dark.accent.hexval() == "0x8b7bff" and light.accent.hexval() == "0x12a198"     # violeta / aqua
    assert Pal("otro").bg.hexval() == dark.bg.hexval()


def test_individual_pdf_has_no_size_limit(core, acct, tmp_path):
    out = tmp_path / "todo.pdf"
    res = core.export.export_pdf(acct.account_id, FORM_ID, str(out), ExportOptions(scope="individual"))
    assert res.responses == 3 and out.exists() and not list(tmp_path.glob("*.tmp*"))


def _tiny_png() -> bytes:
    import struct
    import zlib

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"\x00" + b"\xff\x00\x00\xff" * 4
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 1, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw * 1)) + chunk(b"IEND", b""))


@pytest.mark.parametrize("logo", [_tiny_png(), b"esto no es una imagen"])
def test_pdf_with_logo_or_with_broken_logo_still_exports(core, acct, tmp_path, monkeypatch, logo):
    from tally_monitor.core import assets
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "logo.png").write_bytes(logo)
    monkeypatch.setattr(assets, "ASSETS_DIR", tmp_path / "assets")
    out = tmp_path / "l.pdf"
    core.export.export_pdf(acct.account_id, FORM_ID, str(out), ExportOptions(style="light"))
    assert out.read_bytes().startswith(b"%PDF")

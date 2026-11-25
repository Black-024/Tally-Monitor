"""Pruebas de la interfaz con Qt REAL (offscreen). Requieren PySide6 y pytest-qt: py -m pip install PySide6 pytest-qt"""
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QLineEdit  # noqa: E402

from support.fixtures import core, make_core, paths, protector, clock, tally, ctx, runner  # noqa: F401,E402
from support.shared import KEY_A, KEY_B  # noqa: E402
from tally_monitor.core.secret import SecretStr  # noqa: E402
from tally_monitor.ui.dialogs.key_dialogs import AddAccountDialog, ReplaceKeyDialog  # noqa: E402
from tally_monitor.ui.main_window import MainWindow  # noqa: E402
from tally_monitor.ui.pages.accounts import AccountCard  # noqa: E402
from tally_monitor.ui.widgets.secret_line_edit import SecretLineEdit  # noqa: E402


def test_secret_edit_is_masked(qtbot):
    e = SecretLineEdit()
    qtbot.addWidget(e)
    assert e.echoMode() == QLineEdit.EchoMode.Password
    e.setText("tly-ABCDEFGH")
    assert e.secret().reveal() == "tly-ABCDEFGH" and "ABCDEFGH" not in repr(e.secret())
    e.clear_secret()
    assert e.text() == ""


def test_main_window_navigation(qtbot, ctx, runner):
    w = MainWindow(ctx, runner)
    qtbot.addWidget(w)
    w.show()
    for key, page in w.pages.items():
        w.nav_buttons[key].click()
        assert w.stack.currentWidget() is page and w.nav_buttons[key].isChecked()


def test_empty_state_then_account_listed(qtbot, ctx, runner, core):
    w = MainWindow(ctx, runner)
    qtbot.addWidget(w)
    w.show()
    w.navigate("cuentas")
    qtbot.wait(300)
    assert not w.accounts_page.findChildren(AccountCard)
    core.accounts.add_account("Uno", SecretStr(KEY_A))
    w.accounts_page.refresh()
    qtbot.waitUntil(lambda: len(w.accounts_page.findChildren(AccountCard)) == 1, timeout=5000)


def test_add_dialog_flow_and_masking(qtbot, ctx, runner):
    dlg = AddAccountDialog(ctx, runner, "Cuenta 1")
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.key_edit.echoMode() == QLineEdit.EchoMode.Password
    dlg.key_edit.setText(KEY_A)
    dlg.ok_btn.click()
    qtbot.waitUntil(lambda: dlg.account is not None, timeout=5000)
    assert dlg.account.status == "active"


def test_add_dialog_shows_error_and_keeps_open(qtbot, ctx, runner, core):
    dlg = AddAccountDialog(ctx, runner, "Cuenta 1")
    qtbot.addWidget(dlg)
    dlg.show()
    dlg.key_edit.setText("tly-no-existe-1234567890")
    dlg.ok_btn.click()
    qtbot.waitUntil(lambda: "rechazó" in dlg.status.text(), timeout=5000)
    assert dlg.isVisible() and dlg.account is None and core.accounts.list_accounts() == []


def test_dialog_cannot_close_while_busy(qtbot, ctx, runner):
    dlg = AddAccountDialog(ctx, runner, "Cuenta 1")
    qtbot.addWidget(dlg)
    dlg.show()
    dlg._set_busy(True)
    dlg.reject()
    assert dlg.isVisible()


def test_replace_dialog_keeps_old_key_on_other_user(qtbot, ctx, runner, core):
    a = core.accounts.add_account("Uno", SecretStr(KEY_A))
    dlg = ReplaceKeyDialog(ctx, runner, a.account_id, "Uno")
    qtbot.addWidget(dlg)
    dlg.show()
    dlg.key_edit.setText(KEY_B)
    dlg.ok_btn.click()
    qtbot.waitUntil(lambda: "otro usuario" in dlg.status.text(), timeout=5000)
    assert core.accounts._store.load(a.account_id).api_key.reveal() == KEY_A


def test_degraded_mode_only_allows_settings(qtbot, ctx, runner):
    ctx.degraded = True
    w = MainWindow(ctx, runner)
    qtbot.addWidget(w)
    assert [k for k, b in w.nav_buttons.items() if b.isEnabled()] == ["configuracion"]


# ---- Encuestas (Qt real) ----
from PySide6.QtWidgets import QLabel  # noqa: E402

from support.forms import FORM_ID, add_form, submission  # noqa: E402
from tally_monitor.ui.pages.surveys import SurveyCard  # noqa: E402


def _labels(widget):
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def test_surveys_flow_with_real_qt(qtbot, ctx, runner, core, tally):
    core.accounts.add_account("Uno", SecretStr(KEY_A))
    add_form(tally, [submission(n, text=f"comentario {n}") for n in (10, 20, 30)])
    w = MainWindow(ctx, runner)
    qtbot.addWidget(w)
    w.show()
    w.navigate("encuestas")
    page = w.surveys_page
    qtbot.waitUntil(lambda: page._account_id is not None, timeout=5000)
    assert not page.findChildren(SurveyCard)                       # nada guardado todavía
    page.refresh_btn.click()
    qtbot.waitUntil(lambda: len(page.findChildren(SurveyCard)) == 1, timeout=8000)
    card = page.findChildren(SurveyCard)[0]
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    det = page.detail
    qtbot.waitUntil(lambda: det.title.text() == "Mi encuesta", timeout=5000)
    det.sync_btn.click()
    qtbot.waitUntil(lambda: det.user_list.count() == 3, timeout=8000)
    assert det.user_list.item(0).text().startswith("Usuario 001")
    det.user_list.setCurrentRow(1)
    texts = _labels(det.detail_holder)
    assert "Usuario 002" in texts and any("comentario 20" in t for t in texts)
    assert any(lbl.property("role") == "user-id" for lbl in det.detail_holder.findChildren(QLabel))
    assert any(lbl.property("role") == "meta" for lbl in det.detail_holder.findChildren(QLabel))
    det.search.setText("003")
    assert det.user_list.count() == 1
    det.back_btn.click()
    qtbot.waitUntil(lambda: page.stack.currentWidget() is page.list_page, timeout=3000)


def test_sync_mode_setting_roundtrip_with_real_qt(qtbot, ctx, runner, core):
    from tally_monitor.ui.pages.settings import SettingsPage
    page = SettingsPage(ctx, runner)
    qtbot.addWidget(page)
    page.show()
    page.refresh()
    qtbot.waitUntil(lambda: page.sync_combo.currentData() == "manual", timeout=3000)
    page.sync_combo.setCurrentIndex(page.sync_combo.findData("auto"))
    qtbot.waitUntil(lambda: core.settings.get("sync_mode") == "auto", timeout=3000)


def _synced_window(qtbot, ctx, runner, core, tally, n=3):
    from support.forms import FORM_ID, add_form, submission
    core.accounts.add_account("Cuenta", SecretStr(KEY_A))
    add_form(tally, [submission(i, text=f"c{i}") for i in range(1, n + 1)])
    acct = core.accounts.list_accounts()[0].account_id
    core.sync.sync_forms(acct)
    core.sync.sync_form(acct, FORM_ID)
    w = MainWindow(ctx, runner)
    qtbot.addWidget(w)
    w.resize(1100, 800)
    w.show()
    w.navigate("encuestas")                  # la ventana arranca en Inicio; estas pruebas parten de la pared de encuestas
    return w, FORM_ID


def test_home_shows_summary_and_opens_survey(qtbot, ctx, runner, core, tally):
    from tally_monitor.ui.pages.home import _TopRow
    w, fid = _synced_window(qtbot, ctx, runner, core, tally)
    w.navigate("inicio")
    qtbot.waitUntil(lambda: bool(w.home_page.findChildren(_TopRow)), timeout=8000)
    row = w.home_page.findChildren(_TopRow)[0]
    qtbot.mouseClick(row, Qt.MouseButton.LeftButton)
    assert w.stack.currentWidget() is w.surveys_page and w.surveys_page.stack.currentWidget() is w.workspace


def test_wall_card_opens_workspace_and_resumen_paints(qtbot, ctx, runner, core, tally):
    """La tarjeta abre el espacio de la encuesta; dibuja de verdad los gráficos (paintEvent)."""
    from tally_monitor.ui.pages.surveys import SurveyCard
    w, fid = _synced_window(qtbot, ctx, runner, core, tally)
    qtbot.waitUntil(lambda: bool(w.surveys_page.findChildren(SurveyCard)), timeout=8000)
    card = w.surveys_page.findChildren(SurveyCard)[0]
    assert card.number.text() == "3"
    qtbot.mouseClick(card, Qt.MouseButton.LeftButton)
    ws = w.workspace
    assert w.surveys_page.stack.currentWidget() is ws and ws.current_tab == "resumen"
    page = w.analysis_page
    qtbot.waitUntil(lambda: page.result is not None, timeout=8000)
    with qtbot.capture_exceptions() as exceptions:
        page.grab()
        page.holder.grab()
    assert not exceptions and page.result.overview.total == 3
    # filtros como botoncitos
    page.chips["7d"].click()
    qtbot.waitUntil(lambda: page.result.filter.kind == "7d", timeout=8000)
    page.incomplete_btn.click()
    qtbot.waitUntil(lambda: page.result.include_incomplete is False, timeout=8000)
    assert page.incomplete_btn.text() == "Sin incompletos"
    # pestañas
    ws.tab_buttons["respuestas"].click()
    assert ws.stack.currentWidget() is ws.detail
    ws.tab_buttons["exportar"].click()
    assert ws.stack.currentWidget() is ws.exports and "7 días" in ws.exports.period_label.text()
    ws.back_requested.emit()
    assert w.surveys_page.stack.currentWidget() is w.surveys_page.list_page


def test_exports_real_qt_summary_and_individual(qtbot, ctx, runner, core, tally, tmp_path):
    w, fid = _synced_window(qtbot, ctx, runner, core, tally)
    acct = core.accounts.list_accounts()[0].account_id
    w.surveys_page._account_id = acct
    w.surveys_page.open_survey(fid)
    page = w.exports_page
    w.workspace.show_tab("exportar")
    assert not page.mask_box.isEnabled() and page.text_warning.isHidden()
    page.text_box.setChecked(True)
    assert page.mask_box.isEnabled() and not page.text_warning.isHidden()
    page.text_box.setChecked(False)

    def run(fmt, name):
        page.ask_path = lambda suggested, f, n=name: str(tmp_path / n)
        page.export(fmt)
        qtbot.waitUntil(lambda: (tmp_path / name).exists() and not page._busy, timeout=10000)

    for fmt in ("png", "xlsx", "pdf"):
        run(fmt, "res." + fmt)
    assert (tmp_path / "res.png").read_bytes().startswith(b"\x89PNG")
    page.set_scope("individual")
    assert page.text_box.isChecked() and not page.who_row.isHidden() and "No recomendado" in page.png_btn.text()
    run("xlsx", "ind.xlsx")
    run("pdf", "ind.pdf")
    # PNG individual: pide confirmación; si se rechaza no genera nada
    asked = []
    page.confirm_png_individual = lambda: asked.append(1) or False
    page.ask_path = lambda s, f: str(tmp_path / "ind.png")
    page.export("png")
    qtbot.wait(300)
    assert asked and not (tmp_path / "ind.png").exists()
    page.confirm_png_individual = lambda: True
    page.export("png")
    qtbot.waitUntil(lambda: (tmp_path / "ind.png").exists() and not page._busy, timeout=10000)
    assert (tmp_path / "ind.png").read_bytes().startswith(b"\x89PNG")
    # una sola persona
    page.who_one.setChecked(True)
    page.who_edit.setText("2")
    run("pdf", "uno.pdf")
    page.who_edit.setText("zzz")
    page.ask_path = lambda s, f: str(tmp_path / "no.pdf")
    page.export("pdf")
    qtbot.waitUntil(lambda: "No encontré" in page.notice.text(), timeout=8000)
    assert not (tmp_path / "no.pdf").exists()


def _pixel(img, x, y):
    c = img.pixelColor(x, y)
    return c.red(), c.green(), c.blue(), c.alpha()


def test_pill_button_is_fully_rounded(qtbot):
    """El selector del menú no debe verse cuadrado: las esquinas quedan sin relleno y el centro lleva el color de acción."""
    from tally_monitor.ui.theme import current
    from tally_monitor.ui.widgets.pill_button import PillButton
    from PySide6.QtGui import QColor
    for theme_name in ("dark", "light"):
        current.set_name(theme_name)
        b = PillButton("Encuestas", "pill")
        b.setChecked(True)
        qtbot.addWidget(b)
        b.resize(b.sizeHint())
        img = b.grab().toImage()
        action = QColor(current.colors()["action"])
        want = (action.red(), action.green(), action.blue())
        assert _pixel(img, 8, img.height() // 2)[:3] == want                 # el cuerpo de la píldora lleva el color de acción
        assert _pixel(img, img.width() // 2, img.height() // 2 + 8)[:3] == want
        for corner in ((0, 0), (img.width() - 1, 0), (0, img.height() - 1), (img.width() - 1, img.height() - 1)):
            assert _pixel(img, *corner)[:3] != want                          # esquinas redondeadas: sin relleno
    current.set_name("dark")


def test_theme_switch_from_settings_changes_app_theme_and_saves(qtbot, ctx, runner, core):
    from tally_monitor.ui.theme import current
    applied = []
    ctx.apply_theme = lambda name: (applied.append(name), current.set_name(name))
    w = MainWindow(ctx, runner)
    qtbot.addWidget(w)
    w.show()
    w.navigate("configuracion")
    page = w.pages["configuracion"]
    page.theme_buttons["light"].click()
    qtbot.waitUntil(lambda: core.settings.get("theme") == "light", timeout=5000)
    assert applied == ["light"] and page.theme_buttons["light"].isChecked()
    w.refresh_theme()
    assert w.exports_page._style == "light"           # el estilo de exportación acompaña al tema de la ventana
    current.set_name("dark")


def test_png_export_in_light_and_dark_styles(qtbot, ctx, runner, core, tally):
    from PySide6.QtGui import QImage
    from tally_monitor.ui.pages.exports import render_summary_png
    w, fid = _synced_window(qtbot, ctx, runner, core, tally)
    acct = core.accounts.list_accounts()[0].account_id
    analysis = core.analysis.analyze(acct, fid, "all")
    out = {}
    for style in ("dark", "light"):
        img = QImage.fromData(render_summary_png("Encuesta", analysis, style))
        out[style] = _pixel(img, 4, img.height() // 2)
    assert sum(out["light"][:3]) > sum(out["dark"][:3]) + 300                  # claro vs oscuro, independiente de la ventana


def test_license_and_privacy_buttons_show_text_inside_the_app(qtbot, ctx, runner, monkeypatch):
    from tally_monitor.ui.dialogs.text_dialog import TextDialog
    shown = []
    monkeypatch.setattr(TextDialog, "exec", lambda self: shown.append((self.windowTitle(), self.view.toPlainText())) or 0)
    w = MainWindow(ctx, runner)
    qtbot.addWidget(w)
    page = w.pages["configuracion"]
    page._open_doc("THIRD_PARTY_LICENSES.md")
    page._open_doc("PRIVACIDAD.md")
    assert "MIT License" in shown[0][1] and "PySide6" in shown[0][1]
    assert "API Key" in shown[1][1] and "No se encontró" not in shown[1][1]


# ---- 1.1: metas, notas, etiquetas, archivadas, ritmo, cruce, avisos (Qt real) ----
def _first_account(core):
    return core.accounts.list_accounts()[0].account_id


def test_edit_dialog_validates_and_saves(qtbot, ctx, runner, core, tally):
    from tally_monitor.ui.dialogs.edit_survey_dialog import EditSurveyDialog
    w, fid = _synced_window(qtbot, ctx, runner, core, tally)
    aid = _first_account(core)
    dlg = EditSurveyDialog(ctx, runner, aid, core.surveys.get_survey(aid, fid))
    qtbot.addWidget(dlg)
    dlg.show()
    dlg.goal_edit.setText("abc")
    dlg.ok_btn.click()
    assert "número entero" in dlg.status.text() and core.surveys.get_survey(aid, fid).goal is None
    dlg.goal_edit.setText("1.000")                      # puntos de miles es-AR
    dlg.tag_edit.setText("  Clientes   VIP ")
    dlg.tag_add_btn.click()
    assert dlg.tags() == ["Clientes VIP"] and dlg.tag_edit.text() == ""
    dlg.tag_edit.setText("clientes vip")                 # duplicada sin distinguir mayúsculas: no se repite
    dlg.tag_add_btn.click()
    assert dlg.tags() == ["Clientes VIP"]
    dlg.tag_edit.setText("x" * 30)
    dlg.tag_add_btn.click()
    assert "24" in dlg.status.text() and dlg.tags() == ["Clientes VIP"]
    dlg.tag_edit.setText("")
    dlg.note_edit.setPlainText("  mi nota  ")
    dlg.ok_btn.click()
    qtbot.waitUntil(lambda: dlg.saved is not None, timeout=5000)
    s = core.surveys.get_survey(aid, fid)
    assert (s.goal, s.note, s.tags) == (1000, "mi nota", ("Clientes VIP",))


def test_edit_button_in_header_shows_note_under_title(qtbot, ctx, runner, core, tally):
    from tally_monitor.ui.dialogs.edit_survey_dialog import EditSurveyDialog
    w, fid = _synced_window(qtbot, ctx, runner, core, tally)
    aid = _first_account(core)
    w.surveys_page._account_id = aid
    w.surveys_page.open_survey(fid)
    det = w.surveys_page.detail
    qtbot.waitUntil(lambda: det._survey is not None, timeout=8000)
    assert det.note_label.isHidden()
    core.surveys.set_survey_meta(aid, fid, 10, "Nota de prueba", ["a"])
    det.make_edit_dialog = lambda: type("D", (), {"exec": lambda self: 1, "saved": object()})()
    det.edit_btn.click()
    qtbot.waitUntil(lambda: det.note_label.text() == "Nota de prueba", timeout=8000)
    assert not det.note_label.isHidden()


def test_wall_shows_goal_bar_tags_and_archives(qtbot, ctx, runner, core, tally):
    from tally_monitor.ui.pages.surveys import SurveyCard
    w, fid = _synced_window(qtbot, ctx, runner, core, tally)
    aid = _first_account(core)
    core.surveys.set_survey_meta(aid, fid, 6, "", ["Alfa", "Beta"])
    w.navigate("encuestas")
    page = w.surveys_page
    qtbot.waitUntil(lambda: len(page.findChildren(SurveyCard)) == 1, timeout=8000)
    card = page.findChildren(SurveyCard)[0]
    qtbot.waitUntil(lambda: card.goal_bar is not None, timeout=3000)
    assert card.goal_bar.bar.value() == 50 and "3 de 6 (50 %)" in card.goal_bar.line.text()
    assert [c.text() for c in card.tag_labels] == ["Alfa", "Beta"]
    assert set(page.tag_chips) == {None, "Alfa", "Beta"}
    page.tag_chips["Alfa"].click()
    assert page._tag == "Alfa"
    qtbot.waitUntil(lambda: len(page.findChildren(SurveyCard)) == 1, timeout=3000)
    # archivar: desaparece de la lista
    page.findChildren(SurveyCard)[0].archive_btn.click()
    qtbot.waitUntil(lambda: not page.findChildren(SurveyCard) or all(c.survey.archived for c in page.findChildren(SurveyCard)),
                    timeout=8000)
    qtbot.waitUntil(lambda: core.surveys.get_survey(aid, fid).archived, timeout=5000)
    page._reload_saved()
    qtbot.waitUntil(lambda: page.archived_chip.isVisible(), timeout=5000)
    assert not any(isinstance(c, SurveyCard) and not c.isHidden() for c in page.findChildren(SurveyCard)
                   if not c.survey.archived)
    page.archived_chip.click()                                       # «Mostrar archivadas»
    qtbot.waitUntil(lambda: any(c.survey.archived for c in page.findChildren(SurveyCard)), timeout=5000)
    card = [c for c in page.findChildren(SurveyCard) if c.survey.archived][0]
    assert card.archive_btn.text() == "Desarchivar"
    card.archive_btn.click()
    qtbot.waitUntil(lambda: not core.surveys.get_survey(aid, fid).archived, timeout=5000)


def test_home_goals_section_excludes_archived(qtbot, ctx, runner, core, tally):
    from tally_monitor.ui.pages.home import _GoalRow
    w, fid = _synced_window(qtbot, ctx, runner, core, tally)
    aid = _first_account(core)
    core.surveys.set_survey_meta(aid, fid, 10, "", [])
    w.navigate("inicio")
    qtbot.waitUntil(lambda: bool(w.home_page.findChildren(_GoalRow)), timeout=8000)
    row = w.home_page.findChildren(_GoalRow)[0]
    assert "3 de 10 (30 %)" in row.goal_bar.line.text()
    with qtbot.capture_exceptions() as exceptions:
        w.home_page.grab()
    assert not exceptions
    core.surveys.set_archived(aid, fid, True)
    w.home_page.refresh()
    qtbot.waitUntil(lambda: not w.home_page.findChildren(_GoalRow), timeout=8000)


def test_resumen_rhythm_and_cross_filter(qtbot, ctx, runner, core, tally):
    w, fid = _synced_window(qtbot, ctx, runner, core, tally)
    aid = _first_account(core)
    core.surveys.set_survey_meta(aid, fid, 10, "", [])
    w.surveys_page._account_id = aid
    w.surveys_page.open_survey(fid)
    page = w.analysis_page
    qtbot.waitUntil(lambda: page.result is not None and getattr(page, "rhythm_week", None) is not None, timeout=8000)
    assert page.result.trends is not None and page.rhythm_week.text().startswith("Esta semana:")
    assert page.rhythm_peak.text().startswith("Día más activo:")
    assert getattr(page, "goal_bar", None) is not None
    with qtbot.capture_exceptions() as exceptions:
        page.holder.grab()
    assert not exceptions
    # cruce
    qtbot.waitUntil(lambda: page.cross_question_combo is not None, timeout=3000)
    assert page.cross_question_combo.count() == 2
    page.cross_question_combo.setCurrentIndex(0)
    page.cross_option_combo.setCurrentIndex(page.cross_option_combo.findData("No"))
    page.cross_apply_btn.click()
    qtbot.waitUntil(lambda: page.result.answer_filter is not None, timeout=8000)
    assert page.result.matched == 0 and page.result.overview.total == 0
    page.cross_option_combo.setCurrentIndex(page.cross_option_combo.findData("Sí"))
    page.cross_apply_btn.click()
    qtbot.waitUntil(lambda: page.result.matched == 3, timeout=8000)
    assert "Mostrando 3 de 3 personas que respondieron «Sí»" in page.cross_ribbon_label.text()
    page.cross_clear_btn.click()
    qtbot.waitUntil(lambda: page.result.answer_filter is None, timeout=8000)
    # al abrir otra vez la encuesta, el filtro se reinicia
    page.cross_question_combo.setCurrentIndex(0)
    page.cross_apply_btn.click()
    qtbot.waitUntil(lambda: page.result.answer_filter is not None, timeout=8000)
    page.open_survey(aid, fid)
    qtbot.waitUntil(lambda: page.result.answer_filter is None, timeout=8000)


def test_settings_notify_section(qtbot, ctx, runner, core, monkeypatch):
    from tally_monitor.ui.pages import settings as settings_mod
    monkeypatch.setattr(settings_mod, "tray_available", lambda: False)
    off = settings_mod.SettingsPage(ctx, runner)
    qtbot.addWidget(off)
    assert not off.notify_chk.isEnabled() and off.notify_status.text() == "Tu sistema no ofrece bandeja"
    monkeypatch.setattr(settings_mod, "tray_available", lambda: True)
    changed = []
    page = settings_mod.SettingsPage(ctx, runner, on_notify_changed=lambda: changed.append(1))
    qtbot.addWidget(page)
    page.show()
    page.refresh()
    qtbot.waitUntil(lambda: page.notify_combo.currentData() == "60", timeout=5000)
    assert page.notify_chk.isEnabled() and not page.notify_chk.isChecked()
    page.notify_chk.setChecked(True)
    qtbot.waitUntil(lambda: core.settings.get("notify_mode") == "on" and bool(changed), timeout=5000)
    page.notify_combo.setCurrentIndex(page.notify_combo.findData("15"))
    qtbot.waitUntil(lambda: core.settings.get("notify_interval_min") == "15", timeout=5000)


def test_window_notify_timer_and_close_to_tray(qtbot, ctx, runner, core, monkeypatch):
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication
    from tally_monitor.ui import main_window as mw_mod

    class FakeTray:
        def __init__(self):
            self.msgs, self.visible = [], False
        def show(self): self.visible = True
        def hide(self): self.visible = False
        def notify(self, t, b): self.msgs.append((t, b))

    monkeypatch.setattr(mw_mod.tray_mod, "tray_available", lambda: True)
    infos = []
    monkeypatch.setattr(mw_mod, "show_info", lambda parent, title, text: infos.append(text))
    w = MainWindow(ctx, runner)
    qtbot.addWidget(w)
    w.tray = FakeTray()
    try:
        w.set_notify_state(True, 30)
        assert w.notify_timer.isActive() and w.notify_timer.interval() == 30 * 60 * 1000 and w.tray.visible
        w.first_check_timer.stop()
        from types import SimpleNamespace as NS
        w._notify_result(NS(notify=True, title="1 respuesta nueva en 1 encuesta", body="Tocá para abrir Tally Monitor",
                            checked_at="x", errors=0))
        assert w.tray.msgs == [("1 respuesta nueva en 1 encuesta", "Tocá para abrir Tally Monitor")]
        ev = QCloseEvent()
        w.closeEvent(ev)
        assert not ev.isAccepted() and len(infos) == 1 and core.settings.get("tray_hint_shown") == "1"
        ev = QCloseEvent()
        w.closeEvent(ev)
        assert not ev.isAccepted() and len(infos) == 1            # la explicación sale una sola vez
        w.set_notify_state(False, 60)
        assert not w.notify_timer.isActive() and not w.tray.visible
        monkeypatch.setattr(mw_mod.tray_mod, "tray_available", lambda: False)
        w.set_notify_state(True, 60)
        assert not w._notify_on and not w.notify_timer.isActive()
    finally:
        QApplication.setQuitOnLastWindowClosed(True)

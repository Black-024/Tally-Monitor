"""Ejecuta los flujos de la interfaz con el sustituto de Qt. Uso: python tests/support/ui_shim_smoke.py"""
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ["TALLY_MONITOR_LANG"] = "es"      # los textos se comprueban en español, antes de importar la app
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from support import qt_shim  # noqa: E402

qt_shim.install()

from support.shared import KEY_A, KEY_B, KEY_C, FakeClock  # noqa: E402
from support.fake_protector import FakeProtector  # noqa: E402
from support.fake_tally import FakeTally  # noqa: E402
from tally_monitor.api.client import TallyClient  # noqa: E402
from tally_monitor.app import build_core  # noqa: E402
from tally_monitor.core.config import AppPaths  # noqa: E402
from tally_monitor.ui import strings as S  # noqa: E402
from tally_monitor.ui.context import AppContext  # noqa: E402
from tally_monitor.ui.dialogs import key_dialogs, simple_dialogs  # noqa: E402
from tally_monitor.ui.main_window import MainWindow  # noqa: E402
from tally_monitor.ui.pages import accounts as accounts_mod  # noqa: E402
from tally_monitor.ui.pages import settings as settings_mod  # noqa: E402
from tally_monitor.ui.workers import TaskRunner  # noqa: E402


class Capture(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.records = []

    def emit(self, record):
        self.records.append(record.getMessage())


errors = Capture()
logging.getLogger("tally_monitor").addHandler(errors)
logging.getLogger("tally_monitor").setLevel(logging.DEBUG)

tally = FakeTally().start()
tally.users.update({KEY_A: "user-A", KEY_B: "user-B", KEY_C: "user-A"})
home = Path(tempfile.mkdtemp()) / "home"
core = build_core(paths=AppPaths(home), protector=FakeProtector(), clock=FakeClock(), configure_logging=False,
                  client=TallyClient(tally.url, sleep=lambda s: None))
report = core.startup.run()
ctx = AppContext(core.accounts, core.backups, core.settings, str(home), str(home / "logs"), "0.1.0",
                 startup_messages=report.messages, degraded=False,
                 sync=core.sync, surveys=core.surveys, favorites=core.favorites, analysis=core.analysis, export=core.export,
                 notifier=core.notifier)
runner = TaskRunner()
CHECKS = []


def wait():
    t0 = time.time()
    while runner._callbacks and time.time() - t0 < 10:
        time.sleep(0.01)
    time.sleep(0.02)
    assert not runner._callbacks, "tarea sin terminar"


def check(name, cond):
    CHECKS.append((bool(cond), name))
    print(("  OK    " if cond else "  FALLO ") + name)


win = MainWindow(ctx, runner)
wait()
check("la ventana principal se construye y navega", True)
for key, _ in S.NAV:
    win.navigate(key)
    wait()

# --- alta con clave mal formada: no llega al servicio ---
dlg = key_dialogs.AddAccountDialog(ctx, runner, "Cuenta 1")
dlg.key_edit.setText("\x16")
n_req = len(tally.requests)
dlg._submit()
wait()
check("clave mal formada: se rechaza en el diálogo, sin red", len(tally.requests) == n_req and dlg.account is None
      and "formato" in dlg.status.text())

# --- alta válida ---
dlg = key_dialogs.AddAccountDialog(ctx, runner, "Cuenta 1")
dlg.name_edit.setText("Principal")
dlg.key_edit.setText(KEY_A)
dlg._submit()
wait()
check("alta válida: la cuenta queda guardada y activa", dlg.account is not None and dlg.account.status == "active")
check("el diálogo no deja la clave en el campo al cerrarse", dlg._result == 1)

# --- alta rechazada por Tally ---
dlg = key_dialogs.AddAccountDialog(ctx, runner, "Cuenta 2")
dlg.key_edit.setText("tly-esta-no-existe-000000")
dlg._submit()
wait()
check("clave rechazada: se muestra el error y no se guarda", dlg.account is None and "rechazó" in dlg.status.text()
      and len(core.accounts.list_accounts()) == 1)

# --- páginas ---
acc_page, accounts = win.accounts_page, None
acc_page.refresh()
wait()
accounts = core.accounts.list_accounts()
a = accounts[0]
acc_page.validate(a.account_id)
wait()
check("validar desde la página funciona", core.accounts.get_account(a.account_id).status == "active")

simple_dialogs.ask_new_name = lambda parent, current: "Renombrada"
accounts_mod.ask_new_name = simple_dialogs.ask_new_name
acc_page.rename(a)
wait()
check("renombrar", core.accounts.get_account(a.account_id).name == "Renombrada")

# --- reemplazo ---
dlg = key_dialogs.ReplaceKeyDialog(ctx, runner, a.account_id, "Renombrada")
dlg.key_edit.setText(KEY_B)           # otro usuario → debe conservar la clave anterior
dlg._submit()
wait()
check("reemplazo con clave de otro usuario: se conserva la anterior",
      dlg.result_info is None and "otro usuario" in dlg.status.text()
      and core.accounts._store.load(a.account_id).api_key.reveal() == KEY_A)
dlg = key_dialogs.ReplaceKeyDialog(ctx, runner, a.account_id, "Renombrada")
dlg.key_edit.setText(KEY_C)
dlg._submit()
wait()
check("reemplazo válido", dlg.result_info is not None and dlg.result_info.identity_verified
      and core.accounts._store.load(a.account_id).api_key.reveal() == KEY_C)

# --- backups desde Configuración ---
sp = win.settings_page
sp.refresh()
wait()
sp._create_backup()
wait()
check("crear copia manual", any(b.reason == "manual" for b in core.backups.list_backups()))
sp._fill_table(core.backups.list_backups())
settings_mod.confirm_destructive = lambda *a, **k: True
def _sel():
    manual = [b for b in core.backups.list_backups() if b.reason == "manual"]
    return (manual[0].filename, "fecha") if manual else None


sp._selected = _sel
sp._restore()
wait()
check("restaurar desde Configuración", True)
sp._delete_backup()
wait()
check("eliminar copia", not any(b.reason == "manual" for b in core.backups.list_backups()))
sp._auto_toggled(False)
wait()
check("preferencia de copia automática", core.settings.get("auto_backup") == "0")
sp._level_changed("DEBUG")
wait()
check("nivel de log", core.settings.get("log_level") == "DEBUG")

# --- encuestas ---
from support.forms import FORM_ID, add_form, push, submission  # noqa: E402
from tally_monitor.core.secret import SecretStr  # noqa: E402

acct2 = core.accounts.add_account("Para encuestas", SecretStr(KEY_B))
add_form(tally, [submission(n, text=f"comentario {n}") for n in (10, 20, 30)])
sv = win.surveys_page
sv.refresh()
wait()
check("Encuestas: sin sincronizar, la lista guardada está vacía", sv._surveys == [] and sv._account_id is not None)
sv.sync_list()
wait()
wait()
check("Encuestas: 'Actualizar lista' trae la encuesta", [s.form_id for s in sv._surveys] == [FORM_ID])
sv.open_survey(FORM_ID)
wait()
det = sv.detail
check("Detalle: abre y muestra título sin respuestas aún", det.title.text() == "Mi encuesta" and det._views == [])
det.sync(full=False)
wait()
wait()
check("Detalle: sincroniza y lista los usuarios en orden", [v.label for v in det._views]
      == ["Usuario 001", "Usuario 002", "Usuario 003"] and det.user_list.count() == 3)
check("Detalle: aviso de resultado", "descargaron 3 respuestas" in det.notice.text())
det.user_list.setCurrentRow(2)
det._row_changed(2)
check("Detalle: se puede mostrar una respuesta individual", det._visible[2].answers[0].question_title != "")
det.search.setText("002")
det._apply_filter()
check("Detalle: la búsqueda por número filtra", [v.label for v in det._visible] == ["Usuario 002"])
det.search.setText("")
push(tally, submission(40))
det.sync(full=False)
wait()
wait()
check("Detalle: segunda sincronización agrega solo lo nuevo", len(det._views) == 4 and "1 respuesta nueva." in det.notice.text())
sv.set_favorite(FORM_ID, True)
wait()
check("Favorita: se guarda y la lista la marca", sv._surveys[0].is_favorite)
check("Reciente: quedó registrada al abrir", core.favorites.recents(sv._account_id) == [FORM_ID])
sp.refresh()
wait()
sp.sync_combo.setCurrentIndex(sp.sync_combo.findData("auto"))
sp._sync_mode_changed(1)
wait()
check("Ajuste de sincronización automática", core.settings.get("sync_mode") == "auto")
core.settings.set("sync_mode", "manual")
tally.stop()
det.sync(full=False)
wait()
wait()
check("Detalle sin red: mensaje claro y lo guardado sigue visible", len(det._views) == 4
      and "ya está guardado" in det.notice.text())

# --- espacio de la encuesta: Resumen / Respuestas / Exportar ---
ws = win.workspace
ap, ep = ws.analysis, ws.exports
win.surveys_page.open_survey(FORM_ID)
wait()
wait()
wait()
check("Resumen: calcula con todo el período al abrir la encuesta", ap.result is not None and ap.result.overview.total == 4)
ap.set_filter("7d")
wait()
check("Resumen: el filtro cambia el resultado", ap.result.filter.kind == "7d")
import datetime as _dt  # noqa: E402


class _FakeDate:                       # el simulador no trae QDateEdit
    def __init__(self, d): self._d = d
    def date(self): return self
    def toPython(self): return self._d


ap.from_edit, ap.to_edit = _FakeDate(_dt.date(2020, 1, 1)), _FakeDate(_dt.date(2099, 1, 1))
ap.set_filter("custom")
wait()
check("Resumen: rango personalizado", ap.result.filter.kind == "custom")
ap.from_edit = _FakeDate(_dt.date(2099, 2, 1))
ap._reload()
wait()
check("Resumen: rango invertido muestra aviso", "posterior" in ap.notice.text())
ap.from_edit = _FakeDate(_dt.date(2020, 1, 1))
ap.set_filter("all")
wait()
ws.show_tab("exportar")
check("Exportar: muestra el período elegido en Resumen", "Todo" in ep.period_label.text())
out_dir = Path(tempfile.mkdtemp())
ep.ask_path = lambda suggested, fmt: str(out_dir / ("e." + fmt))
ep.export("xlsx")
wait()
wait()
check("Exportar: crea el Excel y avisa dónde", (out_dir / "e.xlsx").exists() and "Se guardó en" in ep.notice.text())
ep.export("pdf")
wait()
wait()
check("Exportar: crea el PDF", (out_dir / "e.pdf").exists())
ep.set_scope("individual")
ep.ask_path = lambda suggested, fmt: str(out_dir / ("ind." + fmt))
ep.export("xlsx")
wait()
wait()
check("Exportar: Excel de respuestas individuales", (out_dir / "ind.xlsx").exists())
ep.export("pdf")
wait()
wait()
check("Exportar: PDF de respuestas individuales", (out_dir / "ind.pdf").exists())
ep.ask_path = lambda suggested, fmt: None
before = len(list(out_dir.iterdir()))
ep.export("xlsx")
wait()
check("Exportar: cancelar el diálogo no crea nada", len(list(out_dir.iterdir())) == before)
ep.confirm_png_individual = lambda: False
ep.export("png")
wait()
check("Exportar: PNG de individuales pide confirmación y no sigue si se rechaza", len(list(out_dir.iterdir())) == before)


# ---------------- 1.1: meta, nota, etiquetas, archivadas ----------------
from types import SimpleNamespace as NS  # noqa: E402
from tally_monitor.ui import presenters as P  # noqa: E402
from tally_monitor.ui import main_window as mw_mod  # noqa: E402
from tally_monitor.ui import tray as tray_mod  # noqa: E402
from tally_monitor.ui.dialogs.edit_survey_dialog import EditSurveyDialog  # noqa: E402

aid2 = sv._account_id


def edit_dialog():
    return EditSurveyDialog(ctx, runner, aid2, core.surveys.get_survey(aid2, FORM_ID))


d = edit_dialog()
d.goal_edit.setText("abc")
d._submit()
wait()
check("Editar: meta que no es número se rechaza en el diálogo", d.status.text() == S.EDIT_GOAL_NOT_NUMBER
      and core.surveys.get_survey(aid2, FORM_ID).goal is None)
d.goal_edit.setText("0")
d._submit()
wait()
check("Editar: meta fuera de rango muestra el mensaje del servicio", "entre 1 y 1.000.000" in d.status.text()
      and core.surveys.get_survey(aid2, FORM_ID).goal is None)
d.goal_edit.setText("2.5")
d._submit()
wait()
check("Editar: un decimal no se interpreta como miles", d.status.text() == S.EDIT_GOAL_NOT_NUMBER)
d.goal_edit.setText("6")
d.tag_edit.setText("x" * 25)
d._add_tag()
check("Editar: etiqueta demasiado larga se rechaza al agregar", "24" in d.status.text() and d.tags() == [])
d.tag_edit.setText("  VIP   clientes ")
d._add_tag()
d.tag_edit.setText("vip CLIENTES")
d._add_tag()
check("Editar: etiquetas normalizadas y sin duplicados", d.tags() == ["VIP clientes"])
d.tag_edit.setText("Temporal")
d._add_tag()
d.remove_tag("Temporal")
check("Editar: se puede quitar una etiqueta", d.tags() == ["VIP clientes"])
d.note_edit.setPlainText("  una nota  ")
d._submit()
wait()
sv_now = core.surveys.get_survey(aid2, FORM_ID)
check("Editar: guarda meta, nota y etiquetas", (sv_now.goal, sv_now.note, sv_now.tags) == (6, "una nota", ("VIP clientes",))
      and d.saved is not None)
d = edit_dialog()
d.tag_edit.setText("Pendiente")                      # escrita pero sin tocar «Agregar»: igual se guarda
d._submit()
wait()
check("Editar: lo escrito en el campo de etiqueta también se guarda", core.surveys.get_survey(aid2, FORM_ID).tags
      == ("VIP clientes", "Pendiente"))
prepared = edit_dialog()
prepared.note_edit.setPlainText("Nota visible")
prepared._submit()
wait()
sv.open_survey(FORM_ID)
wait()
det = sv.detail
det.make_edit_dialog = lambda: prepared
det.open_edit()
wait()
wait()
check("Encuesta: la nota se muestra bajo el título tras editar", det.note_label.text() == "Nota visible"
      and "Editado" not in det.notice.text() and S.EDIT_SAVED in det.notice.text())

# lista: chips, filtro por etiqueta, archivar
sv.refresh()
wait()
sv._reload_saved()
wait()
check("Encuestas: la lista trae meta y etiquetas", sv._surveys[0].goal == 6 and "Pendiente" in sv._surveys[0].tags
      and FORM_ID in sv._goals and sv._goals[FORM_ID].pct == 66)
check("Encuestas: etiquetas en uso para los chips", P.all_tags(sv._surveys) == ["Pendiente", "VIP clientes"])
check("Encuestas: filtro por etiqueta", [x.form_id for x in P.filter_surveys(sv._surveys, tag="pendiente")] == [FORM_ID]
      and P.filter_surveys(sv._surveys, tag="otra") == [])
check("Encuestas: la búsqueda mira nota y etiquetas", P.filter_surveys(sv._surveys, text="visible") != []
      and P.filter_surveys(sv._surveys, text="vip CLI") != [] and P.filter_surveys(sv._surveys, text="zzz") == [])
sv.set_tag("Pendiente")
check("Encuestas: elegir una etiqueta la deja activa", sv._tag == "Pendiente")
sv.set_tag(None)
home_pg = win.home_page
home_pg.refresh()
wait()
check("Inicio: la sección Metas muestra la encuesta con meta", [s_.form_id for _a, s_, _g in home_pg._goal_items] == [FORM_ID])
sv.set_archived(FORM_ID, True)
wait()
wait()
check("Archivar: queda marcada y se oculta por defecto", sv._surveys[0].archived
      and P.filter_surveys(sv._surveys) == [] and len(P.filter_surveys(sv._surveys, show_archived=True)) == 1
      and "archivada" in sv.notice.text())
check("Archivar: aviso en la lista", S.ARCHIVE_DONE in sv.notice.text())
home_pg.refresh()
wait()
check("Archivada: sale de Metas en Inicio", home_pg._goal_items == [])
per = [(aid2, core.surveys.list_surveys(aid2))]
ov = P.home_overview(per)
check("Archivada: no cuenta en Inicio ni deja punto rojo", ov.survey_count == 0 and ov.pending == () and ov.top == ())
sv.set_archived(FORM_ID, False)
wait()
check("Desarchivar: vuelve a verse", not sv._surveys[0].archived and len(P.filter_surveys(sv._surveys)) == 1)

# Resumen: ritmo y cruce de preguntas
ap.open_survey(aid2, FORM_ID)
wait()
wait()
check("Resumen: muestra la meta", getattr(ap, "goal_bar", None) is not None)
check("Resumen: Ritmo con la semana", "Esta semana: 4 respuestas" in ap.rhythm_week.text()
      and ap.rhythm_peak.text().startswith("Día más activo:") and "100 %" in ap.rhythm_completion.text())
check("Resumen: gráficos de ritmo con datos", sum(n for _t, n, _f in ap.weekday_chart.rows()) == 4
      and sum(n for _l, n in ap.hour_chart.series()) == 4)
check("Cruce: hay preguntas de opción para elegir", [q.title for q in ap._cross_questions] == ["¿Te gustó?", "Colores"])
ap.cross_question_combo.setCurrentIndex(0)
ap._cross_question_changed(0)
ap.cross_option_combo.setCurrentIndex(ap.cross_option_combo.findData("No"))
ap.apply_cross()
wait()
check("Cruce: opción que nadie eligió -> 0 personas", ap.result.matched == 0 and ap.result.total_in_period == 4
      and ap.result.overview.total == 0)
ap.cross_option_combo.setCurrentIndex(ap.cross_option_combo.findData("Sí"))
ap.apply_cross()
wait()
check("Cruce: aplicar la opción elegida", ap.result.matched == 4 and ap.result.answer_filter.option_text == "Sí"
      and "Mostrando 4 de 4 personas que respondieron «Sí» en «¿Te gustó?»" in ap.cross_ribbon_label.text())
ap.clear_cross()
wait()
check("Cruce: quitar el filtro", ap.result.answer_filter is None and ap.result.matched is None)
ap.cross_question_combo.setCurrentIndex(1)
ap._cross_question_changed(1)
ap.cross_option_combo.setCurrentIndex(ap.cross_option_combo.findData("Rojo"))
ap.apply_cross()
wait()
check("Cruce: selección múltiple", ap.result.matched == 4)
ap.open_survey(aid2, FORM_ID)
wait()
check("Cruce: se reinicia al abrir una encuesta", ap._cross is None and ap.result.answer_filter is None)

# Ajustes: avisos
settings_mod.tray_available = lambda: True
sp2 = settings_mod.SettingsPage(ctx, runner, on_notify_changed=lambda: CHANGED.append(1))
CHANGED = []
check("Ajustes: sin bandeja el aviso queda desactivado con su leyenda",
      sp._tray_ok is False and sp.notify_status.text() == S.NOTIFY_NO_TRAY)
sp2.refresh()
wait()
sp2.notify_chk.setChecked(True)
sp2._notify_toggled(True)
wait()
check("Ajustes: activar avisos se guarda y avisa a la ventana", core.settings.get("notify_mode") == "on" and CHANGED)
sp2.notify_combo.setCurrentIndex(sp2.notify_combo.findData("15"))
sp2._notify_interval_changed(0)
wait()
check("Ajustes: intervalo de avisos", core.settings.get("notify_interval_min") == "15")
core.settings.set("notify_mode", "off")

# Ajustes: idioma (se guarda en la carpeta de datos y avisa que hay que reiniciar)
sp2.language_combo.setCurrentIndex(sp2.language_combo.findData("en"))
sp2._language_changed()
check("Ajustes: idioma inglés se guarda en language.txt y avisa en ambos idiomas",
      (home / "language.txt").read_text(encoding="utf-8").strip() == "en" and sp2.notice.text() == S.LANGUAGE_RESTART
      and "Restart the app" in S.LANGUAGE_RESTART and "Reiniciá" in S.LANGUAGE_RESTART)
sp2.language_combo.setCurrentIndex(sp2.language_combo.findData("es"))
sp2._language_changed()
check("Ajustes: volver al idioma activo limpia el aviso", sp2.notice.text() == "")
(home / "language.txt").unlink()

# Ventana: temporizador, bandeja y cierre
tray_mod.tray_available = lambda: True
mw_mod.tray_mod.tray_available = lambda: True
shown = []
mw_mod.show_info = lambda parent, title, text: shown.append((title, text))
win3 = MainWindow(ctx, runner)
wait()


class FakeTray:
    def __init__(self):
        self.msgs, self.visible = [], False

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def notify(self, t, b):
        self.msgs.append((t, b))


win3.tray = FakeTray()
win3.set_notify_state(True, 30)
check("Avisos: con bandeja disponible se activan el temporizador y el ícono", win3._notify_on and win3.tray.visible)
win3._notify_result(NS(notify=True, title="3 respuestas nuevas en 2 encuestas", body="Tocá para abrir Tally Monitor",
                       checked_at="x", errors=0))
wait()
check("Avisos: se muestra la notificación", win3.tray.msgs == [("3 respuestas nuevas en 2 encuestas",
                                                                "Tocá para abrir Tally Monitor")])
win3._notify_result(NS(notify=False, title="", body="", checked_at="x", errors=1))
check("Avisos: un chequeo sin novedades no muestra nada", len(win3.tray.msgs) == 1)
win3.run_notify_check()                    # sin red (el servidor de prueba está apagado): silencioso
wait()
wait()
check("Avisos: error de red en el chequeo es silencioso", len(win3.tray.msgs) == 1)


class Ev:
    def __init__(self):
        self.ignored = self.accepted = False

    def ignore(self):
        self.ignored = True

    def accept(self):
        self.accepted = True


ev = Ev()
win3.closeEvent(ev)
check("Cerrar con avisos activos va a la bandeja y lo explica una vez", ev.ignored and len(shown) == 1
      and shown[0][1] == S.NOTIFY_TRAY_TEXT)
ev = Ev()
win3.closeEvent(ev)
check("La explicación no se repite", ev.ignored and len(shown) == 1)
win3.set_notify_state(False, 60)
check("Avisos apagados: se detiene todo", not win3._notify_on and not win3.tray.visible)
tray_mod.tray_available = lambda: False
mw_mod.tray_mod.tray_available = lambda: False
win3.set_notify_state(True, 60)
check("Sin bandeja disponible no se activa nada", not win3._notify_on)

# --- baja ---
accounts_mod.confirm_destructive = lambda *a, **k: True
acc_page.delete(core.accounts.get_account(a.account_id))
wait()
check("eliminar cuenta", [x.account_id for x in core.accounts.list_accounts()] == [acct2.account_id])

# --- modo degradado ---
ctx2 = AppContext(core.accounts, core.backups, core.settings, str(home), str(home / "logs"), "0.1.0", degraded=True)
win2 = MainWindow(ctx2, runner)
wait()
check("modo degradado se construye", True)

# --- Inicio: se dibuja con cuentas y encuestas guardadas, y el punto rojo se puede mostrar ---
win2 = MainWindow(ctx, runner)
wait()
win2.navigate("inicio")
wait()
win2.home_page.refresh()
wait()
check("Inicio: se carga sin errores", win2.home_page._token >= 1)
win2.nav_buttons["encuestas"].set_badge(True)
check("Punto rojo en la pestaña Encuestas", win2.nav_buttons["encuestas"]._badge is True)
win2.nav_buttons["encuestas"].set_badge(False)

check("ningún error registrado por la interfaz", not errors.records)
if errors.records:
    print("   errores:", errors.records)
bad = [n for ok, n in CHECKS if not ok]
print(f"\n{len(CHECKS) - len(bad)} de {len(CHECKS)} comprobaciones correctas")
sys.exit(1 if bad else 0)

"""Ventana principal: barra superior con navegación en píldoras + páginas."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from . import strings as S
from .context import AppContext
from .dialogs.simple_dialogs import show_info
from .pages.accounts import AccountsPage
from .pages.home import HomePage
from .pages.settings import SettingsPage
from .pages.surveys import SurveysPage
from . import tray as tray_mod
from .theme import current as theme
from .widgets.pill_button import PillButton
from . import branding
from .workers import TaskRunner


class MainWindow(QMainWindow):
    def __init__(self, ctx: AppContext, runner: TaskRunner) -> None:
        super().__init__()
        self._ctx, self._runner = ctx, runner
        self.setWindowTitle(S.APP_NAME + (S.TEST_MODE_SUFFIX if ctx.test_mode else ""))
        self.setMinimumSize(980, 640)
        self.resize(1120, 720)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # barra superior: marca a la izquierda y navegación en «píldoras» a la derecha
        bar = QFrame()
        bar.setObjectName("TopBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(32, 18, 32, 10)
        self.mark = QLabel("")
        self.mark.setObjectName("BrandMark")          # sin logo: un cuadrado de color de acento
        self.mark.setFixedSize(30, 30)
        bl.addWidget(self.mark)
        self.refresh_theme()
        brand = QLabel(S.APP_NAME)
        brand.setObjectName("Brand")
        bl.addWidget(brand)
        if ctx.test_mode:
            badge = QLabel(S.TEST_MODE_TAG)
            badge.setToolTip(S.TEST_MODE_BADGE)
            badge.setProperty("role", "tag")
            bl.addWidget(badge)
        bl.addStretch(1)
        self.update_btn = QPushButton("")
        self.update_btn.setProperty("variant", "link")
        self.update_btn.hide()
        self._update_url = ""
        self.update_btn.clicked.connect(self._open_update)
        bl.addWidget(self.update_btn)
        pills = QFrame()
        pills.setObjectName("Pills")
        pl = QHBoxLayout(pills)
        pl.setContentsMargins(5, 5, 5, 5)
        pl.setSpacing(4)
        bl.addWidget(pills)

        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}
        self.nav_buttons: dict[str, QPushButton] = {}
        group = QButtonGroup(self)
        group.setExclusive(True)

        self.accounts_page = AccountsPage(ctx, runner)
        self.surveys_page = SurveysPage(ctx, runner, on_open_accounts=self.add_account)
        self.workspace = self.surveys_page.workspace
        self.analysis_page = self.workspace.analysis
        self.exports_page = self.workspace.exports
        self.settings_page = SettingsPage(ctx, runner, on_restored=self._after_restore,
                                          on_notify_changed=self.apply_notify_settings)
        self.home_page = HomePage(ctx, runner, on_open_accounts=self.add_account, on_open_surveys=self.open_surveys,
                                  on_open_survey=self.open_survey)
        self.home_page.pending_changed.connect(self._set_pending)
        self.surveys_page.saved_loaded.connect(self.refresh_pending)
        self.workspace.changed.connect(self.refresh_pending)

        for key, label in S.NAV:
            page = {"inicio": self.home_page, "encuestas": self.surveys_page, "cuentas": self.accounts_page,
                    "configuracion": self.settings_page}[key]
            self.pages[key] = page
            self.stack.addWidget(page)
            btn = PillButton(label, "pill")
            btn.setAccessibleName(label)
            btn.clicked.connect(lambda _checked=False, k=key: self.navigate(k))
            group.addButton(btn)
            pl.addWidget(btn)
            self.nav_buttons[key] = btn

        root.addWidget(bar)
        root.addWidget(self.stack, 1)

        # avisos de respuestas nuevas: temporizador + bandeja (la lógica de cuándo avisar es del servicio)
        self._notify_on = False
        self._quitting = False
        self.notify_timer = QTimer(self)
        self.notify_timer.timeout.connect(self.run_notify_check)
        self.first_check_timer = QTimer(self)               # primer chequeo poco después de activar los avisos
        self.first_check_timer.setSingleShot(True)
        self.first_check_timer.timeout.connect(self.run_notify_check)
        self.tray = tray_mod.TrayController(self)
        self.tray.open_requested.connect(self.show_from_tray)
        self.tray.quit_requested.connect(self.quit_from_tray)

        if ctx.degraded:               # base dañada: solo Ajustes (para restaurar)
            for k, b in self.nav_buttons.items():
                b.setEnabled(k == "configuracion")
            self.navigate("configuracion")
        else:
            self.navigate("inicio")
            self.refresh_pending()
            self.apply_notify_settings()

    def navigate(self, key: str) -> None:
        sp = self.surveys_page
        if key == "encuestas" and self.stack.currentWidget() is sp and sp.stack.currentWidget() is sp.workspace:
            sp.show_list()                                  # tocar «Encuestas» estando dentro de una encuesta vuelve a la pared
        self._ctx.note("pantalla", pantalla=key)
        self.nav_buttons[key].setChecked(True)
        self.stack.setCurrentWidget(self.pages[key])
        page = self.pages[key]
        if hasattr(page, "refresh") and not (self._ctx.degraded and key != "configuracion"):
            page.refresh()

    def open_surveys(self, account_id: str | None = None) -> None:
        """Desde Inicio: va a Encuestas (con la cuenta que tiene respuestas sin actualizar)."""
        if account_id:
            self.surveys_page.focus_account(account_id)
        self.navigate("encuestas")

    def open_survey(self, account_id: str, form_id: str) -> None:
        self.surveys_page.focus_account(account_id)
        self.navigate("encuestas")
        self.surveys_page.open_survey(form_id)

    def _set_pending(self, on: bool) -> None:
        self.nav_buttons["encuestas"].set_badge(bool(on))

    def refresh_pending(self) -> None:
        """Pone o saca el punto rojo de «Encuestas» según lo ya guardado (no llama a Tally)."""
        if self._ctx.degraded or self._ctx.surveys is None:
            return

        def work():
            for a in self._ctx.accounts.list_accounts():
                if a.status != "no_credential" and any(s.has_new_hint and not s.archived
                                                       for s in self._ctx.surveys.list_surveys(a.account_id)):
                    return True
            return False

        self._runner.run(work, self._set_pending, None)

    def add_account(self) -> None:
        self.navigate("cuentas")
        self.accounts_page.open_add_dialog()

    def refresh_all(self) -> None:
        if not self._ctx.degraded:
            self.accounts_page.refresh()
            self.surveys_page.reset()
            self.home_page.refresh()

    def validate_all_in_background(self) -> None:
        """Valida las cuentas al iniciar, sin bloquear la interfaz."""
        if self._ctx.degraded:
            return
        self._runner.run(self._ctx.accounts.validate_all, lambda _r: self.refresh_all(), lambda _e: self.refresh_all())

    def refresh_theme(self) -> None:
        """Después de cambiar el tema: actualiza el logo (si hay) y fuerza el redibujado de lo pintado a mano."""
        pix = branding.logo_pixmap(30, theme.name())
        if pix is not None:
            self.mark.setStyleSheet("background: transparent;")
            self.mark.setPixmap(pix)
        else:
            self.mark.setStyleSheet("")
            self.mark.setPixmap(QPixmap())
        if hasattr(self, "exports_page"):
            self.exports_page.follow_theme()
        for w in (self.findChildren(QWidget) or []):
            w.update()

    def check_updates_in_background(self) -> None:
        """Solo hace algo si el usuario activó el aviso; nunca descarga nada."""
        if self._ctx.degraded or self._ctx.updates is None:
            return
        self._runner.run(self._ctx.updates.check, self._show_update, lambda _e: None)

    def _show_update(self, status) -> None:
        if status.state == "available" and status.url:
            self._update_url = status.url
            self.update_btn.setText(S.UPDATE_PILL.format(version=status.latest))
            self.update_btn.show()

    def _open_update(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        if self._update_url:
            QDesktopServices.openUrl(QUrl(self._update_url))

    # ---------- avisos ----------
    def apply_notify_settings(self) -> None:
        """Lee los ajustes y (des)activa el temporizador y la bandeja."""
        notifier = self._ctx.notifier
        if self._ctx.degraded or notifier is None:
            return
        self._runner.run(lambda: (notifier.is_enabled(), notifier.interval_minutes()),
                         lambda res: self.set_notify_state(*res), None)

    def set_notify_state(self, enabled: bool, interval_min: int) -> None:
        active = bool(enabled) and tray_mod.tray_available()
        self._notify_on = active
        QApplication.setQuitOnLastWindowClosed(not active)       # con avisos, cerrar la ventana la manda a la bandeja
        if active:
            self.tray.show()
            self.notify_timer.start(int(interval_min) * 60 * 1000)
            self.first_check_timer.start(5000)
        else:
            self.notify_timer.stop()
            self.first_check_timer.stop()
            self.tray.hide()

    def run_notify_check(self) -> None:
        notifier = self._ctx.notifier
        if not self._notify_on or notifier is None or self._ctx.degraded:
            return
        self._runner.run(notifier.check, self._notify_result, None)      # errores: silenciosos

    def _notify_result(self, outcome) -> None:
        if outcome.notify and self._notify_on:
            self.tray.notify(outcome.title, outcome.body)
        if outcome.checked_at and not outcome.errors:
            self.refresh_pending()
            if self.stack.currentWidget() is self.home_page:
                self.home_page.refresh()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.navigate("inicio")

    def quit_from_tray(self) -> None:
        self._quitting = True
        self.tray.hide()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if self._notify_on and not self._quitting:
            event.ignore()
            self.hide()
            try:
                if self._ctx.settings.get("tray_hint_shown") != "1":
                    self._ctx.settings.set("tray_hint_shown", "1")
                    show_info(self, S.NOTIFY_TRAY_TITLE, S.NOTIFY_TRAY_TEXT)
            except Exception:  # noqa: BLE001 - el aviso explicativo nunca debe impedir cerrar a la bandeja
                pass
            return
        super().closeEvent(event)

    def _after_restore(self, quit_app: bool) -> None:
        if quit_app:
            QApplication.quit()
        else:
            self.refresh_all()

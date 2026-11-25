"""Hoja de estilos generada desde la paleta activa. Colores lisos (sin degradados) y solo propiedades que Qt soporta.
Las «píldoras» del menú y los chips los dibuja `widgets/pill_button.py`; el resto de los botones se redondea acá."""
from .tokens import DARK, FONT_FAMILIES, FONT_SIZE, RADIUS

# «sans-serif» es una familia genérica y va sin comillas; los nombres reales van entre comillas.
_FONTS = ", ".join(f if f == "sans-serif" else f'"{f}"' for f in FONT_FAMILIES)


def build_qss(t: dict = DARK) -> str:
    return f"""
* {{ font-family: {_FONTS}; font-size: {FONT_SIZE}pt; }}
QWidget {{ background: {t['bg']}; color: {t['text']}; }}
QLabel {{ background: transparent; }}
QLabel[role="title"] {{ font-size: 22pt; font-weight: 700; }}
QLabel[role="section"] {{ font-size: 12pt; font-weight: 700; }}
QLabel[role="muted"] {{ color: {t['muted']}; }}
QLabel[role="error"] {{ color: {t['danger']}; }}
QLabel[role="notice"] {{ color: {t['text']}; background: {t['surface2']}; border: 1px solid {t['border']};
    border-radius: 12px; padding: 8px 14px; }}
QLabel[role="banner"] {{ color: {t['text']}; background: {t['warn_bg']}; border: 1px solid {t['warn']};
    border-radius: 12px; padding: 8px 14px; }}
QLabel[role="tag"] {{ color: {t['action']}; background: {t['warn_bg']}; border-radius: 10px; padding: 2px 10px;
    font-size: 8pt; font-weight: 700; }}
QLabel[role="user-id"] {{ font-size: 24pt; font-weight: 800; color: {t['text']}; }}
QLabel[role="meta"] {{ font-size: 8pt; color: {t['dim']}; }}
QLabel[role="question"] {{ color: {t['muted']}; font-size: 9pt; }}
QLabel[role="answer"] {{ font-size: 11pt; }}
QLabel[role="tile-number"] {{ font-size: 26pt; font-weight: 800; }}
QLabel[role="big-number"] {{ font-size: 36pt; font-weight: 800; color: {t['accent']}; }}
QFrame#TopBar {{ background: transparent; }}
QFrame#TopBar QLabel#Brand {{ font-size: 14pt; font-weight: 800; }}
QFrame#TopBar QLabel#BrandMark {{ background: {t['accent']}; border-radius: 9px; }}
QFrame#Pills {{ background: {t['bg2']}; border: 1px solid {t['border']}; border-radius: 22px; }}
QPushButton[tab="true"] {{ background: transparent; border: none; border-bottom: 3px solid transparent; border-radius: 0;
    padding: 8px 4px; color: {t['muted']}; font-weight: 700; font-size: 12pt; }}
QPushButton[tab="true"]:hover {{ color: {t['text']}; }}
QPushButton[tab="true"]:checked {{ color: {t['text']}; border-bottom: 3px solid {t['action']}; }}
QPushButton[tab="true"]:focus {{ color: {t['text']}; }}
QLabel[badge="true"] {{ border-radius: {RADIUS}px; padding: 2px 10px; font-weight: 600; border: 1px solid {t['neutral']};
    color: {t['neutral']}; background: {t['neutral_bg']}; }}
QLabel[badge="true"][tone="ok"] {{ color: {t['ok']}; background: {t['ok_bg']}; border-color: {t['ok']}; }}
QLabel[badge="true"][tone="warn"] {{ color: {t['warn']}; background: {t['warn_bg']}; border-color: {t['warn']}; }}
QLabel[badge="true"][tone="danger"] {{ color: {t['danger']}; background: {t['danger_bg']}; border-color: {t['danger']}; }}
QFrame[divider="true"] {{ background: {t['border']}; border: none; }}
QFrame#Card {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: {RADIUS + 6}px; }}
QFrame#Card QLabel {{ background: transparent; }}
QFrame#SurveyCard {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: {RADIUS + 10}px; }}
QFrame#SurveyCard:hover {{ border: 1px solid {t['accent']}; background: {t['surface2']}; }}
QFrame#SurveyCard QLabel {{ background: transparent; }}
QFrame#AnswerBox {{ background: {t['surface2']}; border: none; border-left: 3px solid {t['action']}; border-radius: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t['accent']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QPushButton {{ background: {t['surface2']}; color: {t['text']}; border: 1px solid {t['border']};
    border-radius: 11px; padding: 7px 16px; }}
QPushButton:hover {{ border-color: {t['accent']}; }}
QPushButton:focus {{ border: 2px solid {t['accent']}; }}
QPushButton:disabled {{ color: {t['dim']}; background: {t['bg2']}; border-color: {t['border']}; }}
QPushButton[variant="primary"] {{ background: {t['action']}; color: {t['action_text']}; border: none; border-radius: 17px;
    padding: 9px 22px; font-weight: 800; }}
QPushButton[variant="primary"]:hover {{ background: {t['action_hover']}; }}
QPushButton[variant="primary"]:focus {{ border: 2px solid {t['text']}; }}
QPushButton[variant="primary"]:disabled {{ background: {t['surface2']}; color: {t['dim']}; border: none; }}
QPushButton[variant="danger"] {{ color: {t['danger']}; }}
QPushButton[variant="link"] {{ background: transparent; border: none; color: {t['muted']}; font-weight: 600; padding: 4px 6px; }}
QPushButton[variant="link"]:hover {{ color: {t['text']}; }}
QPushButton[variant="link"]:focus {{ border: 2px solid {t['accent']}; border-radius: 8px; }}
QPushButton[big="true"] {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 20px;
    padding: 22px 12px; font-size: 13pt; font-weight: 700; }}
QPushButton[big="true"]:hover {{ border: 1px solid {t['action']}; background: {t['surface2']}; }}
QPushButton[big="true"]:disabled {{ color: {t['dim']}; }}
QLineEdit, QComboBox, QPlainTextEdit, QDateEdit {{ background: {t['surface2']}; border: 1px solid {t['border']};
    border-radius: 10px; padding: 7px 10px; selection-background-color: {t['accent']}; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border: 2px solid {t['accent']}; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; border: 1px solid {t['border']};
    selection-background-color: {t['surface2']}; selection-color: {t['text']}; }}
QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox::indicator {{ width: 20px; height: 20px; border-radius: 7px; border: 1px solid {t['border']};
    background: {t['surface2']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border: 1px solid {t['accent']}; }}
QCheckBox::indicator:disabled {{ background: {t['bg2']}; }}
QListWidget {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 16px; padding: 6px; }}
QListWidget::item {{ padding: 8px 10px; border-radius: 10px; }}
QListWidget::item:selected {{ background: {t['surface2']}; color: {t['action']}; }}
QTableWidget {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 12px;
    gridline-color: {t['border']}; selection-background-color: {t['surface2']}; selection-color: {t['text']}; }}
QHeaderView::section {{ background: {t['surface2']}; color: {t['muted']}; border: none; padding: 6px; }}
QProgressBar {{ background: {t['surface2']}; border: none; border-radius: 3px; max-height: 6px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 3px; }}
QDialog, QMessageBox, QInputDialog {{ background: {t['surface']}; }}
QToolTip {{ background: {t['surface2']}; color: {t['text']}; border: 1px solid {t['border']}; }}
"""

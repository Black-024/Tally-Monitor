"""Sustituto MÍNIMO de PySide6 para ejecutar la LÓGICA Python de la interfaz sin Qt.

Qué valida: que el código de ui/ importa, construye sus páginas y diálogos y ejecuta sus flujos
(alta, validación, reemplazo, renombrado, baja, backups) contra los servicios reales, sin errores de Python.
Qué NO valida: nada de Qt real (aspecto, layouts, eventos, enums, firmas de métodos de Qt).
"""
import sys
import threading
import types


class _Meta(type):
    def __getattr__(cls, name):           # Qt.AlignmentFlag.AlignTop, QMessageBox.Icon.Warning, …
        if name.startswith("__"):
            raise AttributeError(name)
        return _Any()


class _Any(metaclass=_Meta):
    def __init__(self, *a, **k):
        pass

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        v = _Any()
        self.__dict__[name] = v
        return v

    def __call__(self, *a, **k):
        return _Any()

    def __bool__(self):
        return False

    def __index__(self):
        return 0

    def __int__(self):
        return 0


class _BoundSignal:
    def __init__(self):
        self._slots = []

    def connect(self, fn):
        self._slots.append(fn)

    def emit(self, *args):
        for fn in list(self._slots):
            fn(*args)


class Signal:
    def __init__(self, *types_):
        pass

    def __set_name__(self, owner, name):
        self._name = "_sig_" + name

    def __get__(self, inst, owner=None):
        if inst is None:
            return self
        return inst.__dict__.setdefault(self._name, _BoundSignal())


def Slot(*a, **k):
    return lambda f: f


class QObject(_Any):
    def __init__(self, parent=None):
        pass


class QLineEdit(_Any):
    def __init__(self, text="", parent=None):
        self._text = text if isinstance(text, str) else ""

    def text(self):
        return self._text

    def setText(self, t):
        self._text = t

    def clear(self):
        self._text = ""


class QLabel(_Any):
    def __init__(self, text="", parent=None):
        self._text = text if isinstance(text, str) else ""

    def text(self):
        return self._text

    def setText(self, t):
        self._text = t


class QPlainTextEdit(_Any):
    def __init__(self, *a, **k):
        self._text = ""

    def toPlainText(self):
        return self._text

    def setPlainText(self, t):
        self._text = t


class QCheckBox(_Any):
    def __init__(self, *a, **k):
        self._on = False

    def isChecked(self):
        return self._on

    def setChecked(self, v):
        self._on = bool(v)


class QComboBox(_Any):
    def __init__(self, *a, **k):
        self._items, self._idx = [], -1

    def addItem(self, text, data=None):
        self._items.append((text, data))
        if self._idx < 0:
            self._idx = 0

    def addItems(self, texts):
        for t in texts:
            self.addItem(t)

    def clear(self):
        self._items, self._idx = [], -1

    def findData(self, data):
        return next((i for i, (_, d) in enumerate(self._items) if d == data), -1)

    def currentIndex(self):
        return self._idx

    def setCurrentIndex(self, i):
        self._idx = i

    def currentData(self):
        return self._items[self._idx][1] if 0 <= self._idx < len(self._items) else None

    def itemData(self, i):
        return self._items[i][1] if 0 <= i < len(self._items) else None

    def currentText(self):
        return self._items[self._idx][0] if 0 <= self._idx < len(self._items) else ""

    def setCurrentText(self, t):
        self._idx = next((i for i, (x, _) in enumerate(self._items) if x == t), self._idx)


class QListWidget(_Any):
    def __init__(self, *a, **k):
        self._rows, self._cur = [], -1

    def clear(self):
        self._rows, self._cur = [], -1

    def addItem(self, text):
        self._rows.append(text)

    def count(self):
        return len(self._rows)

    def currentRow(self):
        return self._cur

    def setCurrentRow(self, i):
        self._cur = i


class QDialog(_Any):
    def __init__(self, parent=None):
        self._result = 0

    def accept(self):
        self.done(1)

    def reject(self):
        self.done(0)

    def done(self, r):
        self._result = r

    def exec(self):
        return 0


def install():
    mods = {}
    for name in ("PySide6", "PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets"):
        m = types.ModuleType(name)

        def make_getattr(mod):
            def __getattr__(attr):
                if attr.startswith("__"):
                    raise AttributeError(attr)
                cls = type(attr, (_Any,), {})
                setattr(mod, attr, cls)
                return cls
            return __getattr__
        m.__getattr__ = make_getattr(m)
        mods[name] = m
        sys.modules[name] = m
    core = mods["PySide6.QtCore"]
    core.Signal, core.Slot, core.QObject = Signal, Slot, QObject
    w = mods["PySide6.QtWidgets"]
    w.QLineEdit, w.QLabel, w.QCheckBox, w.QDialog = QLineEdit, QLabel, QCheckBox, QDialog
    w.QComboBox, w.QListWidget, w.QPlainTextEdit = QComboBox, QListWidget, QPlainTextEdit
    sys.modules["PySide6"].QtCore, sys.modules["PySide6"].QtWidgets = core, w
    sys.modules["PySide6"].QtGui = mods["PySide6.QtGui"]

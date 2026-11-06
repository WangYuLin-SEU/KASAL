"""Live text bindings; changing language never rebuilds the workbench or scene."""
from __future__ import annotations

import weakref
from PySide6 import QtWidgets as W
from PySide6.QtCore import QLibraryInfo, QLocale, QSignalBlocker, QTranslator
from shiboken6 import isValid


class Text(str):
    def __new__(cls, owner, zh, en):
        value = super().__new__(cls, en if owner.language == 'en' else zh)
        value.owner, value.zh, value.en = owner, zh, en
        return value


def bind(widget, method, value, *prefix):
    """Replace a property's binding, including when new text is not translated."""
    bindings = getattr(widget, '_text_bindings', None)
    if bindings is None:
        bindings = widget._text_bindings = {}
    key = (method, prefix)
    if isinstance(value, Text):
        bindings[key] = (value.zh, value.en)
        value.owner.widgets.add(widget)
    else:
        bindings.pop(key, None)
    return str(value)


class Localizer:
    def __init__(self, language):
        self.language = 'en' if language == 'en' else 'zh'
        self.widgets = weakref.WeakSet()
        self.translator = QTranslator()
        self.translator.load('qtbase_zh_CN', QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
        self.set_language(self.language)

    def text(self, zh, en):
        return Text(self, zh, en)

    def set_language(self, language):
        self.language = 'en' if language == 'en' else 'zh'
        app = W.QApplication.instance()
        app.removeTranslator(self.translator)
        QLocale.setDefault(QLocale('en_US' if self.language == 'en' else 'zh_CN'))
        if self.language == 'zh':
            app.installTranslator(self.translator)
        for widget in list(self.widgets):
            if not isValid(widget):
                continue
            # Combo text changes must not alter parameters or selection.
            blocker = QSignalBlocker(widget)
            for (method, prefix), (zh, en) in list(widget._text_bindings.items()):
                getattr(widget, method)(*prefix, Text(self, zh, en))
            del blocker
            if isinstance(widget, W.QWidget):
                widget.update()


class _TextWidget:
    def __init__(self, text='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText(text)

    def setText(self, value):
        super().setText(bind(self, 'setText', value))

    def setToolTip(self, value):
        super().setToolTip(bind(self, 'setToolTip', value))


class QLabel(_TextWidget, W.QLabel):
    pass


class QPushButton(_TextWidget, W.QPushButton):
    pass


class QCheckBox(_TextWidget, W.QCheckBox):
    pass


class QLineEdit(W.QLineEdit):
    def setPlaceholderText(self, value):
        super().setPlaceholderText(bind(self, 'setPlaceholderText', value))


class QComboBox(W.QComboBox):
    def clear(self):
        bindings = getattr(self, '_text_bindings', {})
        for key in list(bindings):
            if key[0] == 'setItemText':
                del bindings[key]
        super().clear()

    def addItem(self, text, userData=None):
        super().addItem(bind(self, 'setItemText', text, self.count()), userData)

    def setItemText(self, index, text):
        super().setItemText(index, bind(self, 'setItemText', text, index))

    def setToolTip(self, value):
        super().setToolTip(bind(self, 'setToolTip', value))


class QMenu(W.QMenu):
    def addAction(self, text, callback):
        action = super().addAction(str(text), callback)
        bind(action, 'setText', text)
        return action


class QFormLayout(W.QFormLayout):
    def addRow(self, *args):
        if args and isinstance(args[0], Text):
            args = (QLabel(args[0]), *args[1:])
        super().addRow(*args)


class QDialog(W.QDialog):
    def setWindowTitle(self, value):
        super().setWindowTitle(bind(self, 'setWindowTitle', value))


class QFileDialog(W.QFileDialog):
    """Use Qt dialogs so their controls follow Studio's selected language."""
    @staticmethod
    def getExistingDirectory(*args, **kwargs):
        kwargs['options'] = kwargs.get('options', W.QFileDialog.Option.ShowDirsOnly) | W.QFileDialog.Option.DontUseNativeDialog
        return W.QFileDialog.getExistingDirectory(*args, **kwargs)

    @staticmethod
    def getOpenFileName(*args, **kwargs):
        kwargs['options'] = kwargs.get('options', W.QFileDialog.Option(0)) | W.QFileDialog.Option.DontUseNativeDialog
        return W.QFileDialog.getOpenFileName(*args, **kwargs)

    @staticmethod
    def getSaveFileName(*args, **kwargs):
        kwargs['options'] = kwargs.get('options', W.QFileDialog.Option(0)) | W.QFileDialog.Option.DontUseNativeDialog
        return W.QFileDialog.getSaveFileName(*args, **kwargs)

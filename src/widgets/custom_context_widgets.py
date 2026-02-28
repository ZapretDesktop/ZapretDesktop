"""
Кастомные виджеты (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox)
с единым контекстным меню ПКМ, стилизованным через StyleMenu.
"""

from PyQt6.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtCore import Qt
from src.core.config_manager import ConfigManager
from src.core.translator import tr
from .style_menu import StyleMenu


class ContextLineEdit(QLineEdit):
    """QLineEdit с кастомным контекстным меню."""
    
    def contextMenuEvent(self, event):
        # Не задаём родителя меню, чтобы stylesheet родителя не переопределял стиль StyleMenu
        menu = StyleMenu()
        lang = ConfigManager().load_settings().get('language', 'ru')
        
        # Undo / Redo
        act_undo = QAction(tr('editor_undo', lang), self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(self.undo)
        act_undo.setEnabled(self.isUndoAvailable())
        menu.addAction(act_undo)

        act_redo = QAction(tr('editor_redo', lang), self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.triggered.connect(self.redo)
        act_redo.setEnabled(self.isRedoAvailable())
        menu.addAction(act_redo)

        menu.addSeparator()

        # Cut / Copy / Paste / Delete
        act_cut = QAction(tr('editor_cut', lang), self)
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.triggered.connect(self.cut)
        act_cut.setEnabled(self.hasSelectedText())
        menu.addAction(act_cut)

        act_copy = QAction(tr('editor_copy', lang), self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(self.copy)
        act_copy.setEnabled(self.hasSelectedText())
        menu.addAction(act_copy)

        act_paste = QAction(tr('editor_paste', lang), self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self.paste)
        menu.addAction(act_paste)

        act_delete = QAction(tr('editor_delete', lang), self)

        def _delete():
            # Удаляем выделенный текст или символ под курсором
            try:
                self.del_()
            except Exception:
                # Если del_ недоступен, просто очищаем выделение
                if self.hasSelectedText():
                    cursor_pos = self.cursorPosition()
                    txt = self.text()
                    start = self.selectionStart()
                    end = start + len(self.selectedText())
                    self.setText(txt[:start] + txt[end:])
                    self.setCursorPosition(cursor_pos)

        act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        act_delete.triggered.connect(_delete)
        act_delete.setEnabled(self.hasSelectedText() or bool(self.text()))
        menu.addAction(act_delete)

        menu.addSeparator()

        # Select all
        act_select_all = QAction(tr('editor_select_all', lang), self)
        act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        act_select_all.triggered.connect(self.selectAll)
        menu.addAction(act_select_all)

        menu.exec(event.globalPos())


class ContextTextEdit(QTextEdit):
    """QTextEdit с кастомным контекстным меню."""

    def contextMenuEvent(self, event):
        menu = StyleMenu()
        lang = ConfigManager().load_settings().get('language', 'ru')
        lang = ConfigManager().load_settings().get('language', 'ru')

        # Undo / Redo
        act_undo = QAction(tr('editor_undo', lang), self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(self.undo)
        act_undo.setEnabled(self.document().isUndoAvailable())
        menu.addAction(act_undo)

        act_redo = QAction(tr('editor_redo', lang), self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.triggered.connect(self.redo)
        act_redo.setEnabled(self.document().isRedoAvailable())
        menu.addAction(act_redo)

        menu.addSeparator()

        # Cut / Copy / Paste / Delete
        act_cut = QAction(tr('editor_cut', lang), self)
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.triggered.connect(self.cut)
        act_cut.setEnabled(self.textCursor().hasSelection())
        menu.addAction(act_cut)

        act_copy = QAction(tr('editor_copy', lang), self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(self.copy)
        act_copy.setEnabled(self.textCursor().hasSelection())
        menu.addAction(act_copy)

        act_paste = QAction(tr('editor_paste', lang), self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self.paste)
        menu.addAction(act_paste)

        act_delete = QAction(tr('editor_delete', lang), self)

        def _delete():
            cursor = self.textCursor()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            else:
                # Удаляем символ под курсором
                cursor.deleteChar()
            self.setTextCursor(cursor)

        act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        act_delete.triggered.connect(_delete)
        act_delete.setEnabled(self.textCursor().hasSelection() or bool(self.toPlainText()))
        menu.addAction(act_delete)

        menu.addSeparator()

        # Select all
        act_select_all = QAction(tr('editor_select_all', lang), self)
        act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        act_select_all.triggered.connect(self.selectAll)
        menu.addAction(act_select_all)

        menu.exec(event.globalPos())


class ContextPlainTextEdit(QPlainTextEdit):
    """QPlainTextEdit с кастомным контекстным меню."""

    def contextMenuEvent(self, event):
        menu = StyleMenu()

        act_undo = QAction(tr('editor_undo', lang), self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(self.undo)
        act_undo.setEnabled(self.document().isUndoAvailable())
        menu.addAction(act_undo)

        act_redo = QAction(tr('editor_redo', lang), self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.triggered.connect(self.redo)
        act_redo.setEnabled(self.document().isRedoAvailable())
        menu.addAction(act_redo)

        menu.addSeparator()

        act_cut = QAction(tr('editor_cut', lang), self)
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.triggered.connect(self.cut)
        act_cut.setEnabled(self.textCursor().hasSelection())
        menu.addAction(act_cut)

        act_copy = QAction(tr('editor_copy', lang), self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(self.copy)
        act_copy.setEnabled(self.textCursor().hasSelection())
        menu.addAction(act_copy)

        act_paste = QAction(tr('editor_paste', lang), self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(self.paste)
        menu.addAction(act_paste)

        act_delete = QAction(tr('editor_delete', lang), self)

        def _delete():
            cursor = self.textCursor()
            if cursor.hasSelection():
                cursor.removeSelectedText()
            else:
                cursor.deleteChar()
            self.setTextCursor(cursor)

        act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        act_delete.triggered.connect(_delete)
        act_delete.setEnabled(self.textCursor().hasSelection() or bool(self.toPlainText()))
        menu.addAction(act_delete)

        menu.addSeparator()

        act_select_all = QAction(tr('editor_select_all', lang), self)
        act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        act_select_all.triggered.connect(self.selectAll)
        menu.addAction(act_select_all)

        menu.exec(event.globalPos())


class ContextSpinBox(QSpinBox):
    """QSpinBox с кастомным контекстным меню для поля ввода."""

    def _line_edit(self):
        le = self.lineEdit()
        return le

    def contextMenuEvent(self, event):
        le = self._line_edit()
        if le is None:
            return super().contextMenuEvent(event)

        menu = StyleMenu()
        lang = ConfigManager().load_settings().get('language', 'ru')

        # Undo / Redo (если поддерживается)
        act_undo = QAction(tr('editor_undo', lang), self)
        act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        act_undo.triggered.connect(le.undo)
        act_undo.setEnabled(getattr(le, "isUndoAvailable", lambda: False)())
        menu.addAction(act_undo)

        act_redo = QAction(tr('editor_redo', lang), self)
        act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        act_redo.triggered.connect(le.redo)
        act_redo.setEnabled(getattr(le, "isRedoAvailable", lambda: False)())
        menu.addAction(act_redo)

        menu.addSeparator()

        # Cut / Copy / Paste / Delete
        act_cut = QAction(tr('editor_cut', lang), self)
        act_cut.setShortcut(QKeySequence.StandardKey.Cut)
        act_cut.triggered.connect(le.cut)
        act_cut.setEnabled(le.hasSelectedText())
        menu.addAction(act_cut)

        act_copy = QAction(tr('editor_copy', lang), self)
        act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        act_copy.triggered.connect(le.copy)
        act_copy.setEnabled(le.hasSelectedText())
        menu.addAction(act_copy)

        act_paste = QAction(tr('editor_paste', lang), self)
        act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        act_paste.triggered.connect(le.paste)
        menu.addAction(act_paste)

        act_delete = QAction(tr('editor_delete', lang), self)

        def _delete():
            try:
                le.del_()
            except Exception:
                if le.hasSelectedText():
                    cursor_pos = le.cursorPosition()
                    txt = le.text()
                    start = le.selectionStart()
                    end = start + len(le.selectedText())
                    le.setText(txt[:start] + txt[end:])
                    le.setCursorPosition(cursor_pos)

        act_delete.setShortcut(QKeySequence.StandardKey.Delete)
        act_delete.triggered.connect(_delete)
        act_delete.setEnabled(le.hasSelectedText() or bool(le.text()))
        menu.addAction(act_delete)

        menu.addSeparator()

        act_select_all = QAction(tr('editor_select_all', lang), self)
        act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        act_select_all.triggered.connect(le.selectAll)
        menu.addAction(act_select_all)

        menu.exec(event.globalPos())


"""
Редактор с нумерацией строк и отображением текущей позиции (строка, столбец).
Стиль как в Android Studio: подсветка текущей строки, выделение номера текущей строки.
"""

from PyQt6.QtWidgets import QPlainTextEdit, QWidget, QTextEdit
from PyQt6.QtGui import QColor, QPainter, QFont, QBrush, QTextFormat
from PyQt6.QtCore import Qt, QRect, QSize
from PyQt6.QtGui import QTextCursor, QTextDocument
from src.widgets.style_menu import StyleMenu
from PyQt6.QtGui import QAction, QKeySequence
from src.core.config_manager import ConfigManager
from src.core.translator import tr


# Цвета в стиле Android Studio / IntelliJ
LINE_NUMBER_BG = QColor(31, 31, 31)
LINE_NUMBER_FG = QColor(128, 128, 128)
LINE_NUMBER_CURRENT_FG = QColor(212, 212, 212)
CURRENT_LINE_BG = QColor(0x28, 0x28, 0x28)  # #282828
OCCURRENCE_BG = QColor(0x3a, 0x3a, 0x2e)   # подсветка вхождений слова


class LineNumberArea(QWidget):
    """Виджет нумерации строк слева от редактора"""
    
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
    
    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)
    
    def paintEvent(self, event):
        self.editor.line_number_area_paint_event(event)


class LineNumberPlainTextEdit(QPlainTextEdit):
    """
    QPlainTextEdit с нумерацией строк слева, подсветкой текущей строки и контекстным меню.
    Как в Android Studio: текущая строка подсвечена в тексте, номер текущей строки выделен в колонке.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # Флаг, разрешена ли подсветка текущей строки
        self._highlight_enabled = True
        self.line_number_area = LineNumberArea(self)
        self.blockCountChanged.connect(self.update_line_number_area_width)
        self.updateRequest.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self._on_cursor_position_changed)
        self.selectionChanged.connect(self._on_selection_changed)
        self.update_line_number_area_width(0)
        self._update_extra_selections()
    
    def _on_cursor_position_changed(self):
        self._update_extra_selections()
        self.line_number_area.update()

    def _on_selection_changed(self):
        self._update_extra_selections()
    
    def set_highlight_current_line_enabled(self, enabled: bool):
        """Включает/выключает подсветку текущей строки."""
        self._highlight_enabled = bool(enabled)
        if not self._highlight_enabled:
            self.setExtraSelections([])
        else:
            self._update_extra_selections()

    def _get_occurrence_highlights(self) -> list:
        """Подсветка всех вхождений выделенного слова (как в VS Code)."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return []
        text = cursor.selectedText()
        text = text.replace("\u2029", "\n")  # Qt uses U+2029 for newlines in selectedText
        if not text or "\n" in text or any(c.isspace() for c in text) or len(text) > 100:
            return []
        doc = self.document()
        extra = []
        pos = 0
        flags = (
            QTextDocument.FindFlag.FindCaseSensitively
            | QTextDocument.FindFlag.FindWholeWords
        )
        while True:
            found = doc.find(text, pos, flags)
            if found.isNull():
                break
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QBrush(OCCURRENCE_BG))
            sel.cursor = found
            extra.append(sel)
            pos = found.selectionEnd()
        return extra

    def _update_extra_selections(self):
        """Объединяет подсветку текущей строки и вхождений выделенного слова."""
        if not getattr(self, "_highlight_enabled", True):
            self.setExtraSelections([])
            return
        extra = list(self._get_occurrence_highlights())
        if not self.textCursor().hasSelection():
            line_sel = QTextEdit.ExtraSelection()
            line_sel.format.setBackground(QBrush(CURRENT_LINE_BG))
            line_sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            line_sel.cursor = self.textCursor()
            line_sel.cursor.clearSelection()
            extra.append(line_sel)
        self.setExtraSelections(extra)
    
    def line_number_area_width(self):
        digits = 1
        count = max(1, self.blockCount())
        while count >= 10:
            count //= 10
            digits += 1
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return max(space, 36)
    
    def update_line_number_area_width(self, _):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)
    
    def refresh_line_number_area(self):
        """Принудительно обновляет ширину и перерисовку колонки номеров (после смены файла)."""
        self.update_line_number_area_width(0)
        self.line_number_area.update()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), self.line_number_area_width(), cr.height())
        )
    
    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), LINE_NUMBER_BG)
        
        cursor_block = self.textCursor().block()
        current_block_number = cursor_block.blockNumber()
        
        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                is_current = block_number == current_block_number
                num_rect = QRect(0, top, self.line_number_area.width() - 4, self.fontMetrics().height())
                if is_current:
                    painter.setPen(LINE_NUMBER_CURRENT_FG)
                    f = painter.font()
                    f.setBold(True)
                    painter.setFont(f)
                else:
                    painter.setPen(LINE_NUMBER_FG)
                    painter.setFont(self.font())
                number = str(block_number + 1)
                painter.drawText(num_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, number)
            
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1
    
    def update_line_number_area(self, rect, dy):
        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.update_line_number_area_width(0)
    
    def get_cursor_position(self):
        """Возвращает (line, column) — 1-based"""
        cursor = self.textCursor()
        return cursor.blockNumber() + 1, cursor.columnNumber() + 1
    
    def contextMenuEvent(self, event):
        menu = StyleMenu(self)
        lang = ConfigManager().load_settings().get('language', 'ru')
        
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

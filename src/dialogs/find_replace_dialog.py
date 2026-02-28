"""
Окно поиска и замены для QPlainTextEdit / QTextEdit
"""

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import QTextDocument
from src.core.translator import tr
from src.widgets.custom_checkbox import CustomCheckBox
from src.widgets.custom_context_widgets import ContextLineEdit
import pywinstyles


class FindReplaceDialog(QDialog):
    """Отдельное окно поиска и замены в тексте"""
    
    def __init__(self, parent=None, editor=None, language='ru'):
        super().__init__(parent)
        self.editor = editor
        self.language = language
        
        from src.core.embedded_assets import get_app_icon
        self.setWindowIcon(get_app_icon())
        
        pywinstyles.change_header_color(self, color="#181818")
        self.setWindowTitle(tr('find_replace_title', language))
        self.setWindowFlags(Qt.WindowType.Tool)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumWidth(520)
        self.setMaximumHeight(180)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        row1 = QHBoxLayout()
        row1.addWidget(QLabel(tr('find_search', language)))
        self.search_edit = ContextLineEdit()
        self.search_edit.setPlaceholderText(tr('find_search_placeholder', language))
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.search_edit.returnPressed.connect(self._find_next)
        row1.addWidget(self.search_edit, 1)
        row1.addWidget(QLabel(tr('find_replace_label', language)))
        self.replace_edit = ContextLineEdit()
        self.replace_edit.setPlaceholderText(tr('find_replace_placeholder', language))
        self.replace_edit.returnPressed.connect(self._find_next)
        row1.addWidget(self.replace_edit, 1)
        layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        self.case_check = CustomCheckBox(tr('find_case', language))
        row2.addWidget(self.case_check)
        self.whole_check = CustomCheckBox(tr('find_whole', language))
        row2.addWidget(self.whole_check)
        row2.addStretch()
        self.btn_find_next = QPushButton(tr('find_next', language))
        self.btn_find_next.clicked.connect(self._find_next)
        row2.addWidget(self.btn_find_next)
        self.btn_find_prev = QPushButton(tr('find_prev', language))
        self.btn_find_prev.clicked.connect(self._find_prev)
        row2.addWidget(self.btn_find_prev)
        self.btn_replace = QPushButton(tr('find_replace_btn', language))
        self.btn_replace.clicked.connect(self._replace_one)
        row2.addWidget(self.btn_replace)
        self.btn_replace_all = QPushButton(tr('find_replace_all', language))
        self.btn_replace_all.clicked.connect(self._replace_all)
        row2.addWidget(self.btn_replace_all)
        layout.addLayout(row2)
        
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.status_label)
        
        self.btn_find_next.setEnabled(False)
        self.btn_find_prev.setEnabled(False)
        self.btn_replace.setEnabled(False)
        self.btn_replace_all.setEnabled(False)
    
    def set_editor(self, editor):
        self.editor = editor
    
    def _get_editor(self):
        return self.editor
    
    def _get_flags(self, backward=False):
        flags = QTextDocument.FindFlag(0)
        if self.case_check.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.whole_check.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward
        return flags
    
    def _on_search_changed(self, text):
        has_text = bool(text.strip())
        self.btn_find_next.setEnabled(has_text)
        self.btn_find_prev.setEnabled(has_text)
        self.btn_replace.setEnabled(has_text)
        self.btn_replace_all.setEnabled(has_text)
        if not has_text:
            self.status_label.clear()
    
    def _find_next(self):
        editor = self._get_editor()
        if not editor:
            return
        text = self.search_edit.text()
        if not text:
            return
        found = editor.find(text, self._get_flags(backward=False))
        if not found:
            self.status_label.setText(tr('find_not_found', self.language))
        else:
            self.status_label.clear()
    
    def _find_prev(self):
        editor = self._get_editor()
        if not editor:
            return
        text = self.search_edit.text()
        if not text:
            return
        found = editor.find(text, self._get_flags(backward=True))
        if not found:
            self.status_label.setText(tr('find_not_found', self.language))
        else:
            self.status_label.clear()
    
    def _selection_matches(self, cursor, search_text):
        if not cursor.hasSelection():
            return False
        sel = cursor.selectedText()
        if self.case_check.isChecked():
            return sel == search_text
        return sel.lower() == search_text.lower()
    
    def _replace_one(self):
        editor = self._get_editor()
        if not editor:
            return
        search_text = self.search_edit.text()
        replace_text = self.replace_edit.text()
        if not search_text:
            return
        cursor = editor.textCursor()
        if self._selection_matches(cursor, search_text):
            cursor.insertText(replace_text)
            self.status_label.setText(tr('find_replace_done', self.language))
            return
        found = editor.find(search_text, self._get_flags(backward=False))
        if found:
            c = editor.textCursor()
            if c.hasSelection():
                c.insertText(replace_text)
            self.status_label.setText(tr('find_replace_done', self.language))
        else:
            self.status_label.setText(tr('find_not_found', self.language))
    
    def _replace_all(self):
        editor = self._get_editor()
        if not editor:
            return
        search_text = self.search_edit.text()
        replace_text = self.replace_edit.text()
        if not search_text:
            return
        cursor = editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        editor.setTextCursor(cursor)
        count = 0
        cursor.beginEditBlock()
        while editor.find(search_text, self._get_flags(backward=False)):
            c = editor.textCursor()
            if c.hasSelection():
                c.insertText(replace_text)
                count += 1
        cursor.endEditBlock()
        self.status_label.setText(tr('find_replace_count', self.language).format(count))

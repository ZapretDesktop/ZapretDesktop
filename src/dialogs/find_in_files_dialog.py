"""
Диалог поиска по файлам в папке текущей вкладки редактора.
"""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from src.core.translator import tr
from src.widgets.custom_checkbox import CustomCheckBox
from src.widgets.custom_context_widgets import ContextLineEdit
import pywinstyles


class SearchInFilesThread(QThread):
    """Поток поиска по файлам."""
    finished = pyqtSignal(list)  # [(filepath, line_num, line_text), ...]

    def __init__(self, folder, file_patterns, search_text, case_sensitive):
        super().__init__()
        self.folder = folder
        self.file_patterns = file_patterns  # ['*.txt'], ['*.bat'] или список имён
        self.search_text = search_text
        self.case_sensitive = case_sensitive

    def run(self):
        results = []
        if not self.search_text or not os.path.isdir(self.folder):
            self.finished.emit(results)
            return

        needle = self.search_text if self.case_sensitive else self.search_text.lower()

        import fnmatch

        def matches(fname):
            for pat in self.file_patterns:
                if '*' in pat and fnmatch.fnmatch(fname, pat):
                    return True
                if fname == pat:
                    return True
            return False

        try:
            files = [f for f in os.listdir(self.folder)
                     if os.path.isfile(os.path.join(self.folder, f)) and matches(f)]
            for filename in sorted(files):
                path = os.path.join(self.folder, filename)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            haystack = line if self.case_sensitive else line.lower()
                            if needle in haystack:
                                results.append((path, filename, i, line.rstrip('\n\r')))
                except Exception:
                    pass
        except OSError:
            pass
        self.finished.emit(results)


class FindInFilesDialog(QDialog):
    """Диалог поиска по файлам в папке текущей вкладки."""

    def __init__(self, parent=None, language='ru'):
        super().__init__(parent)
        self.parent_editor = parent  # UnifiedEditorWindow
        self.language = language
        self._results = []  # [(path, filename, line_num, line_text), ...]
        self._search_thread = None

        from src.core.embedded_assets import get_app_icon
        self.setWindowIcon(get_app_icon())

        pywinstyles.change_header_color(self, color="#181818")
        self.setWindowTitle(tr('find_in_files_title', language))
        self.setWindowFlags(Qt.WindowType.Tool)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setMinimumSize(580, 400)
        self.setMaximumSize(900, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel(tr('find_in_files_search', language)))
        self.search_edit = ContextLineEdit()
        self.search_edit.setPlaceholderText(tr('find_search_placeholder', language))
        self.search_edit.returnPressed.connect(self._do_search)
        row1.addWidget(self.search_edit, 1)

        self.case_check = CustomCheckBox(tr('find_case', language))
        row1.addWidget(self.case_check)

        self.btn_search = QPushButton(tr('find_in_files_search_btn', language))
        self.btn_search.clicked.connect(self._do_search)
        row1.addWidget(self.btn_search)
        layout.addLayout(row1)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.status_label)

        self.results_list = QListWidget()
        self.results_list.setFont(QFont("Consolas", 9))
        self.results_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_list.itemDoubleClicked.connect(self._on_result_double_clicked)
        self.results_list.setStyleSheet("""
            QListWidget { background-color: #1f1f1f; border: 1px solid #2b2b2b; color: #cccccc; }
            QListWidget::item { padding: 2px 4px; }
            QListWidget::item:hover { background-color: #2a2d2e; }
            QListWidget::item:selected { background-color: #04395e; color: #ffffff; }
        """)
        layout.addWidget(self.results_list, 1)

        self.search_edit.textChanged.connect(self._on_search_changed)
        self.btn_search.setEnabled(False)

    def _on_search_changed(self, text):
        self.btn_search.setEnabled(bool(text.strip()))

    def set_scope(self, folder, file_patterns, tab_index):
        """Устанавливает область поиска: папка, маска файлов, индекс вкладки."""
        self._folder = folder
        self._file_patterns = file_patterns
        self._tab_index = tab_index

    def _get_scope_from_parent(self):
        """Берёт область поиска из текущей вкладки родительского окна."""
        if not self.parent_editor or not hasattr(self.parent_editor, 'tabs'):
            return False
        tab = self.parent_editor.current_tab_content()
        if tab is None:
            return False
        self._folder = tab.folder
        if getattr(tab, 'tab_kind', '') == 'bat':
            self._file_patterns = ['*.bat']
        elif getattr(tab, 'tab_kind', '') == 'lists':
            self._file_patterns = ['*.txt']
        elif getattr(tab, 'tab_kind', '') == 'etc':
            from src.editor.unified_editor_window import ETC_FILES
            self._file_patterns = ETC_FILES
        else:
            self._file_patterns = ['*']
        for i in range(self.parent_editor.tabs.count()):
            if self.parent_editor.tabs.widget(i) is tab:
                self._tab_index = i
                break
        return True

    def _do_search(self):
        if not self._get_scope_from_parent():
            self.status_label.setText(tr('find_in_files_no_scope', self.language))
            return
        text = self.search_edit.text().strip()
        if not text:
            return
        if self._search_thread and self._search_thread.isRunning():
            return
        self.btn_search.setEnabled(False)
        self.status_label.setText(tr('find_in_files_searching', self.language))
        self.results_list.clear()
        self._results = []

        self._search_thread = SearchInFilesThread(
            self._folder,
            self._file_patterns,
            text,
            self.case_check.isChecked()
        )
        self._search_thread.finished.connect(self._on_search_finished)
        self._search_thread.start()

    def _on_search_finished(self, results):
        self._results = results
        self._search_thread = None
        self.btn_search.setEnabled(bool(self.search_edit.text().strip()))

        for path, filename, line_num, line_text in results:
            item = QListWidgetItem(f"{filename}:{line_num}: {line_text[:80]}{'…' if len(line_text) > 80 else ''}")
            item.setData(Qt.ItemDataRole.UserRole, (path, filename, line_num))
            self.results_list.addItem(item)

        count = len(results)
        if count == 0:
            self.status_label.setText(tr('find_not_found', self.language))
        else:
            self.status_label.setText(tr('find_in_files_results', self.language).format(count))

    def _on_result_double_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        path, filename, line_num = data
        if self.parent_editor and hasattr(self.parent_editor, 'open_file_at_line'):
            self.parent_editor.open_file_at_line(self._tab_index, filename, line_num)
        self.close()

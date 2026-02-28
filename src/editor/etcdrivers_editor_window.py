"""
Редактор файлов из папки drivers\\etc (C:\\Windows\\System32\\drivers\\etc)
"""

import os
import subprocess
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import QFont, QAction, QKeySequence
from src.core.translator import tr
from src.ui.standard_dialog import StandardDialog
from src.dialogs.find_replace_dialog import FindReplaceDialog
from src.widgets.custom_combobox import CustomComboBox
from .line_number_editor import LineNumberPlainTextEdit
from src.widgets.style_menu import StyleMenu
import pywinstyles


def get_etcdrivers_folder():
    """Возвращает путь к папке drivers\\etc"""
    system_root = os.environ.get('SystemRoot', 'C:\\Windows')
    return os.path.join(system_root, 'System32', 'drivers', 'etc')


class EtcdriversEditorWindow(StandardDialog):
    """Окно редактирования файлов из drivers\\etc (hosts, lmhosts, networks, protocol, services)"""
    
    ETC_FILES = ['hosts', 'lmhosts', 'networks', 'protocol', 'services']
    
    def __init__(self, parent=None):
        self.etc_folder = get_etcdrivers_folder()
        self.language = 'ru'
        if parent:
            if hasattr(parent, 'settings'):
                self.language = parent.settings.get('language', 'ru')
            elif hasattr(parent, 'config'):
                try:
                    self.language = parent.config.load_settings().get('language', 'ru')
                except Exception:
                    pass
        
        from src.core.embedded_assets import get_app_icon
        super().__init__(
            parent=parent,
            title=tr('etcdrivers_editor_title', self.language),
            width=700,
            height=500,
            icon=get_app_icon(),
            theme="dark"
        )
        
        pywinstyles.change_header_color(self, color="#181818")
        self.setWindowModality(Qt.WindowModality.NonModal)
        
        self.is_saving = False
        self.file_watcher = QFileSystemWatcher()
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.auto_save_file)
        self._find_replace_dialog = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = self.getContentLayout()
        
        # Верхняя панель: выбор файла
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(tr('lists_editor_file', self.language)))
        self.file_combo = CustomComboBox(self)
        self.file_combo.addItems(self.ETC_FILES)
        self.file_combo.currentTextChanged.connect(self.on_file_changed)
        top_layout.addWidget(self.file_combo, 1)
        layout.addLayout(top_layout)
        
        # Меню Правка
        self.menu_bar = QMenuBar()
        edit_menu = StyleMenu(self.menu_bar)
        edit_menu.setTitle(tr('lists_editor_menu_edit', self.language))
        self.menu_bar.addMenu(edit_menu)
        
        self.action_find_replace = QAction(tr('find_replace_title', self.language), self)
        self.action_find_replace.setShortcut(QKeySequence("Ctrl+H"))
        self.action_find_replace.triggered.connect(self.show_find_replace)
        edit_menu.addAction(self.action_find_replace)
        
        edit_menu.addSeparator()
        
        self.action_open_folder = QAction(tr('etcdrivers_open_folder', self.language), self)
        self.action_open_folder.triggered.connect(self.open_folder)
        edit_menu.addAction(self.action_open_folder)
        
        self.title_bar.addLeftWidget(self.menu_bar)
        
        # Редактор с нумерацией строк
        self.editor = LineNumberPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 10))
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.cursorPositionChanged.connect(self.on_cursor_position_changed)
        layout.addWidget(self.editor)
        
        # Статус: сообщение | строка, столбец
        status_layout = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: gray; font-size: 11px;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        self.position_label = QLabel()
        self.position_label.setStyleSheet("color: gray; font-size: 11px;")
        status_layout.addWidget(self.position_label)
        layout.addLayout(status_layout)
        
        # Загружаем первый файл
        self._current_file = self.file_combo.currentText()
        self.load_current_file()
        
        for f in self.ETC_FILES:
            path = os.path.join(self.etc_folder, f)
            if os.path.exists(path):
                try:
                    self.file_watcher.addPath(path)
                except Exception:
                    pass
        self.file_watcher.fileChanged.connect(self.on_file_changed_externally)
    
    def get_current_file_path(self):
        return os.path.join(self.etc_folder, self.file_combo.currentText())
    
    def open_folder(self):
        """Открывает папку drivers\\etc в проводнике"""
        try:
            if os.path.exists(self.etc_folder):
                subprocess.Popen(['explorer', self.etc_folder])
            else:
                QMessageBox.warning(self, tr('msg_error', self.language),
                    tr('etcdrivers_folder_not_found', self.language))
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))
    
    def load_current_file(self):
        path = self.get_current_file_path()
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            else:
                content = ''
            
            self.editor.blockSignals(True)
            self.editor.setPlainText(content)
            self.editor.blockSignals(False)
            self.editor.document().setModified(False)
            self.save_timer.stop()
            self.update_status(tr('targets_saved', self.language))
            self.on_cursor_position_changed()
        except Exception as e:
            QMessageBox.warning(self, tr('test_error_title', self.language),
                f"{tr('targets_error_loading', self.language)}: {str(e)}")
    
    def save_current_file(self):
        path = self.get_current_file_path()
        try:
            self.is_saving = True
            content = self.editor.toPlainText()
            
            if os.path.exists(path):
                try:
                    self.file_watcher.removePath(path)
                except Exception:
                    pass
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            if os.path.exists(path):
                try:
                    self.file_watcher.addPath(path)
                except Exception:
                    pass
            
            self.editor.document().setModified(False)
            self.save_timer.stop()
            self.update_status(tr('targets_saved', self.language))
        except PermissionError:
            QMessageBox.warning(self, tr('msg_error', self.language),
                tr('etcdrivers_save_admin_required', self.language))
        except Exception as e:
            QMessageBox.warning(self, tr('test_error_title', self.language),
                f"{tr('targets_error_saving', self.language)}: {str(e)}")
        finally:
            self.is_saving = False
    
    def auto_save_file(self):
        if self.is_saving:
            return
        self.save_current_file()
    
    def on_file_changed(self, filename):
        if not filename:
            return
        if self.editor.document().isModified():
            reply = QMessageBox.question(
                self, tr('test_error_title', self.language),
                tr('targets_unsaved_changes', self.language),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.file_combo.blockSignals(True)
                self.file_combo.setCurrentText(getattr(self, '_current_file', self.ETC_FILES[0]))
                self.file_combo.blockSignals(False)
                return
        self._current_file = filename
        self.load_current_file()
    
    def on_text_changed(self):
        self.save_timer.stop()
        self.save_timer.start(1000)
    
    def on_file_changed_externally(self, path):
        if self.is_saving:
            return
        current_path = self.get_current_file_path()
        if path == current_path:
            self.save_timer.stop()
            self.load_current_file()
        if os.path.exists(path) and path not in self.file_watcher.files():
            try:
                self.file_watcher.addPath(path)
            except Exception:
                pass
    
    def update_status(self, text):
        self.status_label.setText(text)
    
    def on_cursor_position_changed(self):
        line, col = self.editor.get_cursor_position()
        self.position_label.setText(tr('editor_line_column', self.language).format(line, col))
    
    def show_find_replace(self):
        if self._find_replace_dialog is None:
            self._find_replace_dialog = FindReplaceDialog(
                parent=self,
                editor=self.editor,
                language=self.language
            )
        self._find_replace_dialog.set_editor(self.editor)
        self._find_replace_dialog.show()
        self._find_replace_dialog.raise_()
        self._find_replace_dialog.activateWindow()

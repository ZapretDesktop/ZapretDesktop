"""
Объединённое окно редакторов: списки winws/lists, файлы drivers\\etc и стратегии (.bat).
QTabWidget, в каждой вкладке: QLineEdit (поиск), QListWidget, QSplitter, QPlainTextEdit.
"""

import os
import subprocess
import locale
from pathlib import Path
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import QFont, QAction, QKeySequence, QTextCursor, QTextDocument
from src.core.translator import tr
from src.core.path_utils import get_winws_path
from src.ui.standard_dialog import StandardDialog
from src.dialogs.find_replace_dialog import FindReplaceDialog
from src.dialogs.find_in_files_dialog import FindInFilesDialog
from src.dialogs.country_blocklist_dialog import CountryBlocklistDialog
from .line_number_editor import LineNumberPlainTextEdit
from src.widgets.style_menu import StyleMenu
from src.widgets.custom_context_widgets import ContextLineEdit
from src.widgets.label_menu_widget import LabelMenuWidget
from src.widgets.breadcrumb_widget import BreadcrumbWidget
from .editor_highlighters import ListHighlighter, EtcHighlighter, BatHighlighter
from .editor_autocomplete import EditorAutocomplete
import pywinstyles


def get_etcdrivers_folder():
    system_root = os.environ.get('SystemRoot', 'C:\\Windows')
    return os.path.join(system_root, 'System32', 'drivers', 'etc')


LIST_FILES = ['list-general.txt', 'list-exclude.txt', 'list-google.txt', 'ipset-all.txt', 'ipset-exclude.txt']
ETC_FILES = ['hosts', 'lmhosts', 'networks', 'protocol', 'services']


def get_bat_files(winws_folder):
    """Возвращает список .bat файлов из папки winws (исключая service.bat)."""
    bat_files = []
    if os.path.exists(winws_folder):
        for filename in os.listdir(winws_folder):
            if filename.endswith('.bat') and filename != 'service.bat' and os.path.isfile(os.path.join(winws_folder, filename)):
                bat_files.append(filename)
        bat_files.sort()
    return bat_files


class EditorTabContent(QWidget):
    """Одна вкладка: фильтр (QLineEdit), список файлов (QListWidget), редактор (QPlainTextEdit) в QSplitter."""
    
    def __init__(self, parent, folder, file_names, language='ru', is_lists_tab=False, tab_kind='lists'):
        super().__init__(parent)
        self.folder = folder
        self.file_names = list(file_names)
        self.language = language
        self.is_lists_tab = is_lists_tab
        self.tab_kind = tab_kind
        self._current_file = self.file_names[0] if self.file_names else ''
        self.is_saving = False
        self.file_watcher = QFileSystemWatcher(self)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.auto_save_file)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        
        
        # Левая панель: поиск + список файлов (+ состояние «ничего не найдено» как в окне настроек)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Строка поиска
        self.filter_edit = ContextLineEdit()
        self.filter_edit.setStyleSheet('border:none;')
        self.filter_edit.setPlaceholderText(tr('settings_search_placeholder', language))
        self.filter_edit.textChanged.connect(self.apply_filter)
        left_layout.addWidget(self.filter_edit)

        # Список файлов + виджет «ничего не найдено» в QStackedWidget
        self.file_list = QListWidget()
        self.file_list.setStyleSheet(''' QListWidget {
    background-color: #1f1f1f;
    border: none;
   
    color: #cccccc;
}

QListWidget::item {
    height: 20px;
  
}

QListWidget::item:hover {
    background-color: #2a2d2e;
 
}

QListWidget::item:selected {
    background-color: #04395e;
    color: #ffffff;
}

QListWidget::item:selected:!active {
    background-color: #04395e;
    color: #ffffff;
}''')
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._on_file_list_context_menu)
        for name in self.file_names:
            self.file_list.addItem(name)
        self.file_list.currentItemChanged.connect(self._on_file_list_item_changed)

        self._left_list_stack = QStackedWidget()
        self._left_list_stack.addWidget(self.file_list)  # index 0: обычный список

        nothing_widget = QWidget()
        nothing_layout = QVBoxLayout(nothing_widget)
        nothing_layout.setContentsMargins(0, 0, 0, 0)
        nothing_label = QLabel(tr('settings_nothing_found', language))
        nothing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nothing_label.setStyleSheet('color: #808080; font-size: 13px;')
        nothing_layout.addWidget(nothing_label)
        nothing_widget.setStyleSheet('background-color: #1f1f1f;')

        self._left_list_stack.addWidget(nothing_widget)  # index 1: «ничего не найдено»
        self._left_list_stack.setCurrentIndex(0)

        left_layout.addWidget(self._left_list_stack)
        splitter.addWidget(left)
        
        # Правая панель: редактор (для вкладки стратегий — с консолью снизу,
        # для вкладки etc — с дополнительным просмотром zapret_hosts.txt)
        self.editor = LineNumberPlainTextEdit()
        self.editor.setStyleSheet('border:none;')
        self.editor.setFont(QFont("Consolas", 10))
        # Устанавливаем табуляцию на 4 пробела
        font_metrics = self.editor.fontMetrics()
        self.editor.setTabStopDistance(4 * font_metrics.horizontalAdvance(' '))
        # Настройки по умолчанию
        self.tab_size = 4
        self.encoding = 'UTF-8'
        self.line_ending = 'CRLF'
        if tab_kind == 'lists':
            self._highlighter = ListHighlighter(self.editor.document())
        elif tab_kind == 'etc':
            self._highlighter = EtcHighlighter(self.editor.document())
        else:
            self._highlighter = BatHighlighter(self.editor.document())
        self._autocomplete = EditorAutocomplete(self.editor, tab_kind=tab_kind)
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.cursorPositionChanged.connect(self.on_cursor_position_changed)
        self.editor.cursorPositionChanged.connect(self._on_editor_cursor_changed)

        if tab_kind == 'bat':
            right_splitter = QSplitter(Qt.Orientation.Vertical)
            right_splitter.setHandleWidth(1)
            right_splitter.addWidget(self.editor)

            cmd_widget = QWidget()
            cmd_layout = QVBoxLayout(cmd_widget)
            cmd_layout.setContentsMargins(0, 0, 0, 0)
            cmd_layout.setSpacing(0)
            cmd_label = QLabel(tr('editor_cmd_panel_title', self.language))
            cmd_label.setStyleSheet("color: #cccccc; font-size: 11px; padding: 2px 6px;")
            cmd_layout.addWidget(cmd_label)

            # Кастомный LineNumberPlainTextEdit как интерактивная консоль cmd.exe (и ввод, и вывод)
            self.command_console = LineNumberPlainTextEdit()
            # Для консоли отключаем подсветку текущей строки
            if hasattr(self.command_console, "set_highlight_current_line_enabled"):
                self.command_console.set_highlight_current_line_enabled(False)
            self.command_console.setStyleSheet("background-color: #141414; border: none; color: #ffffff;")
            self.command_console.setFont(QFont("Consolas", 9))
            self.command_console.installEventFilter(self)
            # Курсор всегда должен быть только на строке ввода (после '>')
            self._cmd_cursor_fixing = False
            self.command_console.cursorPositionChanged.connect(self._on_cmd_cursor_changed)
            cmd_layout.addWidget(self.command_console)

            # Позиция начала текущей команды
            self._cmd_input_start = 0

            # Процесс cmd.exe для интерактивной работы
            # Кодировка консоли: для Windows явно используем chcp 1251
            if os.name == 'nt':
                self._cmd_encoding = 'cp1251'
            else:
                self._cmd_encoding = locale.getpreferredencoding(False) or 'utf-8'

            from PyQt6.QtCore import QProcess
            self.cmd_process = QProcess(self)
            self.cmd_process.setProgram("cmd.exe")
            # Для Windows сразу переключаем кодовую страницу на 1251 и отключаем эхо команд (/Q),
            # чтобы не дублировать введённые команды в выводе.
            if os.name == 'nt':
                self.cmd_process.setArguments(['/Q', '/K', 'chcp 1251>nul'])
            # Рабочая папка — папка стратегий
            if os.path.isdir(self.folder):
                self.cmd_process.setWorkingDirectory(self.folder)
            self.cmd_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
            self.cmd_process.readyReadStandardOutput.connect(self._on_cmd_output)
            self.cmd_process.readyReadStandardError.connect(self._on_cmd_output)
            self.cmd_process.start()

            right_splitter.addWidget(cmd_widget)
            right_splitter.setStretchFactor(0, 4)
            right_splitter.setStretchFactor(1, 1)
            right_splitter.setSizes([500, 200])
            splitter.addWidget(right_splitter)
        elif tab_kind == 'etc':
            right_splitter = QSplitter(Qt.Orientation.Horizontal)
            right_splitter.setHandleWidth(1)
            right_splitter.addWidget(self.editor)

            from PyQt6.QtWidgets import QPlainTextEdit
            self.zapret_hosts_view = QPlainTextEdit()
            self.zapret_hosts_view.setReadOnly(True)
            self.zapret_hosts_view.setStyleSheet("background-color: #181818; border: none; color: #bbbbbb;")
            self.zapret_hosts_view.setFont(QFont("Consolas", 9))
            right_splitter.addWidget(self.zapret_hosts_view)
            right_splitter.setStretchFactor(0, 3)
            right_splitter.setStretchFactor(1, 2)
            splitter.addWidget(right_splitter)
        else:
            splitter.addWidget(self.editor)
        
        splitter.setSizes([302, 500])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)
        
        self._last_status = ''
        self._last_line = 1
        self._last_col = 1
        
        if self.file_names:
            self.file_list.setCurrentRow(0)
        
        for f in self.file_names:
            path = os.path.join(self.folder, f)
            if os.path.exists(path):
                try:
                    self.file_watcher.addPath(path)
                except Exception:
                    pass
        self.file_watcher.fileChanged.connect(self.on_file_changed_externally)
        # Отслеживание добавления/удаления файлов в папке
        if os.path.isdir(self.folder):
            try:
                self.file_watcher.addPath(self.folder)
                self.file_watcher.directoryChanged.connect(self._on_directory_changed)
            except Exception:
                pass
        self._dir_refresh_timer = QTimer(self)
        self._dir_refresh_timer.setSingleShot(True)
        self._dir_refresh_timer.timeout.connect(self._refresh_file_list_from_disk)
    
    def _on_directory_changed(self):
        """Папка изменилась — обновляем список файлов с небольшой задержкой (debounce)."""
        self._dir_refresh_timer.stop()
        self._dir_refresh_timer.start(300)

    def _get_files_from_disk(self):
        """Возвращает актуальный список файлов из папки в зависимости от вкладки."""
        if not os.path.isdir(self.folder):
            return []
        if self.tab_kind == 'bat':
            return get_bat_files(self.folder)
        if self.tab_kind == 'lists':
            try:
                files = [f for f in os.listdir(self.folder) if os.path.isfile(os.path.join(self.folder, f))]
                ordered = [f for f in LIST_FILES if f in files]
                others = sorted(f for f in files if f not in LIST_FILES)
                return ordered + others
            except OSError:
                return list(self.file_names)
        if self.tab_kind == 'etc':
            return [f for f in ETC_FILES if os.path.isfile(os.path.join(self.folder, f))]
        return list(self.file_names)

    def _refresh_file_list_from_disk(self):
        """Обновляет QListWidget и file_names по содержимому папки."""
        new_names = self._get_files_from_disk()
        if new_names == self.file_names:
            return
        current = self.file_list.currentItem()
        current_name = current.text() if current else self._current_file
        filter_text = self.filter_edit.text() if hasattr(self, 'filter_edit') else ''

        # Обновляем file_watcher: убираем старые пути к файлам
        for p in self.file_watcher.files():
            try:
                self.file_watcher.removePath(p)
            except Exception:
                pass

        self.file_names = new_names
        self.file_list.blockSignals(True)
        try:
            self.file_list.clear()
            for name in self.file_names:
                self.file_list.addItem(name)

            # Восстанавливаем выбор
            idx = -1
            for i, name in enumerate(self.file_names):
                if name == current_name:
                    idx = i
                    break
            if idx >= 0:
                self.file_list.setCurrentRow(idx)
                self._current_file = current_name
            elif self.file_names:
                self.file_list.setCurrentRow(0)
                self._current_file = self.file_names[0]
        finally:
            self.file_list.blockSignals(False)

        # Добавляем пути к файлам в watcher
        for f in self.file_names:
            path = os.path.join(self.folder, f)
            if os.path.exists(path):
                try:
                    self.file_watcher.addPath(path)
                except Exception:
                    pass

        self.apply_filter(filter_text)
        # Не перезагружаем текущий файл — список обновился, редактор остаётся без изменений

    def apply_filter(self, text):
        text = text.strip().lower()
        visible_count = 0
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            name = item.text().lower()
            visible = not text or text in name
            item.setHidden(not visible)
            if visible:
                visible_count += 1

        # Переключаемся на виджет «Ничего не найдено», если фильтр есть и видимых элементов нет
        if hasattr(self, '_left_list_stack'):
            if text and visible_count == 0:
                self._left_list_stack.setCurrentIndex(1)
                self.file_list.setCurrentRow(-1)
            else:
                self._left_list_stack.setCurrentIndex(0)
                # Если есть фильтр и текущий элемент не выбран, выбираем первый видимый
                if text and self.file_list.currentRow() < 0:
                    for i in range(self.file_list.count()):
                        if not self.file_list.item(i).isHidden():
                            self.file_list.setCurrentRow(i)
                            break

    def _on_file_list_context_menu(self, pos):
        """Контекстное меню по списку файлов слева."""
        item = self.file_list.itemAt(pos)
        menu = StyleMenu(self.file_list)

        action_open_folder = menu.addAction(tr('lists_editor_open_folder', self.language))

        # Создать файл через родительское окно, если есть такой метод
        win = self.window()
        can_create = hasattr(win, 'create_new_file')
        if can_create:
            action_create = menu.addAction(tr('editor_create_file', self.language))
        else:
            action_create = None

        # Удаление файла разрешаем только для списков и bat
        can_delete = bool(item) and getattr(self, 'tab_kind', '') in ('lists', 'bat')
        if can_delete:
            menu.addSeparator()
            action_delete = menu.addAction(tr('editor_delete_file', self.language))
        else:
            action_delete = None

        global_pos = self.file_list.mapToGlobal(pos)
        chosen = menu.exec(global_pos)
        if not chosen:
            return

        if chosen is action_open_folder:
            self.open_folder()
            return

        if chosen is action_create and can_create:
            win.create_new_file()
            return

        if chosen is action_delete and can_delete:
            filename = item.text()
            path = os.path.join(self.folder, filename)
            reply = QMessageBox.question(
                self,
                tr('msg_confirm', self.language),
                tr('editor_delete_file_confirm', self.language).format(filename),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            try:
                if os.path.exists(path):
                    try:
                        self.file_watcher.removePath(path)
                    except Exception:
                        pass
                    os.remove(path)
                row = self.file_list.row(item)
                self.file_list.takeItem(row)
                if self.file_list.count() > 0:
                    self.file_list.setCurrentRow(max(0, row - 1))
                else:
                    self._current_file = ''
                    self.editor.clear()
            except Exception as e:
                QMessageBox.warning(self, tr('msg_error', self.language), str(e))
    
    def get_current_file_path(self):
        cur = self.file_list.currentItem()
        if not cur:
            return os.path.join(self.folder, self._current_file) if self._current_file else ''
        return os.path.join(self.folder, cur.text())
    
    def get_current_editor(self):
        return self.editor
    
    def load_current_file(self):
        path = self.get_current_file_path()
        if not path or not os.path.basename(path):
            return
        try:
            if os.path.exists(path):
                # Пытаемся определить кодировку
                encoding_map = {'UTF-8': 'utf-8', 'UTF-8 BOM': 'utf-8-sig', 'Windows-1251': 'windows-1251'}
                encoding = encoding_map.get(self.encoding, 'utf-8')
                try:
                    with open(path, 'r', encoding=encoding, errors='ignore') as f:
                        content = f.read()
                except UnicodeDecodeError:
                    # Если не получилось, пробуем UTF-8
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
            else:
                content = ''
                if self.is_lists_tab:
                    os.makedirs(self.folder, exist_ok=True)
            self.editor.blockSignals(True)
            self.editor.setPlainText(content)
            self.editor.blockSignals(False)
            self.editor.document().setModified(False)
            self.editor.refresh_line_number_area()
            self.save_timer.stop()
            self._last_status = tr('targets_saved', self.language)
            self._push_status()
            self.on_cursor_position_changed()
            # Обновляем подсветку текущей строки сразу после загрузки файла
            if hasattr(self.editor, "_on_cursor_position_changed"):
                self.editor._on_cursor_position_changed()
            self._on_editor_cursor_changed()
            # Обновляем заголовок окна после загрузки файла
            win = self.window()
            if win is not self and hasattr(win, '_update_window_title'):
                win._update_window_title()

            # Если это вкладка etc — обновляем просмотр zapret_hosts.txt при открытом hosts
            if getattr(self, 'tab_kind', '') == 'etc' and hasattr(self, 'zapret_hosts_view'):
                self._update_zapret_hosts_view()
        except Exception as e:
            QMessageBox.warning(self, tr('test_error_title', self.language),
                f"{tr('targets_error_loading', self.language)}: {str(e)}")
    
    def save_current_file(self):
        path = self.get_current_file_path()
        if not path:
            return
        try:
            self.is_saving = True
            content = self.editor.toPlainText()
            # Конвертируем окончания строк в выбранный формат
            if self.line_ending == 'CRLF':
                content = content.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
            elif self.line_ending == 'LF':
                content = content.replace('\r\n', '\n').replace('\r', '\n')
            elif self.line_ending == 'CR':
                content = content.replace('\r\n', '\n').replace('\n', '\r')
            if os.path.exists(path):
                try:
                    self.file_watcher.removePath(path)
                except Exception:
                    pass
            if self.is_lists_tab:
                os.makedirs(self.folder, exist_ok=True)
            # Используем выбранную кодировку
            encoding_map = {'UTF-8': 'utf-8', 'UTF-8 BOM': 'utf-8-sig', 'Windows-1251': 'windows-1251'}
            encoding = encoding_map.get(self.encoding, 'utf-8')
            with open(path, 'w', encoding=encoding, newline='') as f:
                if self.encoding == 'UTF-8 BOM':
                    f.write('\ufeff')
                f.write(content)
            if os.path.exists(path):
                try:
                    self.file_watcher.addPath(path)
                except Exception:
                    pass
            self.editor.document().setModified(False)
            self.save_timer.stop()
            self._last_status = tr('targets_saved', self.language)
            self._push_status()
            self._on_editor_cursor_changed()
            # При сохранении hosts можно тоже обновить просмотр zapret_hosts.txt (если нужно)
            if getattr(self, 'tab_kind', '') == 'etc' and hasattr(self, 'zapret_hosts_view'):
                self._update_zapret_hosts_view()
            # Обновляем заголовок окна после сохранения файла
            win = self.window()
            if win is not self and hasattr(win, '_update_window_title'):
                win._update_window_title()
        except PermissionError:
            QMessageBox.warning(self, tr('msg_error', self.language),
                tr('etcdrivers_save_admin_required', self.language))
        except Exception as e:
            QMessageBox.warning(self, tr('test_error_title', self.language),
                f"{tr('targets_error_saving', self.language)}: {str(e)}")
        finally:
            self.is_saving = False
    
    def set_tab_size(self, size):
        """Устанавливает размер табуляции (в пробелах)."""
        self.tab_size = size
        font_metrics = self.editor.fontMetrics()
        self.editor.setTabStopDistance(size * font_metrics.horizontalAdvance(' '))
    
    def set_encoding(self, encoding):
        """Устанавливает кодировку файла."""
        self.encoding = encoding
    
    def set_line_ending(self, line_ending):
        """Устанавливает окончания строк."""
        self.line_ending = line_ending
    
    def auto_save_file(self):
        if self.is_saving:
            return
        self.save_current_file()
    
    def _on_file_list_item_changed(self, current, previous):
        filename = current.text() if current else ''
        self.on_file_selected(filename)
    
    def on_file_selected(self, filename):
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
                for i in range(self.file_list.count()):
                    if self.file_list.item(i).text() == self._current_file:
                        self.file_list.blockSignals(True)
                        self.file_list.setCurrentRow(i)
                        self.file_list.blockSignals(False)
                        break
                return
        self._current_file = filename
        self.load_current_file()
    
    def on_text_changed(self):
        self.save_timer.stop()
        self.save_timer.start(1000)
        self._on_editor_cursor_changed()
    
    def on_file_changed_externally(self, path):
        if self.is_saving:
            return
        if path == self.get_current_file_path():
            self.save_timer.stop()
            self.load_current_file()
        if os.path.exists(path) and path not in self.file_watcher.files():
            try:
                self.file_watcher.addPath(path)
            except Exception:
                pass

    
    def on_cursor_position_changed(self):
        line, col = self.editor.get_cursor_position()
        self._last_line, self._last_col = line, col
        self._push_status()
    
    def _on_editor_cursor_changed(self):
        """Обновляет состояние действий меню при изменении курсора."""
        win = self.window()
        if win is not self and hasattr(win, '_update_actions_state'):
            win._update_actions_state()
    
    def _push_status(self):
        """Обновляет статус-бар родительского окна."""
        win = self.window()
        if win is not self and hasattr(win, 'update_editor_status'):
            win.update_editor_status(self._last_status, self._last_line, self._last_col)

    def _update_zapret_hosts_view(self):
        """Обновляет нижний просмотр zapret_hosts.txt для вкладки etc и файла hosts."""
        if getattr(self, 'tab_kind', '') != 'etc' or not hasattr(self, 'zapret_hosts_view'):
            return
        current_name = self.file_list.currentItem().text() if self.file_list.currentItem() else self._current_file
        if not current_name or current_name.lower() != 'hosts':
            # Для не-hosts просто показываем пусто
            self.zapret_hosts_view.clear()
            return
        # Путь к zapret_hosts.txt совпадает с тем, что использовался в update_hosts_file
        temp_dir = os.environ.get('TEMP', 'C:\\Temp')
        zapret_path = os.path.join(temp_dir, 'zapret_hosts.txt')
        if not os.path.exists(zapret_path):
            self.zapret_hosts_view.setPlainText("zapret_hosts.txt not found.\n\nИспользуйте обновление hosts через основной интерфейс, чтобы загрузить файл.")
            return
        try:
            with open(zapret_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            self.zapret_hosts_view.setPlainText(content)
            self.zapret_hosts_view.moveCursor(self.zapret_hosts_view.textCursor().MoveOperation.Start)
        except Exception as e:
            self.zapret_hosts_view.setPlainText(f"Ошибка чтения zapret_hosts.txt:\n{e}")

    def _on_cmd_cursor_changed(self):
        """Гарантирует, что курсор во вкладке стратегий cmd находится только на строке ввода (после '>')."""
        if getattr(self, 'tab_kind', '') != 'bat':
            return
        if not hasattr(self, 'command_console') or not hasattr(self, '_cmd_input_start'):
            return
        if getattr(self, '_cmd_cursor_fixing', False):
            return
        cursor = self.command_console.textCursor()
        doc = self.command_console.document()
        # Актуализируем позицию начала ввода при изменении документа
        if self._cmd_input_start > doc.characterCount():
            self._cmd_input_start = max(0, doc.characterCount() - 1)
        if cursor.position() < self._cmd_input_start:
            self._cmd_cursor_fixing = True
            try:
                cursor.setPosition(self._cmd_input_start)
                self.command_console.setTextCursor(cursor)
            finally:
                self._cmd_cursor_fixing = False

    def eventFilter(self, obj, event):
        """Обработка ввода в консоль команд (command_console) для вкладки стратегий."""
        from PyQt6.QtCore import QEvent, QProcess
        from PyQt6.QtGui import QTextCursor

        if getattr(self, 'tab_kind', '') == 'bat' and hasattr(self, 'command_console') and obj is self.command_console:
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                mods = event.modifiers()
                cursor = self.command_console.textCursor()

                # Обновляем стартовую позицию, если документ пуст
                if self._cmd_input_start > cursor.document().characterCount():
                    self._cmd_input_start = cursor.document().characterCount()

                # Запрет редактирования истории (выше текущей команды)
                if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Left, Qt.Key.Key_Home):
                    if cursor.position() <= self._cmd_input_start:
                        return True

                if key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
                    # Берём текст текущей команды от _cmd_input_start до конца без использования QTextCursor,
                    # чтобы избежать ошибок setPosition при пустом/коротком документе
                    doc = self.command_console.document()
                    full_text = doc.toPlainText()
                    if self._cmd_input_start >= len(full_text):
                        cmd = ""
                    else:
                        cmd = full_text[self._cmd_input_start:].replace('\u2029', '\n').strip()

                    # Добавляем перевод строки в консоль (новая строка для следующей команды),
                    # даже если команда пустая — как в обычном cmd
                    self.command_console.appendPlainText("")
                    self.command_console.moveCursor(QTextCursor.MoveOperation.End)
                    self._cmd_input_start = self.command_console.document().characterCount() - 1

                    # Отправляем команду во встроенный cmd.exe.
                    # Даже если команда пустая, отправляем пустую строку, чтобы cmd вывел новый промпт.
                    self.run_command_from_input(cmd, allow_empty=True)
                    return True

                # Остальной ввод — обычное поведение, но не даём уйти левее _cmd_input_start
                if cursor.position() < self._cmd_input_start:
                    cursor.setPosition(self._cmd_input_start)
                    self.command_console.setTextCursor(cursor)
            return False

        return super().eventFilter(obj, event)

    def run_command_from_input(self, cmd_text: str, allow_empty: bool = False):
        """Отправляет команду во встроенный cmd.exe (для вкладки стратегий)."""
        if getattr(self, 'tab_kind', '') != 'bat':
            return
        original = cmd_text
        cmd_text = cmd_text.strip()
        if not allow_empty and not cmd_text:
            return
        try:
            # Если процесс cmd по какой-то причине не запущен — перезапускаем
            from PyQt6.QtCore import QProcess
            if not hasattr(self, 'cmd_process') or self.cmd_process.state() != QProcess.ProcessState.Running:
                self.cmd_process.start()

            if hasattr(self, 'cmd_process') and self.cmd_process.state() == QProcess.ProcessState.Running:
                # Если allow_empty=True и после strip команда пуста, всё равно отправляем просто перевод строки,
                # чтобы cmd вывел новый промпт.
                to_send = (cmd_text if cmd_text else '') + '\r\n'
                data = to_send.encode(self._cmd_encoding, errors='ignore')
                self.cmd_process.write(data)
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))

    def _on_cmd_output(self):
        """Читает вывод из встроенного cmd.exe и добавляет его в консоль."""
        if getattr(self, 'tab_kind', '') != 'bat' or not hasattr(self, 'command_console'):
            return
        try:
            if not hasattr(self, 'cmd_process'):
                return
            data = bytes(self.cmd_process.readAllStandardOutput())
            if not data:
                data = bytes(self.cmd_process.readAllStandardError())
            if not data:
                return
            text = data.decode(getattr(self, '_cmd_encoding', 'utf-8'), errors='ignore')
            if not text:
                return
            self.command_console.insertPlainText(text)
            self.command_console.moveCursor(self.command_console.textCursor().MoveOperation.End)
            # Новая позиция ввода всегда в конце
            self._cmd_input_start = self.command_console.document().characterCount() - 1
        except Exception:
            pass
    
    def open_folder(self):
        try:
            if os.path.exists(self.folder):
                subprocess.Popen(['explorer', self.folder])
            else:
                QMessageBox.warning(self, tr('msg_error', self.language),
                    tr('msg_winws_not_found', self.language) if self.is_lists_tab else tr('etcdrivers_folder_not_found', self.language))
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))
    
    def add_file_to_list(self, filename):
        if filename and self.file_list.findItems(filename, Qt.MatchFlag.MatchExactly):
            return
        self.file_names.append(filename)
        self.file_list.addItem(filename)
        self.file_list.setCurrentRow(self.file_list.count() - 1)


class UnifiedEditorWindow(StandardDialog):
    """Окно с двумя вкладками: Редактор списков и Редактор drivers\\etc."""
    
    def __init__(self, parent=None, initial_tab=0):
        self.language = 'ru'
        if parent:
            if hasattr(parent, 'settings'):
                self.language = parent.settings.get('language', 'ru')
            elif hasattr(parent, 'config'):
                try:
                    self.language = parent.config.load_settings().get('language', 'ru')
                except Exception:
                    pass
        
        winws_folder = get_winws_path()
        lists_folder = os.path.join(winws_folder, 'lists')
        etc_folder = get_etcdrivers_folder()
        bat_files = get_bat_files(winws_folder)
        
        from src.core.embedded_assets import get_app_icon
        super().__init__(
            parent=parent,
            title=tr('editor_window_title', self.language),
            width=850,
            height=550,
            icon=get_app_icon(),
            theme="dark"
        )
        
        pywinstyles.change_header_color(self, color="#181818")
        self.setWindowModality(Qt.WindowModality.NonModal)
        # Явно включаем кнопки свернуть/развернуть, чтобы они не пропадали
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        
        self._find_replace_dialog = None
        self._find_in_files_dialog = None
        
        content = self.getContentLayout()
        
        self.status_bar = self.addStatusBar()
        self.status_bar.setStyleSheet("QStatusBar { color: #969696; font-size: 11px; }")
        
        # Хлебные крошки слева (вместо сообщения "Файл сохранен")
        self._breadcrumb_widget = BreadcrumbWidget()
        self._breadcrumb_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._breadcrumb_widget.setMinimumWidth(200)
        self._breadcrumb_widget.partClicked.connect(self._on_breadcrumb_part_clicked)
        self.status_bar.addWidget(self._breadcrumb_widget, 1)
        
        # Добавляем виджеты в статус-бар справа: Строка столбец Spaces UTF-8 CRLF
        # Сначала создаём виджет позиции (будет обновляться в update_editor_status)
        self._position_widget = QLabel("")
        self._position_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self._position_widget.setStyleSheet("""
            QLabel { color: #969696; }
            QLabel:hover { color: #d0d0d0; text-decoration: underline; }
        """)
        self._position_widget.mousePressEvent = lambda e: self.go_to_line()  # type: ignore[method-assign]
        self.status_bar.addPermanentWidget(self._position_widget)
        
        # Затем добавляем LabelMenuWidget для настроек
        self.tab_size_combo = LabelMenuWidget()
        self.tab_size_combo.addItems(['Spaces: 2', 'Spaces: 4', 'Spaces: 8', 'Tabs'])
        self.tab_size_combo.setCurrentText('Spaces: 4')
        self.tab_size_combo.currentTextChanged.connect(self._on_tab_size_changed)
        self.status_bar.addPermanentWidget(self.tab_size_combo)
        
        self.encoding_combo = LabelMenuWidget()
        self.encoding_combo.addItems(['UTF-8', 'UTF-8 BOM', 'Windows-1251'])
        self.encoding_combo.setCurrentText('UTF-8')
        self.encoding_combo.currentTextChanged.connect(self._on_encoding_changed)
        self.status_bar.addPermanentWidget(self.encoding_combo)
        
        self.line_ending_combo = LabelMenuWidget()
        self.line_ending_combo.addItems(['CRLF', 'LF', 'CR'])
        self.line_ending_combo.setCurrentText('CRLF')
        self.line_ending_combo.currentTextChanged.connect(self._on_line_ending_changed)
        self.status_bar.addPermanentWidget(self.line_ending_combo)
        
        self.tabs = QTabWidget()
        self.tabs.setCursor(Qt.CursorShape.PointingHandCursor)
        # Левая граница только у первой вкладки ("Списки")
        tab_bar = self.tabs.tabBar()
        tab_bar.setStyleSheet("""
            QTabBar::tab:first {
                border-left: 1px solid #2b2b2b;
            }
        """)

        self.tab_lists = EditorTabContent(self, lists_folder, LIST_FILES, self.language, is_lists_tab=True, tab_kind='lists')
       
        self.tab_etc = EditorTabContent(self, etc_folder, ETC_FILES, self.language, is_lists_tab=False, tab_kind='etc')
        self.tab_bat = EditorTabContent(self, winws_folder, bat_files, self.language, is_lists_tab=False, tab_kind='bat')
        self.tabs.addTab(self.tab_lists, tr('editor_tab_lists', self.language))
        self.tabs.addTab(self.tab_etc, tr('editor_tab_etc', self.language))
        self.tabs.addTab(self.tab_bat, tr('editor_tab_bat', self.language))
        self.tabs.setCurrentIndex(min(max(0, initial_tab), 2))
        self.tabs.currentChanged.connect(self._on_tab_changed)
        content.addWidget(self.tabs)
        
        # Применяем настройки по умолчанию ко всем вкладкам
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab:
                self._sync_settings_to_tab(tab)
        
        # Подключаем обновление хлебных крошек и заголовка окна
        self.tabs.currentChanged.connect(self._update_breadcrumb)
        self.tabs.currentChanged.connect(self._update_window_title)
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if tab:
                tab.file_list.currentItemChanged.connect(lambda *a: self._update_breadcrumb())
                tab.file_list.currentItemChanged.connect(lambda *a: self._update_window_title())
                tab.editor.document().modificationChanged.connect(self._update_breadcrumb)
                tab.editor.document().modificationChanged.connect(self._update_window_title)
        
        self._update_breadcrumb()
        self._update_window_title()
        
        self.menu_bar = QMenuBar()
        
        # Файл
        file_menu = StyleMenu(self.menu_bar)
        file_menu.setTitle(tr('editor_menu_file', self.language))
        self.menu_bar.addMenu(file_menu)
        
        self.action_create_file = QAction(tr('editor_create_file', self.language), self)
        self.action_create_file.setShortcut(QKeySequence("Ctrl+N"))
        self.action_create_file.triggered.connect(self.create_new_file)
        file_menu.addAction(self.action_create_file)
        
        self.action_save = QAction(tr('editor_save', self.language), self)
        self.action_save.setShortcut(QKeySequence("Ctrl+S"))
        self.action_save.triggered.connect(self.save_current_file)
        file_menu.addAction(self.action_save)
        
        self.action_save_as = QAction(tr('editor_save_as', self.language), self)
        self.action_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.action_save_as.triggered.connect(self.save_as)
        file_menu.addAction(self.action_save_as)
        
        file_menu.addSeparator()
        
        open_folder_sub = StyleMenu(file_menu)
        open_folder_sub.setTitle(tr('editor_open_folder', self.language))
        self.action_open_folder_cmd = QAction(tr('editor_open_folder_cmd', self.language), self)
        self.action_open_folder_cmd.triggered.connect(lambda: self.open_folder_in_terminal('cmd'))
        open_folder_sub.addAction(self.action_open_folder_cmd)
        self.action_open_folder_ps = QAction(tr('editor_open_folder_ps', self.language), self)
        self.action_open_folder_ps.triggered.connect(lambda: self.open_folder_in_terminal('powershell'))
        open_folder_sub.addAction(self.action_open_folder_ps)
        file_menu.addMenu(open_folder_sub)
        
        open_file_sub = StyleMenu(file_menu)
        open_file_sub.setTitle(tr('editor_open_file_folder', self.language))
        self.action_open_file_cmd = QAction(tr('editor_open_folder_cmd', self.language), self)
        self.action_open_file_cmd.triggered.connect(lambda: self.open_file_folder_in_terminal('cmd'))
        open_file_sub.addAction(self.action_open_file_cmd)
        self.action_open_file_ps = QAction(tr('editor_open_folder_ps', self.language), self)
        self.action_open_file_ps.triggered.connect(lambda: self.open_file_folder_in_terminal('powershell'))
        open_file_sub.addAction(self.action_open_file_ps)
        file_menu.addMenu(open_file_sub)
        
        file_menu.addSeparator()
        
        self.action_close = QAction(tr('editor_close', self.language), self)
        self.action_close.setShortcut(QKeySequence("Ctrl+W"))
        self.action_close.triggered.connect(self.close)
        file_menu.addAction(self.action_close)
        
        # Правка
        edit_menu = StyleMenu(self.menu_bar)
        edit_menu.setTitle(tr('lists_editor_menu_edit', self.language))
        self.menu_bar.addMenu(edit_menu)
        
        self.action_undo = QAction(tr('editor_undo', self.language), self)
        self.action_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.action_undo.triggered.connect(self.undo_action)
        edit_menu.addAction(self.action_undo)
        
        self.action_redo = QAction(tr('editor_redo', self.language), self)
        self.action_redo.setShortcut(QKeySequence("Ctrl+Y"))
        self.action_redo.triggered.connect(self.redo_action)
        edit_menu.addAction(self.action_redo)
        
        edit_menu.addSeparator()
        
        self.action_cut = QAction(tr('editor_cut', self.language), self)
        self.action_cut.setShortcut(QKeySequence("Ctrl+X"))
        self.action_cut.triggered.connect(self.cut_action)
        edit_menu.addAction(self.action_cut)
        
        self.action_copy = QAction(tr('editor_copy', self.language), self)
        self.action_copy.setShortcut(QKeySequence("Ctrl+C"))
        self.action_copy.triggered.connect(self.copy_action)
        edit_menu.addAction(self.action_copy)
        
        self.action_paste = QAction(tr('editor_paste', self.language), self)
        self.action_paste.setShortcut(QKeySequence("Ctrl+V"))
        self.action_paste.triggered.connect(self.paste_action)
        edit_menu.addAction(self.action_paste)
        
        self.action_delete = QAction(tr('editor_delete', self.language), self)
        self.action_delete.setShortcut(QKeySequence("Delete"))
        self.action_delete.triggered.connect(self.delete_action)
        edit_menu.addAction(self.action_delete)
        
        edit_menu.addSeparator()
        
        self.action_find = QAction(tr('editor_find', self.language), self)
        self.action_find.setShortcut(QKeySequence("Ctrl+F"))
        self.action_find.triggered.connect(self.show_find_replace)
        edit_menu.addAction(self.action_find)
        
        self.action_find_next = QAction(tr('editor_find_next', self.language), self)
        self.action_find_next.setShortcut(QKeySequence("F3"))
        self.action_find_next.triggered.connect(lambda: self.show_find_replace(go_next=True))
        edit_menu.addAction(self.action_find_next)
        
        self.action_find_prev = QAction(tr('editor_find_prev', self.language), self)
        self.action_find_prev.setShortcut(QKeySequence("Shift+F3"))
        self.action_find_prev.triggered.connect(lambda: self.show_find_replace(go_prev=True))
        edit_menu.addAction(self.action_find_prev)
        
        self.action_replace = QAction(tr('editor_replace', self.language), self)
        self.action_replace.setShortcut(QKeySequence("Ctrl+H"))
        self.action_replace.triggered.connect(self.show_find_replace)
        edit_menu.addAction(self.action_replace)

        self.action_find_in_files = QAction(tr('find_in_files_title', self.language), self)
        self.action_find_in_files.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.action_find_in_files.triggered.connect(self.show_find_in_files)
        edit_menu.addAction(self.action_find_in_files)
        
        self.action_go_to_line = QAction(tr('editor_go_to', self.language), self)
        self.action_go_to_line.setShortcut(QKeySequence("Ctrl+G"))
        self.action_go_to_line.triggered.connect(self.go_to_line)
        edit_menu.addAction(self.action_go_to_line)

        edit_menu.addSeparator()

        self.action_comment = QAction(tr('editor_comment', self.language), self)
        self.action_comment.setShortcut(QKeySequence("Ctrl+/"))
        self.action_comment.triggered.connect(self.comment_action)
        edit_menu.addAction(self.action_comment)

        self.action_uncomment = QAction(tr('editor_uncomment', self.language), self)
        self.action_uncomment.setShortcut(QKeySequence("Ctrl+Shift+/"))
        self.action_uncomment.triggered.connect(self.uncomment_action)
        edit_menu.addAction(self.action_uncomment)
        
        # Selection menu
        selection_menu = StyleMenu(self.menu_bar)
        selection_menu.setTitle(tr('editor_menu_selection', self.language))
        self.menu_bar.addMenu(selection_menu)
        
        self.action_select_all = QAction(tr('editor_select_all', self.language), self)
        self.action_select_all.setShortcut(QKeySequence("Ctrl+A"))
        self.action_select_all.triggered.connect(self.select_all_action)
        selection_menu.addAction(self.action_select_all)
        
        self.action_expand_selection = QAction(tr('editor_expand_selection', self.language), self)
        self.action_expand_selection.setShortcut(QKeySequence("Shift+Alt+Right"))
        self.action_expand_selection.triggered.connect(self.expand_selection_action)
        selection_menu.addAction(self.action_expand_selection)
        
        self.action_shrink_selection = QAction(tr('editor_shrink_selection', self.language), self)
        self.action_shrink_selection.setShortcut(QKeySequence("Shift+Alt+Left"))
        self.action_shrink_selection.triggered.connect(self.shrink_selection_action)
        selection_menu.addAction(self.action_shrink_selection)
        
        selection_menu.addSeparator()
        
        self.action_copy_line_up = QAction(tr('editor_copy_line_up', self.language), self)
        self.action_copy_line_up.setShortcut(QKeySequence("Shift+Alt+Up"))
        self.action_copy_line_up.triggered.connect(self.copy_line_up_action)
        selection_menu.addAction(self.action_copy_line_up)
        
        self.action_copy_line_down = QAction(tr('editor_copy_line_down', self.language), self)
        self.action_copy_line_down.setShortcut(QKeySequence("Shift+Alt+Down"))
        self.action_copy_line_down.triggered.connect(self.copy_line_down_action)
        selection_menu.addAction(self.action_copy_line_down)
        
        self.action_move_line_up = QAction(tr('editor_move_line_up', self.language), self)
        self.action_move_line_up.setShortcut(QKeySequence("Alt+Up"))
        self.action_move_line_up.triggered.connect(self.move_line_up_action)
        selection_menu.addAction(self.action_move_line_up)
        
        self.action_move_line_down = QAction(tr('editor_move_line_down', self.language), self)
        self.action_move_line_down.setShortcut(QKeySequence("Alt+Down"))
        self.action_move_line_down.triggered.connect(self.move_line_down_action)
        selection_menu.addAction(self.action_move_line_down)
        
        self.action_duplicate_selection = QAction(tr('editor_duplicate_selection', self.language), self)
        self.action_duplicate_selection.setShortcut(QKeySequence("Shift+Alt+D"))
        self.action_duplicate_selection.triggered.connect(self.duplicate_selection_action)
        selection_menu.addAction(self.action_duplicate_selection)
        
        selection_menu.addSeparator()
        
        self.action_add_next_occurrence = QAction(tr('editor_add_next_occurrence', self.language), self)
        self.action_add_next_occurrence.setShortcut(QKeySequence("Ctrl+D"))
        self.action_add_next_occurrence.triggered.connect(self.add_next_occurrence_action)
        selection_menu.addAction(self.action_add_next_occurrence)
        
        self.action_add_prev_occurrence = QAction(tr('editor_add_prev_occurrence', self.language), self)
        self.action_add_prev_occurrence.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.action_add_prev_occurrence.triggered.connect(self.add_prev_occurrence_action)
        selection_menu.addAction(self.action_add_prev_occurrence)
        
        self.action_select_all_occurrences = QAction(tr('editor_select_all_occurrences', self.language), self)
        self.action_select_all_occurrences.setShortcut(QKeySequence("Ctrl+Shift+L"))
        self.action_select_all_occurrences.triggered.connect(self.select_all_occurrences_action)
        selection_menu.addAction(self.action_select_all_occurrences)
        
        # View menu
        view_menu = StyleMenu(self.menu_bar)
        view_menu.setTitle(tr('menu_view', self.language))
        self.menu_bar.addMenu(view_menu)
        
        self.action_fullscreen = QAction(tr('editor_fullscreen', self.language), self)
        self.action_fullscreen.setShortcut(QKeySequence("F11"))
        self.action_fullscreen.setCheckable(True)
        self.action_fullscreen.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(self.action_fullscreen)
        
        zoom_sub = StyleMenu(view_menu)
        zoom_sub.setTitle(tr('editor_zoom_menu', self.language))
        self.action_zoom_in = QAction(tr('editor_zoom_in', self.language), self)
        self.action_zoom_in.setShortcut(QKeySequence("Ctrl+="))
        self.action_zoom_in.triggered.connect(self.zoom_in_action)
        zoom_sub.addAction(self.action_zoom_in)
        self.action_zoom_out = QAction(tr('editor_zoom_out', self.language), self)
        self.action_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self.action_zoom_out.triggered.connect(self.zoom_out_action)
        zoom_sub.addAction(self.action_zoom_out)
        self.action_zoom_reset = QAction(tr('editor_zoom_reset_default', self.language), self)
        self.action_zoom_reset.setShortcut(QKeySequence("Ctrl+0"))
        self.action_zoom_reset.triggered.connect(self.zoom_reset_action)
        zoom_sub.addAction(self.action_zoom_reset)
        view_menu.addMenu(zoom_sub)
        
        self.action_word_wrap = QAction(tr('editor_word_wrap', self.language), self)
        self.action_word_wrap.setCheckable(True)
        self.action_word_wrap.setChecked(False)
        # Горячая клавиша для переноса по словам (оставляем Ctrl+Z для Undo)
        self.action_word_wrap.setShortcut(QKeySequence("Alt+Z"))
        self.action_word_wrap.triggered.connect(self.toggle_word_wrap)
        view_menu.addAction(self.action_word_wrap)
        
        # Tools menu
        tools_menu = StyleMenu(self.menu_bar)
        tools_menu.setTitle(tr('menu_tools', self.language))
        self.menu_bar.addMenu(tools_menu)
        
        self.action_country_blocklist = QAction(tr('country_blocklist_btn', self.language), self)
        self.action_country_blocklist.triggered.connect(self.show_country_blocklist)
        tools_menu.addAction(self.action_country_blocklist)
        
        self.action_format_document = QAction(tr('editor_format_document', self.language), self)
        self.action_format_document.setShortcut(QKeySequence("Shift+Alt+F"))
        self.action_format_document.triggered.connect(self.format_document_action)
        tools_menu.addAction(self.action_format_document)
        
        tools_menu.addSeparator()
        
        convert_sub = StyleMenu(tools_menu)
        convert_sub.setTitle(tr('editor_convert_menu', self.language))
        self.action_convert_line_endings = QAction(tr('editor_convert_line_endings_short', self.language), self)
        self.action_convert_line_endings.triggered.connect(self.convert_line_endings_action)
        convert_sub.addAction(self.action_convert_line_endings)
        self.action_convert_encoding = QAction(tr('editor_convert_encoding_short', self.language), self)
        self.action_convert_encoding.triggered.connect(self.convert_encoding_action)
        convert_sub.addAction(self.action_convert_encoding)
        tools_menu.addMenu(convert_sub)
        
        self.title_bar.addLeftWidget(self.menu_bar)
        
        # Обновляем состояние действий при изменении курсора / смене вкладки
        self.tabs.currentChanged.connect(self._update_actions_state)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self._update_actions_state()
        
        self._refresh_status_from_current_tab()
        self._sync_word_wrap_action_state()
    
    def _on_tab_changed(self, index):
        self._refresh_status_from_current_tab()
        self._update_breadcrumb()
        # При смене вкладки синхронизируем настройки
        tab = self.current_tab_content()
        if tab:
            self._sync_settings_to_tab(tab)
        self._sync_word_wrap_action_state()
        self._update_window_title()
    
    def _update_breadcrumb(self):
        """Обновляет хлебные крошки: Folder [chevron] Folder [chevron] File.txt [ (изменен) ]"""
        tab = self.current_tab_content()
        if not tab or not hasattr(self, '_breadcrumb_widget'):
            return
        path = tab.get_current_file_path()
        if not path:
            self._breadcrumb_widget.set_path([])
            return
        # Разбиваем путь на части (используем pathlib для корректной обработки диска на Windows)
        p = Path(path)
        parts = list(p.parts)
        if not parts:
            self._breadcrumb_widget.set_path([])
            return
        # Формируем подписи: для первого элемента убираем конечный слэш, чтобы было "C:" вместо "C:\"
        labels = []
        for i, part in enumerate(parts):
            if i == 0 and part.endswith(os.sep):
                labels.append(part.rstrip(os.sep))
            else:
                labels.append(part)
        # Текст о модификации
        modified_text = ""
        if tab.editor.document().isModified():
            modified_text = tr('editor_file_modified', self.language)
        self._breadcrumb_widget.set_path(labels, modified_text)
    
    def _sync_word_wrap_action_state(self):
        """Делает пункт 'Перенос текста' согласованным с режимом переноса в текущем редакторе."""
        tab = self.current_tab_content()
        if not tab:
            return
        editor = tab.get_current_editor()
        self.action_word_wrap.setChecked(
            editor.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
        )

    def _on_breadcrumb_part_clicked(self, index: int):
        """Обработчик клика по части хлебных крошек.

        Клик по папке — открыть папку в проводнике.
        Клик по файлу — открыть файл в системе (os.startfile).
        """
        tab = self.current_tab_content()
        if not tab:
            return
        path = tab.get_current_file_path()
        if not path:
            return
        try:
            p = Path(path)
            parts = list(p.parts)
            if index < 0 or index >= len(parts):
                return
            target = Path(*parts[: index + 1])
            if target.is_dir():
                try:
                    subprocess.Popen(['explorer', str(target)])
                except Exception as e:
                    QMessageBox.warning(self, tr('msg_error', self.language), str(e))
            elif target.is_file():
                try:
                    os.startfile(str(target))
                except Exception as e:
                    QMessageBox.warning(self, tr('msg_error', self.language), str(e))
        except Exception:
            # В случае неожиданных проблем просто ничего не делаем
            return
    
    def _refresh_status_from_current_tab(self):
        tab = self.current_tab_content()
        if tab and hasattr(tab, '_last_status'):
            self.update_editor_status(tab._last_status, tab._last_line, tab._last_col)
        # Синхронизируем настройки с текущей вкладкой
        if tab:
            self._sync_settings_to_tab(tab)
        self._update_window_title()

    def _update_window_title(self):
        """Обновляет заголовок окна: 'Редактор — путь к файлу •' (если изменен)."""
        base = tr('editor_window_title', self.language)
        tab = self.current_tab_content()
        if not tab:
            self.setWindowTitle(base)
            return
        path = tab.get_current_file_path()
        if not path:
            self.setWindowTitle(base)
            return
        display_path = os.path.normpath(path)
        title = f"{base} — {display_path}"
        if tab.editor.document().isModified():
            title += " •"
        self.setWindowTitle(title)
    
    def _sync_settings_to_tab(self, tab):
        """Синхронизирует настройки из комбобоксов с текущей вкладкой."""
        tab_size_text = self.tab_size_combo.currentText()
        if tab_size_text == 'Tabs':
            tab.set_tab_size(8)  # Для табов используем стандартный размер
        else:
            size = int(tab_size_text.split(':')[1].strip())
            tab.set_tab_size(size)
        tab.set_encoding(self.encoding_combo.currentText())
        tab.set_line_ending(self.line_ending_combo.currentText())
    
    def _on_tab_size_changed(self, text):
        """Обработчик изменения размера табуляции."""
        tab = self.current_tab_content()
        if tab:
            if text == 'Tabs':
                tab.set_tab_size(8)
            else:
                size = int(text.split(':')[1].strip())
                tab.set_tab_size(size)
    
    def _on_encoding_changed(self, text):
        """Обработчик изменения кодировки."""
        tab = self.current_tab_content()
        if tab:
            tab.set_encoding(text)
    
    def _on_line_ending_changed(self, text):
        """Обработчик изменения окончаний строк."""
        tab = self.current_tab_content()
        if tab:
            tab.set_line_ending(text)
    
    def update_editor_status(self, message, line=1, col=1):
        if self.status_bar is None:
            return
        # Хлебные крошки уже в статус-баре — не показываем сообщение "Файл сохранен"
        self.status_bar.clearMessage()
        pos_text = tr('editor_line_column', self.language).format(line, col)
        if hasattr(self, '_position_widget'):
            self._position_widget.setText(pos_text)

    def _show_goto_line_column_dialog(self):
        """Совместимость: старый хелпер, теперь вызывает go_to_line()."""
        self.go_to_line()
    
    def current_tab_content(self):
        return self.tabs.currentWidget()
    
    def _update_actions_state(self):
        """Обновляет состояние действий меню в зависимости от текущего редактора."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        has_selection = cursor.hasSelection()
        
        self.action_undo.setEnabled(editor.document().isUndoAvailable())
        self.action_redo.setEnabled(editor.document().isRedoAvailable())
        self.action_cut.setEnabled(has_selection)
        self.action_copy.setEnabled(has_selection)
        self.action_delete.setEnabled(has_selection or bool(editor.toPlainText()))
        self.action_save.setEnabled(editor.document().isModified())

        # Раскомментировать — enabled только если есть хотя бы одна закомментированная строка
        # Закомментировать — enabled только если есть хотя бы одна не закомментированная строка
        can_uncomment = False
        can_comment = False
        doc = editor.document()
        if not cursor.hasSelection():
            start_block = cursor.block()
            end_block = start_block
        else:
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            if end > start and end > 0:
                end -= 1
            start_block = doc.findBlock(start)
            end_block = doc.findBlock(end)
        block = start_block
        while block.isValid() and block.blockNumber() <= end_block.blockNumber():
            text = block.text()
            stripped = text.lstrip()
            if tab.tab_kind == 'bat':
                if stripped.startswith('rem ') or stripped.rstrip() == 'rem' or stripped.startswith('::'):
                    can_uncomment = True
                elif stripped:  # не пустая строка
                    can_comment = True
            else:
                if stripped.startswith('#'):
                    can_uncomment = True
                elif stripped:  # не пустая строка
                    can_comment = True
            block = block.next()
        if hasattr(self, 'action_comment'):
            self.action_comment.setEnabled(can_comment)
        if hasattr(self, 'action_uncomment'):
            self.action_uncomment.setEnabled(can_uncomment)
    
    def save_current_file(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.save_current_file()
        self._update_actions_state()

    def save_as(self):
        """Сохранить текущий файл как... (в пределах текущей папки вкладки)."""
        tab = self.current_tab_content()
        if tab is None:
            return

        current_path = tab.get_current_file_path()
        current_name = os.path.basename(current_path) if current_path else ''
        initial_dir = tab.folder if hasattr(tab, 'folder') else os.getcwd()
        initial_path = os.path.join(initial_dir, current_name) if current_name else initial_dir

        fname, _ = QFileDialog.getSaveFileName(
            self,
            tr('editor_save_as', self.language),
            initial_path,
            "All Files (*.*)"
        )
        if not fname:
            return

        fname = os.path.normpath(fname)
        target_dir = os.path.dirname(fname)

        # Ограничиваемся текущей папкой вкладки, чтобы модель EditorTabContent оставалась согласованной
        if hasattr(tab, 'folder') and os.path.normcase(target_dir) != os.path.normcase(tab.folder):
            return

        try:
            content = tab.editor.toPlainText()
            # Применяем выбранные окончания строк
            if tab.line_ending == 'CRLF':
                content = content.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')
            elif tab.line_ending == 'LF':
                content = content.replace('\r\n', '\n').replace('\r', '\n')
            elif tab.line_ending == 'CR':
                content = content.replace('\r\n', '\n').replace('\n', '\r')

            if os.path.exists(fname):
                try:
                    tab.file_watcher.removePath(fname)
                except Exception:
                    pass

            if getattr(tab, 'is_lists_tab', False):
                os.makedirs(tab.folder, exist_ok=True)

            encoding_map = {'UTF-8': 'utf-8', 'UTF-8 BOM': 'utf-8-sig', 'Windows-1251': 'windows-1251'}
            encoding = encoding_map.get(getattr(tab, 'encoding', 'UTF-8'), 'utf-8')
            with open(fname, 'w', encoding=encoding, newline='') as f:
                if getattr(tab, 'encoding', 'UTF-8') == 'UTF-8 BOM':
                    f.write('\ufeff')
                f.write(content)

            if os.path.exists(fname):
                try:
                    tab.file_watcher.addPath(fname)
                except Exception:
                    pass

            tab.editor.document().setModified(False)
            tab.save_timer.stop()
            tab._last_status = tr('targets_saved', self.language)
            tab._push_status()
            tab._on_editor_cursor_changed()

            new_name = os.path.basename(fname)
            # Обновляем текущий файл и список файлов
            from PyQt6.QtCore import Qt as _QtAlias  # локальный импорт, чтобы использовать MatchExactly
            existing_items = tab.file_list.findItems(new_name, _QtAlias.MatchFlag.MatchExactly)
            if not existing_items:
                tab.add_file_to_list(new_name)
            else:
                tab._current_file = new_name
                for i in range(tab.file_list.count()):
                    if tab.file_list.item(i).text() == new_name:
                        tab.file_list.setCurrentRow(i)
                        break

            self._update_actions_state()
            self._update_breadcrumb()
            self._update_window_title()
        except Exception as e:
            QMessageBox.warning(
                self,
                tr('test_error_title', self.language),
                f"{tr('targets_error_saving', self.language)}: {str(e)}"
            )
    
    def reload_current_file(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        if tab.editor.document().isModified():
            reply = QMessageBox.question(
                self, tr('test_error_title', self.language),
                tr('targets_unsaved_changes', self.language),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        tab.load_current_file()
        self._update_actions_state()
    
    def undo_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().undo()
        self._update_actions_state()
    
    def redo_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().redo()
        self._update_actions_state()
    
    def cut_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().cut()
        self._update_actions_state()
    
    def copy_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().copy()
    
    def paste_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().paste()
        self._update_actions_state()
    
    def select_all_action(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.get_current_editor().selectAll()
        self._update_actions_state()
    
    def go_to_line(self):
        """Переход к строке/столбцу (диалог). Поддерживает '234' и '234,11'."""
        from PyQt6.QtWidgets import QInputDialog
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        current_line, current_col = editor.get_cursor_position()

        hint = (
            f"{tr('editor_go_to_line', self.language)} ({current_line},{current_col})"
        )
        text, ok = QInputDialog.getText(
            self,
            tr('editor_go_to', self.language),
            hint + ":",
            QLineEdit.EchoMode.Normal,
            f"{current_line},{current_col}"
        )
        if not ok:
            return
        raw = (text or "").strip()
        if not raw:
            return

        import re
        nums = re.findall(r"\d+", raw)
        if not nums:
            return
        try:
            line = int(nums[0])
        except Exception:
            return
        col = 1
        if len(nums) >= 2:
            try:
                col = int(nums[1])
            except Exception:
                col = 1

        if line < 1:
            line = 1
        if col < 1:
            col = 1

        doc = editor.document()
        block = doc.findBlockByNumber(line - 1)
        if not block.isValid():
            cursor = editor.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            editor.setTextCursor(cursor)
            editor.setFocus()
            return

        line_text = block.text()
        max_col = max(1, len(line_text) + 1)
        if col > max_col:
            col = max_col
        pos = block.position() + (col - 1)

        cursor = editor.textCursor()
        cursor.setPosition(pos)
        editor.setTextCursor(cursor)
        editor.setFocus()

    def create_new_file(self):
        """Создать новый файл в текущей открытой папке вкладки."""
        from PyQt6.QtWidgets import QInputDialog
        tab = self.current_tab_content()
        if tab is None or not hasattr(tab, 'folder'):
            return

        if getattr(tab, 'tab_kind', '') == 'lists':
            default_name = 'new-list.txt'
        elif getattr(tab, 'tab_kind', '') == 'etc':
            default_name = 'new-file.txt'
        elif getattr(tab, 'tab_kind', '') == 'bat':
            default_name = 'new.bat'
        else:
            default_name = 'new.txt'

        name, ok = QInputDialog.getText(
            self,
            tr('editor_create_file', self.language),
            tr('editor_create_file', self.language) + ':',
            text=default_name
        )
        if not ok:
            return
        name = os.path.basename(name.strip())
        if not name:
            return

        # Если файл уже есть в списке — просто переключаемся на него
        from PyQt6.QtCore import Qt as _QtAlias  # локальный импорт, чтобы использовать MatchExactly
        existing = tab.file_list.findItems(name, _QtAlias.MatchFlag.MatchExactly)
        if existing:
            for i in range(tab.file_list.count()):
                if tab.file_list.item(i).text() == name:
                    tab.file_list.setCurrentRow(i)
                    break
            return

        try:
            os.makedirs(tab.folder, exist_ok=True)
            path = os.path.join(tab.folder, name)
            if not os.path.exists(path):
                # Создаём пустой файл; содержимое заполнится при первом сохранении
                with open(path, 'w', encoding='utf-8') as f:
                    f.write('')
        except Exception:
            # Если не удалось создать файл на диске, всё равно добавим его в список,
            # чтобы пользователь мог работать с ним как с новым.
            pass

        tab.add_file_to_list(name)
        self._update_actions_state()
    
    def expand_selection_action(self):
        """Расширяет выделение до следующего уровня: слово -> строка -> блок -> документ."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        else:
            doc = editor.document()
            sel_start = min(cursor.selectionStart(), cursor.selectionEnd())
            block = doc.findBlock(sel_start)
            block_start = block.position()
            block_end = block.position() + len(block.text())
            line_start = block_start
            line_end = block_end
            cur_start = min(cursor.selectionStart(), cursor.selectionEnd())
            cur_end = max(cursor.selectionStart(), cursor.selectionEnd())
            doc_len = doc.characterCount()
            if cur_start >= line_start and cur_end <= line_end and (cur_end - cur_start) < (line_end - line_start):
                cursor.movePosition(QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
            elif cur_start >= block_start and cur_end <= block_end:
                cursor.setPosition(block_start)
                cursor.setPosition(block_end, QTextCursor.MoveMode.KeepAnchor)
            elif cur_end - cur_start < doc_len:
                cursor.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.KeepAnchor)
                cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def shrink_selection_action(self):
        """Сужает выделение: документ -> блок -> строка -> слово."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        if not cursor.hasSelection():
            return
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        if start > end:
            start, end = end, start
        doc = editor.document()
        block_start = doc.findBlock(start)
        block_end = doc.findBlock(end)
        if block_start.blockNumber() == block_end.blockNumber():
            line_start = block_start.position()
            line_end = block_start.position() + len(block_start.text())
            if start == line_start and end == line_end:
                cursor.setPosition(start)
                cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            else:
                cursor.setPosition(start)
                cursor.setPosition(line_end, QTextCursor.MoveMode.KeepAnchor)
        else:
            cursor.setPosition(start)
            cursor.setPosition(block_start.position() + len(block_start.text()), QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def copy_line_up_action(self):
        """Копирует текущую строку вверх."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        text = cursor.selectedText().replace('\u2029', '\n')
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText(text + '\n')
        cursor.movePosition(QTextCursor.MoveOperation.Up)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def copy_line_down_action(self):
        """Копирует текущую строку вниз."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        text = cursor.selectedText().replace('\u2029', '\n')
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText('\n' + text)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def move_line_up_action(self):
        """Перемещает текущую строку вверх."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        block = cursor.block()
        if block.blockNumber() == 0:
            return
        line_text = block.text()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.movePosition(QTextCursor.MoveOperation.Up)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText(line_text + '\n')
        cursor.movePosition(QTextCursor.MoveOperation.Up)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def move_line_down_action(self):
        """Перемещает текущую строку вниз."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        block = cursor.block()
        if block.blockNumber() >= editor.blockCount() - 1:
            return
        line_text = block.text()
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.movePosition(QTextCursor.MoveOperation.Down)
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.insertText(line_text + '\n')
        cursor.movePosition(QTextCursor.MoveOperation.Up)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def duplicate_selection_action(self):
        """Дублирует выделение или текущую строку."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        if cursor.hasSelection():
            text = cursor.selectedText().replace('\u2029', '\n')
            end_pos = cursor.selectionEnd()
            cursor.setPosition(end_pos)
            cursor.insertText(text)
            cursor.setPosition(end_pos)
            cursor.setPosition(end_pos + len(text), QTextCursor.MoveMode.KeepAnchor)
        else:
            block = cursor.block()
            text = block.text() + '\n'
            cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
            cursor.insertText('\n' + block.text())
            cursor.movePosition(QTextCursor.MoveOperation.Down)
            cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def add_next_occurrence_action(self):
        """Добавляет следующее вхождение выделенного текста к выделению."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        search_text = cursor.selectedText().replace('\u2029', '\n') if cursor.hasSelection() else None
        if not search_text:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            search_text = cursor.selectedText().replace('\u2029', '\n')
        if not search_text:
            return
        doc = editor.document()
        start_from = cursor.selectionEnd()
        found = doc.find(search_text, start_from, QTextDocument.FindFlag.FindCaseSensitively)
        if found.isNull():
            found = doc.find(search_text, 0, QTextDocument.FindFlag.FindCaseSensitively)
        if not found.isNull():
            cursor.setPosition(found.selectionStart())
            cursor.setPosition(found.selectionEnd(), QTextCursor.MoveMode.KeepAnchor)
            editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def add_prev_occurrence_action(self):
        """Добавляет предыдущее вхождение выделенного текста к выделению."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        search_text = cursor.selectedText().replace('\u2029', '\n') if cursor.hasSelection() else None
        if not search_text:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            search_text = cursor.selectedText().replace('\u2029', '\n')
        if not search_text:
            return
        doc = editor.document()
        start_from = cursor.selectionStart() - 1
        flags = QTextDocument.FindFlag.FindCaseSensitively | QTextDocument.FindFlag.FindBackward
        found = doc.find(search_text, start_from, flags)
        if found.isNull():
            found = doc.find(search_text, doc.characterCount(), flags)
        if not found.isNull():
            cursor.setPosition(found.selectionStart())
            cursor.setPosition(found.selectionEnd(), QTextCursor.MoveMode.KeepAnchor)
            editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def select_all_occurrences_action(self):
        """Выделяет все вхождения выделенного текста."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        search_text = cursor.selectedText().replace('\u2029', '\n') if cursor.hasSelection() else None
        if not search_text:
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            search_text = cursor.selectedText().replace('\u2029', '\n')
        if not search_text:
            return
        doc = editor.document()
        pos = 0
        first_start = -1
        last_end = -1
        found_cursor = doc.find(search_text, pos, QTextDocument.FindFlag.FindCaseSensitively)
        while not found_cursor.isNull():
            if first_start < 0:
                first_start = found_cursor.selectionStart()
            last_end = found_cursor.selectionEnd()
            pos = found_cursor.selectionEnd()
            found_cursor = doc.find(search_text, pos, QTextDocument.FindFlag.FindCaseSensitively)
        if first_start < 0 or last_end < 0:
            return
        cursor.setPosition(first_start)
        cursor.setPosition(last_end, QTextCursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def toggle_fullscreen(self):
        """Переключает полноэкранный режим."""
        if self.isFullScreen():
            self.showNormal()
            self.action_fullscreen.setChecked(False)
        else:
            self.showFullScreen()
            self.action_fullscreen.setChecked(True)
    
    def open_current_folder(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        tab.open_folder()

    def open_folder_in_terminal(self, shell: str):
        """Открыть текущую папку вкладки в cmd или PowerShell."""
        tab = self.current_tab_content()
        if tab is None or not hasattr(tab, 'folder'):
            return
        folder = tab.folder
        if not folder or not os.path.isdir(folder):
            return
        try:
            creation_flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
            if shell == 'cmd':
                subprocess.Popen(['cmd.exe'], cwd=folder, creationflags=creation_flags)
            else:
                subprocess.Popen(['powershell.exe'], cwd=folder, creationflags=creation_flags)
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))

    def open_file_folder_in_terminal(self, shell: str):
        """Запустить текущий файл в cmd или PowerShell."""
        tab = self.current_tab_content()
        if tab is None:
            return
        path = tab.get_current_file_path()
        if not path:
            return
        try:
            creation_flags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
            if shell == 'cmd':
                folder = os.path.dirname(path) or None
                # /K — запустить файл и оставить окно открытым
                subprocess.Popen(
                    ['cmd.exe', '/K', os.path.basename(path)],
                    cwd=folder,
                    creationflags=creation_flags
                )
            else:
                # Powershell: выполнить текущий файл и не закрывать окно
                subprocess.Popen(
                    ['powershell.exe', '-NoExit', '-File', path],
                    creationflags=creation_flags
                )
        except Exception as e:
            QMessageBox.warning(self, tr('msg_error', self.language), str(e))
    
    def show_find_replace(self, go_next=False, go_prev=False):
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        if self._find_replace_dialog is None:
            self._find_replace_dialog = FindReplaceDialog(
                parent=self,
                editor=editor,
                language=self.language
            )
        self._find_replace_dialog.set_editor(editor)
        self._find_replace_dialog.show()
        self._find_replace_dialog.raise_()
        self._find_replace_dialog.activateWindow()
        if go_next and self._find_replace_dialog.search_edit.text():
            self._find_replace_dialog._find_next()
        elif go_prev and self._find_replace_dialog.search_edit.text():
            self._find_replace_dialog._find_prev()

    def show_find_in_files(self):
        """Открыть диалог поиска по файлам."""
        if self._find_in_files_dialog is None:
            self._find_in_files_dialog = FindInFilesDialog(parent=self, language=self.language)
        self._find_in_files_dialog.show()
        self._find_in_files_dialog.raise_()
        self._find_in_files_dialog.activateWindow()
        self._find_in_files_dialog.search_edit.setFocus()

    def open_file_at_line(self, tab_index, filename, line_num):
        """Открыть файл в указанной вкладке и перейти к строке."""
        if tab_index < 0 or tab_index >= self.tabs.count():
            return
        self.tabs.setCurrentIndex(tab_index)
        tab = self.tabs.widget(tab_index)
        if tab is None:
            return
        for i in range(tab.file_list.count()):
            if tab.file_list.item(i).text() == filename:
                tab.file_list.blockSignals(True)
                tab.file_list.setCurrentRow(i)
                tab.file_list.blockSignals(False)
                tab._current_file = filename
                tab.load_current_file()
                editor = tab.get_current_editor()
                block = editor.document().findBlockByLineNumber(line_num - 1)
                cursor = editor.textCursor()
                cursor.setPosition(block.position())
                editor.setTextCursor(cursor)
                editor.setFocus()
                return
        # Файла нет в списке — добавляем
        tab.add_file_to_list(filename)
        tab.load_current_file()
        editor = tab.get_current_editor()
        block = editor.document().findBlockByLineNumber(line_num - 1)
        cursor = editor.textCursor()
        cursor.setPosition(block.position())
        editor.setTextCursor(cursor)
        editor.setFocus()
    
    def show_autocomplete(self):
        """Показать автодополнение (Ctrl+Space)."""
        tab = self.current_tab_content()
        if tab is None:
            return
        if hasattr(tab, '_autocomplete'):
            tab._autocomplete.show()
    
    def show_country_blocklist(self):
        tab = self.current_tab_content()
        if tab is None:
            return
        if not getattr(tab, 'is_lists_tab', False):
            self.tabs.setCurrentIndex(0)
            tab = self.tab_lists
        dlg = CountryBlocklistDialog(
            parent=self,
            lists_folder=tab.folder,
            language=self.language
        )
        dlg.exec()
        if getattr(dlg, 'created_filename', None):
            tab.add_file_to_list(dlg.created_filename)
    
    def delete_action(self):
        """Удаляет выделенный текст или символ под курсором."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        else:
            cursor.deleteChar()
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def duplicate_line_action(self):
        """Дублирует текущую строку."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        block = cursor.block()
        text = block.text()
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine)
        cursor.insertText('\n' + text)
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def comment_action(self):
        """Закомментировать выделенные строки."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        doc = editor.document()
        if not cursor.hasSelection():
            # Без выделения — только текущая строка (блок курсора)
            start_block = cursor.block()
            end_block = start_block
        else:
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            if end > start and end > 0:
                end -= 1
            start_block = doc.findBlock(start)
            end_block = doc.findBlock(end)
        # Собираем (block_number, leading) и обрабатываем снизу вверх, чтобы вставка не сдвигала позиции
        comment_ops = []
        block = start_block
        while block.isValid() and block.blockNumber() <= end_block.blockNumber():
            text = block.text()
            stripped = text.lstrip()
            if tab.tab_kind == 'bat':
                if stripped and not stripped.startswith('rem ') and stripped.rstrip() != 'rem' and not stripped.startswith('::'):
                    leading = len(text) - len(stripped)
                    comment_ops.append((block.blockNumber(), leading))
            else:
                if stripped and not stripped.startswith('#'):
                    leading = len(text) - len(stripped)
                    comment_ops.append((block.blockNumber(), leading))
            block = block.next()
        cursor.beginEditBlock()
        for blk_num, leading in reversed(comment_ops):
            block = doc.findBlockByNumber(blk_num)
            if not block.isValid():
                continue
            insert_pos = block.position() + leading
            cursor.setPosition(insert_pos)
            cursor.insertText('rem ' if tab.tab_kind == 'bat' else '#')
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def uncomment_action(self):
        """Раскомментировать выделенные строки."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        cursor = editor.textCursor()
        doc = editor.document()
        if not cursor.hasSelection():
            start_block = cursor.block()
            end_block = start_block
        else:
            start = min(cursor.selectionStart(), cursor.selectionEnd())
            end = max(cursor.selectionStart(), cursor.selectionEnd())
            if end > start and end > 0:
                end -= 1
            start_block = doc.findBlock(start)
            end_block = doc.findBlock(end)

        # Собираем строки для раскомментирования и обрабатываем снизу вверх, чтобы вставка не сдвигала позиции
        uncomment_ops = []
        block = start_block
        while block.isValid() and block.blockNumber() <= end_block.blockNumber():
            text = block.text()
            stripped = text.lstrip()
            leading = len(text) - len(stripped)
            if tab.tab_kind == 'bat':
                if stripped.startswith('rem '):
                    uncomment_ops.append((block.blockNumber(), leading, 4))
                elif stripped.rstrip() == 'rem':
                    uncomment_ops.append((block.blockNumber(), leading, 3))
                elif stripped.startswith('::'):
                    uncomment_ops.append((block.blockNumber(), leading, 2))
            else:
                if stripped.startswith('#'):
                    uncomment_ops.append((block.blockNumber(), leading, 1))
            block = block.next()

        cursor.beginEditBlock()
        for blk_num, leading, remove_len in reversed(uncomment_ops):
            block = doc.findBlockByNumber(blk_num)
            if not block.isValid():
                continue
            pos = block.position() + leading
            cursor.setPosition(pos)
            cursor.setPosition(pos + remove_len, QTextCursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        self._update_actions_state()
    
    def toggle_word_wrap(self, checked):
        """Переключает перенос строк."""
        tab = self.current_tab_content()
        if tab:
            tab.get_current_editor().setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth if checked else QPlainTextEdit.LineWrapMode.NoWrap)
    
    def zoom_in_action(self):
        """Увеличивает масштаб шрифта."""
        tab = self.current_tab_content()
        if tab:
            editor = tab.get_current_editor()
            font = editor.font()
            font.setPointSize(font.pointSize() + 1)
            editor.setFont(font)
            tab._autocomplete.on_editor_font_changed()

    def zoom_out_action(self):
        """Уменьшает масштаб шрифта."""
        tab = self.current_tab_content()
        if tab:
            editor = tab.get_current_editor()
            font = editor.font()
            if font.pointSize() > 6:
                font.setPointSize(font.pointSize() - 1)
                editor.setFont(font)
            tab._autocomplete.on_editor_font_changed()

    def zoom_reset_action(self):
        """Сбрасывает масштаб шрифта на значение по умолчанию."""
        tab = self.current_tab_content()
        if tab:
            editor = tab.get_current_editor()
            font = QFont("Consolas", 10)
            editor.setFont(font)
            tab._autocomplete.on_editor_font_changed()
    
    def format_document_action(self):
        """Форматирует документ (удаляет лишние пробелы в конце строк)."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        text = editor.toPlainText()
        lines = text.split('\n')
        formatted_lines = [line.rstrip() for line in lines]
        formatted_text = '\n'.join(formatted_lines)
        if formatted_text != text:
            cursor = editor.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.insertText(formatted_text)
            self._update_actions_state()
    
    def convert_line_endings_action(self):
        """Конвертирует окончания строк в выбранный формат."""
        tab = self.current_tab_content()
        if tab is None:
            return
        editor = tab.get_current_editor()
        text = editor.toPlainText()
        # Нормализуем к LF
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        # Конвертируем в выбранный формат
        if tab.line_ending == 'CRLF':
            text = text.replace('\n', '\r\n')
        elif tab.line_ending == 'CR':
            text = text.replace('\n', '\r')
        # Применяем изменения
        cursor = editor.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(text)
        self._update_actions_state()
    
    def convert_encoding_action(self):
        """Конвертирует кодировку файла."""
        tab = self.current_tab_content()
        if tab is None:
            return
        # Просто перезагружаем файл с новой кодировкой
        tab.load_current_file()
        self._update_actions_state()
    
    def show_about(self):
        """Показывает диалог 'О программе'."""
        from src.core.embedded_assets import get_app_icon
        QMessageBox.about(
            self,
            tr('editor_about', self.language),
            f"ZapretDeskop Editor\n\n{tr('editor_window_title', self.language)}"
        )

    def closeEvent(self, event):
        """При закрытии окна сбрасываем singleton, чтобы следующий запуск создавал новое окно
        с корректным состоянием (размер/кнопка разворота)."""
        super().closeEvent(event)
        # Сбрасываем кешированный экземпляр, если он указывает на это окно
        global get_unified_editor_window
        if 'get_unified_editor_window' in globals():
            if getattr(get_unified_editor_window, "_instance", None) is self:
                get_unified_editor_window._instance = None


def get_unified_editor_window(parent=None, initial_tab=0):
    """Возвращает единственный экземпляр окна (или создаёт новый)."""
    if not hasattr(get_unified_editor_window, '_instance') or get_unified_editor_window._instance is None:
        get_unified_editor_window._instance = UnifiedEditorWindow(parent, initial_tab=initial_tab)
    else:
        get_unified_editor_window._instance.tabs.setCurrentIndex(min(max(0, initial_tab), 2))
    return get_unified_editor_window._instance

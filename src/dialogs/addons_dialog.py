"""
Окно «Дополнения»: таблица ссылок на репозитории/релизы GitHub для скачивания списков и стратегий.
"""
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QAbstractItemView, QMessageBox,
    QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from src.core.translator import tr
from src.core.config_manager import ConfigManager
from src.core.embedded_assets import get_app_icon
from src.core.window_styles import apply_window_style
from src.widgets.custom_combobox import CustomComboBox
from src.widgets.custom_context_widgets import ContextLineEdit
from src.widgets.style_menu import StyleMenu

# Значение по умолчанию: один пункт Flowseal
DEFAULT_ADDONS = [
    {"name": "Flowseal (zapret-discord-youtube)", "url": "https://github.com/Flowseal/zapret-discord-youtube"},
]


def _get_addons_from_config():
    """Возвращает список дополнений из конфига или значение по умолчанию."""
    try:
        addons = ConfigManager().get_setting("addons")
        if addons and isinstance(addons, list):
            return [{"name": str(a.get("name", "")), "url": str(a.get("url", ""))} for a in addons]
    except Exception:
        pass
    return list(DEFAULT_ADDONS)


def _save_addons_to_config(addons):
    """Сохраняет список дополнений в конфиг."""
    try:
        ConfigManager().set_setting("addons", addons)
    except Exception:
        pass


class AddonsDialog(QDialog):
    """Диалог с таблицей дополнений (название, ссылка, Скачать, Открыть)."""

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings or {}
        self.lang = self.settings.get("language", "ru")
        self.config = ConfigManager()
        self._addons = _get_addons_from_config()

        apply_window_style(self)
        self.setWindowTitle(tr("addons_title", self.lang))
        self.setMinimumSize(640, 380)
        self.resize(720, 420)
        self.setWindowIcon(get_app_icon())
        self._apply_styles()
        self._create_ui()

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog { background-color: #181818; }
            QLabel { color: #cccccc; }
            QTableWidget::item { padding: 4px 8px; }
            QTableWidget::item:selected { background-color: #0078d4; color: #ffffff; }
            /* Поле ввода внутри таблицы (редактирование ячеек) */
            QTableWidget QLineEdit {
                background-color: #252526;
                color: #ffffff;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
                padding: 2px 4px;
                selection-background-color: #0078d4;
                selection-color: #ffffff;
            }
            QTableWidget QLineEdit:focus {
                border-color: #0078d4;
            }
            QPushButton {
                background-color: transparent;
                color: #ffffff;
                border:none;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #026ec1;
                border: 1px solid #1282d7;
            }

            QPushButton:pressed {
                background-color: #0078d4;
                border: 1px solid #1282d7;
            }

            QPushButton:disabled {
                background-color: #2D2D30;
                color: #656565;
            }
            QPushButton:hover { background-color: #1177bb; }
            QPushButton:pressed { background-color: #094770; }
            QPushButton:disabled { background-color: #3c3c3c; color: #909090; }
        """)

    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        desc = QLabel(tr("addons_description", self.lang))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Верхняя панель: режим установки + поиск
        top_row = QHBoxLayout()
        mode_label = QLabel(tr("addons_mode_label", self.lang) + ":")
        top_row.addWidget(mode_label)
        self.mode_combo = CustomComboBox()
        self.mode_combo.addItems([
            tr("addons_mode_full", self.lang),
            tr("addons_mode_lists", self.lang),
            tr("addons_mode_strategies", self.lang),
            tr("addons_mode_bin", self.lang),
        ])
        top_row.addWidget(self.mode_combo, 0)
        top_row.addStretch()
        self.search_edit = ContextLineEdit()
        self.search_edit.setPlaceholderText(tr("addons_search_placeholder", self.lang))
        self.search_edit.textChanged.connect(self._apply_filter)
        top_row.addWidget(self.search_edit, 1)
        layout.addLayout(top_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            tr("addons_col_name", self.lang),
            tr("addons_col_url", self.lang),
            "",
            "",
        ])
        # Колонки
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 100)
        # Строки: убираем нумерацию и делаем высоту под кнопки
        vh = self.table.verticalHeader()
        vh.setVisible(False)
        vh.setDefaultSectionSize(35)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        self._nothing_row = None
        self._fill_table()

        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.add_btn = QPushButton(tr("addons_add", self.lang))
        self.add_btn.setStyleSheet('''
            QPushButton {
                border: 1px solid #2b2b2b;
            }
            QPushButton:hover {
                background-color: #026ec1;
                border: 1px solid #1282d7;
            }

            QPushButton:pressed {
                background-color: #0078d4;
                border: 1px solid #1282d7;
            }

            QPushButton:disabled {
                background-color: #2D2D30;
                color: #656565;
            }''')
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.clicked.connect(self._on_add)
        self.remove_btn = QPushButton(tr("addons_remove", self.lang))
        self.remove_btn.setStyleSheet('''
            QPushButton {
                border: 1px solid #2b2b2b;
            }
            QPushButton:hover {
                background-color: #026ec1;
                border: 1px solid #1282d7;
            }

            QPushButton:pressed {
                background-color: #0078d4;
                border: 1px solid #1282d7;
            }

            QPushButton:disabled {
                background-color: #2D2D30;
                color: #656565;
            }''')
        self.remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_btn.clicked.connect(self._on_remove)
        
       
        close_btn = QPushButton(tr("settings_ok", self.lang))
        close_btn.setStyleSheet('''
            QPushButton {
                border: 1px solid #2b2b2b;
            }
            QPushButton:hover {
                background-color: #026ec1;
                border: 1px solid #1282d7;
            }

            QPushButton:pressed {
                background-color: #0078d4;
                border: 1px solid #1282d7;
            }

            QPushButton:disabled {
                background-color: #2D2D30;
                color: #656565;
            }''')
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _fill_table(self):
        # Удаляем служебную строку "ничего не найдено", если была
        if getattr(self, "_nothing_row", None) is not None:
            try:
                self.table.removeRow(self._nothing_row)
            except Exception:
                pass
            self._nothing_row = None

        self.table.setRowCount(len(self._addons))
        for row, item in enumerate(self._addons):
            name_item = QTableWidgetItem(item.get("name", ""))
            url_item = QTableWidgetItem(item.get("url", ""))
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, url_item)

            download_btn = QPushButton(tr("addons_download", self.lang))
            download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            download_btn.setProperty("row", row)
            download_btn.clicked.connect(lambda checked, r=row: self._on_download(r))
            open_btn = QPushButton(tr("addons_open_link", self.lang))
            open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            open_btn.setProperty("row", row)
            open_btn.clicked.connect(lambda checked, r=row: self._on_open(r))

            self.table.setCellWidget(row, 2, download_btn)
            self.table.setCellWidget(row, 3, open_btn)

        # Добавляем служебную строку "ничего не найдено" в конец
        self._nothing_row = self.table.rowCount()
        self.table.insertRow(self._nothing_row)
        nothing_item = QTableWidgetItem(tr("addons_nothing_found", self.lang))
        nothing_item.setFlags(Qt.ItemFlag.NoItemFlags)
        nothing_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(self._nothing_row, 0, nothing_item)
        # Растягиваем текст на все 4 колонки
        self.table.setSpan(self._nothing_row, 0, 1, 4)
        # По умолчанию скрываем, пока есть хоть одна подходящая строка
        self.table.setRowHidden(self._nothing_row, True)

    def _table_to_addons(self):
        """Собирает данные из таблицы в список addons."""
        addons = []
        for row in range(self.table.rowCount()):
            # Пропускаем служебную строку "ничего не найдено"
            if getattr(self, "_nothing_row", None) is not None and row == self._nothing_row:
                continue
            name_item = self.table.item(row, 0)
            url_item = self.table.item(row, 1)
            name = name_item.text().strip() if name_item else ""
            url = url_item.text().strip() if url_item else ""
            if name or url:
                addons.append({"name": name, "url": url})
        return addons

    def _on_add(self):
        self._addons = self._table_to_addons()
        self._addons.append({"name": "", "url": ""})
        _save_addons_to_config(self._addons)
        self._fill_table()

    def _on_remove(self):
        # Удаляем все выбранные строки (кроме служебной "ничего не найдено")
        selection = self.table.selectionModel()
        if not selection or not selection.hasSelection():
            row = self.table.currentRow()
            if row < 0 or (getattr(self, "_nothing_row", None) is not None and row == self._nothing_row):
                return
            rows = [row]
        else:
            rows = sorted(
                {idx.row() for idx in selection.selectedIndexes()
                 if getattr(self, "_nothing_row", None) is None or idx.row() != self._nothing_row},
                reverse=True,
            )
            if not rows:
                return
        self._addons = self._table_to_addons()
        for row in rows:
            if 0 <= row < len(self._addons):
                self._addons.pop(row)
        _save_addons_to_config(self._addons)
        self._fill_table()

    def _on_table_context_menu(self, pos):
        """Контекстное меню по правому клику по таблице."""
        menu = StyleMenu(self)
        add_action = menu.addAction(tr("addons_add", self.lang))
        remove_action = menu.addAction(tr("addons_remove", self.lang))
        # Открыть / Скачать доступны только при одном выделении и валидной строке
        row = self.table.currentRow()
        can_row = row >= 0 and (getattr(self, "_nothing_row", None) is None or row != self._nothing_row)
        if can_row:
            menu.addSeparator()
            open_action = menu.addAction(tr("addons_open_link", self.lang))
            download_action = menu.addAction(tr("addons_download", self.lang))
        else:
            open_action = None
            download_action = None
        action = menu.exec(self.table.mapToGlobal(pos))
        if not action:
            return
        if action == add_action:
            self._on_add()
        elif action == remove_action:
            self._on_remove()
        elif action == open_action and can_row:
            self._on_open(row)
        elif action == download_action and can_row:
            self._on_download(row)

    def _on_download(self, row):
        addons = self._table_to_addons()
        if row >= len(addons):
            return
        item = addons[row]
        name, url = item.get("name", ""), item.get("url", "").strip()
        if not url:
            return
        # Определяем режим установки
        mode_index = self.mode_combo.currentIndex() if hasattr(self, "mode_combo") else 0
        mode_map = {
            0: "full",
            1: "lists",
            2: "strategies",
            3: "bin",
        }
        mode = mode_map.get(mode_index, "full")
        # Сохраняем текущее состояние таблицы в конфиг
        _save_addons_to_config(addons)
        if hasattr(self.parent(), "on_addon_download"):
            try:
                self.parent().on_addon_download(name, url, mode)
            except TypeError:
                # Обратная совместимость, если метод ещё принимает только 2 аргумента
                self.parent().on_addon_download(name, url)

    def _on_open(self, row):
        addons = self._table_to_addons()
        if row >= len(addons):
            return
        url = (addons[row].get("url") or "").strip()
        if url:
            webbrowser.open(url)

    def _apply_filter(self, text):
        """Фильтрация строк таблицы по названию/URL, с состоянием 'ничего не найдено'."""
        query = (text or "").strip().lower()
        visible_count = 0
        for row in range(self.table.rowCount()):
            # Пропускаем служебную строку "ничего не найдено"
            if getattr(self, "_nothing_row", None) is not None and row == self._nothing_row:
                continue
            name_item = self.table.item(row, 0)
            url_item = self.table.item(row, 1)
            haystack = ""
            if name_item:
                haystack += name_item.text()
            if url_item:
                haystack += " " + url_item.text()
            haystack = haystack.lower()
            match = (not query) or (query in haystack)
            self.table.setRowHidden(row, not match)
            if match:
                visible_count += 1

        # Управляем служебной строкой: показываем её, только если ничего не найдено
        if getattr(self, "_nothing_row", None) is not None:
            if visible_count == 0:
                self.table.setRowHidden(self._nothing_row, False)
            else:
                self.table.setRowHidden(self._nothing_row, True)

    def accept(self):
        _save_addons_to_config(self._table_to_addons())
        super().accept()

    def closeEvent(self, event):
        _save_addons_to_config(self._table_to_addons())
        super().closeEvent(event)

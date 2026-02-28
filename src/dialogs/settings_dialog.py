"""
Диалоговое окно настроек программы (список категорий слева)
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QWidget,
    QLabel, QPushButton, QGroupBox, QFileDialog,
    QListWidget, QListWidgetItem, QStackedWidget
)
from src.widgets.custom_checkbox import CustomCheckBox as QCheckBox
from src.widgets.custom_context_widgets import ContextLineEdit
from src.core.path_utils import get_base_path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QCursor
from src.core.translator import tr
from src.widgets.custom_combobox import CustomComboBox
from src.core.window_styles import apply_window_style

class SettingsDialog(QDialog):
    """Диалоговое окно настроек со списком категорий слева"""
    
    def __init__(self, parent=None, settings=None, config=None, autostart_manager=None, zapret_updater=None, winws_manager=None):
        super().__init__(parent)
        self.settings = settings or {}
        self.config = config
        self.autostart_manager = autostart_manager
        self.zapret_updater = zapret_updater
        self.winws_manager = winws_manager
        self.lang = self.settings.get('language', 'ru')

        apply_window_style(self)

        self.setWindowTitle(tr('menu_open_settings', self.lang))
        self.setMinimumSize(620, 420)
        self.resize(700, 480)
        from src.core.embedded_assets import get_app_icon
        self.setWindowIcon(get_app_icon())
        
        self._apply_styles()
        self._create_ui()
    
    def _apply_styles(self):
        """Тёмная тема"""
        self.setStyleSheet("""
            QDialog { background-color: #181818; }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #cccccc; }
            QLabel { color: #cccccc; }
            QCheckBox { color: #cccccc; spacing: 8px; }
            QListWidget {
                background-color: #1f1f1f;
                color: #cccccc;
                selection-background-color: #0078d4;
                selection-color: #ffffff;
                outline: none;
                padding: 2px 0px;
                border: 1px solid #2b2b2b;
                border-radius: 6px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border: none;
                min-height: 20px;
                margin: 2px 4px;
                border-radius: 6px; 
            }
            QListWidget::item:first {
                margin-top: 4px;
            }

            QListWidget::item:disabled {
                color: #909090;
            }
            QListWidget::item:last {
                margin-bottom: 4px;
            }
            QListWidget::item:hover {
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                font-weight: bold;
                border-radius: 6px;
            }
            CustomComboBox:focus { border-color: #0078d4; }
             
        """)
    
    def _create_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet('QSplitter::handle { background-color: transparent; }')
        
        # Левая панель — виджет с поиском и списком категорий
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_list_container = QWidget()
        left_list_container.setMinimumWidth(200)
        left_list_container.setMaximumWidth(280)
        left_list_container_layout = QVBoxLayout(left_list_container)
        left_list_container_layout.setContentsMargins(0, 0, 0, 0)
        left_list_container_layout.setSpacing(6)
        
        self.search_edit = ContextLineEdit()
        self.search_edit.setPlaceholderText(tr('settings_search_placeholder', self.lang))
        self.search_edit.textChanged.connect(self._on_search_changed)
        left_list_container_layout.addWidget(self.search_edit)
        
        self.category_list = QListWidget()
        self.category_list.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.category_list.setMinimumWidth(200)
        self.category_list.setMaximumWidth(280)
        self.category_list.setUniformItemSizes(True)
        self.category_list.setSpacing(0)
        self.category_list.setViewportMargins(4, 4, 4, 4)
        self._category_names = [
            tr('settings_category_language', self.lang),       # 0
            tr('settings_category_winws_path', self.lang),    # 1
            tr('settings_category_tray', self.lang),          # 2
            tr('settings_category_exit_behavior', self.lang), # 3
            tr('settings_category_autostart', self.lang),     # 4
            tr('settings_category_filters', self.lang),       # 5
            tr('settings_category_app_restart', self.lang),   # 6 - Автоперезапуск приложений
            tr('settings_category_b_flag', self.lang),        # 7
            tr('settings_category_update', self.lang),        # 8
        ]
        for name in self._category_names:
            self.category_list.addItem(name)
        left_list_stack = QStackedWidget()
        left_list_stack.addWidget(self.category_list)
        nothing_widget = QWidget()
        nothing_layout = QVBoxLayout(nothing_widget)
        nothing_layout.setContentsMargins(0, 0, 0, 0)
        self._nothing_label = QLabel(tr('settings_nothing_found', self.lang))
        self._nothing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nothing_label.setStyleSheet('color: #808080; font-size: 13px;')
        nothing_layout.addWidget(self._nothing_label)
        nothing_widget.setStyleSheet('background-color: #181818; border: 1px solid #2b2b2b; border-radius: 6px;')
        left_list_stack.addWidget(nothing_widget)
        left_list_stack.setCurrentIndex(0)
        self._left_list_stack = left_list_stack
        left_list_container_layout.addWidget(left_list_stack)
        
        left_layout.addWidget(left_list_container)
        splitter.addWidget(left_panel)
        
        # Правая панель — страницы настроек
        self.stacked = QStackedWidget()
        self.stacked.setMinimumWidth(350)
        
        self._create_pages()
        
        splitter.addWidget(self.stacked)
        splitter.setSizes([220, 460])
        
        main_layout.addWidget(splitter)
        
        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton(tr('settings_ok', self.lang))
        ok_btn.setDefault(True)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(tr('settings_cancel', self.lang))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        main_layout.addLayout(btn_row)
        
        self.category_list.currentRowChanged.connect(
            lambda row: self.stacked.setCurrentIndex(row) if row >= 0 else None
        )
        self.category_list.setCurrentRow(0)
    
    def _on_search_changed(self, text):
        """Фильтрация списка категорий по строке поиска"""
        text = text.strip().lower()
        visible_count = 0
        n = len(self._category_names)
        for i in range(n):
            item = self.category_list.item(i)
            name = self._category_names[i]
            visible = not text or text in name.lower()
            item.setHidden(not visible)
            if visible:
                visible_count += 1
        if text and visible_count == 0:
            self._left_list_stack.setCurrentIndex(1)
            self.category_list.setCurrentRow(-1)
        else:
            self._left_list_stack.setCurrentIndex(0)
            if text and self.category_list.currentRow() < 0:
                for i in range(n):
                    if not self.category_list.item(i).isHidden():
                        self.category_list.setCurrentRow(i)
                        break
    
    def _create_pages(self):
        """Создаёт страницы настроек"""
        # 0: Язык
        lang_page = QWidget()
        lang_layout = QVBoxLayout(lang_page)
        lang_group = QGroupBox(tr('menu_change_language', self.lang))
        lang_grp = QVBoxLayout()
        self.lang_combo = CustomComboBox()
        self.lang_combo.addItems([tr('settings_lang_russian', self.lang), tr('settings_lang_english', self.lang)])
        self.lang_combo.setCurrentIndex(0 if self.settings.get('language', 'ru') == 'ru' else 1)
        lang_grp.addWidget(self.lang_combo)
        lang_group.setLayout(lang_grp)
        lang_layout.addWidget(lang_group)
        lang_layout.addStretch()
        self.stacked.addWidget(lang_page)

        # 1: Папка winws
        winws_page = QWidget()
        winws_layout = QVBoxLayout(winws_page)
        winws_group = QGroupBox(tr('settings_winws_path_label', self.lang))
        winws_grp = QVBoxLayout()
        winws_row = QHBoxLayout()
        self.winws_path_edit = ContextLineEdit()
        self.winws_path_edit.setPlaceholderText(tr('settings_winws_path_placeholder', self.lang))
        self.winws_path_edit.setText(self.settings.get('winws_path', '').strip())
        winws_row.addWidget(self.winws_path_edit)
        winws_browse_btn = QPushButton(tr('settings_winws_path_browse', self.lang))
        winws_browse_btn.setFixedHeight(26)
        winws_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        winws_browse_btn.clicked.connect(self._on_browse_winws_path)
        winws_row.addWidget(winws_browse_btn)
        winws_grp.addLayout(winws_row)
        winws_group.setLayout(winws_grp)
        winws_layout.addWidget(winws_group)
        winws_layout.addStretch()
        self.stacked.addWidget(winws_page)
        
        # 2: Трей
        tray_page = QWidget()
        tray_layout = QVBoxLayout(tray_page)
        tray_group = QGroupBox(tr('settings_category_tray', self.lang))
        tray_grp = QVBoxLayout()
        self.show_tray_cb = QCheckBox(tr('settings_show_tray', self.lang))
        self.show_tray_cb.setChecked(self.settings.get('show_in_tray', True))
        self.show_tray_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        tray_grp.addWidget(self.show_tray_cb)

        self.start_minimized_cb = QCheckBox(tr('settings_start_minimized', self.lang))
        self.start_minimized_cb.setChecked(self.settings.get('start_minimized', False))
        self.start_minimized_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        # Показываем «Запускать свернутым в трей» только когда включён пункт «Отображать в трее»
        self.start_minimized_cb.setVisible(self.show_tray_cb.isChecked())
        self.show_tray_cb.toggled.connect(self.start_minimized_cb.setVisible)
        tray_grp.addWidget(self.start_minimized_cb)
        tray_group.setLayout(tray_grp)
        tray_layout.addWidget(tray_group)
        tray_layout.addStretch()
        self.stacked.addWidget(tray_page)
        
        # 2: Выход
        exit_page = QWidget()
        exit_layout = QVBoxLayout(exit_page)
        exit_group = QGroupBox(tr('settings_category_exit_behavior', self.lang))
        exit_grp = QVBoxLayout()
        self.close_winws_cb = QCheckBox(tr('settings_close_winws', self.lang))
        self.close_winws_cb.setChecked(self.settings.get('close_winws_on_exit', True))
        self.close_winws_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_grp.addWidget(self.close_winws_cb)
        exit_group.setLayout(exit_grp)
        exit_layout.addWidget(exit_group)
        exit_layout.addStretch()
        self.stacked.addWidget(exit_page)
        
        # 3: Автозапуск
        autostart_page = QWidget()
        autostart_layout = QVBoxLayout(autostart_page)
        autostart_group = QGroupBox(tr('settings_category_autostart', self.lang))
        autostart_grp = QVBoxLayout()
        self.autostart_cb = QCheckBox(tr('settings_autostart_windows', self.lang))
        self.autostart_cb.setToolTip(tr('settings_autostart_tooltip', self.lang))
        self.autostart_cb.setChecked(self.autostart_manager and self.autostart_manager.is_enabled())
        self.autostart_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        autostart_grp.addWidget(self.autostart_cb)
        self.auto_start_cb = QCheckBox(tr('settings_auto_start', self.lang))
        self.auto_start_cb.setChecked(self.settings.get('auto_start_last_strategy', False))
        self.auto_start_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        autostart_grp.addWidget(self.auto_start_cb)
        self.auto_restart_cb = QCheckBox(tr('settings_auto_restart_strategy', self.lang))
        self.auto_restart_cb.setChecked(self.settings.get('auto_restart_strategy', False))
        self.auto_restart_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        autostart_grp.addWidget(self.auto_restart_cb)
        autostart_group.setLayout(autostart_grp)
        autostart_layout.addWidget(autostart_group)
        autostart_layout.addStretch()
        self.stacked.addWidget(autostart_page)
        
        # 4: Фильтры (Game Filter, IPSet Filter)
        filters_page = QWidget()
        filters_layout = QVBoxLayout(filters_page)
        filters_group = QGroupBox(tr('settings_category_filters', self.lang))
        filters_grp = QVBoxLayout()
        self.game_filter_cb = QCheckBox(tr('settings_game_filter', self.lang))
        game_enabled = self.settings.get('game_filter_enabled', False)
        if self.winws_manager:
            game_enabled = self.winws_manager.is_game_filter_enabled()
        self.game_filter_cb.setChecked(game_enabled)
        self.game_filter_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        filters_grp.addWidget(self.game_filter_cb)
        ipset_label = QLabel(tr('settings_ipset_filter', self.lang) + ':')
        filters_grp.addWidget(ipset_label)
        self.ipset_combo = CustomComboBox()
        self.ipset_combo.addItems([
            tr('settings_ipset_loaded', self.lang),
            tr('settings_ipset_none', self.lang),
            tr('settings_ipset_any', self.lang),
        ])
        ipset_mode = self.settings.get('ipset_filter_mode', 'loaded')
        if self.winws_manager:
            ipset_mode = self.winws_manager.get_ipset_mode()
        mode_idx = {'loaded': 0, 'none': 1, 'any': 2}.get(ipset_mode, 0)
        self.ipset_combo.setCurrentIndex(mode_idx)
        filters_grp.addWidget(self.ipset_combo)
        filters_group.setLayout(filters_grp)
        filters_layout.addWidget(filters_group)
        filters_layout.addStretch()
        self.stacked.addWidget(filters_page)
        
        # 5: Автоперезапуск приложений
        apps_page = QWidget()
        apps_layout = QVBoxLayout(apps_page)
        apps_group = QGroupBox(tr('settings_category_app_restart', self.lang))
        apps_grp = QVBoxLayout()
        desc_label = QLabel(tr('settings_app_restart_description', self.lang))
        desc_label.setWordWrap(True)
        apps_grp.addWidget(desc_label)
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
        self.apps_table = QTableWidget(0, 1)
        self.apps_table.setHorizontalHeaderLabels([tr('settings_app_restart_column_app', self.lang)])
        self.apps_table.horizontalHeader().setStretchLastSection(True)
        self.apps_table.verticalHeader().setVisible(False)
        self.apps_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.apps_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.apps_table.setShowGrid(False)
        self.apps_table.setStyleSheet("QTableWidget { background-color: #1f1f1f; border: 1px solid #2b2b2b; color: #cccccc; }")
        # Заполняем из настроек
        for name in self.settings.get('auto_restart_apps', []):
            row = self.apps_table.rowCount()
            self.apps_table.insertRow(row)
            item = QTableWidgetItem(str(name))
            self.apps_table.setItem(row, 0, item)
        apps_grp.addWidget(self.apps_table)
        # Кнопки Добавить / Удалить
        btn_row = QHBoxLayout()
        add_btn = QPushButton(tr('settings_app_restart_add', self.lang))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn = QPushButton(tr('settings_app_restart_remove', self.lang))
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        apps_grp.addLayout(btn_row)
        apps_group.setLayout(apps_grp)
        apps_layout.addWidget(apps_group)
        apps_layout.addStretch()
        self.stacked.addWidget(apps_page)

        add_btn.clicked.connect(self._on_add_app_clicked)
        remove_btn.clicked.connect(self._on_remove_app_clicked)
        
        # 6: Флаг /B
        bflag_page = QWidget()
        bflag_layout = QVBoxLayout(bflag_page)
        bflag_group = QGroupBox(tr('menu_add_b_flag_submenu', self.lang))
        bflag_grp = QVBoxLayout()
        self.add_b_on_update_cb = QCheckBox(tr('menu_add_b_flag_on_update', self.lang))
        self.add_b_on_update_cb.setChecked(self.settings.get('add_b_flag_on_update', False))
        self.add_b_on_update_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        bflag_grp.addWidget(self.add_b_on_update_cb)
        btn_layout = QHBoxLayout()
        add_b_btn = QPushButton(tr('menu_add_b_flag', self.lang))
        add_b_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_b_btn.clicked.connect(self._on_add_b_clicked)
        remove_b_btn = QPushButton(tr('menu_remove_b_flag', self.lang))
        remove_b_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_b_btn.clicked.connect(self._on_remove_b_clicked)
        btn_layout.addWidget(add_b_btn)
        btn_layout.addWidget(remove_b_btn)
        btn_layout.addStretch()
        bflag_grp.addLayout(btn_layout)
        bflag_group.setLayout(bflag_grp)
        bflag_layout.addWidget(bflag_group)
        bflag_layout.addStretch()
        self.stacked.addWidget(bflag_page)
        
        # 7: Обновление
        update_page = QWidget()
        update_layout = QVBoxLayout(update_page)
        update_group = QGroupBox(tr('settings_category_update', self.lang))
        update_grp = QVBoxLayout()
        self.remove_check_cb = QCheckBox(tr('settings_remove_check_zapret', self.lang))
        self.remove_check_cb.setChecked(self.settings.get('remove_check_updates', False))
        self.remove_check_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        update_grp.addWidget(self.remove_check_cb)
        # Поле для переопределения репозитория zapret
        repo_label = QLabel(tr('settings_zapret_repo_label', self.lang))
        update_grp.addWidget(repo_label)
        self.zapret_repo_edit = ContextLineEdit()
        self.zapret_repo_edit.setPlaceholderText(tr('settings_zapret_repo_placeholder', self.lang))
        self.zapret_repo_edit.setText(self.settings.get('zapret_repo', ''))
        update_grp.addWidget(self.zapret_repo_edit)
        update_group.setLayout(update_grp)
        update_layout.addWidget(update_group)
        update_layout.addStretch()
        self.stacked.addWidget(update_page)
    
    def _on_add_b_clicked(self):
        if self.parent() and hasattr(self.parent(), 'add_b_flag_to_all_strategies'):
            self.parent().add_b_flag_to_all_strategies(silent=False)
    
    def _on_remove_b_clicked(self):
        if self.parent() and hasattr(self.parent(), 'remove_b_flag_from_all_strategies'):
            self.parent().remove_b_flag_from_all_strategies(silent=False)

    def _on_browse_winws_path(self):
        start = self.winws_path_edit.text().strip() or get_base_path()
        folder = QFileDialog.getExistingDirectory(self, tr('settings_winws_path_label', self.lang), start)
        if folder:
            self.winws_path_edit.setText(folder)
    
    def _on_add_app_clicked(self):
        """Добавляет строку в таблицу автоперезапуска приложений."""
        from PyQt6.QtWidgets import QInputDialog, QTableWidgetItem
        app_name, ok = QInputDialog.getText(
            self,
            tr('settings_app_restart_add', self.lang),
            tr('settings_app_restart_column_app', self.lang) + ':'
        )
        if not ok:
            return
        app_name = app_name.strip()
        if not app_name:
            return
        row = self.apps_table.rowCount()
        self.apps_table.insertRow(row)
        self.apps_table.setItem(row, 0, QTableWidgetItem(app_name))

    def _on_remove_app_clicked(self):
        """Удаляет выбранную строку из таблицы автоперезапуска приложений."""
        row = self.apps_table.currentRow()
        if row < 0:
            return
        self.apps_table.removeRow(row)

    def get_settings_changes(self):
        """Возвращает словарь с изменениями настроек"""
        changes = {}
        lang = 'ru' if self.lang_combo.currentIndex() == 0 else 'en'
        if lang != self.settings.get('language', 'ru'):
            changes['language'] = lang
        if self.show_tray_cb.isChecked() != self.settings.get('show_in_tray', True):
            changes['show_in_tray'] = self.show_tray_cb.isChecked()
        if self.start_minimized_cb.isChecked() != self.settings.get('start_minimized', False):
            changes['start_minimized'] = self.start_minimized_cb.isChecked()
        if self.close_winws_cb.isChecked() != self.settings.get('close_winws_on_exit', True):
            changes['close_winws_on_exit'] = self.close_winws_cb.isChecked()
        changes['autostart_enabled'] = self.autostart_cb.isChecked()
        if self.auto_start_cb.isChecked() != self.settings.get('auto_start_last_strategy', False):
            changes['auto_start_last_strategy'] = self.auto_start_cb.isChecked()
        if self.auto_restart_cb.isChecked() != self.settings.get('auto_restart_strategy', False):
            changes['auto_restart_strategy'] = self.auto_restart_cb.isChecked()
        if self.add_b_on_update_cb.isChecked() != self.settings.get('add_b_flag_on_update', False):
            changes['add_b_flag_on_update'] = self.add_b_on_update_cb.isChecked()
        if self.remove_check_cb.isChecked() != self.settings.get('remove_check_updates', False):
            changes['remove_check_updates'] = self.remove_check_cb.isChecked()
        game_enabled = self.game_filter_cb.isChecked()
        if game_enabled != self.settings.get('game_filter_enabled', False):
            changes['game_filter_enabled'] = game_enabled
        ipset_mode = ['loaded', 'none', 'any'][self.ipset_combo.currentIndex()]
        if ipset_mode != self.settings.get('ipset_filter_mode', 'loaded'):
            changes['ipset_filter_mode'] = ipset_mode
        winws_path = self.winws_path_edit.text().strip()
        if winws_path != self.settings.get('winws_path', '').strip():
            changes['winws_path'] = winws_path
        # Репозиторий zapret
        zapret_repo = self.zapret_repo_edit.text().strip()
        if zapret_repo != self.settings.get('zapret_repo', '').strip():
            changes['zapret_repo'] = zapret_repo
        # Автоперезапуск приложений
        apps = []
        if hasattr(self, 'apps_table'):
            from PyQt6.QtWidgets import QTableWidgetItem
            for row in range(self.apps_table.rowCount()):
                item = self.apps_table.item(row, 0)
                if item:
                    name = item.text().strip()
                    if name:
                        apps.append(name)
        if apps != self.settings.get('auto_restart_apps', []):
            changes['auto_restart_apps'] = apps
        return changes

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import *
from .system_tray import SystemTray
from src.core.config_manager import ConfigManager, VERSION, MD5
from src.core.translator import tr
from src.core.autostart_manager import AutostartManager
from src.core.zapret_updater import ZapretUpdater
from src.core.app_updater import AppUpdater
from src.core.winws_manager import WinwsManager
from .test_window import TestWindow
from src.dialogs.settings_dialog import SettingsDialog
from src.editor.unified_editor_window import get_unified_editor_window
from src.dialogs.bin_creator_dialog import BinCreatorDialog
from src.core.path_utils import get_base_path, get_config_path, get_winws_path
from src.core.embedded_assets import get_app_icon
from .standard_window import StandardMainWindow
from .standard_dialog import StandardDialog
from src.widgets.style_menu import StyleMenu
from src.widgets.custom_combobox import CustomComboBox
from src.widgets.custom_context_widgets import ContextTextEdit
from src.dialogs.vs_update_dialog import VSUpdateDialog
from src.ui.message_box_utils import configure_message_box
from src.dialogs.addons_dialog import AddonsDialog
import os
import re
import requests
import subprocess
import psutil
import threading
import winreg
import json
import csv
from datetime import datetime


class _StartWorker(QThread):
    """Фоновый запуск .bat: автоперезапуск приложений и Popen. Не блокирует UI."""
    done_signal = pyqtSignal(bool, object, str)  # success, process, error_message

    def __init__(self, main_win, bat_path_abs, bat_dir, is_nt):
        super().__init__()
        self._main_win = main_win
        self._bat_path_abs = bat_path_abs
        self._bat_dir = bat_dir
        self._is_nt = is_nt

    def run(self):
        try:
            import time
            time.sleep(0.5)  # столько же времени прохода, как при завершении (terminate + 0.5s)
            self._main_win._handle_auto_restart_apps()
            if self._is_nt:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                proc = subprocess.Popen(
                    ['cmd.exe', '/c', self._bat_path_abs],
                    cwd=self._bat_dir,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                proc = subprocess.Popen(
                    [self._bat_path_abs],
                    cwd=self._bat_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            self.done_signal.emit(True, proc, '')
        except Exception as e:
            self.done_signal.emit(False, None, str(e))


class _StopWorker(QThread):
    """Фоновое завершение процессов winws.exe. Не блокирует UI."""
    done_signal = pyqtSignal()

    def __init__(self, main_win):
        super().__init__()
        self._main_win = main_win

    def run(self):
        try:
            self._main_win._do_stop_winws_process()
        except Exception:
            pass
        self.done_signal.emit()


class MainWindow(StandardMainWindow):
    update_found_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__(title="ZapretDeskop", width=640, height=480, icon=get_app_icon(), theme="dark")
        self.is_running = False
        self.bat_process = None  # Процесс запущенного .bat файла
        self.running_strategy = None  # Название запущенной стратегии для перезапуска
        # True если winws был запущен из этой сессии ZapretDeskop (для отличия от "внешнего" запуска)
        self._started_winws_this_session = False
        self.is_restarting = False  # Флаг для предотвращения множественных перезапусков
        self.user_stopped = False  # Флаг явной остановки пользователем (чтобы не запускать автоперезапуск)
        self.bat_start_time = None  # Время запуска .bat файла (для проверки появления winws.exe)
        self.process_monitor_timer = QTimer(self)  # Таймер для отслеживания процесса
        self.process_monitor_timer.timeout.connect(self.check_winws_process)
        self._start_worker = None  # фоновый запуск стратегии
        self._stop_worker = None   # фоновая остановка
        # Инициализация менеджера конфигурации
        self.config = ConfigManager()
        # Загружаем настройки из файла
        self.settings = self.config.load_settings()
        # Инициализация менеджера автозапуска
        self.autostart_manager = AutostartManager()
        # Инициализация менеджера обновлений zapret
        self.zapret_updater = ZapretUpdater()
        # Инициализация менеджера обновлений программы
        self.app_updater = AppUpdater()
        self.latest_available_version = None   
        self.update_found_signal.connect(self._on_background_update_found)
        # Инициализация менеджера настроек winws
        self.winws_manager = WinwsManager()
        # Защита от повторного открытия окна настроек
        self._settings_dialog = None
        self._settings_dialog_opening = False
        self.init_ui()
        self.init_menu_bar()
        self.init_tray()
        # Применяем переводы после инициализации всех компонентов
        self.retranslate_ui()
        
        # Синхронизируем настройки фильтров с файлами winws
        self.update_filter_statuses()
        # Обновляем заголовок окна с учётом текущей стратегии (если уже запущена)
        self._update_window_title_with_strategy()
        
        # Если включена настройка start_minimized, сворачиваем в трей при запуске
        if self.settings.get('start_minimized', False):
            # Скрываем окно в трей, если включена настройка
            self.hide()
        else:
            # Показываем окно, если настройка выключена
            self.show()
        
        # Запускаем мониторинг процесса (проверка каждые 1 секунду)
        self.process_monitor_timer.start(1000)
        
        # Если включен автозапуск последней стратегии, запускаем её
        if self.settings.get('auto_start_last_strategy', False):
            # Небольшая задержка, чтобы окно успело полностью инициализироваться
            QTimer.singleShot(1000, lambda: self.auto_start_last_strategy())
    
    def _is_autostart(self):
        """Проверяет, запущено ли приложение через автозапуск"""
        # Проверяем аргумент командной строки --autostart
        import sys
        if '--autostart' in sys.argv:
            return True
        
        # Проверяем, включен ли автозапуск (через Task Scheduler)
        if self.autostart_manager.is_enabled():
            # Дополнительная проверка: если родительский процесс - explorer.exe, winlogon.exe или userinit.exe,
            # и автозапуск включен, то вероятно это автозапуск
            try:
                current_process = psutil.Process()
                parent = current_process.parent()
                if parent:
                    parent_name = parent.name().lower()
                    # Если родитель - explorer.exe и автозапуск включен, это может быть автозапуск
                    # Но explorer.exe также может быть родителем при обычном запуске
                    # Поэтому проверяем только winlogon.exe и userinit.exe как более надежные индикаторы
                    if parent_name in ['winlogon.exe', 'userinit.exe']:
                        return True
                    # Для explorer.exe используем дополнительную проверку - время запуска
                    # При автозапуске процесс обычно запускается сразу после входа в систему
                    if parent_name == 'explorer.exe':
                        # Проверяем, что процесс запущен недавно (в течение последних 30 секунд)
                        # Это может указывать на автозапуск
                        import time
                        process_create_time = current_process.create_time()
                        current_time = time.time()
                        if current_time - process_create_time < 30:
                            return True
            except Exception:
                pass
        
        return False
    
    def init_ui(self):
        # Используем content_layout из StandardMainWindow
        # Центральный виджет
        central_widget = QWidget()
        self.setContentWidget(central_widget)
        
        # Основной layout
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 10)
        central_widget.setLayout(layout)
        
        # Тонкая полоска прогресса под QMenuBar (1px); скрыта по умолчанию, без сдвига виджетов
        self.menu_progress_bar = QProgressBar()
        self.menu_progress_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.menu_progress_bar.setTextVisible(False)
        self.menu_progress_bar.setRange(0, 100)
        self.menu_progress_bar.setValue(0)
        # Явные стили, чтобы полоска была видна на любой теме (фон и заливка)
        self.menu_progress_bar.setStyleSheet(
            "QProgressBar { background: transparent; border: none; min-height: 1px; max-height: 1px; } "
            "QProgressBar::chunk { background: #0078d4; min-height: 1px; }"
        )
        # Нулевая высота до добавления в layout — при первом запуске виджеты не сдвигаются
        self.menu_progress_bar.setFixedHeight(0)
        self.menu_progress_bar.setMaximumHeight(0)
        layout.addWidget(self.menu_progress_bar)
        
        # Добавляем растягивающий элемент сверху, чтобы элементы были по центру
        layout.addStretch()
        
        # ComboBox
        self.combo_box = CustomComboBox()
        self.load_bat_files()
        # Сохраняем стратегию при изменении
        self.combo_box.currentTextChanged.connect(self.on_strategy_changed)
        self.combo_box.setMinimumHeight(35)
        self.combo_box.setMinimumWidth(300)
        # Выравниваем ComboBox по центру
        combo_layout = QHBoxLayout()
        combo_layout.addStretch()
        combo_layout.addWidget(self.combo_box)
        combo_layout.addStretch()
        layout.addLayout(combo_layout)
        
        # Кнопка Запустить/Остановить
        self.action_button = QPushButton('')
        self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_button.setMinimumHeight(40)
        self.action_button.setMinimumWidth(300)  # Та же ширина, что и у ComboBox
        self.action_button.clicked.connect(self.toggle_action)
        # Выравниваем кнопку по центру
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.action_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Восстанавливаем последнюю выбранную стратегию (после создания action_button)
        self.restore_last_strategy()
        
        # Добавляем растягивающий элемент, чтобы версия была внизу
        layout.addStretch()
        
        # Отдельный вертикальный лейаут с нулевым отступом между версией и почтой
        bottom_layout = QVBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(0)
        
        # Виджет с информацией о версии / MD5
        self.version_label = QLabel()
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setTextFormat(Qt.TextFormat.RichText)
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.version_label.setOpenExternalLinks(True)
        self.version_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.version_label.setStyleSheet("color: gray; font-size: 10px; margin: 0px;")
        self.version_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.version_label.customContextMenuRequested.connect(self._show_version_context_menu)
        self.load_version_info()
        bottom_layout.addWidget(self.version_label)

        # Кликабельный e-mail (mailto)
        self.contact_label = QLabel(
            '<a href="mailto:ZapretDeskop@proton.me">ZapretDeskop@proton.me</a>'
        )
        self.contact_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.contact_label.setTextFormat(Qt.TextFormat.RichText)
        self.contact_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.contact_label.setOpenExternalLinks(True)
        self.contact_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.contact_label.setStyleSheet("color: gray; font-size: 10px; margin: 0px;")
        self.contact_label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.contact_label.customContextMenuRequested.connect(self._show_contact_context_menu)
        bottom_layout.addWidget(self.contact_label)

        layout.addLayout(bottom_layout)

        # Проверка обновлений программы один раз при запуске (с задержкой, когда event loop уже работает)
        QTimer.singleShot(0, self._run_startup_update_check)
        
        # Сохраняем ссылки на меню для обновления переводов
        self.menubar = None
        self.settings_menu = None
        self.update_menu = None
        self.language_menu = None
        self.check_app_updates_action = None
        self.check_updates_action = None
        self.manual_update_action = None
    
    def init_menu_bar(self):
        """Создает меню бар"""
        self.menubar = QMenuBar()
        self.setMenuBar(self.menubar)
      
        
        lang = self.settings.get('language', 'ru')
        
        # Меню "Tools"
        self.tools_menu = StyleMenu(self.menubar)
        
        # Запуск теста
        self.run_test_action = QAction('', self)
        self.run_test_action.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.run_test_action.triggered.connect(self.show_test_window)
        self.tools_menu.addAction(self.run_test_action)
        
        # Run Diagnostics
        self.run_diagnostics_action = QAction('', self)
        self.run_diagnostics_action.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.run_diagnostics_action.triggered.connect(self.run_diagnostics)
        self.tools_menu.addAction(self.run_diagnostics_action)
        
        self.tools_menu.addSeparator()

        # Редактор (списки + drivers\etc)
        self.editor_action = QAction('', self)
        self.editor_action.setShortcut(QKeySequence("Ctrl+E"))
        self.editor_action.triggered.connect(self.show_editor)
        self.tools_menu.addAction(self.editor_action)

        self.tools_menu.addSeparator()
        
        # Создание стратегий
        self.create_strategy_action = QAction(tr('menu_create_strategy', lang), self)
        self.create_strategy_action.setShortcut(QKeySequence("Ctrl+N"))
        self.create_strategy_action.triggered.connect(self.show_strategy_creator)
        self.tools_menu.addAction(self.create_strategy_action)

        # Создание bin
        self.create_bin_action = QAction('', self)
        self.create_bin_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.create_bin_action.triggered.connect(self.show_bin_creator)
        self.tools_menu.addAction(self.create_bin_action)

        self.tools_menu.addSeparator()

        # Открыть папку...
        self.open_folder_menu = StyleMenu(self.tools_menu)
        self.open_folder_menu.setTitle('')
        self.open_winws_folder_action = QAction('', self)
        self.open_winws_folder_action.setShortcut(QKeySequence("Ctrl+Shift+W"))
        self.open_winws_folder_action.triggered.connect(self.open_winws_folder)
        self.open_folder_menu.addAction(self.open_winws_folder_action)
        self.open_config_folder_action = QAction('', self)
        self.open_config_folder_action.setShortcut(QKeySequence("Ctrl+Shift+O"))
        self.open_config_folder_action.triggered.connect(self.open_config_folder)
        self.open_folder_menu.addAction(self.open_config_folder_action)
        self.tools_menu.addMenu(self.open_folder_menu)

        self.tools_menu.addSeparator()

        # Свернуть окно (если активный трей)
        self.minimize_to_tray_action = QAction('', self)
        self.minimize_to_tray_action.setShortcut(QKeySequence("Ctrl+M"))
        self.minimize_to_tray_action.triggered.connect(self.minimize_to_tray)
        self.tools_menu.addAction(self.minimize_to_tray_action)

        # Закрыть программу
        self.quit_app_action = QAction('', self)
        self.quit_app_action.setShortcut(QKeySequence("Ctrl+Q"))
        self.quit_app_action.triggered.connect(self.quit_application)
        self.tools_menu.addAction(self.quit_app_action)
        
        # Добавляем меню Tools в менюбар
        self.tools_menu_action = self.menubar.addAction('')
        self.tools_menu_action.setMenu(self.tools_menu)
        
        # Меню "Настройки"
        self.settings_menu = StyleMenu(self.menubar)
        
        # Параметры программы
        self.open_settings_action = QAction('', self)
        self.open_settings_action.setShortcut(QKeySequence("Ctrl+,"))
        self.open_settings_action.triggered.connect(self.show_settings_dialog)
        self.settings_menu.addAction(self.open_settings_action)
        
        # Добавляем меню Settings в менюбар
        self.settings_menu_action = self.menubar.addAction('')
        self.settings_menu_action.setMenu(self.settings_menu)
        
        # Сохраняем ссылки на действия для обновления в диалоге настроек
        # (они больше не в меню, но нужны для синхронизации)
        self.show_tray_action = None
        self.start_minimized_action = None
        self.close_winws_action = None
        self.autostart_action = None
        self.auto_start_action = None
        self.auto_restart_action = None
        self.language_menu = None
        
        # Меню "Дополнения"
        self.addons_menu = StyleMenu(self.menubar)
        self.addons_action = QAction('', self)
        self.addons_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        self.addons_action.triggered.connect(self._show_addons_dialog)
        self.addons_menu.addAction(self.addons_action)
        self.addons_menu_action = self.menubar.addAction('')
        self.addons_menu_action.setMenu(self.addons_menu)
        
        # Меню "Обновление"
        self.update_menu = StyleMenu(self.menubar)
        
        # Проверить наличие обновлений программы ZapretDeskop
        self.check_app_updates_action = QAction('', self)
        self.check_app_updates_action.setShortcut(QKeySequence("Ctrl+F5"))
        self.check_app_updates_action.triggered.connect(self.check_app_updates)
        self.update_menu.addAction(self.check_app_updates_action)
        
        self.update_menu.addSeparator()
        
        # Проверить наличие обновление стратегий zapret
        self.check_updates_action = QAction('', self)
        self.check_updates_action.setShortcut(QKeySequence("F5"))
        self.check_updates_action.triggered.connect(self.check_zapret_updates)
        self.update_menu.addAction(self.check_updates_action)
        
        # Обновить стратегии в ручную
        self.manual_update_action = QAction('', self)
        self.manual_update_action.setShortcut(QKeySequence("Ctrl+Shift+U"))
        self.manual_update_action.triggered.connect(self.manual_update_strategies)
        self.update_menu.addAction(self.manual_update_action)
        
        self.update_menu.addSeparator()
        
        # Update IPSet List
        self.update_ipset_action = QAction('', self)
        self.update_ipset_action.triggered.connect(self.update_ipset_list)
        self.update_menu.addAction(self.update_ipset_action)
        
        # Update Hosts File — перенесено в редактор etc (hosts + zapret_hosts.txt)
        
        # Добавляем меню Update в менюбар
        self.update_menu_action = self.menubar.addAction('')
        self.update_menu_action.setMenu(self.update_menu)
        
        # Меню "Справка"
        self.help_menu = StyleMenu(self.menubar)
        
        # Открыть страницу Github
        self.open_github_action = QAction('', self)
        self.open_github_action.setShortcut(QKeySequence("F1"))
        self.open_github_action.triggered.connect(self.open_github)
        self.help_menu.addAction(self.open_github_action)
        
        # Открыть Github Flowseal zapret
        self.open_github_zapret_action = QAction('', self)
        self.open_github_zapret_action.setShortcut(QKeySequence("Shift+F1"))
        self.open_github_zapret_action.triggered.connect(self.open_github_zapret)
        self.help_menu.addAction(self.open_github_zapret_action)
        
        # Добавляем меню Help в менюбар
        self.help_menu_action = self.menubar.addAction('')
        self.help_menu_action.setMenu(self.help_menu)
    
    def update_strategies_menu(self, menu):
        """Обновляет меню со списком стратегий"""
        menu.clear()
        winws_folder = get_winws_path()
        
        # Добавляем пункт "Открыть папку winws"
        lang = self.settings.get('language', 'ru')
        open_folder_action = QAction(tr('strategies_open_winws_folder', lang), self)
        open_folder_action.triggered.connect(self.open_winws_folder)
        menu.addAction(open_folder_action)
        
        # Добавляем разделитель
        menu.addSeparator()
        
        if os.path.exists(winws_folder):
            bat_files = []
            for filename in os.listdir(winws_folder):
                if filename.endswith('.bat') and os.path.isfile(os.path.join(winws_folder, filename)):
                    name_without_ext = filename[:-4]
                    bat_files.append((name_without_ext, filename))
            
            bat_files.sort(key=lambda x: x[0])
            
            for name, filename in bat_files:
                action = QAction(name, self)
                action.triggered.connect(lambda checked, f=filename: self.select_strategy(f))
                menu.addAction(action)
        else:
            action = QAction(tr('msg_winws_not_found', lang), self)
            action.setEnabled(False)
            menu.addAction(action)
    
    def select_strategy(self, filename):
        """Выбирает стратегию из меню"""
        name_without_ext = filename[:-4]
        index = self._find_combo_index_by_data(name_without_ext)
        if index >= 0:
            self.combo_box.setCurrentIndex(index)
            # Сохраняем последнюю выбранную стратегию
            self.config.set_setting('last_strategy', name_without_ext)
            self.settings['last_strategy'] = name_without_ext
    
    def retranslate_ui(self):
        """Обновляет все тексты интерфейса в соответствии с текущим языком"""
        lang = self.settings.get('language', 'ru')
        
        # Обновляем меню
        if hasattr(self, 'tools_menu_action') and self.tools_menu_action:
            self.tools_menu_action.setText(tr('menu_file', lang))
        if hasattr(self, 'run_test_action') and self.run_test_action:
            self.run_test_action.setText(tr('menu_run_test', lang))
        if hasattr(self, 'run_diagnostics_action') and self.run_diagnostics_action:
            self.run_diagnostics_action.setText(tr('menu_run_diagnostics', lang))
        if hasattr(self, 'editor_action') and self.editor_action:
            self.editor_action.setText(tr('menu_editor', lang))
        if hasattr(self, 'create_strategy_action') and self.create_strategy_action:
            self.create_strategy_action.setText(tr('menu_create_strategy', lang))
        if hasattr(self, 'create_bin_action') and self.create_bin_action:
            self.create_bin_action.setText(tr('menu_create_bin', lang))
        if hasattr(self, 'open_folder_menu') and self.open_folder_menu:
            self.open_folder_menu.setTitle(tr('menu_open_folder', lang))
        if hasattr(self, 'open_winws_folder_action') and self.open_winws_folder_action:
            self.open_winws_folder_action.setText(tr('menu_open_winws_folder', lang))
        if hasattr(self, 'open_config_folder_action') and self.open_config_folder_action:
            self.open_config_folder_action.setText(tr('menu_open_config_folder', lang))
        if hasattr(self, 'minimize_to_tray_action') and self.minimize_to_tray_action:
            self.minimize_to_tray_action.setText(tr('menu_minimize_to_tray', lang))
            # Активна только когда трей включён
            has_tray = bool(self.settings.get('show_in_tray', True) and hasattr(self, 'tray') and self.tray)
            self.minimize_to_tray_action.setEnabled(has_tray)
        if hasattr(self, 'quit_app_action') and self.quit_app_action:
            self.quit_app_action.setText(tr('menu_quit_app', lang))
        
        if hasattr(self, 'settings_menu_action') and self.settings_menu_action:
            self.settings_menu_action.setText(tr('menu_settings', lang))
        if hasattr(self, 'open_settings_action') and self.open_settings_action:
            self.open_settings_action.setText(tr('tray_program_parameters', lang))
        if hasattr(self, 'update_menu_action') and self.update_menu_action:
            self.update_menu_action.setText(tr('menu_update', lang))
        if hasattr(self, 'check_app_updates_action') and self.check_app_updates_action:
            self.check_app_updates_action.setText(tr('update_check_app', lang))
        if self.check_updates_action:
            self.check_updates_action.setText(tr('update_check_zapret', lang))
        if self.manual_update_action:
            self.manual_update_action.setText(tr('update_manual', lang))
        if hasattr(self, 'update_ipset_action') and self.update_ipset_action:
            self.update_ipset_action.setText(tr('update_ipset_list', lang))
        if hasattr(self, 'addons_menu_action') and self.addons_menu_action:
            self.addons_menu_action.setText(tr('menu_addons', lang))
        if hasattr(self, 'addons_action') and self.addons_action:
            self.addons_action.setText(tr('addons_title', lang))
        # Пункт Update Hosts File теперь отсутствует (функциональность перенесена в редактор)
        
        # Обновляем меню "Справка"
        if hasattr(self, 'help_menu_action') and self.help_menu_action:
            self.help_menu_action.setText(tr('menu_help', lang))
        if hasattr(self, 'open_github_action') and self.open_github_action:
            self.open_github_action.setText(tr('help_open_github', lang))
        if hasattr(self, 'open_github_zapret_action') and self.open_github_zapret_action:
            # Имя пользователя берём из настроек zapret_repo (owner/repo или URL)
            slug = getattr(self.zapret_updater, "github_repo", ZapretUpdater.GITHUB_REPO)
            slug = (slug or "").strip().strip("/")
            owner = "Flowseal"
            if slug:
                if slug.lower().startswith("http://") or slug.lower().startswith("https://"):
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(slug)
                        path = (parsed.path or "").strip("/ ")
                        parts = path.split("/")
                        if len(parts) >= 1 and parts[0]:
                            owner = parts[0]
                    except Exception:
                        owner = "Flowseal"
                else:
                    parts = slug.split("/", 1)
                    if parts and parts[0]:
                        owner = parts[0]
            self.open_github_zapret_action.setText(
                tr('help_open_github_zapret', lang).format(owner=owner)
            )
        
        # Синхронизируем кнопку и ComboBox с текущим состоянием запуска
        self._sync_run_state_ui()
        
        # Обновляем трей меню
        if hasattr(self, 'tray') and self.tray:
            self.tray.update_menu()
    
    def set_language(self, lang):
        """Устанавливает язык и обновляет интерфейс"""
        self.settings['language'] = lang
        self.config.set_setting('language', lang)
        self.retranslate_ui()
    
    def toggle_show_in_tray(self):
        """Переключает отображение в трее"""
        value = self.show_tray_action.isChecked()
        # Сохраняем настройку
        self.settings['show_in_tray'] = value
        self.config.set_setting('show_in_tray', value)
        # Применяем настройку
        if value:
            if hasattr(self, 'tray') and self.tray:
                self.tray.show()
        else:
            if hasattr(self, 'tray') and self.tray:
                self.tray.hide()
        # Обновляем доступность пункта "Свернуть окно" в меню Инструменты
        if hasattr(self, 'minimize_to_tray_action') and self.minimize_to_tray_action:
            has_tray = bool(self.settings.get('show_in_tray', True) and hasattr(self, 'tray') and self.tray)
            self.minimize_to_tray_action.setEnabled(has_tray)
    
    def toggle_close_winws(self):
        """Переключает настройку закрытия winws при выходе"""
        value = self.close_winws_action.isChecked()
        self.settings['close_winws_on_exit'] = value
        self.config.set_setting('close_winws_on_exit', value)
    
    def toggle_start_minimized(self):
        """Переключает настройку запуска свернутым"""
        value = self.start_minimized_action.isChecked()
        self.settings['start_minimized'] = value
        self.config.set_setting('start_minimized', value)
    
    def toggle_auto_start(self):
        """Переключает автозапуск последней стратегии"""
        value = self.auto_start_action.isChecked()
        self.settings['auto_start_last_strategy'] = value
        self.config.set_setting('auto_start_last_strategy', value)
    
    def toggle_auto_restart(self):
        """Переключает автоперезапуск стратегии"""
        value = self.auto_restart_action.isChecked()
        self.settings['auto_restart_strategy'] = value
        self.config.set_setting('auto_restart_strategy', value)
    
    def toggle_autostart(self):
        """Переключает автозапуск приложения с Windows"""
        if self.autostart_action.isChecked():
            if self.autostart_manager.enable():
                self.settings['autostart_enabled'] = True
                self.config.set_setting('autostart_enabled', True)
            else:
                # Если не удалось включить, снимаем галочку
                self.autostart_action.setChecked(False)
                lang = self.settings.get('language', 'ru')
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(tr('msg_autostart_enable_failed', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
        else:
            if self.autostart_manager.disable():
                self.settings['autostart_enabled'] = False
                self.config.set_setting('autostart_enabled', False)
    
    def show_settings_dialog(self):
        """Открывает диалоговое окно с настройками (отложено для корректного закрытия меню)"""
        # Если диалог уже открыт — просто активируем его
        if self._settings_dialog is not None and self._settings_dialog.isVisible():
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        # Если открытие уже запланировано/идёт — не дублируем
        if self._settings_dialog_opening:
            return
        self._settings_dialog_opening = True
        QTimer.singleShot(0, self._show_settings_dialog_impl)
    
    def _show_settings_dialog_impl(self):
        """Реализация открытия диалога настроек"""
        dialog = SettingsDialog(
            parent=self,
            settings=self.settings,
            config=self.config,
            autostart_manager=self.autostart_manager,
            zapret_updater=self.zapret_updater,
            winws_manager=self.winws_manager
        )
        self._settings_dialog = dialog
        
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            changes = dialog.get_settings_changes()
            
            # Применяем изменения
            # Язык
            if 'language' in changes:
                self.set_language(changes['language'])
            
            # Отображать в трее
            if 'show_in_tray' in changes:
                show_tray_value = changes['show_in_tray']
                self.settings['show_in_tray'] = show_tray_value
                self.config.set_setting('show_in_tray', show_tray_value)
                if show_tray_value:
                    if hasattr(self, 'tray') and self.tray:
                        self.tray.show()
                else:
                    if hasattr(self, 'tray') and self.tray:
                        self.tray.hide()
                # Обновляем доступность пункта "Свернуть окно" в меню Инструменты,
                # если настройки менялись через диалог
                if hasattr(self, 'minimize_to_tray_action') and self.minimize_to_tray_action:
                    has_tray = bool(show_tray_value and hasattr(self, 'tray') and self.tray)
                    self.minimize_to_tray_action.setEnabled(has_tray)
            
            # Запускать свернутым
            if 'start_minimized' in changes:
                self.settings['start_minimized'] = changes['start_minimized']
                self.config.set_setting('start_minimized', changes['start_minimized'])
            
            # Закрывать winws при выходе
            if 'close_winws_on_exit' in changes:
                self.settings['close_winws_on_exit'] = changes['close_winws_on_exit']
                self.config.set_setting('close_winws_on_exit', changes['close_winws_on_exit'])
            
            # Автозапуск с Windows
            if 'autostart_enabled' in changes:
                autostart_value = changes['autostart_enabled']
                if autostart_value != self.autostart_manager.is_enabled():
                    if autostart_value:
                        if not self.autostart_manager.enable():
                            lang = self.settings.get('language', 'ru')
                            msg = configure_message_box(QMessageBox(self))
                            msg.setWindowTitle(tr('msg_error', lang))
                            msg.setText(tr('msg_autostart_enable_failed', lang))
                            msg.setIcon(QMessageBox.Icon.Warning)
                            msg.exec()
                        else:
                            self.settings['autostart_enabled'] = True
                            self.config.set_setting('autostart_enabled', True)
                    else:
                        if not self.autostart_manager.disable():
                            lang = self.settings.get('language', 'ru')
                            msg = configure_message_box(QMessageBox(self))
                            msg.setWindowTitle(tr('msg_error', lang))
                            msg.setText(tr('msg_autostart_disable_failed', lang))
                            msg.setIcon(QMessageBox.Icon.Warning)
                            msg.exec()
                        else:
                            self.settings['autostart_enabled'] = False
                            self.config.set_setting('autostart_enabled', False)

            # Автозапуск последней стратегии
            if 'auto_start_last_strategy' in changes:
                self.settings['auto_start_last_strategy'] = changes['auto_start_last_strategy']
                self.config.set_setting('auto_start_last_strategy', changes['auto_start_last_strategy'])
            
            # Автоперезапуск стратегии
            if 'auto_restart_strategy' in changes:
                self.settings['auto_restart_strategy'] = changes['auto_restart_strategy']
                self.config.set_setting('auto_restart_strategy', changes['auto_restart_strategy'])
            
            # Добавлять /B при обновлении
            if 'add_b_flag_on_update' in changes:
                self.settings['add_b_flag_on_update'] = changes['add_b_flag_on_update']
                self.config.set_setting('add_b_flag_on_update', changes['add_b_flag_on_update'])
            
            # Проверка обновлений zapret
            if 'remove_check_updates' in changes:
                self.settings['remove_check_updates'] = changes['remove_check_updates']
                self.config.set_setting('remove_check_updates', changes['remove_check_updates'])
            
            # Game Filter
            if 'game_filter_enabled' in changes:
                try:
                    if changes['game_filter_enabled']:
                        self.winws_manager.enable_game_filter()
                    else:
                        self.winws_manager.disable_game_filter()
                    self.settings['game_filter_enabled'] = changes['game_filter_enabled']
                    self.config.set_setting('game_filter_enabled', changes['game_filter_enabled'])
                except Exception as e:
                    lang = self.settings.get('language', 'ru')
                    msg = configure_message_box(QMessageBox(self))
                    msg.setWindowTitle(tr('msg_error', lang))
                    msg.setText(str(e))
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.exec()
            
            # IPSet Filter
            if 'ipset_filter_mode' in changes:
                try:
                    self.winws_manager.set_ipset_mode(changes['ipset_filter_mode'])
                    self.settings['ipset_filter_mode'] = changes['ipset_filter_mode']
                    self.config.set_setting('ipset_filter_mode', changes['ipset_filter_mode'])
                except Exception as e:
                    lang = self.settings.get('language', 'ru')
                    msg = configure_message_box(QMessageBox(self))
                    msg.setWindowTitle(tr('msg_error', lang))
                    err = str(e)
                    if 'Backup' in err or 'backup' in err:
                        err = tr('msg_backup_not_found', lang)
                    msg.setText(err)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.exec()

            # Путь к папке winws
            if 'winws_path' in changes:
                self.settings['winws_path'] = changes['winws_path']
                self.config.set_setting('winws_path', changes['winws_path'])
                self.load_bat_files()

            # Автоперезапуск приложений
            if 'auto_restart_apps' in changes:
                self.settings['auto_restart_apps'] = changes['auto_restart_apps']
                self.config.set_setting('auto_restart_apps', changes['auto_restart_apps'])
        finally:
            self._settings_dialog = None
            self._settings_dialog_opening = False
    
    
    def minimize_to_tray(self):
        """Сворачивает окно в трей"""
        self.hide()
    
    def quit_application(self):
        """Полностью закрывает приложение"""
        # Если нужно закрыть winws при выходе
        if self.settings.get('close_winws_on_exit', True):
            self.stop_winws_process(silent=True)
        
        QApplication.quit()
    
    def check_app_updates(self):
        """Проверяет наличие обновлений программы ZapretDeskop"""
        lang = self.settings.get('language', 'ru')
        
        # Показываем окно проверки в стиле VS
        update_dialog = VSUpdateDialog(self, lang)
        update_dialog.set_status(tr('update_checking_app', lang))
        update_dialog.show()
        QApplication.processEvents()
        
        # Проверяем обновления
        update_info = self.app_updater.check_for_updates()
        update_dialog.close()

        if 'error' in update_info:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(update_info['error'])
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        if not update_info['has_update']:
            self.latest_available_version = None
            self.load_version_info()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_check_updates_title', lang))
            msg.setText(tr('update_not_found', lang))
            msg.setInformativeText(tr('update_current_version', lang).format(update_info["current_version"]))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            return

        self.latest_available_version = update_info['latest_version']
        self.load_version_info()
        # Есть обновление - спрашиваем пользователя
        reply = QMessageBox.question(
            self,
            tr('update_available_title', lang),
            tr('update_available_text_app', lang).format(update_info["latest_version"], update_info["current_version"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.download_and_install_app_update(update_info)
    
    def download_and_install_app_update(self, update_info):
        """Скачивает и устанавливает обновление программы"""
        lang = self.settings.get('language', 'ru')
        
        if not update_info.get('download_url'):
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('update_error_url_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        # Показываем окно обновления в стиле VS
        update_dialog = VSUpdateDialog(self, lang)
        update_dialog.set_status(tr('update_downloading', lang))
        update_dialog.show_cancel(False)
        update_dialog.show()
        QApplication.processEvents()
        
        last_progress_update = [0]
        def update_progress(value):
            update_dialog.set_progress(value)
            # Обновляем детали только каждые 5% для уменьшения нагрузки
            if value - last_progress_update[0] >= 5 or value >= 100:
                update_dialog.add_detail(f"{tr('update_downloading', lang)}: {value:.0f}%")
                last_progress_update[0] = value
            QApplication.processEvents()
            if update_dialog.is_cancelled():
                raise Exception("Обновление отменено пользователем")
        
        try:
            # Скачиваем обновление
            update_dialog.set_status(tr('update_downloading', lang))
            update_dialog.add_detail(f"{tr('update_downloading', lang)} {update_info['latest_version']}...")
            exe_path = self.app_updater.download_update(
                update_info['download_url'],
                progress_callback=update_progress
            )
            
            # Устанавливаем обновление
            update_dialog.set_status(tr('update_installing', lang))
            update_dialog.set_progress(90)
            update_dialog.add_detail(tr('update_installing', lang) + "...")
            QApplication.processEvents()
            
            self.app_updater.install_update(exe_path, update_info['latest_version'])
            
            update_dialog.set_progress(100)
            update_dialog.set_status(tr('update_completed', lang))
            update_dialog.add_detail(tr('update_completed_text_app', lang).format(update_info["latest_version"]))
            QApplication.processEvents()
            
            # Небольшая задержка чтобы пользователь увидел завершение
            import time
            start_time = time.time()
            while time.time() - start_time < 1.0:
                QApplication.processEvents()
                time.sleep(0.05)
            update_dialog.close()
            
            # Показываем сообщение об успехе и закрываем программу
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_completed', lang))
            msg.setText(tr('update_completed_text_app', lang).format(update_info["latest_version"]))
            msg.setInformativeText(tr('update_restart_required', lang))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
            # Закрываем программу (скрипт обновления запустит новую версию)
            QApplication.quit()
            
        except Exception as e:
            update_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('update_error_text', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()
    
    def check_zapret_updates(self):
        """Проверяет наличие обновлений стратегий zapret"""
        lang = self.settings.get('language', 'ru')
        
        # Показываем окно проверки в стиле VS
        update_dialog = VSUpdateDialog(self, lang)
        update_dialog.set_status(tr('update_checking', lang))
        update_dialog.show()
        QApplication.processEvents()
        
        # Проверяем обновления
        update_info = self.zapret_updater.check_for_updates()
        update_dialog.close()
        
        if 'error' in update_info:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(update_info['error'])
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        if not update_info['has_update']:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_check_updates_title', lang))
            msg.setText(tr('update_not_found', lang))
            msg.setInformativeText(tr('update_current_version', lang).format(update_info["current_version"]))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            return
        
        # Есть обновление - спрашиваем пользователя
        reply = QMessageBox.question(
            self,
            tr('update_available_title', lang),
            tr('update_available_text', lang).format(update_info["latest_version"], update_info["current_version"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.download_and_install_update(update_info)
    
    def download_and_install_update(self, update_info):
        """Скачивает и устанавливает обновление"""
        lang = self.settings.get('language', 'ru')
        
        if not update_info.get('download_url'):
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('update_error_url_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        # Сначала останавливаем winws.exe, если он запущен
        winws_running = False
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == 'winws.exe':
                        winws_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception:
            pass
        
        if winws_running:
            # Показываем диалог остановки
            stop_dialog = QMessageBox(self)
            stop_dialog.setWindowTitle(tr('update_stopping_winws', lang))
            stop_dialog.setText(tr('update_winws_running', lang))
            stop_dialog.setInformativeText(tr('update_winws_stop_required', lang))
            stop_dialog.setIcon(QMessageBox.Icon.Question)
            stop_dialog.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            stop_dialog.setDefaultButton(QMessageBox.StandardButton.Yes)
            
            reply = stop_dialog.exec()
            if reply == QMessageBox.StandardButton.Yes:
                # Останавливаем процесс
                self.stop_winws_process(silent=True)
                # Ждем немного, чтобы процесс точно завершился
                QApplication.processEvents()
                import time
                time.sleep(3)  # Увеличена задержка для полного освобождения файлов
                
                # Дополнительная проверка - ждем пока процесс точно завершится
                for i in range(10):
                    winws_still_running = False
                    try:
                        for proc in psutil.process_iter(['pid', 'name']):
                            try:
                                if proc.info['name'] and proc.info['name'].lower() == 'winws.exe':
                                    winws_still_running = True
                                    break
                            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                pass
                    except Exception:
                        pass
                    
                    if not winws_still_running:
                        break
                    time.sleep(0.5)
                    QApplication.processEvents()
            else:
                # Пользователь отменил остановку
                return
        
        # Показываем окно обновления в стиле VS
        update_dialog = VSUpdateDialog(self, lang)
        update_dialog.set_status(tr('update_downloading', lang))
        update_dialog.show_cancel(False)
        update_dialog.show()
        QApplication.processEvents()
        
        last_progress_update = [0]
        def update_progress(value):
            update_dialog.set_progress(value)
            # Обновляем детали только каждые 5% для уменьшения нагрузки
            if value - last_progress_update[0] >= 5 or value >= 100:
                update_dialog.add_detail(f"{tr('update_downloading', lang)}: {value:.0f}%")
                last_progress_update[0] = value
            QApplication.processEvents()
            if update_dialog.is_cancelled():
                raise Exception("Обновление отменено пользователем")
        
        try:
            # Скачиваем обновление
            update_dialog.set_status(tr('update_downloading', lang))
            update_dialog.add_detail(f"{tr('update_downloading', lang)} {update_info['latest_version']}...")
            zip_path = self.zapret_updater.download_update(
                update_info['download_url'],
                progress_callback=update_progress
            )
            
            # Устанавливаем обновление
            update_dialog.set_status(tr('update_installing', lang))
            update_dialog.set_progress(90)
            update_dialog.add_detail(tr('update_installing', lang) + "...")
            QApplication.processEvents()
            
            self.zapret_updater.extract_and_update(zip_path, update_info['latest_version'])
            
            update_dialog.set_progress(100)
            update_dialog.set_status(tr('update_completed', lang))
            update_dialog.add_detail(tr('update_completed_text', lang).format(update_info["latest_version"]))
            QApplication.processEvents()
            
            # Небольшая задержка чтобы пользователь увидел завершение
            import time
            start_time = time.time()
            while time.time() - start_time < 1.0:
                QApplication.processEvents()
                time.sleep(0.05)
            update_dialog.close()
            
            # Обновляем список стратегий в ComboBox
            current_strategy = self._get_selected_strategy_name()
            self.combo_box.clear()
            self.load_bat_files()
            # Восстанавливаем выбранную стратегию, если она еще существует
            index = self._find_combo_index_by_data(current_strategy)
            if index >= 0:
                self.combo_box.setCurrentIndex(index)
            
            # Если включена настройка "Добавлять /B при обновлении", добавляем /B флаг
            if self.settings.get('add_b_flag_on_update', False):
                self.add_b_flag_to_all_strategies(silent=True)
            
            # Если включена настройка "Удалять проверку обновлений", удаляем строку check_updates
            if self.settings.get('remove_check_updates', False):
                self.remove_check_updates_from_all_strategies(silent=True)
            
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_completed', lang))
            msg.setText(tr('update_completed_text', lang).format(update_info["latest_version"]))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
        except Exception as e:
            update_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('update_error_text', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()
    
    def _show_addons_dialog(self):
        """Открывает окно «Дополнения»."""
        d = AddonsDialog(self, self.settings)
        d.exec()
    
    def _parse_github_repo(self, url):
        """Из URL вида https://github.com/owner/repo или https://github.com/owner/repo/ извлекает (owner, repo)."""
        if not url:
            return None, None
        url = url.strip().rstrip('/')
        m = re.match(r'https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)', url, re.IGNORECASE)
        if m:
            return m.group(1), m.group(2)
        return None, None
    
    def on_addon_download(self, name, url, mode="full"):
        """Скачивает дополнение: для основного репозитория запрашивает обновление zapret,
        для остальных — скачивает релиз GitHub в winws.

        mode: 'full' | 'lists' | 'strategies' | 'bin' (зарезервировано под будущие режимы установки).
        """
        lang = self.settings.get('language', 'ru')
        owner, repo = self._parse_github_repo(url)
        if not owner or not repo:
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('addons_error_download', lang).format('Некорректная ссылка на GitHub'))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        repo_slug = f"{owner}/{repo}"
        # Если это тот же репозиторий, что используется для zapret‑обновлений — запускаем стандартную проверку
        if repo_slug.lower() == getattr(self.zapret_updater, "github_repo", ZapretUpdater.GITHUB_REPO).lower():
            self.check_zapret_updates()
            return
        self._download_addon_from_github(lang, name, owner, repo, mode)
    
    def _download_addon_from_github(self, lang, name, owner, repo, mode="full"):
        """Скачивает последний релиз/архив GitHub и распаковывает его в winws.

        mode:
          - full/strategies/bin: передаётся в zapret_updater (пока обрабатывается как полная установка)
          - lists: обновляет только winws\\lists (list-*.txt, ipset-*.txt и т.п.)
        """
        winws_running = False
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == 'winws.exe':
                        winws_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception:
            pass
        if winws_running:
            reply = QMessageBox.question(
                self,
                tr('update_stopping_winws', lang),
                tr('update_winws_running', lang) + '\n' + tr('update_winws_stop_required', lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_winws_process(silent=True)
                QApplication.processEvents()
                import time
                time.sleep(3)
            else:
                return
        update_dialog = VSUpdateDialog(self, lang)
        update_dialog.set_status(tr('update_downloading', lang))
        update_dialog.show_cancel(False)
        update_dialog.show()
        QApplication.processEvents()
        try:
            download_url = None
            # Сначала пытаемся взять последний релиз
            api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
            r = requests.get(api_url, timeout=15)
            if r.status_code == 404:
                # У репозитория нет релизов — падаем обратно на архив ветки по умолчанию
                repo_api = f"https://api.github.com/repos/{owner}/{repo}"
                r_repo = requests.get(repo_api, timeout=15)
                r_repo.raise_for_status()
                repo_data = r_repo.json()
                default_branch = (repo_data.get("default_branch") or "main").strip()
                if not default_branch:
                    default_branch = "main"
                download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"
            else:
                r.raise_for_status()
                data = r.json()
                for asset in data.get('assets', []):
                    if asset.get('name', '').endswith('.zip'):
                        download_url = asset.get('browser_download_url')
                        break
                # Если в релизе нет zip‑ассетов, тоже пробуем архив ветки по умолчанию
                if not download_url:
                    repo_api = f"https://api.github.com/repos/{owner}/{repo}"
                    r_repo = requests.get(repo_api, timeout=15)
                    r_repo.raise_for_status()
                    repo_data = r_repo.json()
                    default_branch = (repo_data.get("default_branch") or "main").strip()
                    if not default_branch:
                        default_branch = "main"
                    download_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/{default_branch}.zip"

            if not download_url:
                update_dialog.close()
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('update_error_title', lang))
                msg.setText(tr('addons_error_no_zip', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
                return
            last_progress = [0]
            def progress_cb(value):
                update_dialog.set_progress(value)
                QApplication.processEvents()
            zip_path = self.zapret_updater.download_update(download_url, progress_callback=progress_cb)
            update_dialog.set_status(tr('update_installing', lang))
            QApplication.processEvents()

            # Режим "списки": обновляем только winws\lists, не требуем .bat в архиве
            if mode == "lists":
                self._install_lists_from_zip(zip_path, lang)
            else:
                # Для full/strategies/bin пока используем стандартную логику zapret_updater
                self.zapret_updater.extract_zip_to_winws(zip_path)
            update_dialog.close()
            current_strategy = self._get_selected_strategy_name()
            self.combo_box.clear()
            self.load_bat_files()
            idx = self._find_combo_index_by_data(current_strategy)
            if idx >= 0:
                self.combo_box.setCurrentIndex(idx)
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_completed', lang))
            msg.setText(tr('addons_success', lang))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        except Exception as e:
            update_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('addons_error_download', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()

    def _install_lists_from_zip(self, zip_path, lang):
        """Устанавливает только списки (txt-файлы) из архива в winws\\lists."""
        import zipfile
        winws_folder = get_winws_path()
        lists_folder = os.path.join(winws_folder, "lists")
        os.makedirs(lists_folder, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    name = info.filename.replace("\\", "/")
                    if not name.lower().endswith(".txt"):
                        continue
                    base = name.split("/")[-1]
                    dest_path = os.path.join(lists_folder, base)
                    try:
                        with zf.open(info, "r") as src, open(dest_path, "wb") as dst:
                            dst.write(src.read())
                    except Exception:
                        continue
        except Exception as e:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('addons_error_download', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()
    
    def manual_update_strategies(self):
        """Обновляет стратегии вручную из выбранного архива"""
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        
        # Проверяем, запущен ли winws.exe
        winws_running = False
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == 'winws.exe':
                        winws_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception:
            pass
        
        if winws_running:
            reply = QMessageBox.question(
                self,
                tr('update_stopping_winws', lang),
                tr('update_winws_running', lang) + '\n' + tr('update_winws_stop_required', lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_winws_process(silent=True)
                import time
                time.sleep(2)
            else:
                return
        
        # Открываем диалог выбора файла
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle(tr('update_manual_select_archive', lang))
        file_dialog.setNameFilter('ZIP файлы (*.zip);;Все файлы (*.*)')
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        
        if not file_dialog.exec():
            return
        
        selected_files = file_dialog.selectedFiles()
        if not selected_files:
            return
        
        archive_path = selected_files[0]
        
        # Показываем прогресс
        progress_dialog = QProgressDialog(self)
        progress_dialog.setWindowTitle(tr('update_manual_title', lang))
        progress_dialog.setLabelText(tr('update_manual_extracting', lang))
        progress_dialog.setRange(0, 0)
        progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # Распаковываем архив
            self.extract_archive_to_winws(archive_path, winws_folder)
            
            progress_dialog.close()
            
            # Обновляем список стратегий в ComboBox
            current_strategy = self._get_selected_strategy_name()
            self.combo_box.clear()
            self.load_bat_files()
            # Восстанавливаем выбранную стратегию, если она еще существует
            index = self._find_combo_index_by_data(current_strategy)
            if index >= 0:
                self.combo_box.setCurrentIndex(index)
            
            # Если включена настройка "Добавлять /B при обновлении", добавляем /B флаг
            if self.settings.get('add_b_flag_on_update', False):
                self.add_b_flag_to_all_strategies(silent=True)
            
            # Если включена настройка "Удалять проверку обновлений", удаляем строку check_updates
            if self.settings.get('remove_check_updates', False):
                self.remove_check_updates_from_all_strategies(silent=True)
            
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_completed', lang))
            msg.setText(tr('update_manual_completed', lang))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
        except Exception as e:
            progress_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_error_title', lang))
            msg.setText(tr('update_error_text', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()
    
    def extract_archive_to_winws(self, archive_path, winws_folder):
        """Распаковывает архив (ZIP или RAR) в папку winws"""
        import time
        import zipfile
        import shutil
        
        # Нормализуем пути до абсолютных
        winws_folder = os.path.abspath(winws_folder)
        archive_path = os.path.abspath(archive_path)
        
        # Создаем резервную копию
        backup_folder = f"{winws_folder}_backup"
        if os.path.exists(winws_folder):
            if os.path.exists(backup_folder):
                shutil.rmtree(backup_folder)
            shutil.copytree(winws_folder, backup_folder)
        
        # Ждем немного для освобождения файлов
        time.sleep(1)
        
        # Определяем тип архива
        archive_ext = os.path.splitext(archive_path)[1].lower()
        
        # Создаем временную папку для распаковки
        winws_parent = os.path.dirname(winws_folder) or os.getcwd()
        temp_extract = os.path.join(winws_parent, 'temp_manual_extract')
        if os.path.exists(temp_extract):
            shutil.rmtree(temp_extract)
        os.makedirs(temp_extract, exist_ok=True)
        
        try:
            if archive_ext == '.zip':
                # Распаковываем ZIP
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract)
            else:
                raise Exception(f'Неподдерживаемый формат архива: {archive_ext}. Поддерживается только ZIP формат.')
            
            # Ищем папку winws или .bat файлы в распакованном архиве
            winws_source = None
            
            # Сначала ищем папку winws
            for root, dirs, files in os.walk(temp_extract):
                if 'winws' in dirs:
                    winws_source = os.path.join(root, 'winws')
                    break
            
            # Если папки winws нет, ищем .bat файлы
            if not winws_source:
                bat_files_found = []
                for root, dirs, files in os.walk(temp_extract):
                    for file in files:
                        if file.endswith('.bat'):
                            bat_files_found.append((root, file))
                
                if bat_files_found:
                    # Определяем общую папку для всех .bat файлов
                    first_bat_dir = bat_files_found[0][0]
                    all_same_dir = all(dir_path == first_bat_dir for dir_path, _ in bat_files_found)
                    if all_same_dir:
                        winws_source = first_bat_dir
                    else:
                        winws_source = temp_extract
            
            if not winws_source:
                raise Exception('Не найдены .bat файлы или папка winws в архиве')
            
            # Обновляем файлы по одному
            if os.path.isdir(winws_source):
                # Нормализуем путь источника до абсолютного
                winws_source = os.path.abspath(winws_source)
                
                # Создаем папку winws если её нет
                if not os.path.exists(winws_folder):
                    os.makedirs(winws_folder, exist_ok=True)
                
                # Рекурсивно копируем все файлы и папки из winws_source в winws_folder
                def copy_tree(src, dst):
                    """Рекурсивно копирует дерево файлов и папок"""
                    src = os.path.abspath(src)
                    dst = os.path.abspath(dst)
                    
                    if os.path.isdir(src):
                        # Если папка назначения существует, удаляем её содержимое
                        if os.path.exists(dst):
                            # Удаляем существующую папку и её содержимое
                            for attempt in range(5):
                                try:
                                    shutil.rmtree(dst)
                                    break
                                except (PermissionError, OSError):
                                    if attempt < 4:
                                        time.sleep(0.5)
                                    else:
                                        raise
                        # Создаем папку назначения
                        os.makedirs(dst, exist_ok=True)
                        # Копируем содержимое папки
                        for item in os.listdir(src):
                            src_item = os.path.join(src, item)
                            dst_item = os.path.join(dst, item)
                            copy_tree(src_item, dst_item)
                    else:
                        # Копируем файл
                        # Сначала создаем родительские папки если нужно
                        parent_dir = os.path.dirname(dst)
                        if parent_dir:
                            os.makedirs(parent_dir, exist_ok=True)
                        # Удаляем существующий файл если есть
                        if os.path.exists(dst):
                            for attempt in range(5):
                                try:
                                    os.remove(dst)
                                    break
                                except (PermissionError, OSError):
                                    if attempt < 4:
                                        time.sleep(0.5)
                                    else:
                                        raise
                        shutil.copy2(src, dst)
                
                # Копируем все содержимое
                for item in os.listdir(winws_source):
                    src_item = os.path.join(winws_source, item)
                    dst_item = os.path.join(winws_folder, item)
                    copy_tree(src_item, dst_item)
            
            # Очищаем временные файлы
            try:
                shutil.rmtree(temp_extract)
            except Exception:
                pass
                
        except Exception as e:
            # Восстанавливаем из резервной копии при ошибке
            if os.path.exists(backup_folder):
                if os.path.exists(winws_folder):
                    try:
                        shutil.rmtree(winws_folder)
                    except Exception:
                        pass
                # Используем рекурсивное копирование вместо copytree
                os.makedirs(winws_folder, exist_ok=True)
                for item in os.listdir(backup_folder):
                    src_item = os.path.join(backup_folder, item)
                    dst_item = os.path.join(winws_folder, item)
                    if os.path.isdir(src_item):
                        shutil.copytree(src_item, dst_item)
                    else:
                        shutil.copy2(src_item, dst_item)
            raise
    
    def toggle_add_b_flag_on_update(self):
        """Переключает настройку добавления /B флага при обновлении"""
        value = self.add_b_flag_on_update_action.isChecked()
        self.settings['add_b_flag_on_update'] = value
        self.config.set_setting('add_b_flag_on_update', value)
    
    def show_test_window(self):
        """Открывает окно тестирования стратегий"""
        # Передаем None, чтобы TestWindow сам определил правильный путь
        test_window = TestWindow(self, winws_folder=None)
        test_window.exec()
    
    def show_editor(self):
        """Открывает объединённый редактор (списки, drivers\\etc, стратегии)"""
        w = get_unified_editor_window(self, initial_tab=0)
        w.show()
        w.raise_()
        w.activateWindow()

    def show_bin_creator(self):
        """Открывает диалог создания bin-файлов (winws/bin/*.bin)."""
        lang = self.settings.get('language', 'ru')
        dlg = BinCreatorDialog(self, language=lang)
        dlg.exec()
    
    def show_strategy_creator(self):
        """Открывает окно создания стратегий"""
        from src.dialogs.strategy_creator_window import RuleDialog
        dialog = RuleDialog(self)
        if dialog.exec():
            # Обновляем список стратегий в комбобоксе после создания новой
            self.load_bat_files()
    
    def run_diagnostics(self):
        """Запускает диагностику системы, выполняя все проверки из service.bat"""
        lang = self.settings.get('language', 'ru')
        dialog = StandardDialog(
            parent=self,
            title=tr('menu_run_diagnostics', lang),
            width=700,
            height=500,
            icon=get_app_icon(),
            theme="dark"
        )
        
        # Устанавливаем отступы для content_layout
        content_layout = dialog.getContentLayout()
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)
        
        # Текстовое поле для результатов
        text_edit = ContextTextEdit()
        text_edit.setStyleSheet('border: 1px solid #2b2b2b;')
       
        text_edit.setReadOnly(True)
        content_layout.addWidget(text_edit)
        
        # Добавляем меню "Экспорт" в title_bar
        menu_bar = QMenuBar()
        menu_bar.setNativeMenuBar(False)
        
        # Меню "Экспорт" c кастомным StyleMenu
        export_menu = StyleMenu(dialog)
        export_menu.setTitle(tr('export_menu_title', lang))
        menu_bar.addMenu(export_menu)
        
        # Действия для экспорта
        export_txt = QAction(tr('export_txt', lang), dialog)
        export_txt.triggered.connect(lambda: self._export_diagnostics_text(text_edit, lang))
        export_menu.addAction(export_txt)
        
        export_csv = QAction(tr('export_csv', lang), dialog)
        export_csv.triggered.connect(lambda: self._export_diagnostics_csv(text_edit, lang))
        export_menu.addAction(export_csv)
        
        export_json = QAction(tr('export_json', lang), dialog)
        export_json.triggered.connect(lambda: self._export_diagnostics_json(text_edit, lang))
        export_menu.addAction(export_json)
        
        # Добавляем QMenuBar в левую часть кастомного title bar
        if hasattr(dialog, "title_bar"):
            dialog.title_bar.addLeftWidget(menu_bar)
        
        # Добавляем начальное сообщение
        
        text_edit.append(tr('diag_running', lang))
        QApplication.processEvents()
        
        results = []
        
        # 1. Base Filtering Engine
        try:
            result = subprocess.run(['sc', 'query', 'BFE'], capture_output=True, text=True, timeout=5)
            if 'RUNNING' in result.stdout:
                results.append(("✓", tr('diag_bfe_passed', lang)))
            else:
                results.append(("✗", tr('diag_bfe_failed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_bfe', lang).format(str(e))))
        
        # 2. Proxy check
        try:
            import winreg
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
                proxy_enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
                if proxy_enable:
                    proxy_server, _ = winreg.QueryValueEx(key, "ProxyServer")
                    results.append(("?", tr('diag_proxy_enabled', lang).format(proxy_server)))
                    results.append(("?", tr('diag_proxy_check_proxy', lang)))
                else:
                    results.append(("✓", tr('diag_proxy_passed', lang)))
                winreg.CloseKey(key)
            except FileNotFoundError:
                results.append(("✓", tr('diag_proxy_passed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_proxy', lang).format(str(e))))
        
        # 3. TCP timestamps check
        try:
            result = subprocess.run(['netsh', 'interface', 'tcp', 'show', 'global'], 
                                  capture_output=True, text=True, timeout=5)
            if 'timestamps' in result.stdout.lower() and 'enabled' in result.stdout.lower():
                results.append(("✓", tr('diag_tcp_passed', lang)))
            else:
                results.append(("?", tr('diag_tcp_disabled', lang)))
                enable_result = subprocess.run(['netsh', 'interface', 'tcp', 'set', 'global', 'timestamps=enabled'],
                                              capture_output=True, text=True, timeout=5)
                if enable_result.returncode == 0:
                    results.append(("✓", tr('diag_tcp_enabled', lang)))
                else:
                    results.append(("✗", tr('diag_tcp_failed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_tcp', lang).format(str(e))))
        
        # 4. AdguardSvc.exe
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() == 'adguardsvc.exe':
                    results.append(("✗", tr('diag_adguard_found', lang)))
                    results.append(("✗", "https://github.com/Flowseal/zapret-discord-youtube/issues/417"))
                    break
            else:
                results.append(("✓", tr('diag_adguard_passed', lang)))
        except Exception:
            results.append(("✓", tr('diag_adguard_passed', lang)))
        
        # 5. Killer services
        try:
            result = subprocess.run(['sc', 'query'], capture_output=True, text=True, timeout=5)
            if 'Killer' in result.stdout:
                results.append(("✗", tr('diag_killer_found', lang)))
                results.append(("✗", "https://github.com/Flowseal/zapret-discord-youtube/issues/2512#issuecomment-2821119513"))
            else:
                results.append(("✓", tr('diag_killer_passed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_killer', lang).format(str(e))))
        
        # 6. Intel Connectivity Network Service
        try:
            result = subprocess.run(['sc', 'query'], capture_output=True, text=True, timeout=5)
            if 'Intel' in result.stdout and 'Connectivity' in result.stdout and 'Network' in result.stdout:
                results.append(("✗", tr('diag_intel_found', lang)))
                results.append(("✗", "https://github.com/ValdikSS/GoodbyeDPI/issues/541#issuecomment-2661670982"))
            else:
                results.append(("✓", tr('diag_intel_passed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_intel', lang).format(str(e))))
        
        # 7. Check Point
        try:
            result = subprocess.run(['sc', 'query'], capture_output=True, text=True, timeout=5)
            checkpoint_found = 'TracSrvWrapper' in result.stdout or 'EPWD' in result.stdout
            if checkpoint_found:
                results.append(("✗", tr('diag_checkpoint_found', lang)))
                results.append(("✗", tr('diag_checkpoint_uninstall', lang)))
            else:
                results.append(("✓", tr('diag_checkpoint_passed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_checkpoint', lang).format(str(e))))
        
        # 8. SmartByte
        try:
            result = subprocess.run(['sc', 'query'], capture_output=True, text=True, timeout=5)
            if 'SmartByte' in result.stdout:
                results.append(("✗", tr('diag_smartbyte_found', lang)))
                results.append(("✗", tr('diag_smartbyte_uninstall', lang)))
            else:
                results.append(("✓", tr('diag_smartbyte_passed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_smartbyte', lang).format(str(e))))
        
        # 9. WinDivert64.sys file
        try:
            winws_folder = get_winws_path()
            bin_path = os.path.join(winws_folder, 'bin')
            sys_files = [f for f in os.listdir(bin_path) if f.endswith('.sys')] if os.path.exists(bin_path) else []
            if not sys_files:
                results.append(("✗", tr('diag_windivert_not_found', lang)))
            else:
                results.append(("✓", tr('diag_windivert_found', lang).format(', '.join(sys_files))))
        except Exception as e:
            results.append(("?", tr('diag_error_windivert', lang).format(str(e))))
        
        # 10. VPN services
        try:
            result = subprocess.run(['sc', 'query'], capture_output=True, text=True, timeout=5)
            if 'VPN' in result.stdout:
                vpn_services = []
                for line in result.stdout.split('\n'):
                    if 'VPN' in line:
                        parts = line.split(':')
                        if len(parts) > 1:
                            vpn_services.append(parts[1].strip())
                if vpn_services:
                    results.append(("?", tr('diag_vpn_found', lang).format(', '.join(vpn_services))))
                    results.append(("?", tr('diag_vpn_disable', lang)))
                else:
                    results.append(("✓", tr('diag_vpn_passed', lang)))
            else:
                results.append(("✓", tr('diag_vpn_passed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_vpn', lang).format(str(e))))
        
        # 11. DNS (DoH check)
        try:
            ps_cmd = "Get-ChildItem -Recurse -Path 'HKLM:System\\CurrentControlSet\\Services\\Dnscache\\InterfaceSpecificParameters\\' -ErrorAction SilentlyContinue | Get-ItemProperty -ErrorAction SilentlyContinue | Where-Object { $_.DohFlags -gt 0 } | Measure-Object | Select-Object -ExpandProperty Count"
            result = subprocess.run(['powershell', '-Command', ps_cmd], capture_output=True, text=True, timeout=10)
            doh_found = result.stdout.strip().isdigit() and int(result.stdout.strip()) > 0
            if not doh_found:
                results.append(("?", tr('diag_dns_configure', lang)))
                results.append(("?", tr('diag_dns_win11', lang)))
            else:
                results.append(("✓", tr('diag_secure_dns_passed', lang)))
        except Exception:
            results.append(("?", tr('diag_dns_unknown', lang)))
        
        # 12. WinDivert conflict
        try:
            winws_running = False
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() == 'winws.exe':
                    winws_running = True
                    break
            
            windivert_running = False
            try:
                result = subprocess.run(['sc', 'query', 'WinDivert'], capture_output=True, text=True, timeout=5)
                windivert_running = 'RUNNING' in result.stdout or 'STOP_PENDING' in result.stdout
            except:
                pass
            
            if not winws_running and windivert_running:
                results.append(("?", tr('diag_windivert_attempt', lang)))
                try:
                    subprocess.run(['net', 'stop', 'WinDivert'], capture_output=True, timeout=5)
                    subprocess.run(['sc', 'delete', 'WinDivert'], capture_output=True, timeout=5)
                    result = subprocess.run(['sc', 'query', 'WinDivert'], capture_output=True, text=True, timeout=5)
                    if result.returncode != 0:
                        results.append(("✓", tr('diag_windivert_removed', lang)))
                    else:
                        results.append(("✗", tr('diag_windivert_delete_failed', lang)))
                except Exception as e:
                    results.append(("✗", tr('diag_windivert_error', lang).format(str(e))))
            else:
                results.append(("✓", tr('diag_windivert_conflict_passed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_windivert_conflict', lang).format(str(e))))
        
        # 13. Проверка статуса службы zapret
        try:
            result = subprocess.run(['sc', 'query', 'zapret'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                if 'RUNNING' in result.stdout:
                    results.append(("✓", tr('diag_zapret_running', lang)))
                    # Пытаемся получить информацию о стратегии из реестра
                    try:
                        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"System\CurrentControlSet\Services\zapret")
                        strategy_path, _ = winreg.QueryValueEx(key, "zapret-discord-youtube")
                        results.append(("✓", tr('diag_zapret_strategy', lang).format(strategy_path)))
                        winreg.CloseKey(key)
                    except:
                        pass
                elif 'STOPPED' in result.stdout:
                    results.append(("?", tr('diag_zapret_stopped', lang)))
                else:
                    results.append(("?", tr('diag_zapret_unknown', lang)))
            else:
                results.append(("?", tr('diag_zapret_not_installed', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_zapret', lang).format(str(e))))
        
        # 14. Проверка запущен ли winws.exe
        try:
            winws_running = False
            winws_pid = None
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'] and proc.info['name'].lower() == 'winws.exe':
                    winws_running = True
                    winws_pid = proc.info['pid']
                    break
            
            if winws_running:
                results.append(("✓", tr('diag_winws_running', lang).format(winws_pid)))
            else:
                results.append(("?", tr('diag_winws_not_running', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_winws', lang).format(str(e))))
        
        # 15. Проверка версии Windows и архитектуры
        try:
            import platform
            windows_version = platform.version()
            windows_release = platform.release()
            architecture = platform.machine()
            results.append(("✓", tr('diag_windows_version', lang).format(windows_release, windows_version, architecture)))
        except Exception as e:
            results.append(("?", tr('diag_error_windows', lang).format(str(e))))
        
        # 16. Проверка прав администратора
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            if is_admin:
                results.append(("✓", tr('diag_admin_yes', lang)))
            else:
                results.append(("✗", tr('diag_admin_no', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_admin', lang).format(str(e))))
        
        # 17. Проверка наличия файлов стратегий
        try:
            winws_folder = get_winws_path()
            strategies_path = os.path.join(winws_folder, 'strategies')
            if os.path.exists(strategies_path):
                bat_files = [f for f in os.listdir(strategies_path) if f.endswith('.bat')]
                if bat_files:
                    results.append(("✓", tr('diag_strategies_found', lang).format(len(bat_files))))
                else:
                    results.append(("?", tr('diag_strategies_empty', lang)))
            else:
                results.append(("?", tr('diag_strategies_not_found', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_strategies', lang).format(str(e))))
        
        # 18. Проверка DNS серверов
        try:
            result = subprocess.run(['ipconfig', '/all'], capture_output=True, text=True, timeout=5)
            dns_servers = []
            for line in result.stdout.split('\n'):
                if 'DNS Servers' in line or 'DNS-серверы' in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        dns = parts[1].strip()
                        if dns and dns not in dns_servers:
                            dns_servers.append(dns)
            if dns_servers:
                results.append(("✓", tr('diag_dns_servers', lang).format(', '.join(dns_servers[:3]))))
            else:
                results.append(("?", tr('diag_dns_not_detected', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_dns', lang).format(str(e))))
        
        # 19. Проверка сетевых адаптеров
        try:
            result = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=5)
            adapters = []
            current_adapter = None
            for line in result.stdout.split('\n'):
                if 'adapter' in line.lower() or 'адаптер' in line.lower():
                    if current_adapter:
                        adapters.append(current_adapter)
                    current_adapter = line.strip()
            if current_adapter:
                adapters.append(current_adapter)
            if adapters:
                results.append(("✓", tr('diag_adapters_found', lang).format(len(adapters))))
            else:
                results.append(("?", tr('diag_adapters_not_detected', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_adapters', lang).format(str(e))))
        
        # 20. Проверка наличия файла targets.txt
        try:
            winws_folder = get_winws_path()
            targets_path = os.path.join(winws_folder, 'utils', 'targets.txt')
            if os.path.exists(targets_path):
                with open(targets_path, 'r', encoding='utf-8') as f:
                    targets_count = len([line for line in f if line.strip()])
                results.append(("✓", tr('diag_targets_found', lang).format(targets_count)))
            else:
                results.append(("?", tr('diag_targets_not_found', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_targets', lang).format(str(e))))
        
        # 21. Проверка наличия файла hosts
        try:
            hosts_path = r"C:\Windows\System32\drivers\etc\hosts"
            if os.path.exists(hosts_path):
                with open(hosts_path, 'r', encoding='utf-8', errors='ignore') as f:
                    hosts_lines = [line for line in f if line.strip() and not line.strip().startswith('#')]
                results.append(("✓", tr('diag_hosts_found', lang).format(len(hosts_lines))))
            else:
                results.append(("✗", tr('diag_hosts_not_found', lang)))
        except Exception as e:
            results.append(("?", tr('diag_error_hosts', lang).format(str(e))))
        
        # Отображаем результаты
        for status, message in results:
            if status == "✓":
                text_edit.setTextColor(QColor(0, 128, 0))  # Зеленый
            elif status == "✗":
                text_edit.setTextColor(QColor(255, 0, 0))  # Красный
            else:
                text_edit.setTextColor(QColor(255, 165, 0))  # Оранжевый
            text_edit.append(f"{status} {message}")
            QApplication.processEvents()
        
        text_edit.setTextColor(QColor(0, 0, 0))  # Черный для остального текста
        text_edit.append(tr('diag_completed', lang))
        
        dialog.exec()
    
    def _export_diagnostics_text(self, text_edit, lang):
        """Экспортирует результаты диагностики в TXT формат"""
        content = text_edit.toPlainText()
        if not content.strip():
            QMessageBox.information(self, tr('export_menu_title', lang), tr('export_no_data', lang))
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"diagnostics_{timestamp}.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr('export_menu_title', lang),
            default_filename,
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                QMessageBox.information(self, tr('export_menu_title', lang), tr('export_success', lang).format(file_path))
            except Exception as e:
                QMessageBox.critical(self, tr('export_error_title', lang), tr('export_error', lang).format(str(e)))
    
    def _export_diagnostics_csv(self, text_edit, lang):
        """Экспортирует результаты диагностики в CSV формат"""
        content = text_edit.toPlainText()
        if not content.strip():
            QMessageBox.information(self, tr('export_menu_title', lang), tr('export_no_data', lang))
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"diagnostics_{timestamp}.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr('export_menu_title', lang),
            default_filename,
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
                    writer.writerow(["Status", "Message"])
                    # Парсим содержимое и экспортируем построчно
                    for line in content.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        # Извлекаем статус и сообщение
                        if line.startswith('✓'):
                            status = "PASS"
                            message = line[1:].strip()
                        elif line.startswith('✗'):
                            status = "FAIL"
                            message = line[1:].strip()
                        elif line.startswith('?'):
                            status = "WARNING"
                            message = line[1:].strip()
                        else:
                            status = "INFO"
                            message = line
                        writer.writerow([status, message])
                QMessageBox.information(self, tr('export_menu_title', lang), tr('export_success', lang).format(file_path))
            except Exception as e:
                QMessageBox.critical(self, tr('export_error_title', lang), tr('export_error', lang).format(str(e)))
    
    def _export_diagnostics_json(self, text_edit, lang):
        """Экспортирует результаты диагностики в JSON формат"""
        content = text_edit.toPlainText()
        if not content.strip():
            QMessageBox.information(self, tr('export_menu_title', lang), tr('export_no_data', lang))
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"diagnostics_{timestamp}.json"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr('export_menu_title', lang),
            default_filename,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            try:
                json_data = {
                    "export_date": datetime.now().isoformat(),
                    "diagnostics": []
                }
                
                # Парсим содержимое и экспортируем построчно
                for line in content.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    # Извлекаем статус и сообщение
                    if line.startswith('✓'):
                        status = "PASS"
                        message = line[1:].strip()
                    elif line.startswith('✗'):
                        status = "FAIL"
                        message = line[1:].strip()
                    elif line.startswith('?'):
                        status = "WARNING"
                        message = line[1:].strip()
                    else:
                        status = "INFO"
                        message = line
                    json_data["diagnostics"].append({
                        "status": status,
                        "message": message
                    })
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                QMessageBox.information(self, tr('export_menu_title', lang), tr('export_success', lang).format(file_path))
            except Exception as e:
                QMessageBox.critical(self, tr('export_error_title', lang), tr('export_error', lang).format(str(e)))
    
    def add_b_flag_to_all_strategies(self, silent=False):
        """Добавляет /B флаг во все .bat файлы стратегий
        
        Args:
            silent: Если True, не показывает диалоги подтверждения и результатов
        """
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        
        if not os.path.exists(winws_folder):
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_winws_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        # Ищем все .bat файлы
        bat_files = []
        for filename in os.listdir(winws_folder):
            if filename.endswith('.bat') and os.path.isfile(os.path.join(winws_folder, filename)):
                bat_files.append(filename)
        
        if not bat_files:
            if not silent:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_information', lang))
                msg.setText(tr('msg_no_bat_to_process', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
            return
        
        # Подтверждение (только если не silent режим)
        if not silent:
            old_s = 'start "zapret: %~n0" /min'
            new_s = 'start "zapret: %~n0" /B /min'
            reply = QMessageBox.question(
                self,
                tr('msg_add_b_flag_title', lang),
                tr('msg_add_b_flag_text', lang).format(len(bat_files), old_s, new_s),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Обрабатываем файлы
        processed_count = 0
        modified_count = 0
        errors = []
        
        for filename in bat_files:
            file_path = os.path.join(winws_folder, filename)
            try:
                # Читаем файл
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Ищем и заменяем строку
                old_string = 'start "zapret: %~n0" /min'
                new_string = 'start "zapret: %~n0" /B /min'
                
                if old_string in content:
                    # Заменяем все вхождения
                    new_content = content.replace(old_string, new_string)
                    
                    # Сохраняем файл
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    modified_count += 1
                
                processed_count += 1
            except Exception as e:
                errors.append(f'{filename}: {str(e)}')
        
        # Показываем результат (только если не silent режим)
        if not silent:
            result_text = tr('msg_processed_count', lang).format(processed_count, modified_count)
            if errors:
                result_text += '\n\n' + tr('msg_errors_section', lang) + '\n'.join(errors)
            
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_result', lang))
            msg.setText(result_text)
            if errors:
                msg.setIcon(QMessageBox.Icon.Warning)
            else:
                msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
    
    def remove_b_flag_from_all_strategies(self, silent=False):
        """Удаляет /B флаг из всех .bat файлов стратегий
        
        Args:
            silent: Если True, не показывает диалоги подтверждения и результатов
        """
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        
        if not os.path.exists(winws_folder):
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_winws_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        # Ищем все .bat файлы
        bat_files = []
        for filename in os.listdir(winws_folder):
            if filename.endswith('.bat') and os.path.isfile(os.path.join(winws_folder, filename)):
                bat_files.append(filename)
        
        if not bat_files:
            if not silent:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_information', lang))
                msg.setText(tr('msg_no_bat_to_process', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
            return
        
        # Подтверждение (только если не silent режим)
        if not silent:
            old_s = 'start "zapret: %~n0" /B /min'
            new_s = 'start "zapret: %~n0" /min'
            reply = QMessageBox.question(
                self,
                tr('msg_remove_b_flag_title', lang),
                tr('msg_remove_b_flag_text', lang).format(len(bat_files), old_s, new_s),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Обрабатываем файлы
        processed_count = 0
        modified_count = 0
        errors = []
        
        for filename in bat_files:
            file_path = os.path.join(winws_folder, filename)
            try:
                # Читаем файл
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Ищем и заменяем строку
                old_string = 'start "zapret: %~n0" /B /min'
                new_string = 'start "zapret: %~n0" /min'
                
                if old_string in content:
                    # Заменяем все вхождения
                    new_content = content.replace(old_string, new_string)
                    
                    # Сохраняем файл
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    modified_count += 1
                
                processed_count += 1
            except Exception as e:
                errors.append(f'{filename}: {str(e)}')
        
        # Показываем результат (только если не silent режим)
        if not silent:
            result_text = tr('msg_processed_count', lang).format(processed_count, modified_count)
            if errors:
                result_text += '\n\n' + tr('msg_errors_section', lang) + '\n'.join(errors)
            
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_result', lang))
            msg.setText(result_text)
            
            if errors:
                msg.setIcon(QMessageBox.Icon.Warning)
            else:
                msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
    
    def remove_check_updates_from_all_strategies(self, silent=False):
        """Удаляет строку "call service.bat check_updates" из всех .bat файлов стратегий
        
        Args:
            silent: Если True, не показывает диалоги подтверждения и результатов
        """
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        
        if not os.path.exists(winws_folder):
            if not silent:
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(tr('msg_winws_not_found', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
            return
        
        # Ищем все .bat файлы
        bat_files = []
        for filename in os.listdir(winws_folder):
            if filename.endswith('.bat') and os.path.isfile(os.path.join(winws_folder, filename)):
                bat_files.append(filename)
        
        if not bat_files:
            return
        
        # Обрабатываем файлы
        processed_count = 0
        modified_count = 0
        errors = []
        
        for filename in bat_files:
            file_path = os.path.join(winws_folder, filename)
            try:
                # Читаем файл
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                
                # Удаляем строки с "call service.bat check_updates"
                new_lines = []
                modified = False
                for line in lines:
                    # Проверяем, содержит ли строка "call service.bat check_updates"
                    # Учитываем возможные пробелы и регистр
                    stripped_line = line.strip()
                    # Проверяем точное совпадение или с возможными пробелами
                    if (stripped_line.lower() == 'call service.bat check_updates' or
                        'call service.bat check_updates' in stripped_line.lower()):
                        modified = True
                        continue  # Пропускаем эту строку
                    new_lines.append(line)
                
                if modified:
                    # Сохраняем файл
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    modified_count += 1
                
                processed_count += 1
            except Exception as e:
                errors.append(f'{filename}: {str(e)}')
        
        # Показываем результат (только если не silent режим)
        if not silent and (modified_count > 0 or errors):
            result_text = tr('msg_processed_count', lang).format(processed_count, modified_count)
            if errors:
                result_text += '\n\n' + tr('msg_errors_section', lang) + '\n'.join(errors)
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_result', lang))
            msg.setText(result_text)
            if errors:
                msg.setIcon(QMessageBox.Icon.Warning)
            else:
                msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
    
    def toggle_remove_check_updates(self):
        """Переключает настройку удаления проверки обновлений"""
        checked = self.remove_check_updates_action.isChecked()
        self.settings['remove_check_updates'] = checked
        self.config.set_setting('remove_check_updates', checked)
    
    def update_ipset_list(self):
        """Обновляет список IPSet из репозитория"""
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        list_file = os.path.join(winws_folder, 'lists', 'ipset-all.txt')
        url = 'https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/ipset-service.txt'
        
        # Показываем прогресс
        progress_dialog = QProgressDialog(self)
        progress_dialog.setWindowTitle(tr('update_ipset_list', lang))
        progress_dialog.setLabelText(tr('update_ipset_progress', lang))
        progress_dialog.setRange(0, 0)
        progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # Создаем директорию если не существует
            os.makedirs(os.path.dirname(list_file), exist_ok=True)
            
            # Пробуем использовать curl
            curl_path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'curl.exe')
            if os.path.exists(curl_path):
                result = subprocess.run(
                    [curl_path, '-L', '-o', list_file, url],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    raise Exception(f'curl failed: {result.stderr}')
            else:
                # Используем PowerShell
                ps_command = f'''
$url = '{url}';
$out = '{list_file}';
$dir = Split-Path -Parent $out;
if (-not (Test-Path $dir)) {{ New-Item -ItemType Directory -Path $dir | Out-Null }};
$res = Invoke-WebRequest -Uri $url -TimeoutSec 10 -UseBasicParsing;
if ($res.StatusCode -eq 200) {{ $res.Content | Out-File -FilePath $out -Encoding UTF8 }} else {{ exit 1 }}
'''
                result = subprocess.run(
                    ['powershell', '-Command', ps_command],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    raise Exception(f'PowerShell failed: {result.stderr}')
            
            progress_dialog.close()
            
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('update_ipset_list', lang))
            msg.setText(tr('update_ipset_success', lang))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
        except Exception as e:
            progress_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('update_ipset_error', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
    
    def update_hosts_file(self):
        """Обновляет hosts файл из репозитория"""
        lang = self.settings.get('language', 'ru')
        hosts_file = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'drivers', 'etc', 'hosts')
        hosts_url = 'https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/refs/heads/main/.service/hosts'
        temp_file = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), 'zapret_hosts.txt')
        
        # Показываем прогресс
        progress_dialog = QProgressDialog(self)
        progress_dialog.setWindowTitle(tr('update_hosts_file', lang))
        progress_dialog.setLabelText(tr('update_hosts_progress', lang))
        progress_dialog.setRange(0, 0)
        progress_dialog.setCancelButton(None)
        progress_dialog.show()
        QApplication.processEvents()
        
        try:
            # Скачиваем файл
            curl_path = os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'curl.exe')
            if os.path.exists(curl_path):
                result = subprocess.run(
                    [curl_path, '-L', '-s', '-o', temp_file, hosts_url],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    raise Exception(f'curl failed: {result.stderr}')
            else:
                # Используем PowerShell
                ps_command = f'''
$url = '{hosts_url}';
$out = '{temp_file}';
$res = Invoke-WebRequest -Uri $url -TimeoutSec 10 -UseBasicParsing;
if ($res.StatusCode -eq 200) {{ $res.Content | Out-File -FilePath $out -Encoding UTF8 }} else {{ exit 1 }}
'''
                result = subprocess.run(
                    ['powershell', '-Command', ps_command],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    raise Exception(f'PowerShell failed: {result.stderr}')
            
            if not os.path.exists(temp_file):
                raise Exception(tr('update_hosts_download_failed', lang))
            
            # Читаем первую и последнюю строки из скачанного файла
            with open(temp_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]
            
            if not lines:
                raise Exception(tr('update_hosts_file_empty', lang))
            
            first_line = lines[0]
            last_line = lines[-1]
            
            # Проверяем, нужно ли обновление
            needs_update = False
            if os.path.exists(hosts_file):
                with open(hosts_file, 'r', encoding='utf-8') as f:
                    hosts_content = f.read()
                    if first_line not in hosts_content or last_line not in hosts_content:
                        needs_update = True
            else:
                needs_update = True
            
            progress_dialog.close()
            
            if needs_update:
                # Открываем скачанный файл в notepad и проводник с hosts файлом
                msg = QMessageBox(self)
                msg.setWindowTitle(tr('update_hosts_file', lang))
                msg.setText(tr('update_hosts_needs_update', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
                
                # Открываем скачанный файл в notepad
                subprocess.Popen(['notepad', temp_file])
                
                # Открываем проводник с hosts файлом
                subprocess.Popen(['explorer', '/select,', hosts_file])
            else:
                # Удаляем временный файл
                try:
                    os.remove(temp_file)
                except:
                    pass
                
                msg = QMessageBox(self)
                msg.setWindowTitle(tr('update_hosts_file', lang))
                msg.setText(tr('update_hosts_up_to_date', lang))
                msg.setIcon(QMessageBox.Icon.Information)
                msg.exec()
        except Exception as e:
            progress_dialog.close()
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('update_hosts_error', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
    
    def update_filter_statuses(self):
        """Синхронизирует настройки Game Filter и IPSet Filter из файлов с конфигом"""
        game_filter_enabled = self.winws_manager.is_game_filter_enabled()
        if game_filter_enabled != self.settings.get('game_filter_enabled', False):
            self.settings['game_filter_enabled'] = game_filter_enabled
            self.config.set_setting('game_filter_enabled', game_filter_enabled)
        ipset_mode = self.winws_manager.get_ipset_mode()
        if ipset_mode != self.settings.get('ipset_filter_mode', 'loaded'):
            self.settings['ipset_filter_mode'] = ipset_mode
            self.config.set_setting('ipset_filter_mode', ipset_mode)

    def _update_window_title_with_strategy(self):
        """Обновляет заголовок окна вида 'ZapretDeskop — <стратегия>' если стратегия запущена."""
        base_title = "ZapretDeskop"
        if self.is_running and self.running_strategy:
            self.setWindowTitle(f"{base_title} — {self.running_strategy}")
        else:
            self.setWindowTitle(base_title)

    def _sync_run_state_ui(self):
        """Синхронизирует кнопку «Запустить/Остановить» и ComboBox с is_running и состоянием воркеров."""
        lang = self.settings.get('language', 'ru')
        start_busy = getattr(self, '_start_worker', None) and self._start_worker.isRunning()
        stop_busy = getattr(self, '_stop_worker', None) and self._stop_worker.isRunning()
        busy = start_busy or stop_busy
        if hasattr(self, 'action_button') and self.action_button:
            self.action_button.setText(tr('button_stop', lang) if self.is_running else tr('button_start', lang))
            self.action_button.setEnabled(not busy)
        if hasattr(self, 'combo_box') and self.combo_box:
            self.combo_box.setEnabled(not self.is_running and not busy)

    def _show_menu_progress_bar(self):
        """Показывает тонкую полоску прогресса под меню (1px), не сдвигая остальные виджеты."""
        if hasattr(self, 'menu_progress_bar') and self.menu_progress_bar:
            self.menu_progress_bar.setFixedHeight(1)
            self.menu_progress_bar.setMaximumHeight(1)
            # Режим «неопределённо» — анимация, полоска сразу заметна
            self.menu_progress_bar.setMaximum(0)
            self.menu_progress_bar.show()
            self.menu_progress_bar.update()
            QApplication.processEvents()

    def _hide_menu_progress_bar(self):
        """Скрывает полоску прогресса без резерва места в layout (виджеты не сдвигаются)."""
        if hasattr(self, 'menu_progress_bar') and self.menu_progress_bar:
            self.menu_progress_bar.setMaximum(100)
            self.menu_progress_bar.setValue(0)
            self.menu_progress_bar.setFixedHeight(0)
            self.menu_progress_bar.setMaximumHeight(0)
    
    def toggle_game_filter(self):
        """Переключает Game Filter"""
        lang = self.settings.get('language', 'ru')
        
        try:
            game_filter_enabled = self.winws_manager.toggle_game_filter()
            
            # Сохраняем в конфиг
            self.settings['game_filter_enabled'] = game_filter_enabled
            self.config.set_setting('game_filter_enabled', game_filter_enabled)
            
            # Показываем сообщение
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('settings_game_filter', lang))
            status_text = tr('msg_game_filter_enabled', lang) if game_filter_enabled else tr('msg_game_filter_disabled', lang)
            msg.setText(tr('msg_game_filter_restart', lang).format(status_text))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
            # Обновляем статус
            self.update_filter_statuses()
        except Exception as e:
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_game_filter_toggle_error', lang).format(str(e)))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
    
    def toggle_ipset_filter(self):
        """Переключает IPSet Filter между режимами: loaded -> none -> any -> loaded"""
        lang = self.settings.get('language', 'ru')
        
        try:
            current_mode = self.winws_manager.get_ipset_mode()
            
            # Определяем следующий режим в цикле: loaded -> none -> any -> loaded
            mode_cycle = {'loaded': 'none', 'none': 'any', 'any': 'loaded'}
            next_mode = mode_cycle.get(current_mode, 'loaded')
            
            self.winws_manager.set_ipset_mode(next_mode)
            
            # Сохраняем в конфиг
            self.settings['ipset_filter_mode'] = next_mode
            self.config.set_setting('ipset_filter_mode', next_mode)
            
            # Показываем сообщение
            mode_names = {
                'loaded': ('loaded', 'loaded'),
                'none': ('none', 'none'),
                'any': ('any', 'any')
            }
            mode_name_ru, mode_name_en = mode_names.get(next_mode, ('unknown', 'unknown'))
            mode_name = mode_name_ru if lang == 'ru' else mode_name_en
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('settings_ipset_filter', lang))
            msg.setText(tr('msg_ipset_filter_restart', lang).format(mode_name))
            msg.setIcon(QMessageBox.Icon.Information)
            msg.exec()
            
            # Обновляем статус
            self.update_filter_statuses()
        except Exception as e:
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            error_text = str(e)
            if 'Backup file not found' in error_text or 'Backup not found' in error_text:
                error_text = tr('msg_backup_not_found_short', lang)
            else:
                error_text = tr('msg_ipset_filter_toggle_error', lang).format(str(e))
            msg.setText(error_text)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
    
    def load_version_info(self):
        """Показывает версию программы и MD5.

        Версия всегда берётся из константы VERSION, а не из config.json,
        чтобы ручные правки конфига не ломали контроль версий.
        MD5 (или другой идентификатор сборки) по‑прежнему читается из конфига при наличии.
        """
        version = VERSION
        md5 = MD5
        # Ссылка на релиз текущей версии
        release_url = f"https://github.com/ZapretDeskop/ZapretDeskop/releases/tag/{version}"
        if self.latest_available_version and self.latest_available_version != version:
            latest = self.latest_available_version
            latest_release_url = f"https://github.com/ZapretDeskop/ZapretDeskop/releases/tag/{latest}"
            version_text = (
                f'<a href="{release_url}">{version}</a> '
                f'(→<a href="{latest_release_url}"><span style="color:#0b6b2a;">{latest}</span></a>)'
            )
        else:
            version_text = f'<a href="{release_url}">{version}</a>'
        # Если MD5 не является тем же самым e-mail, можно добавить его отдельной строкой
        if md5 and md5 != "ZapretDeskop@proton.me":
            version_text += f"<br>{md5}"
        self.version_label.setText(version_text)

    def _show_version_context_menu(self, pos):
        """Контекстное меню по версии (открыть релиз / копировать ссылку)."""
        lang = self.settings.get('language', 'ru')
        menu = StyleMenu(self)
        open_action = menu.addAction(tr('link_open_release', lang))
        copy_action = menu.addAction(tr('link_copy_release', lang))
        action = menu.exec(self.version_label.mapToGlobal(pos))
        if not action:
            return
        version = VERSION
        release_url = f"https://github.com/ZapretDeskop/ZapretDeskop/releases/tag/{version}"
        if action == open_action:
            QDesktopServices.openUrl(QUrl(release_url))
        elif action == copy_action:
            QGuiApplication.clipboard().setText(release_url)

    def _show_contact_context_menu(self, pos):
        """Контекстное меню по e-mail (mailto / копировать адрес)."""
        lang = self.settings.get('language', 'ru')
        menu = StyleMenu(self)
        send_action = menu.addAction(tr('link_send_email', lang))
        copy_action = menu.addAction(tr('link_copy_email', lang))
        action = menu.exec(self.contact_label.mapToGlobal(pos))
        if not action:
            return
        email = "ZapretDeskop@proton.me"
        if action == send_action:
            QDesktopServices.openUrl(QUrl(f"mailto:{email}"))
        elif action == copy_action:
            QGuiApplication.clipboard().setText(email)
    
    def open_github(self):
        """Открывает страницу GitHub проекта"""
        url = QUrl('https://github.com/ZapretDeskop/ZapretDeskop')
        QDesktopServices.openUrl(url)
    
    def open_github_zapret(self):
        """Открывает страницу GitHub репозитория zapret из настроек."""
        slug = getattr(self.zapret_updater, "github_repo", ZapretUpdater.GITHUB_REPO)
        slug = (slug or "").strip().strip("/")
        # Если вдруг в github_repo уже попал полный URL — используем его как есть
        if slug.lower().startswith("http://") or slug.lower().startswith("https://"):
            url = QUrl(slug)
        else:
            url = QUrl(f'https://github.com/{slug}')
        QDesktopServices.openUrl(url)
    
    def open_winws_folder(self):
        """Открывает папку winws в проводнике Windows"""
        winws_folder = get_winws_path()
        if os.path.exists(winws_folder):
            # Открываем папку в проводнике Windows
            os.startfile(winws_folder)
        else:
            lang = self.settings.get('language', 'ru')
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_winws_not_found', lang))
            msg.setText(tr('msg_winws_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()

    def open_config_folder(self):
        """Открывает папку конфигурации программы в проводнике Windows"""
        try:
            config_path = get_config_path()
            config_dir = os.path.dirname(config_path)
            if config_dir and os.path.exists(config_dir):
                os.startfile(config_dir)
            else:
                lang = self.settings.get('language', 'ru')
                msg = configure_message_box(QMessageBox(self))
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(config_dir or "Config folder not found")
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
        except Exception as e:
            lang = self.settings.get('language', 'ru')
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(str(e))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
    
    def load_bat_files(self):
        """Загружает названия .bat файлов из папки winws"""
        lang = self.settings.get('language', 'ru')
        winws_folder = get_winws_path()
        bat_files = []
        
        if os.path.exists(winws_folder):
            # Получаем все файлы из папки winws
            for filename in os.listdir(winws_folder):
                # Проверяем, что это .bat файл и это файл, а не папка
                # Исключаем service.bat
                if filename.endswith('.bat') and filename != 'service.bat' and os.path.isfile(os.path.join(winws_folder, filename)):
                    # Убираем расширение .bat
                    name_without_ext = filename[:-4]  # Убираем последние 4 символа (.bat)
                    bat_files.append(name_without_ext)
            
            # Сортируем список для удобства
            bat_files.sort()
            
            # Сохраняем текущий выбор
            current_strategy = self._get_selected_strategy_name()
            
            # Очищаем и добавляем в ComboBox
            self.combo_box.clear()
            if bat_files:
                for name in bat_files:
                    self.combo_box.addItem(name, name)
                # Восстанавливаем выбор, если он еще существует
                index = self._find_combo_index_by_data(current_strategy)
                if index >= 0:
                    self.combo_box.setCurrentIndex(index)
            else:
                self.combo_box.addItem(tr('msg_no_bat_files', lang), None)
        else:
            self.combo_box.clear()
            self.combo_box.addItem(tr('msg_winws_not_found', lang), None)

        # После пересборки списка стратегий — обновляем отображение версии/ pid
        self._refresh_strategy_display()

    def _get_selected_strategy_name(self):
        """Возвращает "сырой" идентификатор стратегии (без украшений), если выбран реальный .bat."""
        try:
            data = self.combo_box.currentData()
            if isinstance(data, str) and data:
                return data
        except Exception:
            pass
        # fallback для старых/нестандартных элементов
        return self.combo_box.currentText()

    def _find_combo_index_by_data(self, data):
        """Эквивалент QComboBox.findData для CustomComboBox."""
        try:
            for i in range(self.combo_box.count()):
                if self.combo_box.itemData(i) == data:
                    return i
        except Exception:
            return -1
        return -1

    def _set_combo_item_text(self, index: int, text: str) -> None:
        """
        Безопасно меняет текст элемента в CustomComboBox.
        У CustomComboBox нет setItemText(), поэтому обновляем внутренний items[] и пересобираем меню.
        """
        try:
            if not (0 <= index < self.combo_box.count()):
                return
            # CustomComboBox хранит элементы в self.items
            if hasattr(self.combo_box, "items") and isinstance(self.combo_box.items, list):  # type: ignore[attr-defined]
                item = self.combo_box.items[index]  # type: ignore[attr-defined]
                if isinstance(item, dict) and not item.get("separator", False):
                    item["text"] = text
                # Перестраиваем меню и обновляем label текущего элемента
                if hasattr(self.combo_box, "_rebuild_menu"):
                    self.combo_box._rebuild_menu()  # type: ignore[attr-defined]
                if hasattr(self.combo_box, "current_index") and self.combo_box.current_index == index:  # type: ignore[attr-defined]
                    if hasattr(self.combo_box, "text_label"):
                        self.combo_box.text_label.setText(text)  # type: ignore[attr-defined]
                return
        except Exception:
            return

    def _get_running_winws_process(self):
        """Возвращает первый найденный процесс winws.exe (psutil.Process) или None."""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info.get('name', '').lower() == 'winws.exe':
                        return proc
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception:
            return None
        return None

    def _guess_winws_root_from_process(self, proc):
        """Пытается определить корень winws (где лежит service.bat) по процессу winws.exe."""
        import pathlib
        candidates = []
        try:
            exe = proc.exe()
            if exe:
                exe_path = pathlib.Path(exe)
                candidates.append(exe_path)                 # ...\bin\winws.exe (как файл)
                candidates.append(exe_path.parent)          # ...\bin
                candidates.append(exe_path.parent.parent)   # ...\winws
                candidates.append(exe_path.parent.parent.parent)
        except Exception:
            pass
        try:
            cwd = proc.cwd()
            if cwd:
                cwd_path = pathlib.Path(cwd)
                candidates.append(cwd_path)
                candidates.append(cwd_path.parent)
                candidates.append(cwd_path.parent.parent)
        except Exception:
            pass

        for c in candidates:
            try:
                # Если это файл — проверяем папку файла
                if c.is_file():
                    if (c.parent / 'service.bat').is_file():
                        return str(c.parent)
                else:
                    if (c / 'service.bat').is_file():
                        return str(c)
            except Exception:
                continue
        return None

    def _get_running_winws_version_and_pid(self):
        """Возвращает (version, pid, winws_root) для запущенного winws.exe, если возможно."""
        proc = self._get_running_winws_process()
        if not proc:
            return (None, None, None)
        pid = None
        try:
            pid = proc.pid
        except Exception:
            pid = None
        winws_root = self._guess_winws_root_from_process(proc)
        version = None
        try:
            from src.core.winws_version import read_local_version_from_winws_root
            if winws_root:
                version = read_local_version_from_winws_root(winws_root)
            # Если не смогли определить корень по процессу — пробуем стандартную папку winws
            if not version:
                version = read_local_version_from_winws_root(get_winws_path())
        except Exception:
            version = None
        return (version, pid, winws_root)

    def _refresh_strategy_display(self):
        """
        Обновляет отображаемые тексты в ComboBox:
        - Для всех стратегий показывает [version] (версия берётся из service.bat в нашей winws)
        - Если winws запущен "внешне" (не этой сессией ZapretDeskop) — для активной стратегии показывает [version | pid]
        """
        ext_key = "__external_winws__"
        # Базовая версия наших стратегий (из нашей winws), показывается всегда
        try:
            from src.core.winws_version import read_local_version_from_winws_root
            base_version = read_local_version_from_winws_root(get_winws_path()) or "unknown"
        except Exception:
            base_version = "unknown"

        # Сначала сбрасываем тексты к "сырым" именам (userData) и сразу украшаем версией
        try:
            for i in range(self.combo_box.count()):
                data = self.combo_box.itemData(i)
                if isinstance(data, str) and data:
                    if data == ext_key:
                        continue
                    self._set_combo_item_text(i, f"{data} [{base_version}]")
        except Exception:
            return

        # Если winws не запущен — убираем специальный пункт "внешний запуск", если он остался
        if not getattr(self, "is_running", False):
            # Удаляем специальный пункт "внешний запуск", если он остался
            try:
                idx = self._find_combo_index_by_data(ext_key)
                if idx >= 0:
                    self.combo_box.removeItem(idx)
            except Exception:
                pass
            return

        # Для стратегий, запущенных из текущей сессии ZapretDeskop, всегда используем базовую
        # версию из нашего winws (service.bat). Для внешнего winws пытаемся определить
        # версию и pid по запущенному процессу.
        external = not getattr(self, "_started_winws_this_session", False)
        version = base_version
        pid = None
        if external:
            v_proc, pid_proc, _root = self._get_running_winws_version_and_pid()
            if v_proc:
                version = v_proc
            pid = pid_proc

        # Если текущая стратегия определена и присутствует в списке — украшаем её
        if self.running_strategy:
            idx = self._find_combo_index_by_data(self.running_strategy)
            if idx >= 0:
                # Для внешнего запуска добавляем pid, иначе оставляем просто версию
                if external and pid:
                    self._set_combo_item_text(idx, f"{self.running_strategy} [{version} | {pid}]")
                else:
                    self._set_combo_item_text(idx, f"{self.running_strategy} [{version}]")
                return

        # Иначе (стратегия не определена или не видна) — добавляем/обновляем специальный пункт
        lang = self.settings.get('language', 'ru')
        ext_title = "Внешний запуск winws" if lang == 'ru' else "External winws"
        suffix = f"[{version} | {pid}]" if pid else f"[{version}]"
        display = f"{ext_title} {suffix}"

        ext_idx = self._find_combo_index_by_data(ext_key)
        if ext_idx < 0:
            self.combo_box.insertItem(0, display, ext_key)
            ext_idx = 0
        else:
            self._set_combo_item_text(ext_idx, display)
        # Выбираем внешний пункт, чтобы пользователь видел, что запущено не из списка
        if self.combo_box.currentIndex() != ext_idx:
            self.combo_box.setCurrentIndex(ext_idx)
    
    def _detect_running_strategy(self):
        """Определяет запущенную стратегию по командной строке winws.exe.
        Возвращает имя стратегии (без .bat) или None если не удалось определить."""
        try:
            proc_cmdline = None
            proc_exe = None
            # Ищем реально запущенный winws.exe и его путь на диске
            for proc in psutil.process_iter(['name', 'cmdline', 'exe']):
                try:
                    if proc.info.get('name', '').lower() == 'winws.exe':
                        cmdline = proc.info.get('cmdline')
                        if cmdline:
                            proc_cmdline = ' '.join(cmdline) if isinstance(cmdline, list) else str(cmdline)
                        proc_exe = proc.info.get('exe') or ''
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            if not proc_cmdline or 'winws.exe' not in proc_cmdline.lower():
                return None
            if not proc_exe:
                return None

            # Определяем папку winws на основе пути к запущенному winws.exe:
            # [папка winws]\bin\winws.exe -> [папка winws]
            exe_path = os.path.abspath(proc_exe)
            bin_folder = os.path.dirname(exe_path)
            winws_folder = os.path.abspath(os.path.join(bin_folder, os.pardir))
            if not os.path.isdir(winws_folder):
                return None

            # Нормализуем: заменяем пути на плейсхолдеры для сравнения
            bin_path = os.path.normpath(os.path.join(winws_folder, 'bin'))
            lists_path = os.path.normpath(os.path.join(winws_folder, 'lists'))
            proc_norm = proc_cmdline
            for p, ph in [(bin_path, 'BIN'), (lists_path, 'LISTS')]:
                proc_norm = proc_norm.replace(p, ph).replace(p.replace('\\', '/'), ph)
            # Берём только аргументы после winws.exe
            if 'winws.exe' in proc_norm.lower():
                idx = proc_norm.lower().find('winws.exe')
                proc_norm = proc_norm[idx + len('winws.exe'):].strip()
            best_match = None
            best_score = 0
            for filename in os.listdir(winws_folder):
                if not filename.endswith('.bat') or filename == 'service.bat':
                    continue
                strategy_name = filename[:-4]
                bat_path = os.path.join(winws_folder, filename)
                if not os.path.isfile(bat_path):
                    continue
                try:
                    with open(bat_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception:
                    continue
                # Извлекаем аргументы winws.exe из bat (строки после start ... winws.exe)
                bat_args = ''
                for line in content.splitlines():
                    if 'winws.exe' in line.lower():
                        idx = line.lower().find('winws.exe')
                        part = line[idx + len('winws.exe'):].strip()
                        part = part.rstrip('^').strip()
                        bat_args += ' ' + part
                    elif bat_args and line.strip().startswith('--'):
                        bat_args += ' ' + line.strip().rstrip('^').strip()
                bat_args = bat_args.strip()
                if not bat_args:
                    continue
                bat_norm = bat_args.replace('%BIN%', 'BIN').replace('%LISTS%', 'LISTS').replace('%GameFilter%', '')
                bat_norm = bat_norm.replace('"', ' ').replace('\\', '/')
                proc_norm_clean = proc_norm.replace('"', ' ').replace('\\', '/')
                # Считаем совпадение: сколько характерных токенов из bat есть в proc
                bat_tokens = set(t for t in bat_norm.split() if t.startswith('--') and '=' in t)
                if not bat_tokens:
                    continue
                matches = sum(1 for t in bat_tokens if t in proc_norm_clean)
                score = matches / len(bat_tokens) if bat_tokens else 0
                if score > best_score and score >= 0.5:
                    best_score = score
                    best_match = strategy_name
            return best_match
        except Exception:
            return None
    
    def restore_last_strategy(self):
        """Восстанавливает последнюю выбранную стратегию.
        Если winws.exe уже запущен (программа перезапущена), пытается определить
        запущенную стратегию и выбрать её в ComboBox."""
        strategy_to_select = None
        winws_running = False
        try:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info.get('name', '').lower() == 'winws.exe':
                        winws_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception:
            pass
        if winws_running:
            detected = self._detect_running_strategy()
            if detected:
                strategy_to_select = detected
                self.is_running = True
                self.running_strategy = detected
        if not strategy_to_select:
            strategy_to_select = self.settings.get('last_strategy', '')
        if strategy_to_select:
            index = self._find_combo_index_by_data(strategy_to_select)
            if index >= 0:
                self.combo_box.setCurrentIndex(index)
                if winws_running:
                    # Если стратегия уже запущена при старте приложения, обновляем заголовок
                    self._update_window_title_with_strategy()
                elif self.settings.get('auto_start_last_strategy', False):
                    QTimer.singleShot(500, self.auto_start_strategy)
        # Всегда синхронизируем кнопку и ComboBox с is_running после восстановления
        self._sync_run_state_ui()
    
    def auto_start_strategy(self):
        """Автоматически запускает выбранную стратегию"""
        if not self.is_running:
            self.toggle_action()
    
    def auto_start_last_strategy(self):
        """Автоматически запускает последнюю сохраненную стратегию при запуске программы
        Запускает стратегию только если last_strategy явно указан в конфиге и найден в списке"""
        last_strategy = self.settings.get('last_strategy', '')
        
        # Если last_strategy не указан (пустой), не запускаем ничего
        # Пользователь должен сам выбрать стратегию при первом запуске
        if not last_strategy:
            return
        
        # Пытаемся найти указанную стратегию в списке
        index = self._find_combo_index_by_data(last_strategy)
        if index < 0:
            # Стратегия не найдена в списке - не запускаем
            return
        
        # Стратегия найдена - выбираем и запускаем её
        self.combo_box.setCurrentIndex(index)
        # Инициализация полоски прогресса для первого запуска (автозапуск без кнопки)
        if last_strategy.lower() != 'service':
            self._show_menu_progress_bar()
        # Запускаем стратегию асинхронно (заголовок обновятся в _on_start_worker_done)
        if not self.is_running:
            self.start_bat_file()
    
    def restart_strategy(self):
        """Перезапускает стратегию, которая была запущена ранее"""
        # ВАЖНО: Проверяем настройку автоперезапуска ПЕРВЫМ делом
        # Если настройка выключена, не перезапускаем
        if not self.settings.get('auto_restart_strategy', False):
            return
        
        # Не перезапускаем, если пользователь явно остановил процесс или уже идет перезапуск
        if not self.running_strategy or self.is_restarting or self.user_stopped:
            return
        
        # Устанавливаем флаг перезапуска
        self.is_restarting = True
        
        # Проверяем, что стратегия все еще существует
        index = self._find_combo_index_by_data(self.running_strategy)
        if index < 0:
            # Стратегия больше не существует
            self.running_strategy = None
            self.is_restarting = False
            return
        
        # Проверяем еще раз перед запуском (на случай, если пользователь нажал Stop во время задержки)
        if self.user_stopped:
            self.is_restarting = False
            return
        
        # Выбираем стратегию в ComboBox
        self.combo_box.setCurrentIndex(index)
        
        # Запускаем стратегию
        if not self.is_running:
            self.start_bat_file()
        
        # Сбрасываем флаг перезапуска через небольшую задержку
        QTimer.singleShot(2000, lambda: setattr(self, 'is_restarting', False))
    
    def on_strategy_changed(self, strategy_name):
        """Обработчик изменения стратегии в ComboBox"""
        try:
            data = self.combo_box.currentData()
        except Exception:
            data = None
        if not isinstance(data, str) or not data or data == "__external_winws__":
            return
        self.config.set_setting('last_strategy', data)
        self.settings['last_strategy'] = data
    
    def init_tray(self):
        self.tray = SystemTray(self)
        # Применяем настройку show_in_tray при инициализации
        if self.settings.get('show_in_tray', True):
            self.tray.show()
        else:
            self.tray.hide()
    
    def center_window(self):
        """Центрирует окно на экране"""
        screen = QApplication.primaryScreen().geometry()
        window_geometry = self.frameGeometry()
        window_geometry.moveCenter(screen.center())
        self.move(window_geometry.topLeft())
    
    def toggle_action(self):
        """Переключает состояние между Запустить и Остановить"""
        if not self.is_running:
            self.user_stopped = False  # Сбрасываем флаг при запуске
            self.start_bat_file()  # асинхронно, заголовок обновится в _on_start_worker_done
        else:
            # Останавливаем процесс winws.exe
            # Показываем полоску прогресса до исчезновения winws.exe
            self._show_menu_progress_bar()
            # ВАЖНО: Устанавливаем флаги ДО остановки процесса, чтобы check_winws_process() их увидел
            self.user_stopped = True  # Устанавливаем флаг явной остановки пользователем
            self.running_strategy = None  # Очищаем название стратегии при явной остановке
            self.is_restarting = False  # Сбрасываем флаг перезапуска
            self._started_winws_this_session = False
            # Останавливаем процесс в фоне (обновление UI в _on_stop_worker_done)
            self.stop_winws_process()
    
    def start_bat_file(self):
        """Запускает выбранный .bat файл"""
        lang = self.settings.get('language', 'ru')
        current_strategy = self._get_selected_strategy_name()
        
        # Проверяем, что стратегия выбрана
        if not current_strategy or current_strategy in [tr('msg_no_bat_files', lang), tr('msg_winws_not_found', lang)]:
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_no_strategy_selected', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        # Формируем путь к .bat файлу
        bat_filename = f"{current_strategy}.bat"
        winws_folder = get_winws_path()
        bat_path = os.path.join(winws_folder, bat_filename)
        
        # Контроль запуска: только .bat из папки winws, без path traversal
        try:
            bat_path_real = os.path.realpath(bat_path)
            winws_folder_real = os.path.realpath(winws_folder)
            if not bat_path_real.startswith(winws_folder_real + os.sep) and bat_path_real != winws_folder_real:
                msg = QMessageBox(self)
                msg.setWindowTitle(tr('msg_error', lang))
                msg.setText(tr('msg_bat_path_not_allowed', lang))
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.exec()
                return
        except (OSError, ValueError):
            pass  # дальше сработает проверка exists
        
        # Разрешены только файлы из списка загруженных стратегий (исключая service.bat)
        allowed = set()
        if os.path.exists(winws_folder):
            for f in os.listdir(winws_folder):
                if f.endswith('.bat') and f != 'service.bat' and os.path.isfile(os.path.join(winws_folder, f)):
                    allowed.add(f[:-4])
        if current_strategy not in allowed:
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_bat_not_in_list', lang).format(current_strategy))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        if not os.path.exists(bat_path):
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_file_not_found', lang).format(bat_filename, bat_path))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        
        bat_path_abs = os.path.abspath(bat_path)
        bat_dir = os.path.dirname(bat_path_abs)
        is_service_file = bat_filename.lower().startswith('service')

        # Показываем полоску прогресса до появления winws.exe (и при ручном запуске, и при автозапуске)
        if not is_service_file:
            self._show_menu_progress_bar()

        # Запуск в фоне: UI не замирает
        if self._start_worker is not None and self._start_worker.isRunning():
            return
        self._start_worker = _StartWorker(self, bat_path_abs, bat_dir, os.name == 'nt')
        self._start_worker.done_signal.connect(
            lambda ok, proc, err: self._on_start_worker_done(ok, proc, err, current_strategy, bat_filename)
        )
        def _on_start_worker_finished():
            self._start_worker = None
            self._sync_run_state_ui()
        self._start_worker.finished.connect(_on_start_worker_finished)
        self._start_worker.start()
        self._sync_run_state_ui()  # кнопка/комбо disabled пока воркер запуска

    def _on_start_worker_done(self, success, process, error_message, current_strategy, bat_filename):
        """Вызывается в главном потоке после завершения _StartWorker."""
        lang = self.settings.get('language', 'ru')
        is_service_file = bat_filename.lower().startswith('service')
        if not success:
            self.is_running = False
            self._hide_menu_progress_bar()
            self._sync_run_state_ui()
            msg = QMessageBox(self)
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_error_on_start', lang).format(error_message or ''))
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.exec()
            return
        import time
        self.bat_process = process
        self.is_running = True
        self.running_strategy = current_strategy
        self._started_winws_this_session = True
        self.user_stopped = False
        self.is_restarting = False
        if not is_service_file:
            self.bat_start_time = time.time()
        else:
            self.bat_start_time = None
        self._sync_run_state_ui()
        self._refresh_strategy_display()
        self._update_window_title_with_strategy()
        if not is_service_file:
            self.config.set_setting('last_strategy', current_strategy)
            self.settings['last_strategy'] = current_strategy
        else:
            self.running_strategy = None

    def _handle_auto_restart_apps(self):
        """Перезапуск указанных в настройках приложений при запуске стратегии.

        Логика:
        - Берём список имён процессов из settings['auto_restart_apps'] (например, ['discord.exe']).
        - Для каждого находим запущенные процессы, запоминаем полный путь exe.
        - Завершаем эти процессы.
        - После этого снова запускаем их по тем же путям (если пути найдены).
        """
        apps = self.settings.get('auto_restart_apps', [])
        if not apps:
            return
        try:
            import psutil
        except ImportError:
            return

        targets = [name.lower() for name in apps if name]
        if not targets:
            return

        to_restart = []
        for proc in psutil.process_iter(['name', 'exe']):
            try:
                name = (proc.info.get('name') or '').lower()
                if name in targets:
                    exe_path = proc.info.get('exe')
                    if exe_path and os.path.exists(exe_path):
                        to_restart.append(exe_path)
                    # Пытаемся аккуратно завершить
                    try:
                        proc.terminate()
                    except Exception:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Перезапускаем приложения
        for exe_path in to_restart:
            try:
                if os.name == 'nt':
                    # На Windows запускаем через ShellExecute (os.startfile),
                    # чтобы процесс не был дочерним для ZapretDeskop и не зависел от него.
                    os.startfile(exe_path)
                else:
                    # На других платформах отделяем процесс с новой сессией
                    subprocess.Popen(
                        [exe_path],
                        cwd=os.path.dirname(exe_path) or None,
                        start_new_session=True,
                    )
            except Exception:
                continue
    
    def _do_stop_winws_process(self):
        """Синхронно завершает все процессы winws.exe (вызывается из потока или main)."""
        import time
        processes_to_kill = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info.get('name', '').lower() == 'winws.exe':
                    processes_to_kill.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        for proc in processes_to_kill:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if processes_to_kill:
            time.sleep(0.5)
        remaining = []
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info.get('name', '').lower() == 'winws.exe':
                    remaining.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        for proc in remaining:
            try:
                proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

    def stop_winws_process(self, silent=False):
        """Останавливает процесс winws.exe. При silent=False — в фоне (UI не замирает).
        Args:
            silent: Если True, выполняется синхронно (для выхода/обновлений); иначе в фоне.
        """
        if not silent:
            self.process_monitor_timer.stop()
            self.user_stopped = True
            self.running_strategy = None
            self.is_restarting = False

        if silent:
            self._do_stop_winws_process()
            # Чтобы UI не показывал «Остановить» до следующего тика таймера
            self.is_running = False
            self.bat_start_time = None
            self.bat_process = None
            self._hide_menu_progress_bar()
            self._sync_run_state_ui()
            return
        if self._stop_worker is not None and self._stop_worker.isRunning():
            return
        self._stop_worker = _StopWorker(self)
        self._stop_worker.done_signal.connect(
            lambda: self._on_stop_worker_done(False)
        )
        def _on_stop_worker_finished():
            self._stop_worker = None
            self._sync_run_state_ui()
        self._stop_worker.finished.connect(_on_stop_worker_finished)
        self._stop_worker.start()
        self._sync_run_state_ui()  # кнопка/комбо disabled пока воркер останавливает

    def _on_stop_worker_done(self, silent):
        """Вызывается в главном потоке после завершения _StopWorker."""
        if not silent:
            self.is_running = False
            self.bat_start_time = None
            self.bat_process = None
            self._sync_run_state_ui()
            self._update_window_title_with_strategy()
            self._refresh_strategy_display()
            QTimer.singleShot(2000, lambda: self.process_monitor_timer.start(1000))
    
    def check_winws_process(self):
        """Проверяет наличие процесса winws.exe и обновляет состояние кнопки
        Также проверяет, появился ли процесс winws.exe в течение 5 секунд после запуска стратегии"""
        lang = self.settings.get('language', 'ru')
        import time
        
        # Проверяем, запущен ли процесс winws.exe
        winws_running = False
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] and proc.info['name'].lower() == 'winws.exe':
                        winws_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
        except Exception:
            pass
        
        # Скрываем полоску прогресса только когда процесс исчез и мы не ждём его появления
        # (при ожидании старта bat_start_time не None и is_running True — не скрываем)
        if not winws_running and (self.bat_start_time is None or not self.is_running):
            self._hide_menu_progress_bar()
        
        # Проверка запуска: если прошло более 5 секунд с момента запуска .bat файла
        # и процесс winws.exe не появился - останавливаем процесс запуска
        # ВАЖНО: Проверка выполняется только один раз, после чего bat_start_time сбрасывается
        if (self.bat_start_time is not None and 
            self.is_running and 
            not self.user_stopped and
            self.bat_process is not None):
            elapsed_time = time.time() - self.bat_start_time
            if elapsed_time >= 5.0:
                # Прошло 5 секунд - проверяем один раз и сбрасываем время запуска
                strategy_name = self.running_strategy if self.running_strategy else self._get_selected_strategy_name()
                self.bat_start_time = None  # Сбрасываем время запуска сразу, чтобы проверка не повторялась
                
                if not winws_running:
                    # Процесс не появился в течение 5 секунд - останавливаем запуск
                    # Останавливаем процесс .bat файла
                    try:
                        self.bat_process.terminate()
                        try:
                            self.bat_process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            self.bat_process.kill()
                    except Exception:
                        pass
                    
                    # Обновляем состояние
                    self.is_running = False
                    self.running_strategy = None
                    self.bat_process = None
                    self._hide_menu_progress_bar()
                    self._sync_run_state_ui()
                    
                    # Показываем сообщение об ошибке
                    msg = QMessageBox(self)
                    msg.setWindowTitle(tr('msg_error_launch_title', lang))
                    msg.setText(tr('msg_winws_not_started', lang).format(strategy_name))
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.exec()
                    return
        
        # Если процесс winws.exe появился, сбрасываем время запуска и скрываем полоску прогресса
        if winws_running and self.bat_start_time is not None:
            self.bat_start_time = None
            self._hide_menu_progress_bar()
        
        # Синхронизируем состояние кнопки с реальным состоянием процесса
        if winws_running and not self.is_running:
            # Процесс запущен, но кнопка показывает "Запустить" (программа перезапущена)
            self.is_running = True
            # winws появился без запуска из текущей сессии ZapretDeskop
            self._started_winws_this_session = False
            detected = self._detect_running_strategy()
            if detected:
                self.running_strategy = detected
                index = self._find_combo_index_by_data(detected)
                if index >= 0:
                    self.combo_box.setCurrentIndex(index)
            self._sync_run_state_ui()
            # Обновляем заголовок окна с найденной стратегией
            self._update_window_title_with_strategy()
            self._refresh_strategy_display()
        elif not winws_running and self.is_running:
            # Не считаем процесс мёртвым, если мы ещё в периоде ожидания появления winws (до 5 с)
            if self.bat_start_time is not None and (time.time() - self.bat_start_time) < 5.0:
                return
            # Процесс остановлен, но кнопка показывает "Остановить"
            self.is_running = False
            self._started_winws_this_session = False
            self.bat_process = None
            self._hide_menu_progress_bar()
            self._sync_run_state_ui()
            # Обновляем заголовок окна (стратегия больше не запущена)
            self._update_window_title_with_strategy()
            self._refresh_strategy_display()
            
            # ВАЖНО: Проверяем флаг user_stopped ПЕРВЫМ делом
            # Если пользователь явно остановил процесс, НЕ запускаем автоперезапуск
            if self.user_stopped:
                # Пользователь явно остановил процесс - не перезапускаем
                # Флаг будет сброшен при следующем запуске стратегии
                # Также очищаем running_strategy на всякий случай
                self.running_strategy = None
                self.is_restarting = False  # Сбрасываем флаг перезапуска
                return
            
            # ВАЖНО: Проверяем настройку автоперезапуска ВТОРЫМ делом
            # Если настройка выключена, НЕ делаем НИЧЕГО связанного с перезапуском
            auto_restart_enabled = self.settings.get('auto_restart_strategy', False)
            if not auto_restart_enabled:
                # Настройка выключена - полностью отключаем логику перезапуска
                # Очищаем все связанные флаги
                self.running_strategy = None
                self.is_restarting = False
                return
            
            # Только если настройка ВКЛЮЧЕНА и все остальные условия выполнены
            # Если включен автоперезапуск и была запущена стратегия, перезапускаем её
            # Проверяем, что мы не в процессе перезапуска, чтобы избежать множественных перезапусков
            if (self.running_strategy and 
                not self.is_restarting):
                # Небольшая задержка перед перезапуском
                QTimer.singleShot(1000, self.restart_strategy)
    
    def showEvent(self, event):
        """Обработка показа окна - обновляет меню трея"""
        super().showEvent(event)
        # Обновляем меню трея при показе окна
        if hasattr(self, 'tray') and self.tray:
            self.tray.update_menu()

    def _run_startup_update_check(self):
        """Запускает проверку обновлений в отдельном потоке (вызывается из main thread по таймеру)"""
        def check():
            try:
                info = self.app_updater.check_for_updates()
                if not info.get('error') and info.get('has_update'):
                    self.update_found_signal.emit(info['latest_version'])
            except Exception:
                pass
        threading.Thread(target=check, daemon=True).start()

    def _on_background_update_found(self, latest_version):
        """Вызывается из main thread когда проверка нашла обновление"""
        self.latest_available_version = latest_version
        self.load_version_info()
    
    def hideEvent(self, event):
        """Обработка скрытия окна - обновляет меню трея"""
        super().hideEvent(event)
        # Обновляем меню трея при скрытии окна
        if hasattr(self, 'tray') and self.tray:
            self.tray.update_menu()
    
    def closeEvent(self, event):
        """Обработка закрытия окна - скрывает в трей"""
        lang = self.settings.get('language', 'ru')
        if self.settings.get('show_in_tray', True):
            event.ignore()
            self.hide()
            self.tray.update_menu()  # Обновляем меню трея
        else:
            # Если трей отключен, закрываем приложение
            self.quit_application()


"""
Окно быстрой настройки при первом запуске программы.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.ui.standard_dialog import StandardDialog
from src.widgets.custom_checkbox import CustomCheckBox
from src.widgets.custom_combobox import CustomComboBox
from src.core.translator import tr
import pywinstyles


class FirstRunWindow(StandardDialog):
    """Диалог быстрой настройки при первом запуске."""

    def __init__(self, parent=None, config=None):
        self.config = config
        lang = 'ru'
        if config:
            settings = config.load_settings()
            lang = settings.get('language', 'ru')

        from src.core.embedded_assets import get_app_icon
        super().__init__(
            parent=parent,
            title=tr('first_run_title', lang),
            width=420,
            height=380,
            icon=get_app_icon(),
            theme="dark"
        )
        self.lang = lang
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        

        pywinstyles.change_header_color(self, color="#181818")
        layout = self.getContentLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Приветствие
        welcome = QLabel(tr('first_run_welcome', self.lang))
        welcome.setWordWrap(True)
        welcome.setStyleSheet("color: #D4D4D4; font-size: 13px;")
        layout.addWidget(welcome)

        # Язык
        lang_group = QGroupBox(tr('first_run_language', self.lang))
        lang_grp = QVBoxLayout()
        self.lang_combo = CustomComboBox()
        self.lang_combo.addItems([
            tr('settings_lang_russian', self.lang),
            tr('settings_lang_english', self.lang),
        ])
        if lang == 'en':
            self.lang_combo.setCurrentIndex(1)
        else:
            self.lang_combo.setCurrentIndex(0)
        lang_grp.addWidget(self.lang_combo)
        lang_group.setLayout(lang_grp)
        layout.addWidget(lang_group)

        # Основные опции
        opts_group = QGroupBox(tr('first_run_options', self.lang))
        opts_grp = QVBoxLayout()
        self.show_tray_cb = CustomCheckBox(tr('settings_show_tray', self.lang))
        self.show_tray_cb.setChecked(True)
        self.show_tray_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        opts_grp.addWidget(self.show_tray_cb)

        self.start_minimized_cb = CustomCheckBox(tr('settings_start_minimized', self.lang))
        self.start_minimized_cb.setChecked(False)
        self.start_minimized_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_minimized_cb.setEnabled(self.show_tray_cb.isChecked())
        self.show_tray_cb.toggled.connect(self.start_minimized_cb.setEnabled)
        opts_grp.addWidget(self.start_minimized_cb)

        self.autostart_cb = CustomCheckBox(tr('settings_autostart_windows', self.lang))
        self.autostart_cb.setChecked(False)
        self.autostart_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        opts_grp.addWidget(self.autostart_cb)

        self.close_winws_cb = CustomCheckBox(tr('settings_close_winws', self.lang))
        self.close_winws_cb.setChecked(True)
        self.close_winws_cb.setCursor(Qt.CursorShape.PointingHandCursor)
        opts_grp.addWidget(self.close_winws_cb)

        opts_group.setLayout(opts_grp)
        layout.addWidget(opts_group)

        layout.addStretch()

        # Кнопка
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_continue = QPushButton(tr('first_run_continue', self.lang))
        self.btn_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_continue.setMinimumWidth(140)
        self.btn_continue.clicked.connect(self._on_continue)
        btn_layout.addWidget(self.btn_continue)
        layout.addLayout(btn_layout)

    def _on_continue(self):
        """Сохраняем настройки и помечаем первый запуск как выполненный."""
        lang = 'ru' if self.lang_combo.currentIndex() == 0 else 'en'
        settings = self.config.load_settings() if self.config else {}
        settings['language'] = lang
        settings['show_in_tray'] = self.show_tray_cb.isChecked()
        settings['start_minimized'] = self.start_minimized_cb.isChecked()
        settings['close_winws_on_exit'] = self.close_winws_cb.isChecked()
        settings['first_run_done'] = True

        if self.config:
            self.config.save_settings(settings)

        # Автозапуск с Windows (если выбран) — вызываем из main_window после показа окна
        self._autostart_enable = self.autostart_cb.isChecked()
        self.accept()

    @property
    def enable_autostart(self):
        return getattr(self, '_autostart_enable', False)

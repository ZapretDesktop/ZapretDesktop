"""
Окно обновления в стиле Visual Studio.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath
from src.widgets.animated_progressbar import AnimatedProgressBar
from src.ui.standard_dialog import StandardDialog
from src.core.embedded_assets import get_app_icon
from src.core.translator import tr
import pywinstyles


class VSUpdateDialog(StandardDialog):
    """Окно обновления в стиле Visual Studio."""
    
    cancelled = pyqtSignal()
    
    def __init__(self, parent=None, language='ru'):
        self.language = language
        from src.core.embedded_assets import get_app_icon
        super().__init__(
            parent=parent,
            title=tr('update_title', language),
            width=500,
            height=280,
            icon=get_app_icon(),
            theme="dark"
        )
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint | Qt.WindowType.CustomizeWindowHint
        )
        
        pywinstyles.change_header_color(self, color="#181818")
        self._cancelled = False
        
        layout = self.getContentLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Заголовок
        self.title_label = QLabel(tr('update_title', self.language))
        self.title_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 20px;
                font-weight: 600;
            }
        """)
        layout.addWidget(self.title_label)
        
        # Статус
        self.status_label = QLabel(tr('update_checking', self.language))
        self.status_label.setStyleSheet("""
            QLabel {
                color: #D4D4D4;
                font-size: 13px;
            }
        """)
        layout.addWidget(self.status_label)
        
        # Прогресс-бар
        self.progress_bar = AnimatedProgressBar(self)
        self.progress_bar.setIndeterminate(True)
        layout.addWidget(self.progress_bar)
        
        # Детальная информация (скрыта по умолчанию)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(80)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #CCCCCC;
                border: 1px solid #3C3C3C;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        self.details_text.hide()
        layout.addWidget(self.details_text)
        
        layout.addStretch()
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.cancel_btn = QPushButton(tr('settings_cancel', self.language))
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.clicked.connect(self._on_cancel)
        self.cancel_btn.hide()  # Скрыта по умолчанию
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
    
    def set_status(self, text, show_details=False):
        """Устанавливает статус и показывает детали при необходимости."""
        self.status_label.setText(text)
        if show_details:
            self.details_text.show()
        else:
            self.details_text.hide()
    
    def add_detail(self, text):
        """Добавляет строку в детальную информацию."""
        self.details_text.append(text)
        self.details_text.show()
        # Автоскролл вниз
        scrollbar = self.details_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def set_progress(self, value):
        """Устанавливает прогресс (0-100)."""
        self.progress_bar.setIndeterminate(False)
        self.progress_bar.setValue(int(value))
    
    def set_indeterminate(self, indeterminate=True):
        """Устанавливает режим неопределённого прогресса."""
        self.progress_bar.setIndeterminate(indeterminate)
    
    def show_cancel(self, show=True):
        """Показывает/скрывает кнопку отмены."""
        self.cancel_btn.setVisible(show)
    
    def _on_cancel(self):
        """Обработчик отмены."""
        self._cancelled = True
        self.cancelled.emit()
        self.reject()
    
    def is_cancelled(self):
        """Проверяет, была ли отмена."""
        return self._cancelled

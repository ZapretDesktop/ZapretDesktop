import os
import re

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QPlainTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from src.widgets.custom_context_widgets import ContextLineEdit, ContextPlainTextEdit
from src.core.translator import tr
from src.core.path_utils import get_winws_path
from src.ui.message_box_utils import configure_message_box
from src.core.window_styles import apply_window_style


class BinCreatorDialog(QDialog):
    """Окно для генерации bin-файлов (пакетов) в winws/bin."""

    def __init__(self, parent=None, language='ru'):
        super().__init__(parent)
        self.language = language

        from src.core.embedded_assets import get_app_icon
        self.setWindowIcon(get_app_icon())
        self.setWindowTitle(tr('menu_create_bin', language))
        self.setModal(True)
        self.setMinimumWidth(520)

        apply_window_style(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

 
 
 
 
 
        # Имя целевого файла в winws/bin
        dst_row = QHBoxLayout()
        dst_row.addWidget(QLabel(tr('bin_creator_dst_label', language)))
        self.dst_edit = ContextLineEdit()
     
        self.dst_edit.setPlaceholderText(tr('bin_creator_dst_placeholder', language))
        dst_row.addWidget(self.dst_edit, 1)
        layout.addLayout(dst_row)

        # Поле для hex-содержимого
        layout.addWidget(QLabel(tr('bin_creator_hex_label', language)))
        self.hex_edit = ContextPlainTextEdit()
        self.hex_edit.setStyleSheet('border:1px solid #2b2b2b;')
        self.hex_edit.setPlaceholderText(tr('bin_creator_hex_placeholder', language))
        self.hex_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.hex_edit, 1)

        # Кнопки
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        create_btn = QPushButton(tr('bin_creator_create_btn', language))
        create_btn.clicked.connect(self._on_create)
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn = QPushButton(tr('settings_cancel', language))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(create_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _on_create(self):
        lang = self.language
        dst_name = self.dst_edit.text().strip()
        hex_text = self.hex_edit.toPlainText().strip()

        if not hex_text:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('bin_creator_need_hex', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return

        if not dst_name:
            dst_name = "custom.bin"

        if not dst_name.lower().endswith('.bin'):
            dst_name += '.bin'

        winws_folder = get_winws_path()
        if not os.path.exists(winws_folder):
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('msg_winws_not_found', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return

        bin_folder = os.path.join(winws_folder, 'bin')
        try:
            os.makedirs(bin_folder, exist_ok=True)
        except Exception as e:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(f"{tr('bin_creator_cannot_create_dir', lang)}\n{e}")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return

        dst_path = os.path.join(bin_folder, dst_name)

        # Парсим hex: убираем всё, кроме 0-9a-fA-F
        hex_str = re.sub(r'[^0-9a-fA-F]', '', hex_text)
        if not hex_str:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('bin_creator_invalid_hex', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        if len(hex_str) % 2 != 0:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(tr('bin_creator_hex_odd', lang))
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return
        try:
            data = bytes.fromhex(hex_str)
        except ValueError as e:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(f"{tr('bin_creator_hex_parse_error', lang)}\n{e}")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return

        try:
            with open(dst_path, 'wb') as f:
                f.write(data)
        except Exception as e:
            msg = configure_message_box(QMessageBox(self))
            msg.setWindowTitle(tr('msg_error', lang))
            msg.setText(f"{tr('bin_creator_write_error', lang)}\n{e}")
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.exec()
            return

        msg = configure_message_box(QMessageBox(self))
        msg.setWindowTitle(tr('msg_result', lang))
        msg.setText(tr('bin_creator_success', lang).format(dst_path))
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()
        self.accept()


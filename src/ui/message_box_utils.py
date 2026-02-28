from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt


def configure_message_box(msg: QMessageBox) -> QMessageBox:
    """
    Настраивает QMessageBox так, чтобы у него была только кнопка закрытия
    (без кнопок свернуть/развернуть), в соответствии с поведением PyQt6.
    """
    flags = msg.windowFlags()
    # Диалоговое окно с только кнопкой закрытия
    flags |= Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
    flags &= ~Qt.WindowType.WindowMinMaxButtonsHint
    # Убираем кнопку справки, если есть
    msg.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
    msg.setWindowFlags(flags)
    return msg


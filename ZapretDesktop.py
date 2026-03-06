import sys
import ctypes
import os
import traceback
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from src.ui.main_window import MainWindow
from src.core.path_utils import get_resource_path, get_config_path, get_winws_path
from src.core.translator import tr
from src.core.config_manager import ConfigManager
from src.core.embedded_assets import get_app_icon
from src.core.embedded_style import EmbeddedStyle
from src.ui import theme


def is_admin():
    """Проверяет, запущена ли программа от имени администратора"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def _check_single_instance():
    """Проверка одного экземпляра. Возвращает (exit_this_process, shared_memory_to_keep).
    Если exit_this_process True — второй экземпляр, нужно подключиться к первому, показать окно и выйти.
    Иначе — первый экземпляр; shared_memory_to_keep нужно хранить до конца работы приложения."""
    from PyQt6.QtCore import QSharedMemory
    shared = QSharedMemory("ZapretDesktop_SingleInstance")
    if shared.create(1):
        return (False, shared)  # первый экземпляр — держим shared, чтобы сегмент не освободился
    if shared.attach():
        # второй экземпляр — просим первый показать окно
        sock = QLocalSocket()
        sock.connectToServer("ZapretDesktop_Show", QLocalSocket.OpenModeFlag.ReadWrite)
        if sock.waitForConnected(1500):
            sock.write(b"show")
            sock.flush()
            sock.disconnectFromServer()
            if sock.state() != QLocalSocket.LocalSocketState.UnconnectedState:
                sock.waitForDisconnected(500)
        return (True, None)
    shared.create(1)  # предыдущий процесс завершился — занимаем снова
    return (False, shared)


def run_as_admin():
    """Перезапускает программу с правами администратора"""
    if is_admin():
        return True
    else:
        # Перезапускаем с правами администратора
        try:
            # Получаем путь к исполняемому файлу Python и скрипту
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
            
            # Запускаем с правами администратора
            ctypes.windll.shell32.ShellExecuteW(
                None,
                "runas",  # Запрашиваем права администратора
                sys.executable,  # Путь к Python
                f'"{script}" {params}',  # Аргументы
                None,
                1  # SW_SHOWNORMAL
            )
            return False
        except Exception as e:
            # Если не удалось перезапустить, показываем сообщение
            app = QApplication(sys.argv)
            
            # Загружаем настройки для определения языка
            config = ConfigManager()
            settings = config.load_settings()
            lang = settings.get('language', 'ru')
            
            msg_box = QMessageBox()
            msg_box.setWindowIcon(get_app_icon())
            msg_box.setIcon(QMessageBox.Icon.Critical)
            msg_box.setWindowTitle(tr('admin_error_title', lang))
            msg_box.setText(tr('admin_error_text', lang).format(str(e)))
            msg_box.exec()
            return False
 

def main():
    if not is_admin():
        app = QApplication(sys.argv)
        
        config = ConfigManager()
        settings = config.load_settings()
        lang = settings.get('language', 'ru')
        
        msg_box = QMessageBox()
        msg_box.setWindowIcon(get_app_icon())
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(tr('admin_required_title', lang))
        msg_box.setText(tr('admin_required_text', lang))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        reply = msg_box.exec()
        
        if reply == QMessageBox.StandardButton.Yes:
            if not run_as_admin():
                sys.exit(0)
            else:
                sys.exit(0)
        else:
            sys.exit(0)
    
    app = QApplication(sys.argv)
    app.setStyle(EmbeddedStyle('Fusion'))
    app.setApplicationName('ZapretDesktop')
    app.setOrganizationName('ZapretDesktop')

    # Тема из настроек (до создания окна)
    config = ConfigManager()
    settings = config.load_settings()
    theme_value = settings.get('color_theme', 'dark')
    theme.set_theme(theme_value)
    app = QApplication.instance()
    app.setStyleSheet(theme.app_stylesheet())

    from src.widgets.custom_scrollbar import ScrollbarStyler
    ScrollbarStyler.apply_scrollbar_style(app, fade_timeout=1000)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 9))

    # Один экземпляр: при повторном запуске поднимаем существующее окно и выходим
    exit_process, single_instance_shared = _check_single_instance()
    if exit_process:
        sys.exit(0)
    # single_instance_shared держим до конца работы приложения

    winws_path = get_winws_path()
    if not os.path.exists(winws_path):
        from src.dialogs.winws_setup_dialog import WinwsSetupDialog

        setup_dialog = WinwsSetupDialog(None, config)
        if setup_dialog.exec() != QDialog.DialogCode.Accepted:
            sys.exit(0)

    window = MainWindow()
    from src.core.window_styles import apply_window_style
    apply_window_style(window)

    # Локальный сервер: второй экземпляр подключается и просит показать окно
    single_instance_server = QLocalServer()
    def on_show_request():
        conn = single_instance_server.nextPendingConnection()
        if conn:
            conn.disconnectFromServer()
            if conn.state() != QLocalSocket.LocalSocketState.UnconnectedState:
                conn.waitForDisconnected(300)
        if window.isMinimized() or not window.isVisible():
            window.show()
            window.raise_()
            window.activateWindow()
        else:
            window.raise_()
            window.activateWindow()
    single_instance_server.newConnection.connect(on_show_request)
    single_instance_server.listen("ZapretDesktop_Show")
    # single_instance_server держим до конца работы

    sys.exit(app.exec())


def show_critical_error(parent, error_msg, detailed_text):
    """Показывает подробное сообщение о критической ошибке"""

    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("Критическая ошибка")
    msg.setText("<b>Произошла критическая ошибка!</b>")
    msg.setInformativeText(
        "Приложение столкнулось с непредвиденной ошибкой и будет закрыто.\n\n"
        "Попробуйте удалить файлы .json из папки %appdata%\\ZapretDesktop\n\n"
        "ZapretDesktop@proton.me\n\n"
        f"Краткое описание: {str(error_msg)}"
    )
    msg.setDetailedText(f"Детали ошибки:\n{detailed_text}")
    msg.setStandardButtons(
        QMessageBox.StandardButton.Ok | 
        QMessageBox.StandardButton.Save
    )
    msg.button(QMessageBox.StandardButton.Ok).setText("Закрыть")
    msg.button(QMessageBox.StandardButton.Save).setText("Сохранить отчет")
    save_button = msg.button(QMessageBox.StandardButton.Save)
    save_button.clicked.connect(lambda: save_error_report(detailed_text))
    
    return msg.exec()

def save_error_report(error_text):
    """Сохраняет отчет об ошибке в файл"""
    from datetime import datetime
    import os
    
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"error_report_{timestamp}.txt"
        report = f"""ОТЧЕТ ОБ ОШИБКЕ
Время: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Python версия: {sys.version}
PyQt версия: QT Version

{error_text}
"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        QMessageBox.information(None, "Сохранено", 
            f"Отчет сохранен в файл:\n{os.path.abspath(filename)}")
            
    except Exception as e:
        QMessageBox.warning(None, "Ошибка сохранения", 
            f"Не удалось сохранить отчет:\n{str(e)}")


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        error_traceback = traceback.format_exc()
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        show_critical_error(None, error, error_traceback)
        sys.exit(1)
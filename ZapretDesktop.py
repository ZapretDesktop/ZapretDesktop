import sys
import ctypes
import os
import traceback
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
from src.ui.main_window import MainWindow
from src.core.path_utils import get_resource_path, get_config_path
from src.core.translator import tr
from src.core.config_manager import ConfigManager
from src.core.embedded_assets import get_app_icon
from src.core.embedded_style import EmbeddedStyle
 


def is_admin():
    """Проверяет, запущена ли программа от имени администратора"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


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

    from PyQt6.QtGui import QPalette, QColor
    
    dark_palette = QPalette()
    vs_background = QColor(24, 24, 24)      # Main background #181818
    vs_dark_gray = QColor(37, 37, 38)       # Secondary background #252526
    vs_medium_gray = QColor(43, 43, 43)     # Borders, inactive items #2b2b2b
    vs_light_gray = QColor(212, 212, 212)   # Main text #D4D4D4
    vs_accent_blue = QColor(38, 79, 120)    # Accent/highlight color #0078d4
    
    dark_palette.setColor(QPalette.ColorRole.Window, vs_background)
    dark_palette.setColor(QPalette.ColorRole.WindowText, vs_light_gray)
    dark_palette.setColor(QPalette.ColorRole.Base, vs_dark_gray)
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, vs_background)
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, vs_dark_gray)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, vs_light_gray)
    dark_palette.setColor(QPalette.ColorRole.Text, vs_light_gray)
    dark_palette.setColor(QPalette.ColorRole.Button, vs_dark_gray)
    dark_palette.setColor(QPalette.ColorRole.ButtonText, vs_light_gray)
    dark_palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 255, 255))
    dark_palette.setColor(QPalette.ColorRole.Link, vs_accent_blue)
    dark_palette.setColor(QPalette.ColorRole.Highlight, vs_accent_blue)
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(128, 128, 128))
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128, 128, 128))
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(128, 128, 128))
    
    app.setPalette(dark_palette)
    
    
    _style_sheet = '''
    QMainWindow::separator {
        width: 7px;
        background: transparent;
    }

    QMenuBar {
        background-color: transparent;
        color: #cccccc;
        border: none;
    }

    QMenuBar::item {
        background-color: transparent;
        padding: 4px 6px;
        border-radius: 0px;
        color: #cccccc;
        margin-top: 2px;
        margin-bottom: 2px;
    }

    QMenuBar::item:selected {
        background-color: #313232;
        color: #cccccc;
        border-radius: 3px;
    }

    QMenuBar::item:pressed {
        background-color: #313232;
        color: #cccccc;
    }

    QMenu {
        background-color: transparent;
        border: none;
        padding: 6px 0px;
    }

    QMenu::item {
        padding: 6px 12px;
        color: #EFEFEF;
        border-radius: 3px;
        margin: 2px 6px;
    }

    QMenu::item:selected {
        background-color: #0078d4;
        border: none;
    }

    QMenu::item:disabled {
        color: #6D6D6D;
        background-color: transparent;
    }

    QMenu::separator {
        height: 1px;
        background: #333333;
        margin: 4px 0px;
    }

    QMenu::indicator {
        width: 16px;
        height: 16px;
        padding-left: 0px;
        margin-left: 0px;
    }

    QMenu::item {
        padding: 4px 20px 4px 12px;
    }

    QMenu::item:has-indicator {
        padding-left: 12px;
    }

    QPushButton {
        background-color: #181818;
        color: #D4D4D4;
        border: 1px solid #2b2b2b;
        padding: 6px 12px;
        border-radius: 6px;
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

    QComboBox {
        background-color: #313131;
        selection-background-color: #0078d4;
        color: #D4D4D4;
        border: 1px solid #3c3c3c;
        border-radius: 6px;
        padding: 5px 10px;
        min-width: 6em;
    }

    QComboBox:hover {
        background-color: #434346;
    }

    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: right;
        width: 20px;
        border-left: 1px solid #313131;
    }

    QComboBox::down-arrow {
        width: 16px;
        height: 16px;
    }

    QComboBox QAbstractItemView {
        background-color: #1f1f1f;
        border: 1px solid #3c3c3c;
        selection-background-color: #094771;
        color: #D4D4D4;
    }

    QLineEdit {
        background-color: transparent;
        color: #D4D4D4;
        border: 1px solid #3c3c3c;
        border-radius: 6px;
        padding: 3px 5px;
    }

    QLineEdit:focus {
        border: 1px solid #0078d4;
    }

    QStatusBar {
        border-top: 1px solid #2b2b2b;
        background-color: #181818;
        color: white;
    }

    QStatusBar QLabel {
        color: white;
    }

    QStatusBar::item {
        border: none;
    }

    QTreeView, QListView {
        background-color: #181818;
        outline: none;
        color: #D4D4D4;
    }

    QTreeView::item, QListView::item {
        border: 1px solid transparent;
    }

    QListWidget::item {
        border: 1px solid transparent;
    }

    QListWidget::item:alternate {
        background-color: #1f1f1f;
    }

    QListWidget::item:hover {
        background-color: #2D2D30;
    }

    QListWidget::item:selected {
        background-color: #04395e;
        border: 1px solid #0078d4;
        color: #FFFFFF;
    }

    QListWidget::item:selected:!active {
        background-color: #1f1f1f;
        color: #ffffff;
    }

    QTreeView::branch:selected {
        background-color: #04395e;
        border: 1px solid #0078d4;
    }

    QTreeView::item:selected, QListView::item:selected {
        background-color: #04395e;
        border: 1px solid #0078d4;
        color: #FFFFFF;
    }

    QTreeView::item:hover:!selected, QListView::item:hover:!selected {
        background-color: #1f1f1f;
    }

    QTreeView::item:!active:selected {
        background-color: #1f1f1f;
        color: #ffffff;
    }

    QTreeView::branch:!active:selected {
        background-color: #1f1f1f;
        color: #ffffff;
    }

    QTreeView::branch {
        background-color: transparent;
    }

    QTreeView::branch:selected {
        background-color: #04395e;
    }

    QSplitter::handle {
        background-color: #333333;
    }

    QSplitter::handle:horizontal {
        width: 1px;
    }

    QSplitter::handle:vertical {
        height: 1px;
    }

    QSplitter::handle:horizontal:hover {
        background-color: #007fd4;
        width: 1px;
    }

    QSplitter::handle:vertical:hover {
        background-color: #007fd4;
        height: 1px;
    }

    QCheckBox {
        color: #D4D4D4;
        spacing: 5px;
    }

    QCheckBox::indicator {
        width: 13px;
        height: 13px;
        border-radius: 3px;
        border: 1px solid #3c3c3c;
        background-color: #313131;
    }

    QRadioButton {
        color: #D4D4D4;
        spacing: 5px;
    }

    QRadioButton::indicator {
        width: 13px;
        height: 13px;
        border: 1px solid #3c3c3c;
        border-radius: 7px;
        background-color: #333333;
    }

    QRadioButton::indicator:checked {
        background-color: #0078d4;
        border: 1px solid #3c3c3c;
        border-radius: 7px;
        width: 13px;
        height: 13px;
    }

    QGroupBox {
        border: 1px solid #3c3c3c;
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
        color: #D4D4D4;
    }

    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 3px;
        color: #D4D4D4;
    }

    QTableView {
        background-color: #1f1f1f;
        alternate-background-color: #1f1f1f;
        color: #D4D4D4;
        gridline-color: #1f1f1f;
        border: 1px solid #2b2b2b;
        selection-background-color: #0078d4;
        selection-color: #FFFFFF;
        outline: none;
    }

    QTableView::item {
        padding: 4px;
        border: none;
    }

    QTableView::item:selected {
        background-color: #0078d4;
        color: #FFFFFF;
    }

    QTableView::item:hover:!selected {
        background-color: #2D2D30;
    }

    QHeaderView {
        background-color: #1f1f1f;
        color: #D4D4D4;
    }

    QHeaderView::section {
        background-color: #1f1f1f;
        color: #D4D4D4;
        padding: 4px;
        border: none;
    }

    QHeaderView::section:checked {
        background-color: #0078d4;
        color: #FFFFFF;
    }

    QHeaderView::section:hover {
        background-color: #2b2b2b;
    }

    QTabWidget {
        background-color: #1f1f1f; 
        border: 1px solid #2b2b2b;
    }

    QTabWidget::pane {
        background-color: #1f1f1f;
        border:1px solid #2b2b2b;
        margin-top: -1px;
    }

    QTabBar::scroller {
        background-color: #2b2b2b;
    }

    QTabBar::scroller::left-arrow {
        background-color: #2b2b2b;
    }

    QTabBar::scroller::right-arrow {
        background-color: #2b2b2b;
    }

    QTabBar::tab {
        background-color: #181818;
        color: #969696;
        border-right: 1px solid #2b2b2b;
        border-top: 1px solid #2b2b2b;
        border-bottom:1px solid #2b2b2b;
        padding: 7px 10px;
        min-width: 80px;
        max-width: 200px;
    }

    QTabBar::tab:selected {
        background-color: #1f1f1f;
        color: #ffffff;
        border-top: 1px solid #0078d4;
        border-bottom:none;
    }

    QTabBar::tab:hover:!selected {
        background-color: #1f1f1f;
    }
    
    QTabBar::close-button {
        image: url(resources/assets/dark/close.svg);
        subcontrol-position: right;       
    }
    
    QTabBar::close-button:hover {
        background-color: #313232;
        width:20px;
        height:20px;
        border-radius: 6px;
    }

    QDialog {
        background-color: #181818;
        color: #D4D4D4;
    }
    
    QTextEdit, QPlainTextEdit {
        background-color: #1f1f1f;
        color: #D4D4D4;
        border: none;
    }

    QSpinBox, QDoubleSpinBox {
        background-color: #181818;
        color: #D4D4D4;
        border: 1px solid #3c3c3c;
        border-radius: 6px;
        padding: 3px 5px;
    }

    QSpinBox:focus, QDoubleSpinBox:focus {
        border: 1px solid #0078d4;
    }

    QSpinBox::up-button, QDoubleSpinBox::up-button {
        background-color: transparent;
        border-left: 1px solid #3c3c3c;
    }

    QSpinBox::down-button, QDoubleSpinBox::down-button {
        background-color: transparent;
        border-left: 1px solid #3c3c3c;
    }

    QProgressBar {
        background-color: transparent;
        border: none;
        height: 2px;
        text-align: center;
    }

    QProgressBar::chunk {
        background-color: #0078d4;
        border: none;
        border-radius: 0px;
    }

    /* Indeterminate progress bar (infinite animation) */
    QProgressBar[indeterminate="true"] {
        background-color: rgba(0, 122, 204, 0.2);
    }

    QProgressBar[indeterminate="true"]::chunk {
        background-color: #0078d4;
        border: none;
        border-radius: 0px;
    }
'''
    app.setStyleSheet(_style_sheet)
    app.setOrganizationName('ZapretDesktop')
    app.setApplicationName('ZapretDesktop')
    from src.widgets.custom_scrollbar import ScrollbarStyler
    ScrollbarStyler.apply_scrollbar_style(app, fade_timeout=1000)
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 9))

    config = ConfigManager()
    settings = config.load_settings()
    if not settings.get('first_run_done', True):
        from src.dialogs.first_run_window import FirstRunWindow
        first_run = FirstRunWindow(None, config)
        first_run.exec()
        if getattr(first_run, 'enable_autostart', False):
            from src.core.autostart_manager import AutostartManager
            AutostartManager().enable()

    window = MainWindow()
    from src.core.window_styles import apply_window_style
    apply_window_style(window)
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
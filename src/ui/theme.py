from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Theme(Enum):
    DARK = "dark"
    LIGHT = "light"


@dataclass(frozen=True)
class ThemePalette:
    """Базовый набор цветов для темы.

    Сейчас используется только для будущего расширения (светлая тема и т.п.).
    Глобовый stylesheet ниже соответствует тёмной теме.
    """

    bg_window: str
    bg_panel: str
    fg_text: str
    fg_muted: str
    accent: str
    border: str
    hover_bg: str
    # Редактор: нумерация строк и подсветка
    line_number_bg: str
    line_number_fg: str
    line_number_current_fg: str
    current_line_bg: str
    occurrence_bg: str
    # Scrollbars
    scrollbar_track: str
    scrollbar_handle: str


_DARK_PALETTE = ThemePalette(
    bg_window="#181818",
    bg_panel="#1f1f1f",
    fg_text="#d4d4d4",
    fg_muted="#969696",
    accent="#0078d4",
    border="#2b2b2b",
    hover_bg="#2a2d2e",
    line_number_bg="#1f1f1f",
    line_number_fg="#808080",
    line_number_current_fg="#d4d4d4",
    current_line_bg="#282828",
    occurrence_bg="#3a3a2e",
    scrollbar_track="#424242",
    scrollbar_handle="#424242",
)

_LIGHT_PALETTE = ThemePalette(
    bg_window="#ffffff",
    bg_panel="#ffffff",
    fg_text="#202020",
    fg_muted="#808080",
    accent="#0078d4",
    border="#d4d4d4",
    hover_bg="#e8e8e8",
    line_number_bg="#ffffff",
    line_number_fg="#909090",
    line_number_current_fg="#202020",
    current_line_bg="#e8e8e8",
    occurrence_bg="#e8e4c4",
    scrollbar_track="#c1c1c1",
    scrollbar_handle="#c1c1c1",
)

_current_theme: Theme = Theme.DARK


def set_theme(theme_value) -> None:
    """Устанавливает текущую тему.

    Принимает как значение Enum Theme.DARK / Theme.LIGHT,
    так и строки 'dark' / 'light' (регистр не важен).
    """
    global _current_theme
    if isinstance(theme_value, Theme):
        _current_theme = theme_value
        return
    if isinstance(theme_value, str):
        name = theme_value.strip().lower()
        if name == "dark":
            _current_theme = Theme.DARK
        elif name == "light":
            _current_theme = Theme.LIGHT
        return


def palette() -> ThemePalette:
    """Возвращает палитру для текущей темы."""
    return _DARK_PALETTE if _current_theme is Theme.DARK else _LIGHT_PALETTE


def current_theme() -> Theme:
    """Возвращает текущую тему."""
    return _current_theme


def is_light() -> bool:
    """True если выбрана светлая тема."""
    return _current_theme is Theme.LIGHT


def muted_label_style() -> str:
    """Стиль приглушённого текста (статусы, подписи)."""
    p = palette()
    return f"color: {p.fg_muted}; font-size: 11px;"


def small_muted_label_style() -> str:
    """Мелкий приглушённый текст (версия, контакт)."""
    p = palette()
    return f"color: {p.fg_muted}; font-size: 10px; margin: 0px;"


def border_style() -> str:
    """Стиль рамки для панелей."""
    p = palette()
    return f"border: 1px solid {p.border};"


def tab_bar_first_border_style() -> str:
    """Стиль левой границы первой вкладки."""
    p = palette()
    return f"QTabBar::tab:first {{ border-left: 1px solid {p.border}; }}"


def list_widget_style() -> str:
    """Стиль QListWidget (файлы, списки)."""
    p = palette()
    return f"""QListWidget {{
        background-color: {p.bg_panel};
        border: none;
        color: {p.fg_text};
    }}
    QListWidget::item {{ height: 20px; }}
    QListWidget::item:hover {{ background-color: {p.hover_bg}; }}
    QListWidget::item:selected {{ background-color: {p.accent}; color: #ffffff; }}"""


def nothing_found_style() -> str:
    """Стиль надписи «ничего не найдено»."""
    p = palette()
    return f"color: {p.fg_muted}; font-size: 13px;"


def panel_bg_style() -> str:
    """Фон панели."""
    p = palette()
    return f"background-color: {p.bg_panel};"


def console_style() -> str:
    """Стиль консоли (тёмная/светлая)."""
    p = palette()
    return f"background-color: {p.bg_window}; border: none; color: {p.fg_text};"


def progress_bar_visible_style() -> str:
    """Видимый прогрессбар (тест, и т.п.)."""
    p = palette()
    return f"""QProgressBar {{
        background-color: {p.bg_panel};
        border: 1px solid {p.border};
        border-radius: 4px;
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {p.accent};
        border-radius: 4px;
    }}"""


_BASE_QSS = """
    QMainWindow {{
        background-color: {bg_window};
        color: {fg_text};
    }}
    QMainWindow::separator {{
        width: 7px;
        background: transparent;
    }}

    QLabel {{
        color: {fg_text};
    }}

    QMenuBar {{
        background-color: transparent;
        color: {fg_text};
        border: none;
    }}

    QMenuBar::item {{
        background-color: transparent;
        padding: 4px 6px;
        border-radius: 0px;
        color: {fg_text};
        margin-top: 2px;
        margin-bottom: 2px;
    }}

    QMenuBar::item:selected,
    QMenuBar::item:pressed {{
        background-color: {hover_bg};
        color: {fg_text};
        border-radius: 3px;
    }}

    QMenu {{
        background-color: transparent;
        border: none;
        padding: 6px 0px;
    }}

    QMenu::item {{
        padding: 6px 12px;
        color: {fg_text};
        border-radius: 3px;
        margin: 2px 6px;
    }}

    QMenu::item:selected {{
        background-color: {accent};
        border: none;
    }}

    QMenu::item:disabled {{
        color: {fg_muted};
        background-color: transparent;
    }}

    QMenu::separator {{
        height: 1px;
        background: {border};
        margin: 4px 0px;
    }}

    QMenu::indicator {{
        width: 16px;
        height: 16px;
        padding-left: 0px;
        margin-left: 0px;
    }}

    QMenu::item:has-indicator {{
        padding-left: 12px;
    }}

    QPushButton {{
        background-color: {bg_window};
        color: {fg_text};
        border: 1px solid {border};
        padding: 6px 12px;
        border-radius: 6px;
    }}

    QPushButton:hover {{
        background-color: {accent};
        border: 1px solid {accent};
    }}

    QPushButton:pressed {{
        background-color: {accent};
        border: 1px solid {accent};
    }}

    QPushButton:disabled {{
        background-color: {bg_panel};
        color: {fg_muted};
    }}

    QComboBox {{
        background-color: {bg_panel};
        selection-background-color: {accent};
        color: {fg_text};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 5px 10px;
        min-width: 6em;
    }}

    QComboBox:hover {{
        background-color: {hover_bg};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: right;
        width: 20px;
        border-left: 1px solid {border};
    }}

    QComboBox::down-arrow {{
        width: 16px;
        height: 16px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {bg_panel};
        border: 1px solid {border};
        selection-background-color: {accent};
        color: {fg_text};
    }}

    QLineEdit {{
        background-color: transparent;
        color: {fg_text};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 3px 5px;
    }}

    QLineEdit:focus {{
        border: 1px solid {accent};
    }}

    QStatusBar {{
        border-top: 1px solid {border};
        background-color: {bg_window};
        color: {fg_text};
    }}

    QStatusBar QLabel {{
        color: {fg_text};
    }}

    QStatusBar::item {{
        border: none;
    }}

    QTreeView, QListView {{
        background-color: {bg_window};
        outline: none;
        color: {fg_text};
    }}

    QTreeView::item, QListView::item {{
        border: 1px solid transparent;
    }}

    QListWidget::item {{
        border: 1px solid transparent;
    }}

    QListWidget::item:alternate {{
        background-color: {bg_panel};
    }}

    QListWidget::item:hover {{
        background-color: {hover_bg};
    }}

    QListWidget::item:selected {{
        background-color: {accent};
        border: 1px solid {accent};
        color: #ffffff;
    }}

    QListWidget::item:selected:!active {{
        background-color: {bg_panel};
        color: #ffffff;
    }}

    QTreeView::branch:selected {{
        background-color: {accent};
        border: 1px solid {accent};
    }}

    QTreeView::item:selected, QListView::item:selected {{
        background-color: {accent};
        border: 1px solid {accent};
        color: #ffffff;
    }}

    QTreeView::item:hover:!selected, QListView::item:hover:!selected {{
        background-color: {bg_panel};
    }}

    QTreeView::item:!active:selected,
    QTreeView::branch:!active:selected {{
        background-color: {bg_panel};
        color: #ffffff;
    }}

    QTreeView::branch {{
        background-color: transparent;
    }}

    QSplitter::handle {{
        background-color: {border};
    }}

    QSplitter::handle:horizontal {{
        width: 1px;
    }}

    QSplitter::handle:vertical {{
        height: 1px;
    }}

    QSplitter::handle:horizontal:hover,
    QSplitter::handle:vertical:hover {{
        background-color: {accent};
    }}

    QCheckBox {{
        color: {fg_text};
        spacing: 5px;
    }}

    QCheckBox::indicator {{
        width: 13px;
        height: 13px;
        border-radius: 3px;
        border: 1px solid {border};
        background-color: {bg_panel};
    }}

    QRadioButton {{
        color: {fg_text};
        spacing: 5px;
    }}

    QRadioButton::indicator {{
        width: 13px;
        height: 13px;
        border: 1px solid {border};
        border-radius: 7px;
        background-color: {bg_panel};
    }}

    QRadioButton::indicator:checked {{
        background-color: {accent};
        border: 1px solid {border};
        border-radius: 7px;
        width: 13px;
        height: 13px;
    }}

    QGroupBox {{
        border: 1px solid {border};
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 10px;
        color: {fg_text};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 3px;
        color: {fg_text};
    }}

    QTableView {{
        background-color: {bg_panel};
        alternate-background-color: {bg_panel};
        color: {fg_text};
        gridline-color: {bg_panel};
        border: 1px solid {border};
        selection-background-color: {accent};
        selection-color: #ffffff;
        outline: none;
    }}

    QTableView::item {{
        padding: 4px;
        border: none;
    }}

    QTableView::item:selected {{
        background-color: {accent};
        color: #ffffff;
    }}

    QTableView::item:hover:!selected {{
        background-color: {hover_bg};
    }}

    QHeaderView {{
        background-color: {bg_panel};
        color: {fg_text};
    }}

    QHeaderView::section {{
        background-color: {bg_panel};
        color: {fg_text};
        padding: 4px;
        border: none;
    }}

    QHeaderView::section:checked {{
        background-color: {accent};
        color: #ffffff;
    }}

    QHeaderView::section:hover {{
        background-color: {hover_bg};
    }}

    QTabWidget {{
        background-color: {bg_panel};
        border: 1px solid {border};
    }}

    QTabWidget::pane {{
        background-color: {bg_panel};
        border:1px solid {border};
        margin-top: -1px;
    }}

    QTabBar::scroller,
    QTabBar::scroller::left-arrow,
    QTabBar::scroller::right-arrow {{
        background-color: {border};
    }}

    QTabBar::tab {{
        background-color: {bg_window};
        color: {fg_muted};
        border-right: 1px solid {border};
        border-top: 1px solid {border};
        border-bottom:1px solid {border};
        padding: 7px 10px;
        min-width: 80px;
        max-width: 200px;
    }}

    QTabBar::tab:selected {{
        background-color: {bg_panel};
        color: {fg_text};
        border-top: 1px solid {accent};
        border-bottom:none;
    }}
    
    QTabBar::tab:hover:!selected {{
        background-color: {bg_panel};
    }}
    
    QTabBar::close-button {{
        image: url(resources/assets/dark/close.svg);
        subcontrol-position: right;       
    }}
    
    QTabBar::close-button:hover {{
        background-color: {hover_bg};
        width:20px;
        height:20px;
        border-radius: 6px;
    }}

    QDialog {{
        background-color: {bg_window};
        color: {fg_text};
    }}
    
    QTextEdit, QPlainTextEdit {{
        background-color: {bg_panel};
        color: {fg_text};
        border: none;
    }}

    QSpinBox, QDoubleSpinBox {{
        background-color: {bg_window};
        color: {fg_text};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 3px 5px;
    }}

    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {accent};
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button,
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        background-color: transparent;
        border-left: 1px solid {border};
    }}

    QProgressBar {{
        background-color: transparent;
        border: none;
        height: 2px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {accent};
        border: none;
        border-radius: 0px;
    }}

    /* Indeterminate progress bar (infinite animation) */
    QProgressBar[indeterminate="true"] {{
        background-color: rgba(0, 122, 204, 0.2);
    }}

    QProgressBar[indeterminate="true"]::chunk {{
        background-color: {accent};
        border: none;
        border-radius: 0px;
    }}
"""


def app_stylesheet() -> str:
    """Возвращает полный stylesheet приложения для текущей темы.

    Один QSS-шаблон заполняется цветами из текущей палитры.
    """
    p = palette()
    return _BASE_QSS.format(
        bg_window=p.bg_window,
        bg_panel=p.bg_panel,
        fg_text=p.fg_text,
        fg_muted=p.fg_muted,
        accent=p.accent,
        border=p.border,
        hover_bg=p.hover_bg,
    )


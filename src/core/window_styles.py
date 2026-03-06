"""
Helper для безопасного применения нативных стилей окна (локальная реализация py-window-styles).

Использование:
    from src.core.window_styles import apply_window_style
    apply_window_style(self)

Логика:
- На Windows 11: меняем цвет заголовка окна на цвет темы, плюс включаем/выключаем тёмный режим.
- На Windows 10: только включаем/выключаем тёмный режим (dark/light), без конкретного цвета.
- На других ОС: ничего не делаем.
"""

from typing import Any
import sys

from src.core import native_window_styles


def _is_windows() -> bool:
    return sys.platform == "win32"


def _is_win11() -> bool:
    if not _is_windows():
        return False
    ver = sys.getwindowsversion()  # type: ignore[attr-defined]
    return ver.major >= 10 and ver.build >= 22000


def apply_window_style(window: Any) -> None:
    """Применяет оформление заголовка окна в зависимости от темы и версии Windows."""
    if not _is_windows():
        # На других ОС ничего не делаем
        return

    # Пытаемся получить сведения о текущей теме
    header_color = "#181818"
    style_name = "dark"
    try:
        from src.ui import theme

        if theme.is_light():
            header_color = "#ffffff"
            style_name = "light"
        else:
            header_color = "#181818"
            style_name = "dark"
    except Exception:
        # Если тема недоступна — используем тёмный по умолчанию
        header_color = "#181818"
        style_name = "dark"

    # Windows 11: пробуем установить конкретный цвет заголовка
    if _is_win11():
        try:
            native_window_styles.change_header_color(window, header_color)
        except Exception:
            # Ошибки игнорируем, продолжаем с apply_style
            pass

    # Windows 10/11: пробуем включить dark/light режим заголовка
    try:
        native_window_styles.apply_style(window, style_name)
    except Exception:
        # Любые ошибки здесь безопасно игнорируем
        return
    

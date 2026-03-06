"""
- change_header_color(window, color) — меняет цвет заголовка в Windows 11
- apply_style(window, style) — включает тёмный/светлый заголовок в Windows 10/11

На других ОС функции ничего не делают.
"""

from __future__ import annotations

from typing import Any
import sys


def _is_windows() -> bool:
    return sys.platform == "win32"


def _is_win11() -> bool:
    if not _is_windows():
        return False
    ver = sys.getwindowsversion()  # type: ignore[attr-defined]
    # Windows 11 имеет build >= 22000
    return ver.major >= 10 and ver.build >= 22000


def _get_hwnd(window: Any) -> int | None:
    """Пытается получить HWND из PyQt6 окна/виджета."""
    try:
        from PyQt6.QtWidgets import QWidget  # type: ignore

        if isinstance(window, QWidget):
            win_id = window.winId()
            try:
                return int(win_id)
            except Exception:
                return None
    except Exception:
        pass
    return None


def _parse_color_hex(color: str) -> int:
    """#RRGGBB -> COLORREF (0x00BBGGRR) для DwmSetWindowAttribute."""
    c = color.lstrip("#")
    if len(c) != 6:
        return 0
    r = int(c[0:2], 16)
    g = int(c[2:4], 16)
    b = int(c[4:6], 16)
    return (b << 16) | (g << 8) | r


def change_header_color(window: Any, color: str) -> None:
    """Меняет цвет заголовка окна (Windows 11, через DwmSetWindowAttribute).

    На Windows 10 и других ОС — ничего не делает.
    """
    if not _is_win11():
        return

    hwnd = _get_hwnd(window)
    if not hwnd:
        return

    try:
        import ctypes

        DWMWA_CAPTION_COLOR = 35  # доступно начиная с Windows 11
        dwmapi = ctypes.windll.dwmapi  # type: ignore[attr-defined]

        colorref = ctypes.c_int(_parse_color_hex(color))
        dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(DWMWA_CAPTION_COLOR),
            ctypes.byref(colorref),
            ctypes.sizeof(colorref),
        )
    except Exception:
        # Любые ошибки — просто игнорируем, чтобы не рушить приложение
        return


def apply_style(window: Any, style: str) -> None:
    """Применяет тёмный/светлый заголовок в Windows 10/11.

    Поддерживаем только style="dark"/"light". Остальные значения игнорируются.
    На других ОС функция ничего не делает.
    """
    if not _is_windows():
        return

    hwnd = _get_hwnd(window)
    if not hwnd:
        return

    style = (style or "").lower()
    if style not in ("dark", "light"):
        return

    try:
        import ctypes

        DWMWA_USE_IMMERSIVE_DARK_MODE = 20  # Win10 1809+ и Win11
        use_dark = 1 if style == "dark" else 0
        value = ctypes.c_int(use_dark)

        dwmapi = ctypes.windll.dwmapi  # type: ignore[attr-defined]
        dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(DWMWA_USE_IMMERSIVE_DARK_MODE),
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except Exception:
        return


def set_caption_buttons(window: Any, *, minimize: bool = True, maximize: bool = True, close: bool = True) -> None:
    """Включает/выключает стандартные кнопки окна (свернуть/развернуть/закрыть) через WinAPI.

    Используется там, где Qt-флаги (WindowMinimizeButtonHint, WindowMaximizeButtonHint)
    работают нестабильно в PyQt6.
    """
    if not _is_windows():
        return

    hwnd = _get_hwnd(window)
    if not hwnd:
        return

    try:
        import ctypes

        GWL_STYLE = -16
        WS_MINIMIZEBOX = 0x00020000
        WS_MAXIMIZEBOX = 0x00010000
        WS_SYSMENU = 0x00080000

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]

        style = user32.GetWindowLongW(hwnd, GWL_STYLE)

        if minimize:
            style |= WS_MINIMIZEBOX
        else:
            style &= ~WS_MINIMIZEBOX

        if maximize:
            style |= WS_MAXIMIZEBOX
        else:
            style &= ~WS_MAXIMIZEBOX

        if close:
            style |= WS_SYSMENU
        else:
            style &= ~WS_SYSMENU

        user32.SetWindowLongW(hwnd, GWL_STYLE, style)

        SWP_NOSIZE = 0x0001
        SWP_NOMOVE = 0x0002
        SWP_NOZORDER = 0x0004
        SWP_FRAMECHANGED = 0x0020

        user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )
    except Exception:
        # Любые ошибки здесь безопасно игнорируем
        return


"""
Helper для безопасного применения pywinstyles.

Использование:
    from src.core.window_styles import apply_window_style
    apply_window_style(self)

Логика:
- пытаемся вызвать pywinstyles.change_header_color(window, color="#181818")
- если возникает ошибка — пробуем pywinstyles.apply_style(window, style="dark")
- если и это не удалось (или pywinstyles не установлен) — просто выходим без исключений
"""

from typing import Any


def apply_window_style(window: Any) -> None:
    """Безопасно применяет оформление окна через pywinstyles, если библиотека доступна."""
    try:
        import pywinstyles  # type: ignore
    except Exception:
        # pywinstyles не установлен или не может быть импортирован — тихо выходим
        return

    try:
        pywinstyles.change_header_color(window, color="#181818")  # type: ignore[attr-defined]
        return
    except Exception:
        # Падаем в запасной режим
        pass

    try:
        pywinstyles.apply_style(window, style="dark")  # type: ignore[attr-defined]
    except Exception:
        # Если и это не удалось — просто не применяем стилизацию
        return


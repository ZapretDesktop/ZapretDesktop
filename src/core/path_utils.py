"""
Утилита для определения правильных путей к файлам и папкам приложения.
Работает как при обычном запуске, так и после компиляции (PyInstaller).
"""
import os
import sys
import json


def get_base_path():
    """
    Возвращает базовую директорию приложения.
    
    Для PyInstaller (скомпилированное приложение):
    - sys._MEIPASS содержит временную папку с распакованными файлами
    - sys.executable содержит путь к .exe файлу
    - Базовая директория - это директория, где находится .exe файл
    
    Для обычного запуска:
    - Базовая директория - это директория, где находится main.py (корень проекта)
    """
    if getattr(sys, 'frozen', False):
        # Приложение скомпилировано (PyInstaller)
        base_path = os.path.dirname(os.path.abspath(sys.executable))
    else:
        # Обычный запуск: path_utils в src/core/ -> поднимаемся до корня проекта (3 уровня вверх)
        _here = os.path.abspath(__file__)
        for _ in range(3):
            _here = os.path.dirname(_here)
        base_path = _here
    return base_path


def get_resource_path(relative_path):
    """
    Возвращает абсолютный путь к ресурсу.
    
    Для PyInstaller:
    - Ресурсы могут быть в sys._MEIPASS (временная папка) или рядом с .exe
    
    Args:
        relative_path: Относительный путь к ресурсу (например, "resources/assets/icon.ico")
    
    Returns:
        Абсолютный путь к ресурсу
    """
    base_path = get_base_path()
    
    # Сначала проверяем рядом с исполняемым файлом
    resource_path = os.path.join(base_path, relative_path)
    if os.path.exists(resource_path):
        return resource_path
    
    # Если не найдено, проверяем в sys._MEIPASS (для PyInstaller)
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        resource_path = os.path.join(sys._MEIPASS, relative_path)
        if os.path.exists(resource_path):
            return resource_path
    
    return os.path.join(base_path, relative_path)


def get_appdata_config_dir():
    """
    Возвращает путь к папке настроек приложения в AppData (ZapretDesktop).
    На Windows: C:\\Users\\<user>\\AppData\\Roaming\\ZapretDesktop
    Работает надёжно даже при автозапуске через планировщик задач.
    """
    appdata = None
    
    # Способ 1: переменная окружения APPDATA
    appdata = os.environ.get('APPDATA', '')
    
    # Способ 2: через Windows Shell API (надёжнее при автозапуске)
    if not appdata:
        try:
            import ctypes
            from ctypes import wintypes
            CSIDL_APPDATA = 26  # Roaming AppData
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_APPDATA, None, 0, buf)
            if buf.value:
                appdata = buf.value
        except Exception:
            pass
    
    # Способ 3: через USERPROFILE + AppData\Roaming
    if not appdata:
        userprofile = os.environ.get('USERPROFILE', '')
        if userprofile:
            appdata = os.path.join(userprofile, 'AppData', 'Roaming')
    
    # Способ 4: через expanduser
    if not appdata:
        home = os.path.expanduser('~')
        if home and home != '~':
            appdata = os.path.join(home, 'AppData', 'Roaming')
    
    # Крайний fallback
    if not appdata:
        appdata = os.path.join('C:', os.sep, 'Users', 'Default', 'AppData', 'Roaming')
    
    return os.path.join(appdata, 'ZapretDesktop')


def get_config_path(relative_path="config.json"):
    """
    Возвращает путь к файлу конфигурации.
    Настройки хранятся в папке AppData\\ZapretDesktop (не рядом с исполняемым файлом).
    
    Args:
        relative_path: Имя файла или относительный путь внутри папки ZapretDesktop
    
    Returns:
        Абсолютный путь к файлу конфигурации
    """
    config_dir = get_appdata_config_dir()
    return os.path.join(config_dir, relative_path)


WINWS_EXE_REL = os.path.join("bin", "winws.exe")


def _detect_winws_folder(base_path):
    """
    Ищет папку winws по наличию bin/winws.exe.
    Сканирует подпапки в base_path; если в подпапке есть bin/winws.exe — это кандидат.
    Возвращает абсолютный путь к найденной папке или None.
    """
    if not base_path or not os.path.isdir(base_path):
        return None
    # 1) Классический вариант: папка winws рядом с программой
    default_winws = os.path.join(base_path, "winws")
    if os.path.isfile(os.path.join(default_winws, WINWS_EXE_REL)):
        return os.path.abspath(default_winws)
    # 2) Сканируем подпапки в папке программы
    candidates = []
    try:
        for name in os.listdir(base_path):
            subdir = os.path.join(base_path, name)
            if os.path.isdir(subdir) and os.path.isfile(os.path.join(subdir, WINWS_EXE_REL)):
                candidates.append(os.path.abspath(subdir))
    except OSError:
        pass
    if not candidates:
        return None
    # Предпочитаем папку с именем winws
    for path in candidates:
        if os.path.basename(path).lower() == "winws":
            return path
    return candidates[0]


def get_winws_path():
    """
    Возвращает путь к папке winws.
    Если в настройках (config) задан свой путь — используется он.
    Иначе автоопределение: поиск подпапки с bin/winws.exe в папке программы.
    Если не найдено — папка winws рядом с исполняемым файлом.
    
    Returns:
        Абсолютный путь к папке winws
    """
    try:
        config_path = get_config_path()
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                custom = (data.get('app') or {}).get('winws_path', '').strip()
                if custom:
                    return os.path.abspath(custom)
    except Exception:
        pass
    base_path = get_base_path()
    detected = _detect_winws_folder(base_path)
    if detected:
        return detected
    return os.path.join(base_path, "winws")

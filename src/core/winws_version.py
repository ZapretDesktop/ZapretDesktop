import os
import re
from typing import Optional, Iterable


_LOCAL_VERSION_PATTERNS = [
    # set "LOCAL_VERSION=1.9.7"
    re.compile(r'^\s*@?\s*set\s+"LOCAL_VERSION=([^"]+)"\s*$', re.IGNORECASE),
    # set LOCAL_VERSION=1.9.7
    re.compile(r'^\s*@?\s*set\s+LOCAL_VERSION=([^\s"]+)\s*$', re.IGNORECASE),
]


def _iter_candidate_service_paths(winws_root: str) -> Iterable[str]:
    """
    Генерирует пути-кандидаты к service.bat.
    Поддерживает ситуации, когда передали:
    - корень winws
    - папку bin
    - путь к winws.exe
    """
    if not winws_root:
        return

    p = os.path.abspath(winws_root)

    # Если передан файл (например, ...\bin\winws.exe) — берём папку файла
    if os.path.isfile(p):
        p = os.path.dirname(p)

    # 1) service.bat в текущей папке
    yield os.path.join(p, "service.bat")

    # 2) Если это папка bin — поднимаемся на уровень вверх
    if os.path.basename(p).lower() == "bin":
        yield os.path.join(os.path.dirname(p), "service.bat")

    # 3) На всякий случай — поднимаемся ещё на уровень вверх
    yield os.path.join(os.path.dirname(p), "service.bat")
    yield os.path.join(os.path.dirname(os.path.dirname(p)), "service.bat")


def read_local_version_from_service(service_bat_path: str) -> Optional[str]:
    """
    Возвращает значение LOCAL_VERSION из service.bat (строка вида: set "LOCAL_VERSION=1.9.7").
    """
    if not service_bat_path or not os.path.exists(service_bat_path):
        return None
    # service.bat обычно ASCII/ANSI; на всякий случай пробуем несколько кодировок.
    encodings = ("utf-8", "cp1251", "cp866", "latin-1")
    for enc in encodings:
        try:
            with open(service_bat_path, "r", encoding=enc, errors="ignore") as f:
                for _ in range(400):
                    line = f.readline()
                    if not line:
                        break
                    s = line.strip()
                    for rx in _LOCAL_VERSION_PATTERNS:
                        m = rx.match(s)
                        if m:
                            return m.group(1).strip()
        except Exception:
            continue
    return None


def read_local_version_from_winws_root(winws_root: str) -> Optional[str]:
    """
    Ищет service.bat в корне winws и возвращает LOCAL_VERSION, если найдено.
    """
    if not winws_root:
        return None
    for candidate in _iter_candidate_service_paths(winws_root):
        v = read_local_version_from_service(candidate)
        if v:
            return v
    return None


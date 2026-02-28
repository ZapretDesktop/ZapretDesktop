"""
Управление автозапуском приложения в Windows с правами администратора.

Использует Планировщик заданий Windows (Task Scheduler) с флагом /RL HIGHEST —
программа запускается при входе в систему с правами администратора без запроса UAC.
"""

import os
import sys
import subprocess


class AutostartManager:
    """Управление автозапуском ZapretDeskop в Windows.

    Создаёт задачу в Планировщике заданий с правами администратора (Run with highest privileges).
    При входе в Windows программа запускается автоматически без запроса UAC.
    Для создания задачи приложение должно быть запущено с правами администратора.
    """

    def __init__(self, app_name="ZapretDeskop"):
        self.app_name = app_name
        self.task_name = f"\\{app_name}"

    def is_enabled(self):
        """Проверяет, включен ли автозапуск (есть задача в планировщике)."""
        try:
            result = subprocess.run(
                ['schtasks', '/query', '/tn', self.task_name],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False

    def enable(self):
        """Включает автозапуск с правами администратора через Планировщик заданий."""
        try:
            self.disable()

            if getattr(sys, 'frozen', False):
                target_path = sys.executable
                arguments = '--autostart'
                work_dir = os.path.dirname(os.path.abspath(sys.executable))
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                main_py = os.path.join(project_root, 'main.py')
                target_path = sys.executable
                arguments = f'"{main_py}" --autostart'
                work_dir = project_root

            # Путь и аргументы для /TR (пути с пробелами в кавычках)
            tr_arg = f'"{target_path}" {arguments}'

            username = os.environ.get('USERNAME', '')
            if not username:
                username = os.environ.get('USER', '')

            cmd = [
                'schtasks', '/Create',
                '/TN', self.task_name,
                '/TR', tr_arg,
                '/SC', 'ONLOGON',
                '/RL', 'HIGHEST',
                '/F',
            ]
            if username:
                cmd.extend(['/RU', username])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode == 0:
                return True
            err = result.stderr or result.stdout or ''
            print(f"Ошибка при создании задачи автозапуска: {err}")
            return False

        except Exception as e:
            print(f"Ошибка при включении автозапуска: {e}")
            return False

    def disable(self):
        """Выключает автозапуск (удаляет задачу из планировщика)."""
        try:
            subprocess.run(
                ['schtasks', '/delete', '/tn', self.task_name, '/f'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            # Удаляем старый ярлык из Startup (миграция со старых версий)
            startup_dir = os.path.join(
                os.environ.get('APPDATA', ''),
                r"Microsoft\Windows\Start Menu\Programs\Startup"
            )
            startup_lnk = os.path.join(startup_dir, f"{self.app_name}.lnk")
            if os.path.exists(startup_lnk):
                try:
                    os.remove(startup_lnk)
                except Exception:
                    pass
            return True
        except Exception as e:
            print(f"Ошибка при выключении автозапуска: {e}")
            return False

    def toggle(self):
        """Переключает состояние автозапуска."""
        if self.is_enabled():
            return self.disable()
        return self.enable()

"""
Класс для проверки и обновления самой программы ZapretDesktop.exe
"""
import os
import requests
import shutil
import sys
import subprocess
from pathlib import Path
from .config_manager import ConfigManager, VERSION
from .path_utils import get_base_path


class AppUpdater:
    """Класс для проверки и обновления программы ZapretDesktop.exe"""
    
    GITHUB_REPO = "ZapretDesktop/ZapretDesktop"
    GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    
    def __init__(self):
        self.config_manager = ConfigManager()
        # Текущая версия всегда берётся из константы VERSION,
        # чтобы конфиг не мог «сломать» логику обновлений.
        self.current_version = self.get_current_version()
        self.base_path = get_base_path()
    
    def get_current_version(self):
        """Получает текущую установленную версию из константы VERSION."""
        return VERSION
    
    def save_version(self, version):
        """Сохраняет версию (сейчас версия приложения задаётся константой VERSION, конфиг не обновляется)."""
        # Версию и md5 больше не храним в config.json, чтобы она контролировалась только из кода.
        return
    
    def check_for_updates(self):
        """Проверяет наличие обновлений на GitHub"""
        try:
            response = requests.get(self.GITHUB_API_URL, timeout=10)
            response.raise_for_status()
            release_data = response.json()
            
            latest_version = release_data.get('tag_name', '').lstrip('v')
            download_url = None
            
            # Ищем exe файл для скачивания
            for asset in release_data.get('assets', []):
                asset_name = asset.get('name', '').lower()
                if asset_name.endswith('.exe') and 'ZapretDesktop' in asset_name:
                    download_url = asset.get('browser_download_url')
                    break
            
            # Если не нашли по имени, ищем любой exe файл
            if not download_url:
                for asset in release_data.get('assets', []):
                    if asset.get('name', '').endswith('.exe'):
                        download_url = asset.get('browser_download_url')
                        break
            
            return {
                'has_update': self._compare_versions(latest_version, self.current_version),
                'latest_version': latest_version,
                'current_version': self.current_version,
                'download_url': download_url,
                'release_url': release_data.get('html_url', ''),
                'release_notes': release_data.get('body', '')
            }
        except requests.RequestException as e:
            return {
                'has_update': False,
                'error': f'Ошибка при проверке обновлений: {str(e)}'
            }
        except Exception as e:
            return {
                'has_update': False,
                'error': f'Неожиданная ошибка: {str(e)}'
            }
    
    def _compare_versions(self, version1, version2):
        """Сравнивает две версии в формате X.Y.Z. Возвращает True если version1 > version2"""
        try:
            # Убираем префикс 'v' если есть
            v1 = version1.lstrip('v').strip()
            v2 = version2.lstrip('v').strip()
            
            v1_parts = [int(x) for x in v1.split('.')]
            v2_parts = [int(x) for x in v2.split('.')]
            
            # Дополняем до одинаковой длины
            max_len = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_len - len(v1_parts)))
            v2_parts.extend([0] * (max_len - len(v2_parts)))
            
            for i in range(max_len):
                if v1_parts[i] > v2_parts[i]:
                    return True
                elif v1_parts[i] < v2_parts[i]:
                    return False
            return False  # Версии равны
        except Exception:
            # Если не удалось сравнить, считаем что есть обновление если версии отличаются
            return v1 != v2 if 'v1' in locals() and 'v2' in locals() else version1 != version2
    
    def download_update(self, download_url, progress_callback=None):
        """Скачивает обновление"""
        try:
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Создаем временную папку для загрузки
            temp_dir = os.path.join(self.base_path, 'temp_update')
            os.makedirs(temp_dir, exist_ok=True)
            
            exe_path = os.path.join(temp_dir, 'ZapretDesktop_new.exe')
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(exe_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress = (downloaded / total_size) * 100
                            progress_callback(progress)
            
            return exe_path
        except Exception as e:
            raise Exception(f'Ошибка при скачивании: {str(e)}')
    
    def install_update(self, exe_path, version):
        """Устанавливает обновление (заменяет старый exe на новый)"""
        try:
            current_exe = sys.executable
            
            # Если программа запущена не из exe файла (например, из Python), используем базовый путь
            if not current_exe.endswith('.exe'):
                current_exe = os.path.join(self.base_path, 'ZapretDesktop.exe')
            
            # Определяем имя exe файла для taskkill
            exe_name = os.path.basename(current_exe)
            
            # Создаем скрипт для обновления
            update_script = os.path.join(self.base_path, 'temp_update', 'update.bat')
            os.makedirs(os.path.dirname(update_script), exist_ok=True)
            
            # Создаем bat файл для замены exe и перезапуска
            with open(update_script, 'w', encoding='utf-8') as f:
                f.write('@echo off\n')
                f.write('timeout /t 2 /nobreak >nul\n')  # Небольшая задержка
                f.write(f'taskkill /F /IM "{exe_name}" >nul 2>&1\n')  # Останавливаем программу
                f.write('timeout /t 1 /nobreak >nul\n')
                f.write(f'copy /Y "{exe_path}" "{current_exe}" >nul\n')  # Копируем новый exe
                f.write(f'if exist "{current_exe}" (\n')
                f.write(f'    start "" "{current_exe}"\n')  # Запускаем новую версию
                f.write(')\n')
                f.write(f'rmdir /S /Q "{os.path.dirname(exe_path)}" >nul 2>&1\n')  # Удаляем временную папку
                f.write(f'del /F /Q "{update_script}" >nul 2>&1\n')  # Удаляем сам скрипт
            
            # Сохраняем версию перед запуском скрипта обновления
            self.save_version(version)
            
            # Запускаем скрипт обновления
            subprocess.Popen([update_script], shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
            
            return True
        except Exception as e:
            raise Exception(f'Ошибка при установке: {str(e)}')

import json
import os
from pathlib import Path
from .path_utils import get_base_path, get_config_path as _get_config_path


VERSION = "1.6.0"
ZAPRET = "1.9.7"
MD5 = "ZapretDesktop@proton.me"

class ConfigManager:
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = _get_config_path()  # AppData/ZapretDesktop/config.json
        # Если путь относительный, делаем его абсолютным относительно папки настроек (AppData)
        if not os.path.isabs(config_path):
            config_dir = os.path.dirname(_get_config_path())
            self.config_path = os.path.join(config_dir, config_path)
        else:
            self.config_path = config_path
        # Не создаём папку json в каталоге программы — конфиг только в AppData
        base_path = get_base_path()
        try:
            base_norm = os.path.normpath(base_path) + os.sep
            path_norm = os.path.normpath(self.config_path)
            if path_norm.startswith(base_norm) and (os.sep + "json" + os.sep in path_norm or path_norm.endswith(os.sep + "json")):
                self.config_path = _get_config_path()
        except Exception:
            pass
        self.default_settings = {
            'language': 'ru',
            'show_in_tray': True,
            'close_winws_on_exit': True,
            'start_minimized': False,
            'auto_start_last_strategy': False,
            'add_b_flag_on_update': True,
            'last_strategy': '',
            'auto_restart_strategy': False,
            'game_filter_enabled': False,
            'ipset_filter_mode': 'loaded',  # 'loaded', 'none', 'any'
            'first_run_done': False,
            'winws_path': '',  # Путь к папке winws; пусто = рядом с программой
            'auto_restart_apps': [],  # Список имён процессов для автоперезапуска (discord.exe и т.п.)
            'zapret_repo': 'Flowseal/zapret-discord-youtube',  # Репозиторий zapret по умолчанию
            'remove_check_updates': False,  # Удалять проверку обновлений zapret из стратегий
        }
        self.default_config = {
            'app': self.default_settings.copy(),
            'zapret_version': {
                'version': ZAPRET
            }
        }
        self.ensure_config_file()
    
    def ensure_config_dir(self):
        """Создает папку конфигурации, если её нет"""
        config_dir = os.path.dirname(self.config_path)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
    
    def ensure_config_file(self):
        """Создает папку и файл конфигурации с настройками по умолчанию, если их нет"""
        self.ensure_config_dir()
        
        if not os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.default_config, f, indent=4, ensure_ascii=False)
            except IOError as e:
                print(f"Ошибка при создании файла конфигурации: {e}")
        else:
            # Миграция старого формата: пытаемся загрузить старые файлы и объединить в новый
            self._migrate_old_config()
    
    def _migrate_old_config(self):
        """Мигрирует старые конфигурационные файлы в новый формат"""
        try:
            # Загружаем текущий config.json
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Если это старый формат (плоский), мигрируем
            if 'app' not in config and any(key in config for key in self.default_settings.keys()):
                old_settings = config.copy()
                config = {
                    'app': {**self.default_settings, **old_settings},
                    'zapret_version': config.get('zapret_version', self.default_config['zapret_version'].copy())
                }
                # Сохраняем мигрированную конфигурацию
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
            
            # Пытаемся загрузить данные из старых файлов, если их еще нет
            base_path = get_base_path()
            old_app_json = os.path.join(base_path, "app/config/app.json")
            old_zapret_version_json = os.path.join(base_path, "app/config/zapret_version.json")
            
            updated = False
            
            # Мигрируем app.json
            if os.path.exists(old_app_json) and 'app' not in config:
                try:
                    with open(old_app_json, 'r', encoding='utf-8') as f:
                        old_app_config = json.load(f)
                        config['app'] = {**self.default_settings, **old_app_config}
                        updated = True
                except Exception:
                    pass
            
            # Мигрируем zapret_version.json
            if os.path.exists(old_zapret_version_json) and 'zapret_version' not in config:
                try:
                    with open(old_zapret_version_json, 'r', encoding='utf-8') as f:
                        config['zapret_version'] = json.load(f)
                        updated = True
                except Exception:
                    pass
            
            # Убеждаемся, что все секции есть
            if 'app' not in config:
                config['app'] = self.default_settings.copy()
                updated = True
            if 'zapret_version' not in config:
                config['zapret_version'] = self.default_config['zapret_version'].copy()
                updated = True
            
            # Сохраняем обновленную конфигурацию
            if updated:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Ошибка при миграции конфигурации: {e}")
    
    def load_all(self):
        """Загружает весь конфигурационный файл"""
        backup_path = self.config_path + '.bak'
        
        # Пробуем загрузить основной конфиг
        config = self._try_load_config(self.config_path)
        
        # Если не удалось, пробуем резервную копию
        if config is None and os.path.exists(backup_path):
            print(f"Восстановление конфигурации из резервной копии...")
            config = self._try_load_config(backup_path)
            if config is not None:
                # Восстанавливаем основной файл из резервной копии
                try:
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, indent=4, ensure_ascii=False)
                except Exception:
                    pass
        
        if config is None:
            return self.default_config.copy()
        
        # Убеждаемся, что все секции присутствуют
        merged_config = {
            'app': {**self.default_settings, **config.get('app', {})},
            'zapret_version': {**self.default_config['zapret_version'], **config.get('zapret_version', {})}
        }
        return merged_config
    
    def _try_load_config(self, path):
        """Пытается загрузить конфиг из указанного файла."""
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        return None
                    return json.loads(content)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Ошибка при загрузке {path}: {e}")
        return None
    
    def load_settings(self):
        """Загружает настройки приложения (секция app) из JSON файла"""
        try:
            config = self.load_all()
            return config.get('app', self.default_settings.copy())
        except Exception as e:
            print(f"Ошибка при загрузке настроек: {e}")
            return self.default_settings.copy()
    
    def save_all(self, config):
        """Сохраняет весь конфигурационный файл"""
        try:
            # Убеждаемся, что папка существует
            self.ensure_config_dir()
            
            # Создаём резервную копию перед сохранением
            backup_path = self.config_path + '.bak'
            if os.path.exists(self.config_path):
                try:
                    import shutil
                    shutil.copy2(self.config_path, backup_path)
                except Exception:
                    pass
            
            # Сохраняем конфигурацию
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Ошибка при сохранении конфигурации: {e}")
            return False
    
    def save_settings(self, settings):
        """Сохраняет настройки приложения (секция app) в JSON файл"""
        try:
            config = self.load_all()
            config['app'] = settings
            return self.save_all(config)
        except Exception as e:
            print(f"Ошибка при сохранении настроек: {e}")
            return False
    
    def get_setting(self, key, default=None):
        """Получает значение настройки"""
        settings = self.load_settings()
        return settings.get(key, default)
    
    def set_setting(self, key, value):
        """Устанавливает значение настройки и сохраняет"""
        settings = self.load_settings()
        settings[key] = value
        self.save_settings(settings)
    
    def update_settings(self, updates):
        """Обновляет несколько настроек одновременно"""
        settings = self.load_settings()
        settings.update(updates)
        self.save_settings(settings)
    
    def get_zapret_version(self):
        """Получает версию zapret"""
        config = self.load_all()
        return config.get('zapret_version', self.default_config['zapret_version'].copy())
    
    def set_zapret_version(self, version):
        """Устанавливает версию zapret"""
        config = self.load_all()
        config['zapret_version'] = {'version': version}
        self.save_all(config)


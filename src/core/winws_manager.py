"""
Модуль для управления настройками winws
"""
import os
from .path_utils import get_winws_path


class WinwsManager:
    """Класс для управления настройками winws"""

    @property
    def winws_folder(self):
        return get_winws_path()

    @property
    def lists_folder(self):
        return os.path.join(self.winws_folder, 'lists')

    @property
    def utils_folder(self):
        return os.path.join(self.winws_folder, 'utils')
    
    # ========== Game Filter Management ==========
    
    def is_game_filter_enabled(self):
        """Проверяет, включен ли Game Filter"""
        game_flag_file = os.path.join(self.utils_folder, 'game_filter.enabled')
        return os.path.exists(game_flag_file)
    
    def enable_game_filter(self):
        """Включает Game Filter"""
        game_flag_file = os.path.join(self.utils_folder, 'game_filter.enabled')
        os.makedirs(self.utils_folder, exist_ok=True)
        with open(game_flag_file, 'w', encoding='utf-8') as f:
            f.write('ENABLED')
    
    def disable_game_filter(self):
        """Выключает Game Filter"""
        game_flag_file = os.path.join(self.utils_folder, 'game_filter.enabled')
        if os.path.exists(game_flag_file):
            os.remove(game_flag_file)
    
    def toggle_game_filter(self):
        """Переключает Game Filter"""
        if self.is_game_filter_enabled():
            self.disable_game_filter()
            return False
        else:
            self.enable_game_filter()
            return True
    
    # ========== IPSet Filter Management ==========
    
    def get_ipset_mode(self):
        """Получает текущий режим IPSet Filter
        
        Returns:
            str: 'loaded', 'none', или 'any'
        """
        list_file = os.path.join(self.lists_folder, 'ipset-all.txt')
        
        if not os.path.exists(list_file):
            return 'loaded'  # По умолчанию
        
        try:
            with open(list_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            line_count = len([line for line in content.split('\n') if line.strip()])
            
            if line_count == 0:
                return 'any'
            elif content == '203.0.113.113/32':
                return 'none'
            else:
                return 'loaded'
        except Exception:
            return 'loaded'
    
    def set_ipset_mode(self, mode):
        """Устанавливает режим IPSet Filter
        
        Args:
            mode: 'loaded', 'none', или 'any'
        """
        list_file = os.path.join(self.lists_folder, 'ipset-all.txt')
        backup_file = list_file + '.backup'
        
        if mode == 'loaded':
            # Восстанавливаем из backup
            if os.path.exists(backup_file):
                if os.path.exists(list_file):
                    os.remove(list_file)
                os.rename(backup_file, list_file)
            else:
                raise Exception('Backup file not found. Update IPSet list first.')
        
        elif mode == 'none':
            # Создаем backup если его нет и файл содержит реальные данные
            if os.path.exists(list_file):
                with open(list_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content and content != '203.0.113.113/32':
                    if not os.path.exists(backup_file):
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            f.write(content)
            
            # Записываем служебный IP
            with open(list_file, 'w', encoding='utf-8') as f:
                f.write('203.0.113.113/32')
        
        elif mode == 'any':
            # Создаем backup если его нет и файл содержит реальные данные
            if os.path.exists(list_file):
                with open(list_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content and content != '203.0.113.113/32':
                    if not os.path.exists(backup_file):
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            f.write(content)
            
            # Делаем файл пустым
            with open(list_file, 'w', encoding='utf-8') as f:
                f.write('')
        else:
            raise ValueError(f'Unknown IPSet mode: {mode}')
    
    # ========== Domain Lists Management ==========
    
    def get_domain_list(self, list_name):
        """Получает содержимое списка доменов
        
        Args:
            list_name: 'list-general.txt', 'list-google.txt', или 'list-exclude.txt'
        
        Returns:
            list: Список доменов
        """
        list_file = os.path.join(self.lists_folder, list_name)
        
        if not os.path.exists(list_file):
            return []
        
        try:
            with open(list_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]
                # Удаляем пустые строки и комментарии
                domains = [line for line in lines if line and not line.startswith('#')]
                return domains
        except Exception:
            return []
    
    def save_domain_list(self, list_name, domains):
        """Сохраняет список доменов
        
        Args:
            list_name: 'list-general.txt', 'list-google.txt', или 'list-exclude.txt'
            domains: list строк с доменами
        """
        list_file = os.path.join(self.lists_folder, list_name)
        os.makedirs(self.lists_folder, exist_ok=True)
        
        # Удаляем пустые строки и очищаем
        clean_domains = [d.strip() for d in domains if d.strip() and not d.strip().startswith('#')]
        
        with open(list_file, 'w', encoding='utf-8') as f:
            for domain in clean_domains:
                f.write(domain + '\n')
    
    def add_domain_to_list(self, list_name, domain):
        """Добавляет домен в список
        
        Args:
            list_name: 'list-general.txt', 'list-google.txt', или 'list-exclude.txt'
            domain: Домен для добавления
        """
        domains = self.get_domain_list(list_name)
        domain = domain.strip()
        
        if domain and domain not in domains:
            domains.append(domain)
            self.save_domain_list(list_name, domains)
    
    def remove_domain_from_list(self, list_name, domain):
        """Удаляет домен из списка
        
        Args:
            list_name: 'list-general.txt', 'list-google.txt', или 'list-exclude.txt'
            domain: Домен для удаления
        """
        domains = self.get_domain_list(list_name)
        domain = domain.strip()
        
        if domain in domains:
            domains.remove(domain)
            self.save_domain_list(list_name, domains)
    
    # ========== IPSet Lists Management ==========
    
    def get_ipset_list(self, list_name='ipset-all.txt'):
        """Получает содержимое IPSet списка
        
        Args:
            list_name: 'ipset-all.txt' или 'ipset-exclude.txt'
        
        Returns:
            list: Список IP адресов в формате CIDR
        """
        list_file = os.path.join(self.lists_folder, list_name)
        
        if not os.path.exists(list_file):
            return []
        
        try:
            with open(list_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines()]
                # Удаляем пустые строки и комментарии
                ips = [line for line in lines if line and not line.startswith('#')]
                return ips
        except Exception:
            return []
    
    def save_ipset_list(self, list_name, ips):
        """Сохраняет IPSet список
        
        Args:
            list_name: 'ipset-all.txt' или 'ipset-exclude.txt'
            ips: list строк с IP адресами в формате CIDR
        """
        list_file = os.path.join(self.lists_folder, list_name)
        os.makedirs(self.lists_folder, exist_ok=True)
        
        # Удаляем пустые строки и очищаем
        clean_ips = [ip.strip() for ip in ips if ip.strip() and not ip.strip().startswith('#')]
        
        with open(list_file, 'w', encoding='utf-8') as f:
            for ip in clean_ips:
                f.write(ip + '\n')
    
    def add_ip_to_list(self, list_name, ip):
        """Добавляет IP адрес в список
        
        Args:
            list_name: 'ipset-all.txt' или 'ipset-exclude.txt'
            ip: IP адрес в формате CIDR
        """
        # Не добавляем служебный IP для ipset-all.txt
        if list_name == 'ipset-all.txt' and ip == '203.0.113.113/32':
            return
        
        ips = self.get_ipset_list(list_name)
        ip = ip.strip()
        
        if ip and ip not in ips:
            ips.append(ip)
            self.save_ipset_list(list_name, ips)
    
    def remove_ip_from_list(self, list_name, ip):
        """Удаляет IP адрес из списка
        
        Args:
            list_name: 'ipset-all.txt' или 'ipset-exclude.txt'
            ip: IP адрес для удаления
        """
        ips = self.get_ipset_list(list_name)
        ip = ip.strip()
        
        if ip in ips:
            ips.remove(ip)
            self.save_ipset_list(list_name, ips)
    
    def validate_cidr(self, cidr):
        """Проверяет корректность CIDR адреса
        
        Args:
            cidr: IP адрес в формате CIDR
        
        Returns:
            bool: True если корректный, False иначе
        """
        import re
        # Простая проверка формата CIDR
        pattern = r'^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$'
        if not re.match(pattern, cidr):
            return False
        
        parts = cidr.split('/')
        ip_parts = parts[0].split('.')
        
        # Проверяем диапазон октетов
        for part in ip_parts:
            num = int(part)
            if num < 0 or num > 255:
                return False
        
        # Проверяем маску если указана
        if len(parts) == 2:
            mask = int(parts[1])
            if mask < 0 or mask > 32:
                return False
        
        return True
    
    def validate_domain(self, domain):
        """Проверяет корректность домена
        
        Args:
            domain: Домен для проверки
        
        Returns:
            bool: True если корректный, False иначе
        """
        import re
        # Простая проверка домена
        pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
        return bool(re.match(pattern, domain))



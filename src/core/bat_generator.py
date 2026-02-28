"""
Модуль для генерации BAT файлов стратегий winws
"""
import os
from .path_utils import get_winws_path
from .winws_manager import WinwsManager


class BatGenerator:
    """Класс для генерации BAT файлов стратегий"""
    
    def __init__(self):
        self.winws_folder = get_winws_path()
        self.winws_manager = WinwsManager()
        self.bin_folder = os.path.join(self.winws_folder, 'bin')
        self.lists_folder = os.path.join(self.winws_folder, 'lists')
    
    def generate_bat_file(self, strategy_name, rules, use_game_filter=True):
        """Генерирует BAT файл стратегии
        
        Args:
            strategy_name: Имя стратегии (без расширения .bat)
            rules: Список правил фильтрации, каждое правило - словарь с параметрами
            use_game_filter: Использовать ли Game Filter
        
        Returns:
            str: Путь к созданному BAT файлу
        """
        bat_file = os.path.join(self.winws_folder, f"{strategy_name}.bat")
        
        # Заголовок BAT файла
        lines = [
            '@echo off',
            'chcp 65001 > nul',
            ':: 65001 - UTF-8',
            '',
            'cd /d "%~dp0"',
            'call service.bat status_zapret',
        ]
        
        if use_game_filter:
            lines.append('call service.bat load_game_filter')
        else:
            lines.append(':: Game Filter disabled')
        
        lines.extend([
            'echo:',
            '',
            'set "BIN=%~dp0bin\\"',
            'set "LISTS=%~dp0lists\\"',
            'cd /d %BIN%',
            '',
        ])
        
        # Собираем порты для Windows Firewall
        wf_tcp_ports = set()
        wf_udp_ports = set()
        
        for rule in rules:
            if 'filter_tcp' in rule:
                ports = self._parse_ports(rule['filter_tcp'])
                wf_tcp_ports.update(ports)
            if 'filter_udp' in rule:
                ports = self._parse_ports(rule['filter_udp'])
                wf_udp_ports.update(ports)
        
        # Добавляем стандартные порты
        wf_tcp_ports.update([80, 443, 2053, 2083, 2087, 2096, 8443])
        wf_udp_ports.update([443, 19294, 19344, 50000, 50100])
        
        if use_game_filter:
            wf_tcp_ports.add('%GameFilter%')
            wf_udp_ports.add('%GameFilter%')
        
        # Формируем строку запуска winws.exe
        wf_tcp_str = ','.join(sorted([str(p) for p in wf_tcp_ports if not isinstance(p, str)]) + 
                                  [p for p in wf_tcp_ports if isinstance(p, str)])
        wf_udp_str = ','.join(sorted([str(p) for p in wf_udp_ports if not isinstance(p, str)]) + 
                                  [p for p in wf_udp_ports if isinstance(p, str)])
        
        # Объединяем диапазоны портов
        wf_tcp_str = self._merge_port_ranges(wf_tcp_str)
        wf_udp_str = self._merge_port_ranges(wf_udp_str)
        
        start_line = f'start "zapret: %~n0" /B /min "%BIN%winws.exe" --wf-tcp={wf_tcp_str} --wf-udp={wf_udp_str}'
        
        # Генерируем правила
        rule_lines = []
        for i, rule in enumerate(rules):
            rule_params = []
            
            # Фильтры трафика
            if 'filter_tcp' in rule:
                rule_params.append(f'--filter-tcp={rule["filter_tcp"]}')
            if 'filter_udp' in rule:
                rule_params.append(f'--filter-udp={rule["filter_udp"]}')
            if 'filter_l7' in rule:
                rule_params.append(f'--filter-l7={rule["filter_l7"]}')
            if 'filter_l3' in rule:
                rule_params.append(f'--filter-l3={rule["filter_l3"]}')
            
            # Списки доменов
            if 'hostlist' in rule:
                rule_params.append(f'--hostlist="%LISTS%{rule["hostlist"]}"')
            if 'hostlist_exclude' in rule:
                rule_params.append(f'--hostlist-exclude="%LISTS%{rule["hostlist_exclude"]}"')
            if 'hostlist_domains' in rule:
                rule_params.append(f'--hostlist-domains={rule["hostlist_domains"]}')
            
            # IPSet списки
            if 'ipset' in rule:
                rule_params.append(f'--ipset="%LISTS%{rule["ipset"]}"')
            if 'ipset_exclude' in rule:
                rule_params.append(f'--ipset-exclude="%LISTS%{rule["ipset_exclude"]}"')
            
            # Дополнительные параметры
            if 'ip_id' in rule:
                rule_params.append(f'--ip-id={rule["ip_id"]}')
            
            # DPI desync методы
            if 'dpi_desync' in rule:
                rule_params.append(f'--dpi-desync={rule["dpi_desync"]}')
                
                if 'dpi_desync_repeats' in rule:
                    rule_params.append(f'--dpi-desync-repeats={rule["dpi_desync_repeats"]}')
                
                if 'dpi_desync_fake_quic' in rule:
                    rule_params.append(f'--dpi-desync-fake-quic="%BIN%{rule["dpi_desync_fake_quic"]}"')
                
                if 'dpi_desync_fake_tls' in rule:
                    rule_params.append(f'--dpi-desync-fake-tls="%BIN%{rule["dpi_desync_fake_tls"]}"')
                
                if 'dpi_desync_fake_tls_mod' in rule:
                    rule_params.append(f'--dpi-desync-fake-tls-mod={rule["dpi_desync_fake_tls_mod"]}')
                
                if 'dpi_desync_fake_unknown_udp' in rule:
                    rule_params.append(f'--dpi-desync-fake-unknown-udp="%BIN%{rule["dpi_desync_fake_unknown_udp"]}"')
                
                if 'dpi_desync_fooling' in rule:
                    rule_params.append(f'--dpi-desync-fooling={rule["dpi_desync_fooling"]}')
                
                if 'dpi_desync_split_seqovl' in rule:
                    rule_params.append(f'--dpi-desync-split-seqovl={rule["dpi_desync_split_seqovl"]}')
                
                if 'dpi_desync_split_pos' in rule:
                    rule_params.append(f'--dpi-desync-split-pos={rule["dpi_desync_split_pos"]}')
                
                if 'dpi_desync_split_seqovl_pattern' in rule:
                    rule_params.append(f'--dpi-desync-split-seqovl-pattern="%BIN%{rule["dpi_desync_split_seqovl_pattern"]}"')
                
                if 'dpi_desync_autottl' in rule:
                    rule_params.append(f'--dpi-desync-autottl={rule["dpi_desync_autottl"]}')
                
                if 'dpi_desync_any_protocol' in rule:
                    rule_params.append(f'--dpi-desync-any-protocol={rule["dpi_desync_any_protocol"]}')
                
                if 'dpi_desync_cutoff' in rule:
                    rule_params.append(f'--dpi-desync-cutoff={rule["dpi_desync_cutoff"]}')
            
            # Добавляем --new для всех правил кроме последнего
            if i < len(rules) - 1:
                rule_params.append('--new')
            
            # Формируем строку правила с переносами
            rule_line = ' ^\n'.join(rule_params)
            if i == 0:
                rule_line = start_line + ' ^\n' + rule_line
            else:
                rule_line = ' ^\n' + rule_line
            
            rule_lines.append(rule_line)
        
        # Объединяем все строки
        lines.extend(rule_lines)
        
        # Записываем файл
        with open(bat_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        return bat_file
    
    def _parse_ports(self, port_string):
        """Парсит строку портов в список
        
        Args:
            port_string: Строка вида "80,443,19294-19344" или "%GameFilter%"
        
        Returns:
            set: Множество портов (может содержать строки типа "%GameFilter%")
        """
        ports = set()
        parts = port_string.split(',')
        
        for part in parts:
            part = part.strip()
            if '-' in part:
                # Диапазон портов
                start, end = part.split('-')
                try:
                    start_port = int(start.strip())
                    end_port = int(end.strip())
                    ports.update(range(start_port, end_port + 1))
                except ValueError:
                    pass
            else:
                # Одиночный порт или переменная
                try:
                    ports.add(int(part))
                except ValueError:
                    # Это может быть переменная типа %GameFilter%
                    ports.add(part)
        
        return ports
    
    def _merge_port_ranges(self, port_string):
        """Объединяет последовательные порты в диапазоны
        
        Args:
            port_string: Строка вида "80,443,19294,19295,19296"
        
        Returns:
            str: Строка с объединенными диапазонами "80,443,19294-19296"
        """
        parts = port_string.split(',')
        ports = []
        variables = []
        
        for part in parts:
            part = part.strip()
            if part.startswith('%') and part.endswith('%'):
                variables.append(part)
            else:
                try:
                    ports.append(int(part))
                except ValueError:
                    ports.append(part)
        
        # Сортируем числовые порты
        numeric_ports = sorted([p for p in ports if isinstance(p, int)])
        other_ports = [p for p in ports if not isinstance(p, int)]
        
        # Объединяем последовательные порты в диапазоны
        merged = []
        if numeric_ports:
            start = numeric_ports[0]
            end = numeric_ports[0]
            
            for port in numeric_ports[1:]:
                if port == end + 1:
                    end = port
                else:
                    if start == end:
                        merged.append(str(start))
                    else:
                        merged.append(f"{start}-{end}")
                    start = port
                    end = port
            
            if start == end:
                merged.append(str(start))
            else:
                merged.append(f"{start}-{end}")
        
        merged.extend(other_ports)
        merged.extend(variables)
        
        return ','.join(merged)
    
    def get_available_bin_files(self):
        """Получает список доступных bin файлов для DPI desync
        
        Returns:
            list: Список имен bin файлов
        """
        bin_files = []
        if os.path.exists(self.bin_folder):
            for file in os.listdir(self.bin_folder):
                if file.endswith('.bin'):
                    bin_files.append(file)
        return bin_files
    
    def get_available_domain_lists(self):
        """Получает список доступных списков доменов
        
        Returns:
            list: Список имен файлов списков доменов
        """
        domain_lists = []
        if os.path.exists(self.lists_folder):
            for file in os.listdir(self.lists_folder):
                if file.endswith('.txt') and not file.startswith('ipset'):
                    domain_lists.append(file)
        return domain_lists
    
    def get_available_ipset_lists(self):
        """Получает список доступных IPSet списков
        
        Returns:
            list: Список имен файлов IPSet списков
        """
        ipset_lists = []
        if os.path.exists(self.lists_folder):
            for file in os.listdir(self.lists_folder):
                if 'ipset' in file.lower() and file.endswith('.txt'):
                    ipset_lists.append(file)
        return ipset_lists
    
    def delete_bat_file(self, strategy_name):
        """Удаляет BAT файл стратегии
        
        Args:
            strategy_name: Имя стратегии (без расширения .bat)
        
        Returns:
            bool: True если файл удален, False если не найден
        """
        bat_file = os.path.join(self.winws_folder, f"{strategy_name}.bat")
        if os.path.exists(bat_file):
            os.remove(bat_file)
            return True
        return False
    
    def get_existing_strategies(self):
        """Получает список существующих стратегий
        
        Returns:
            list: Список имен стратегий (без расширения .bat)
        """
        strategies = []
        if os.path.exists(self.winws_folder):
            for file in os.listdir(self.winws_folder):
                file_path = os.path.join(self.winws_folder, file)
                if file.endswith('.bat') and file != 'service.bat' and os.path.isfile(file_path):
                    strategy_name = file[:-4]  # Убираем .bat
                    strategies.append(strategy_name)
        return sorted(strategies)


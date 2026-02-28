"""
Окно для добавления правила фильтрации winws
"""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from src.core.bat_generator import BatGenerator
from src.widgets.custom_combobox import CustomComboBox
from src.widgets.custom_checkbox import CustomCheckBox
from src.widgets.custom_context_widgets import ContextLineEdit, ContextSpinBox
from src.ui.standard_dialog import StandardDialog
from src.core.translator import tr
import os
import pywinstyles

def StrategyCreatorWindow(parent=None):
    """Функция для открытия окна создания стратегии"""
    dialog = RuleDialog(parent)
    return dialog.exec()


class RuleDialog(StandardDialog):
    """Диалог для создания/редактирования правила фильтрации"""
    
    def __init__(self, parent=None, rule=None):
        self.bat_generator = BatGenerator()
        self.rule = rule or {}
        self.lang = parent.settings.get('language', 'ru') if parent and hasattr(parent, 'settings') else 'ru'
        
        from src.core.embedded_assets import get_app_icon
        super().__init__(
            parent=parent,
            title=tr('create_strategy_title', self.lang),
            width=600,
            height=650,
            icon=get_app_icon(),
            theme="dark"
        )
        
        self.init_ui()
        if rule:
            self.load_rule(rule)
    
     
    def init_ui(self):
        """Инициализация интерфейса"""

        pywinstyles.change_header_color(self, color="#181818")  
    
        # Используем content_layout из StandardDialog
        layout = self.getContentLayout()
        
        # Название стратегии
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel(tr('create_strategy_name_label', self.lang)))
        self.name_edit = ContextLineEdit()
        self.name_edit.setPlaceholderText(tr('create_strategy_placeholder', self.lang))
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        # Использование Game Filter
        self.game_filter_checkbox = CustomCheckBox(tr('create_strategy_use_game_filter', self.lang))
        self.game_filter_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.game_filter_checkbox.setChecked(False)
        layout.addWidget(self.game_filter_checkbox)
        
        # Создаем вкладки
        self.tabs = QTabWidget()
        self.tabs.setCursor(Qt.CursorShape.PointingHandCursor)
        # Левая граница только у первой вкладки ("Фильтры трафика") как в редакторе для вкладки "Списки"
        tab_bar = self.tabs.tabBar()
        tab_bar.setStyleSheet("""
            QTabBar::tab:first {
                border-left: 1px solid #2b2b2b;
            }
        """)
        
        # Вкладка 1: Фильтры трафика
        filters_tab = QWidget()
        filters_layout = QVBoxLayout(filters_tab)
        filters_layout.setContentsMargins(10, 10, 10, 10)
        filters_layout.setSpacing(10)
        
        filter_group = QGroupBox(tr('create_strategy_traffic_filters', self.lang))
        filter_layout = QFormLayout()
        
        self.filter_tcp_edit = ContextLineEdit()
        self.filter_tcp_edit.setPlaceholderText('80,443')
        filter_layout.addRow(tr('create_strategy_tcp_ports', self.lang), self.filter_tcp_edit)
        
        self.filter_udp_edit = ContextLineEdit()
        self.filter_udp_edit.setPlaceholderText('443,19294-19344')
        filter_layout.addRow(tr('create_strategy_udp_ports', self.lang), self.filter_udp_edit)
        
        self.filter_l7_edit = ContextLineEdit()
        self.filter_l7_edit.setPlaceholderText('discord,stun')
        filter_layout.addRow(tr('create_strategy_l7_protocols', self.lang), self.filter_l7_edit)
        
        self.filter_l3_edit = ContextLineEdit()
        self.filter_l3_edit.setPlaceholderText('ipv4')
        filter_layout.addRow(tr('create_strategy_l3_protocols', self.lang), self.filter_l3_edit)
        
        filter_group.setLayout(filter_layout)
        filters_layout.addWidget(filter_group)
        filters_layout.addStretch()
        
        self.tabs.addTab(filters_tab, tr('create_strategy_tab_filters', self.lang))
        
        # Вкладка 2: Списки (Hostlist + IPSet)
        lists_tab = QWidget()
        lists_layout = QVBoxLayout(lists_tab)
        lists_layout.setContentsMargins(10, 10, 10, 10)
        lists_layout.setSpacing(10)
        
        # Списки доменов
        domain_group = QGroupBox(tr('create_strategy_domain_lists', self.lang))
        domain_layout = QFormLayout()
        
        self.hostlist_combo = CustomComboBox()
        self.hostlist_combo.addItem('', '')
        for list_file in self.bat_generator.get_available_domain_lists():
            self.hostlist_combo.addItem(list_file, list_file)
        domain_layout.addRow(tr('create_strategy_hostlist', self.lang), self.hostlist_combo)
        
        self.hostlist_exclude_combo = CustomComboBox()
        self.hostlist_exclude_combo.addItem('', '')
        for list_file in self.bat_generator.get_available_domain_lists():
            self.hostlist_exclude_combo.addItem(list_file, list_file)
        domain_layout.addRow(tr('create_strategy_hostlist_exclude', self.lang), self.hostlist_exclude_combo)
        
        self.hostlist_domains_edit = ContextLineEdit()
        self.hostlist_domains_edit.setPlaceholderText('discord.media')
        domain_layout.addRow(tr('create_strategy_hostlist_domains', self.lang), self.hostlist_domains_edit)
        
        domain_group.setLayout(domain_layout)
        lists_layout.addWidget(domain_group)
        
        # IPSet списки
        ipset_group = QGroupBox(tr('create_strategy_ipset_lists', self.lang))
        ipset_layout = QFormLayout()
        
        self.ipset_combo = CustomComboBox()
        self.ipset_combo.addItem('', '')
        for list_file in self.bat_generator.get_available_ipset_lists():
            self.ipset_combo.addItem(list_file, list_file)
        ipset_layout.addRow(tr('create_strategy_ipset', self.lang), self.ipset_combo)
        
        self.ipset_exclude_combo = CustomComboBox()
        self.ipset_exclude_combo.addItem('', '')
        for list_file in self.bat_generator.get_available_ipset_lists():
            self.ipset_exclude_combo.addItem(list_file, list_file)
        ipset_layout.addRow(tr('create_strategy_ipset_exclude', self.lang), self.ipset_exclude_combo)
        
        ipset_group.setLayout(ipset_layout)
        lists_layout.addWidget(ipset_group)
        lists_layout.addStretch()
        
        self.tabs.addTab(lists_tab, tr('create_strategy_tab_lists', self.lang))
        
        # Вкладка 3: DPI Desync
        dpi_tab = QWidget()
       
        dpi_scroll_widget = QWidget()
        dpi_scroll_layout = QVBoxLayout(dpi_scroll_widget)
        dpi_scroll_layout.setContentsMargins(10, 10, 10, 10)
        dpi_scroll_layout.setSpacing(10)
        
        dpi_group = QGroupBox(tr('create_strategy_dpi_methods', self.lang))
        dpi_layout = QFormLayout()
        
        self.dpi_desync_combo = CustomComboBox()
        self.dpi_desync_combo.addItem('', '')
        self.dpi_desync_combo.addItem('fake', 'fake')
        self.dpi_desync_combo.addItem('multisplit', 'multisplit')
        self.dpi_desync_combo.addItem('syndata', 'syndata')
        self.dpi_desync_combo.addItem('multidisorder', 'multidisorder')
        self.dpi_desync_combo.currentTextChanged.connect(self.on_dpi_method_changed)
        dpi_layout.addRow(tr('create_strategy_dpi_desync', self.lang), self.dpi_desync_combo)
        
        self.dpi_repeats_spin = ContextSpinBox()
        self.dpi_repeats_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.dpi_repeats_spin.setFixedHeight(26)
        self.dpi_repeats_spin.setMinimum(1)
        self.dpi_repeats_spin.setMaximum(20)
        self.dpi_repeats_spin.setValue(6)
        dpi_layout.addRow(tr('create_strategy_repeats', self.lang), self.dpi_repeats_spin)
        
        # Fake QUIC
        self.dpi_fake_quic_combo = CustomComboBox()
        self.dpi_fake_quic_combo.addItem('', '')
        for bin_file in self.bat_generator.get_available_bin_files():
            if 'quic' in bin_file.lower():
                self.dpi_fake_quic_combo.addItem(bin_file, bin_file)
        dpi_layout.addRow(tr('create_strategy_fake_quic', self.lang), self.dpi_fake_quic_combo)
        
        # Fake TLS
        self.dpi_fake_tls_combo = CustomComboBox()
        self.dpi_fake_tls_combo.addItem('', '')
        for bin_file in self.bat_generator.get_available_bin_files():
            if 'tls' in bin_file.lower():
                self.dpi_fake_tls_combo.addItem(bin_file, bin_file)
        dpi_layout.addRow(tr('create_strategy_fake_tls', self.lang), self.dpi_fake_tls_combo)
        
        self.dpi_fake_tls_mod_edit = ContextLineEdit()
        self.dpi_fake_tls_mod_edit.setPlaceholderText(tr('create_strategy_fake_tls_placeholder', self.lang))
        dpi_layout.addRow(tr('create_strategy_fake_tls_mod', self.lang), self.dpi_fake_tls_mod_edit)
        
        # Fooling
        self.dpi_fooling_combo = CustomComboBox()
        self.dpi_fooling_combo.addItem('', '')
        self.dpi_fooling_combo.addItem('ts', 'ts')
        dpi_layout.addRow(tr('create_strategy_fooling', self.lang), self.dpi_fooling_combo)
        
        # Multisplit параметры
        self.dpi_split_seqovl_spin = ContextSpinBox()
        self.dpi_split_seqovl_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.dpi_split_seqovl_spin.setFixedHeight(26)
        self.dpi_split_seqovl_spin.setMinimum(0)
        self.dpi_split_seqovl_spin.setMaximum(2000)
        self.dpi_split_seqovl_spin.setValue(568)
        dpi_layout.addRow(tr('create_strategy_split_seqovl', self.lang), self.dpi_split_seqovl_spin)
        
        self.dpi_split_pos_spin = ContextSpinBox()
        self.dpi_split_pos_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.dpi_split_pos_spin.setFixedHeight(26)
        self.dpi_split_pos_spin.setMinimum(0)
        self.dpi_split_pos_spin.setMaximum(10)
        self.dpi_split_pos_spin.setValue(1)
        dpi_layout.addRow(tr('create_strategy_split_pos', self.lang), self.dpi_split_pos_spin)
        
        self.dpi_split_pattern_combo = CustomComboBox()
        self.dpi_split_pattern_combo.addItem('', '')
        for bin_file in self.bat_generator.get_available_bin_files():
            if 'tls' in bin_file.lower():
                self.dpi_split_pattern_combo.addItem(bin_file, bin_file)
        dpi_layout.addRow(tr('create_strategy_split_pattern', self.lang), self.dpi_split_pattern_combo)
        
        # AutoTTL и другие параметры
        self.dpi_autottl_spin = ContextSpinBox()
        self.dpi_autottl_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.dpi_autottl_spin.setFixedHeight(26)
        self.dpi_autottl_spin.setMinimum(0)
        self.dpi_autottl_spin.setMaximum(10)
        self.dpi_autottl_spin.setValue(0)
        dpi_layout.addRow(tr('create_strategy_autottl', self.lang), self.dpi_autottl_spin)
        
        self.dpi_any_protocol_spin = ContextSpinBox()
        self.dpi_any_protocol_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.dpi_any_protocol_spin.setFixedHeight(26)
        self.dpi_any_protocol_spin.setMinimum(0)
        self.dpi_any_protocol_spin.setMaximum(1)
        self.dpi_any_protocol_spin.setValue(0)
        dpi_layout.addRow(tr('create_strategy_any_protocol', self.lang), self.dpi_any_protocol_spin)
        
        self.dpi_fake_unknown_udp_combo = CustomComboBox()
        self.dpi_fake_unknown_udp_combo.addItem('', '')
        for bin_file in self.bat_generator.get_available_bin_files():
            if 'quic' in bin_file.lower():
                self.dpi_fake_unknown_udp_combo.addItem(bin_file, bin_file)
        dpi_layout.addRow(tr('create_strategy_fake_unknown_udp', self.lang), self.dpi_fake_unknown_udp_combo)
        
        self.dpi_cutoff_combo = CustomComboBox()
        self.dpi_cutoff_combo.addItem('', '')
        self.dpi_cutoff_combo.addItem('n2', 'n2')
        self.dpi_cutoff_combo.addItem('n3', 'n3')
        dpi_layout.addRow(tr('create_strategy_cutoff', self.lang), self.dpi_cutoff_combo)
        
        dpi_group.setLayout(dpi_layout)
        dpi_scroll_layout.addWidget(dpi_group)
        dpi_scroll_layout.addStretch()
        
        
        dpi_tab_layout = QVBoxLayout(dpi_tab)
        dpi_tab_layout.setContentsMargins(0, 0, 0, 0)
        dpi_tab_layout.addWidget(dpi_scroll_widget)
        
        self.tabs.addTab(dpi_tab, tr('create_strategy_tab_dpi', self.lang))
        
        # Вкладка 4: Дополнительно
        extra_tab = QWidget()
        extra_layout = QVBoxLayout(extra_tab)
        extra_layout.setContentsMargins(10, 10, 10, 10)
        extra_layout.setSpacing(10)
        
        extra_group = QGroupBox(tr('create_strategy_extra_params', self.lang))
        extra_form_layout = QFormLayout()
        
        self.ip_id_combo = CustomComboBox()
        self.ip_id_combo.addItem('', '')
        self.ip_id_combo.addItem('zero', 'zero')
        extra_form_layout.addRow(tr('create_strategy_ip_id', self.lang), self.ip_id_combo)
        
        extra_group.setLayout(extra_form_layout)
        extra_layout.addWidget(extra_group)
        extra_layout.addStretch()
        
        self.tabs.addTab(extra_tab, tr('create_strategy_tab_extra', self.lang))
        
        layout.addWidget(self.tabs)
        
        # Кнопка создания файла
        buttons_layout = QHBoxLayout()
        self.create_btn = QPushButton(tr('create_strategy_btn', self.lang))
        self.create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_btn.clicked.connect(self.on_ok_clicked)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.create_btn)
        layout.addLayout(buttons_layout)
    
    def on_ok_clicked(self):
        """Обработка нажатия OK - создание bat файла"""
        # Проверяем название стратегии
        strategy_name = self.name_edit.text().strip()
        if not strategy_name:
            QMessageBox.warning(self, tr('msg_error', self.lang), tr('msg_enter_strategy_name', self.lang))
            return
        
        # Получаем правило
        rule = self.get_rule()
        
        # Проверяем, что правило не пустое
        if not rule:
            QMessageBox.warning(self, tr('msg_error', self.lang), tr('msg_fill_rule_field', self.lang))
            return
        
        # Проверяем, не существует ли уже стратегия с таким именем
        existing = self.bat_generator.get_existing_strategies()
        if strategy_name in existing:
            reply = QMessageBox.question(self, tr('msg_confirm', self.lang),
                tr('msg_confirm_overwrite', self.lang).format(strategy_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            # Создаём bat файл с одним правилом
            self.bat_generator.generate_bat_file(
                strategy_name,
                [rule],  # Список с одним правилом
                self.game_filter_checkbox.isChecked()
            )
            QMessageBox.information(self, tr('msg_success', self.lang), tr('msg_strategy_created', self.lang).format(strategy_name))
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, tr('msg_error', self.lang), tr('msg_error_creating', self.lang).format(str(e)))
    
    def on_dpi_method_changed(self, method):
        """Обновляет доступность полей в зависимости от метода DPI"""
        # Можно добавить логику показа/скрытия полей
        pass
    
    def load_rule(self, rule):
        """Загружает правило в форму"""
        if 'filter_tcp' in rule:
            self.filter_tcp_edit.setText(rule['filter_tcp'])
        if 'filter_udp' in rule:
            self.filter_udp_edit.setText(rule['filter_udp'])
        if 'filter_l7' in rule:
            self.filter_l7_edit.setText(rule['filter_l7'])
        if 'filter_l3' in rule:
            self.filter_l3_edit.setText(rule['filter_l3'])
        if 'hostlist' in rule:
            index = self.hostlist_combo.findData(rule['hostlist'])
            if index >= 0:
                self.hostlist_combo.setCurrentIndex(index)
        if 'hostlist_exclude' in rule:
            index = self.hostlist_exclude_combo.findData(rule['hostlist_exclude'])
            if index >= 0:
                self.hostlist_exclude_combo.setCurrentIndex(index)
        if 'hostlist_domains' in rule:
            self.hostlist_domains_edit.setText(rule['hostlist_domains'])
        if 'ipset' in rule:
            index = self.ipset_combo.findData(rule['ipset'])
            if index >= 0:
                self.ipset_combo.setCurrentIndex(index)
        if 'ipset_exclude' in rule:
            index = self.ipset_exclude_combo.findData(rule['ipset_exclude'])
            if index >= 0:
                self.ipset_exclude_combo.setCurrentIndex(index)
        if 'ip_id' in rule:
            index = self.ip_id_combo.findText(rule['ip_id'])
            if index >= 0:
                self.ip_id_combo.setCurrentIndex(index)
        if 'dpi_desync' in rule:
            index = self.dpi_desync_combo.findText(rule['dpi_desync'])
            if index >= 0:
                self.dpi_desync_combo.setCurrentIndex(index)
        if 'dpi_desync_repeats' in rule:
            self.dpi_repeats_spin.setValue(rule['dpi_desync_repeats'])
        if 'dpi_desync_fake_quic' in rule:
            index = self.dpi_fake_quic_combo.findData(rule['dpi_desync_fake_quic'])
            if index >= 0:
                self.dpi_fake_quic_combo.setCurrentIndex(index)
        if 'dpi_desync_fake_tls' in rule:
            index = self.dpi_fake_tls_combo.findData(rule['dpi_desync_fake_tls'])
            if index >= 0:
                self.dpi_fake_tls_combo.setCurrentIndex(index)
        if 'dpi_desync_fake_tls_mod' in rule:
            self.dpi_fake_tls_mod_edit.setText(rule['dpi_desync_fake_tls_mod'])
        if 'dpi_desync_fooling' in rule:
            index = self.dpi_fooling_combo.findText(rule['dpi_desync_fooling'])
            if index >= 0:
                self.dpi_fooling_combo.setCurrentIndex(index)
        if 'dpi_desync_split_seqovl' in rule:
            self.dpi_split_seqovl_spin.setValue(rule['dpi_desync_split_seqovl'])
        if 'dpi_desync_split_pos' in rule:
            self.dpi_split_pos_spin.setValue(rule['dpi_desync_split_pos'])
        if 'dpi_desync_split_seqovl_pattern' in rule:
            index = self.dpi_split_pattern_combo.findData(rule['dpi_desync_split_seqovl_pattern'])
            if index >= 0:
                self.dpi_split_pattern_combo.setCurrentIndex(index)
        if 'dpi_desync_autottl' in rule:
            self.dpi_autottl_spin.setValue(rule['dpi_desync_autottl'])
        if 'dpi_desync_any_protocol' in rule:
            self.dpi_any_protocol_spin.setValue(rule['dpi_desync_any_protocol'])
        if 'dpi_desync_fake_unknown_udp' in rule:
            index = self.dpi_fake_unknown_udp_combo.findData(rule['dpi_desync_fake_unknown_udp'])
            if index >= 0:
                self.dpi_fake_unknown_udp_combo.setCurrentIndex(index)
        if 'dpi_desync_cutoff' in rule:
            index = self.dpi_cutoff_combo.findText(rule['dpi_desync_cutoff'])
            if index >= 0:
                self.dpi_cutoff_combo.setCurrentIndex(index)
    
    def get_rule(self):
        """Получает правило из формы"""
        rule = {}
        
        filter_tcp = self.filter_tcp_edit.text().strip()
        if filter_tcp:
            rule['filter_tcp'] = filter_tcp
        
        filter_udp = self.filter_udp_edit.text().strip()
        if filter_udp:
            rule['filter_udp'] = filter_udp
        
        filter_l7 = self.filter_l7_edit.text().strip()
        if filter_l7:
            rule['filter_l7'] = filter_l7
        
        filter_l3 = self.filter_l3_edit.text().strip()
        if filter_l3:
            rule['filter_l3'] = filter_l3
        
        hostlist = self.hostlist_combo.currentData()
        if hostlist:
            rule['hostlist'] = hostlist
        
        hostlist_exclude = self.hostlist_exclude_combo.currentData()
        if hostlist_exclude:
            rule['hostlist_exclude'] = hostlist_exclude
        
        hostlist_domains = self.hostlist_domains_edit.text().strip()
        if hostlist_domains:
            rule['hostlist_domains'] = hostlist_domains
        
        ipset = self.ipset_combo.currentData()
        if ipset:
            rule['ipset'] = ipset
        
        ipset_exclude = self.ipset_exclude_combo.currentData()
        if ipset_exclude:
            rule['ipset_exclude'] = ipset_exclude
        
        ip_id = self.ip_id_combo.currentText()
        if ip_id:
            rule['ip_id'] = ip_id
        
        dpi_desync = self.dpi_desync_combo.currentText()
        if dpi_desync:
            rule['dpi_desync'] = dpi_desync
            
            repeats = self.dpi_repeats_spin.value()
            if repeats > 0:
                rule['dpi_desync_repeats'] = repeats
            
            fake_quic = self.dpi_fake_quic_combo.currentData()
            if fake_quic:
                rule['dpi_desync_fake_quic'] = fake_quic
            
            fake_tls = self.dpi_fake_tls_combo.currentData()
            if fake_tls:
                rule['dpi_desync_fake_tls'] = fake_tls
            
            fake_tls_mod = self.dpi_fake_tls_mod_edit.text().strip()
            if fake_tls_mod:
                rule['dpi_desync_fake_tls_mod'] = fake_tls_mod
            
            fooling = self.dpi_fooling_combo.currentText()
            if fooling:
                rule['dpi_desync_fooling'] = fooling
            
            split_seqovl = self.dpi_split_seqovl_spin.value()
            if split_seqovl > 0:
                rule['dpi_desync_split_seqovl'] = split_seqovl
            
            split_pos = self.dpi_split_pos_spin.value()
            if split_pos > 0:
                rule['dpi_desync_split_pos'] = split_pos
            
            split_pattern = self.dpi_split_pattern_combo.currentData()
            if split_pattern:
                rule['dpi_desync_split_seqovl_pattern'] = split_pattern
            
            autottl = self.dpi_autottl_spin.value()
            if autottl > 0:
                rule['dpi_desync_autottl'] = autottl
            
            any_protocol = self.dpi_any_protocol_spin.value()
            if any_protocol > 0:
                rule['dpi_desync_any_protocol'] = any_protocol
            
            fake_unknown_udp = self.dpi_fake_unknown_udp_combo.currentData()
            if fake_unknown_udp:
                rule['dpi_desync_fake_unknown_udp'] = fake_unknown_udp
            
            cutoff = self.dpi_cutoff_combo.currentText()
            if cutoff:
                rule['dpi_desync_cutoff'] = cutoff
        
        return rule

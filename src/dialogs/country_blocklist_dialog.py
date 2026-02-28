"""
Создание списка заблокированных доменов по стране на основе данных OONI.
"""

import os
import re
from urllib.parse import urlparse

from PyQt6.QtWidgets import *
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from src.core.translator import tr
from src.widgets.custom_combobox import CustomComboBox
from src.widgets.custom_checkbox import CustomCheckBox
from src.widgets.custom_context_widgets import ContextLineEdit, ContextSpinBox
from src.core.path_utils import get_winws_path
import pywinstyles

try:
    import requests
except ImportError:
    requests = None

# Страны с известной блокировкой контента (ISO 3166-1 alpha-2)
# (country_code, display_name)
COUNTRIES = [
    ('RU', 'Россия'),
    ('BY', 'Беларусь'),
    ('KZ', 'Казахстан'),
    ('UZ', 'Узбекистан'),
    ('TM', 'Туркменистан'),
    ('TJ', 'Таджикистан'),
    ('KG', 'Киргизия'),
    ('CN', 'Китай'),
    ('IR', 'Иран'),
    ('TR', 'Турция'),
    ('EG', 'Египет'),
    ('VN', 'Вьетнам'),
    ('MM', 'Мьянма'),
    ('PK', 'Пакистан'),
    ('IN', 'Индия'),
    ('AE', 'ОАЭ'),
    ('SA', 'Саудовская Аравия'),
    ('TH', 'Таиланд'),
    ('ID', 'Индонезия'),
    ('MY', 'Малайзия'),
]


def _domain_from_url(url):
    """Извлекает домен из URL."""
    if not url or not isinstance(url, str) or not url.strip():
        return None
    url = url.strip().lower()
    if url.startswith('http://') or url.startswith('https://'):
        try:
            parsed = urlparse(url)
            host = parsed.netloc
            if host and ':' in host:
                host = host.split(':')[0]
            return host if host else None
        except Exception:
            return None
    if url.startswith('stun://') or url.startswith('stun:'):
        # stun://host:port -> host
        m = re.match(r'stun:[/]*([^:/]+)', url, re.I)
        return m.group(1) if m else None
    return None


def fetch_blocked_domains(country_code, limit=1000, confirmed_only=False):
    """
    Загружает список заблокированных доменов для страны через OONI API.
    Возвращает (domains_set, error_message).
    """
    if not requests:
        return set(), 'Модуль requests не установлен'
    
    seen = set()
    next_url = (
        f'https://api.ooni.io/api/v1/measurements'
        f'?probe_cc={country_code}'
        f'&anomaly=true'
        f'&test_name=web_connectivity'
        f'&limit=100'
    )
    if confirmed_only:
        next_url += '&confirmed=true'
    
    fetched = 0
    while next_url and fetched < limit:
        try:
            r = requests.get(next_url, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            return seen, str(e)
        
        results = data.get('results') or []
        for m in results:
            inp = m.get('input')
            domain = _domain_from_url(inp)
            if domain and domain not in seen and '.' in domain:
                seen.add(domain)
                fetched += 1
                if fetched >= limit:
                    break
        
        next_url = data.get('metadata', {}).get('next_url')
        if not results and not next_url:
            break
    
    return seen, None


class CountryBlocklistDialog(QDialog):
    """Диалог создания списка заблокированных адресов по стране"""
    
    def __init__(self, parent=None, lists_folder=None, language='ru'):
        super().__init__(parent)
        self.language = language
        self.lists_folder = lists_folder or os.path.join(get_winws_path(), 'lists')
        self._worker = None
        
        from src.core.embedded_assets import get_app_icon
        self.setWindowIcon(get_app_icon())
        
        pywinstyles.change_header_color(self, color="#181818")
        self.setWindowTitle(tr('country_blocklist_title', language))
        self.setMinimumWidth(420)
        self.resize(450, 280)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel(tr('country_blocklist_description', language)))
        
        form = QFormLayout()
        self.country_combo = CustomComboBox(self)
        for code, name in COUNTRIES:
            self.country_combo.addItem(f'{name} ({code})', code)
        form.addRow(tr('country_blocklist_country', language), self.country_combo)
        
        self.filename_edit = ContextLineEdit()
        self.filename_edit.setPlaceholderText('list-ru.txt')
        self.filename_edit.setText('')
        self.country_combo.currentIndexChanged.connect(lambda: self._update_filename_placeholder())
        form.addRow(tr('country_blocklist_filename', language), self.filename_edit)
        
        self.confirmed_check = CustomCheckBox(tr('country_blocklist_confirmed', language))
        self.confirmed_check.setChecked(True)
        form.addRow('', self.confirmed_check)
        
        self.limit_spin = ContextSpinBox()
        self.limit_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.limit_spin.setRange(100, 5000)
        self.limit_spin.setValue(500)
        self.limit_spin.setSuffix(' ' + tr('country_blocklist_domains', language))
        form.addRow(tr('country_blocklist_limit', language), self.limit_spin)
        
        layout.addLayout(form)
        
        self.progress_label = QLabel()
        self.progress_label.setStyleSheet('color: gray; font-size: 11px;')
        layout.addWidget(self.progress_label)
        
        btns = QHBoxLayout()
        btns.addStretch()
        self.btn_create = QPushButton(tr('country_blocklist_create', language))
        self.btn_create.clicked.connect(self._start_fetch)
        btns.addWidget(self.btn_create)
        self.btn_close = QPushButton(tr('settings_cancel', language))
        self.btn_close.clicked.connect(self.accept)
        btns.addWidget(self.btn_close)
        layout.addLayout(btns)
        
        self._update_filename_placeholder()
        self.created_filename = None  # после успешного создания
    
    def _update_filename_placeholder(self):
        code = self.country_combo.currentData()
        if code:
            self.filename_edit.setPlaceholderText(f'list-{code.lower()}.txt')
    
    def _start_fetch(self):
        if self._worker and self._worker.isRunning():
            return
        filename = self.filename_edit.text().strip()
        if not filename:
            filename = self.filename_edit.placeholderText()
        if not filename.endswith('.txt'):
            filename += '.txt'
        code = self.country_combo.currentData()
        limit = self.limit_spin.value()
        confirmed = self.confirmed_check.isChecked()
        
        self.btn_create.setEnabled(False)
        self.progress_label.setText(tr('country_blocklist_fetching', self.language))
        QApplication.processEvents()
        
        import threading
        def work():
            domains, err = fetch_blocked_domains(code, limit, confirmed)
            self._fetch_result = (domains, err or '', filename)
            QTimer.singleShot(0, self._on_fetch_done)
        
        t = threading.Thread(target=work)
        t.daemon = True
        t.start()
    
    def _on_fetch_done(self):
        if not hasattr(self, '_fetch_result'):
            return
        domains, error, filename = self._fetch_result
        del self._fetch_result
        self.btn_create.setEnabled(True)
        if error:
            self.progress_label.setText(tr('country_blocklist_error', self.language).format(error))
            QMessageBox.warning(
                self, tr('country_blocklist_title', self.language),
                tr('country_blocklist_error', self.language).format(error)
            )
            return
        
        if not domains:
            self.progress_label.setText(tr('country_blocklist_empty', self.language))
            QMessageBox.information(
                self, tr('country_blocklist_title', self.language),
                tr('country_blocklist_empty', self.language)
            )
            return
        
        os.makedirs(self.lists_folder, exist_ok=True)
        path = os.path.join(self.lists_folder, filename)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                for d in sorted(domains):
                    f.write(d + '\n')
            self.created_filename = filename
            self.progress_label.setText(tr('country_blocklist_success', self.language).format(len(domains), path))
            QMessageBox.information(
                self, tr('country_blocklist_title', self.language),
                tr('country_blocklist_success_msg', self.language).format(len(domains), path)
            )
        except Exception as e:
            self.progress_label.setText(str(e))
            QMessageBox.warning(
                self, tr('country_blocklist_title', self.language),
                tr('country_blocklist_save_error', self.language).format(str(e))
            )

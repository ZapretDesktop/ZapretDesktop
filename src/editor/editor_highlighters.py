"""
Подсветка синтаксиса для вкладок редактора: списки, drivers\\etc, .bat
"""

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtCore import QRegularExpression


def _format(color, bold=False, italic=False):
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


class ListHighlighter(QSyntaxHighlighter):
    """Подсветка для списков (list-*.txt, ipset-*.txt): комментарии #, пустые строки."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []
        # Комментарий (# до конца строки)
        fmt_comment = _format("#6A9955")
        self._rules.append((QRegularExpression("#[^\n]*"), fmt_comment))
    
    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class EtcHighlighter(QSyntaxHighlighter):
    """Подсветка для hosts, lmhosts и т.д.: комментарии #, IP-адреса."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []
        fmt_comment = _format("#6A9955")
        self._rules.append((QRegularExpression("#[^\n]*"), fmt_comment))
        # Упрощённый IP (четыре октета)
        fmt_ip = _format("#569CD6")
        self._rules.append((QRegularExpression(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), fmt_ip))
    
    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class BatHighlighter(QSyntaxHighlighter):
    """Подсветка для .bat: комментарии, ключевые слова, строки, переменные, числа, метки."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rules = []
        
        fmt_string = _format("#CE9178")
        self._rules.append((QRegularExpression(r'"[^"]*"'), fmt_string))
        self._rules.append((QRegularExpression(r"'[^']*'"), fmt_string))
        
        fmt_keyword = _format("#C586C0")
        keywords = [
            r"\becho\b", r"\bset\b", r"\bif\b", r"\belse\b", r"\bgoto\b", r"\bcall\b",
            r"\bcd\b", r"\bcls\b", r"\bexit\b", r"\bfor\b", r"\bin\b", r"\bdo\b",
            r"\bstart\b", r"\bendlocal\b", r"\bsetlocal\b", r"\bpushd\b", r"\bpopd\b",
            r"\bshift\b", r"\bpause\b", r"\bbreak\b", r"\bnot\b", r"\bdefined\b",
            r"\bexist\b", r"\berrorlevel\b", r"\bcmd\b", r"\bchoice\b",
            r"\bchcp\b", r"\btimeout\b", r"\btype\b", r"\bcopy\b", r"\bdel\b",
            r"\bmove\b", r"\brename\b", r"\bxcopy\b", r"\bfind\b", r"\bfindstr\b",
            r"\bnetsh\b", r"\bpowershell\b", r"\btaskkill\b", r"\btasklist\b",
            r"\bipconfig\b", r"\bping\b", r"\bsc\b", r"\bschtasks\b", r"\breg\b",
            r"\battrib\b", r"\bmkdir\b", r"\brmdir\b", r"\bdir\b", r"\bmd\b", r"\brd\b",
        ]
        for kw in keywords:
            self._rules.append((QRegularExpression(kw, QRegularExpression.PatternOption.CaseInsensitiveOption), fmt_keyword))
        
        # Операторы сравнения (IF): equ, neq, lss, leq, gtr, geq
        fmt_operator = _format("#D7BA7D")
        self._rules.append((QRegularExpression(r"\b(equ|neq|lss|leq|gtr|geq)\b", QRegularExpression.PatternOption.CaseInsensitiveOption), fmt_operator))
        
        # Опции команд: /c, /k, /d, /b, /min, /a, /p
        fmt_option = _format("#808080")
        self._rules.append((QRegularExpression(r"\s/([a-zA-Z][a-zA-Z0-9-]*)"), fmt_option))
        
        # Переменные окружения: %VAR%, %1, %~dp0, %~n0, %~f0
        fmt_variable = _format("#9CDCFE")
        self._rules.append((QRegularExpression(r"%[^%\s]+%"), fmt_variable))
        self._rules.append((QRegularExpression(r"%~[a-zA-Z]*[0-9]*"), fmt_variable))
        self._rules.append((QRegularExpression(r"%[0-9*]"), fmt_variable))
        
        # Отложенное раскрытие !VAR!
        self._rules.append((QRegularExpression(r"![^!\s]+!"), fmt_variable))
        
        # FOR-переменные %%a, %%i
        self._rules.append((QRegularExpression(r"%%[a-zA-Z]"), fmt_variable))
        
        # Символ @ (подавление вывода)
        self._rules.append((QRegularExpression(r"^\s@"), fmt_option))
        
        # Устройства nul, con, prn
        fmt_device = _format("#569CD6")
        self._rules.append((QRegularExpression(r"\b(nul|con|prn|aux)\b", QRegularExpression.PatternOption.CaseInsensitiveOption), fmt_device))
        
        # Связки &&, || и арифметические операторы SET /A: + - * / %
        self._rules.append((QRegularExpression(r"&&|\|\|"), fmt_operator))
        self._rules.append((QRegularExpression(r"(?<=\d)\s*[+\-*/%]\s*(?=\d)"), fmt_operator))
        self._rules.append((QRegularExpression(r"[()[\]{}]"), fmt_operator))
        
        # Числа: целые, hex (0x...), диапазоны типа 19294-19344
        fmt_number = _format("#B5CEA8")
        self._rules.append((QRegularExpression(r"\b0x[0-9A-Fa-f]+\b"), fmt_number))
        self._rules.append((QRegularExpression(r"\b\d+\b"), fmt_number))
        
        # Параметры --key=value
        fmt_param = _format("#9CDCFE")
        self._rules.append((QRegularExpression(r"--[a-zA-Z0-9-]+"), fmt_param))
        
        # Метки :label (включая кириллицу)
        fmt_label = _format("#DCDCAA")
        self._rules.append((QRegularExpression(r"^\s*:[a-zA-Zа-яА-ЯёЁ0-9_]+\s*$"), fmt_label))
        # Ссылка на метку в goto/call: goto :метка, call :подпрограмма (не ::коммент)
        self._rules.append((QRegularExpression(r"(?<!:):[a-zA-Zа-яА-ЯёЁ0-9_]+"), fmt_label))
        
        # Имена переменных в присваивании: var1=, set "var2=значение2"
        # Исключаем echo (чтобы echo = не подсвечивалось как переменная)
        fmt_var_assign = _format("#9CDCFE")
        self._rules.append((QRegularExpression(r"\b(?!echo\b)[a-zA-Z_а-яА-ЯёЁ][a-zA-Z0-9_а-яА-ЯёЁ]*\s*=", QRegularExpression.PatternOption.CaseInsensitiveOption), fmt_var_assign))
        
        # Комментарии последними, чтобы вся строка была зелёной и курсивом
        fmt_comment = _format("#6A9955", italic=True)
        self._rules.append((QRegularExpression(r"\brem\b[^\n]*", QRegularExpression.PatternOption.CaseInsensitiveOption), fmt_comment))
        self._rules.append((QRegularExpression("::[^\n]*"), fmt_comment))
    
    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

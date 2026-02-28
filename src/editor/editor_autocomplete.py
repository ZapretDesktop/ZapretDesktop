"""
Автодополнение для редактора.
Запуск: Ctrl+Space
Список — дочерний виджет редактора (не окно), фокус не переключается.
"""

import re
from PyQt6.QtWidgets import QFrame, QListWidget, QListWidgetItem, QVBoxLayout, QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PyQt6.QtGui import QTextCursor, QPainter, QPainterPath, QColor, QPen, QFontMetrics, QFont, QRegion
from PyQt6.QtCore import Qt, QPoint, QEvent, QObject, QTimer, QRectF, pyqtSignal, QRect, QSize


# Ключевые слова .bat
BAT_KEYWORDS = [
    "echo", "set", "if", "else", "goto", "call", "cd", "cls", "exit", "for",
    "in", "do", "start", "endlocal", "setlocal", "pushd", "popd", "shift",
    "pause", "break", "not", "defined", "exist", "errorlevel", "chcp",
    "timeout", "type", "copy", "del", "move", "rename", "xcopy", "find",
    "findstr", "netsh", "powershell", "taskkill", "tasklist", "rem",
]

# Опции команд .bat
BAT_OPTIONS = ["/a", "/p", "/c", "/k", "/d", "/b", "/min"]


class AutocompleteItemDelegate(QStyledItemDelegate):
    """Подсветка введённого префикса в тексте дополнения."""

    ITEM_PAD_H = 6  # отступы слева и справа для фона выделения
    ITEM_RADIUS = 4  # радиус закругления углов фона

    def __init__(self, popup, parent=None):
        super().__init__(parent)
        self._popup = popup

    def paint(self, painter, option, index):
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        prefix = getattr(self._popup, "_prefix", "") or ""
        prefix_len = min(len(prefix), len(text)) if prefix and text.lower().startswith(prefix.lower()) else 0
        highlight_color = QColor(42, 170, 255)  # светлее основного текста

        option_copy = QStyleOptionViewItem(option)
        self.initStyleOption(option_copy, index)

        # Фон пункта с отступами и закруглёнными углами
        is_selected = bool(option_copy.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(option_copy.state & QStyle.StateFlag.State_MouseOver)
        bg_rect = option.rect.adjusted(self.ITEM_PAD_H, 2, -self.ITEM_PAD_H, -2)
        if is_selected or is_hover:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            path = QPainterPath()
            path.addRoundedRect(QRectF(bg_rect), self.ITEM_RADIUS, self.ITEM_RADIUS)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(4, 57, 94) if is_selected else QColor(42, 45, 46))
            painter.drawPath(path)
            painter.restore()

        painter.save()
        painter.setFont(self._popup._list.font())
        rect = option.rect.adjusted(self.ITEM_PAD_H + 2, 0, -(self.ITEM_PAD_H + 2), 0)
        fm = painter.fontMetrics()
        y = rect.y() + (rect.height() - fm.height()) // 2 + fm.ascent()

        if prefix_len > 0:
            before = text[:prefix_len]
            after = text[prefix_len:]
            x = rect.x() + 6
            painter.setPen(option_copy.palette.color(option_copy.palette.currentColorGroup(), option_copy.palette.ColorRole.Text))
            is_selected = bool(option_copy.state & QStyle.StateFlag.State_Selected)
            if is_selected:
                painter.setPen(option_copy.palette.color(option_copy.palette.currentColorGroup(), option_copy.palette.ColorRole.HighlightedText))
            # Часть до префикса (обычно пусто)
            # Подсвеченная часть (введённый текст)
            painter.setPen(QColor(42, 170, 255) if is_selected else highlight_color)
            painter.drawText(x, y, before)
            x += fm.horizontalAdvance(before)
            # Остаток
            painter.setPen(option_copy.palette.color(option_copy.palette.currentColorGroup(), option_copy.palette.ColorRole.HighlightedText if is_selected else option_copy.palette.ColorRole.Text))
            painter.drawText(x, y, after)
        else:
            role = option_copy.palette.ColorRole.HighlightedText if (option_copy.state & QStyle.StateFlag.State_Selected) else option_copy.palette.ColorRole.Text
            painter.setPen(option_copy.palette.color(option_copy.palette.currentColorGroup(), role))
            painter.drawText(rect.x() + 6, y, text)
        painter.restore()


class AutocompletePopup(QFrame):
    """Список дополнений как дочерний виджет редактора — не окно, фокус не забирает."""

    itemSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.corner_radius = 6
        self.bg_color = QColor(31, 31, 31)
        self.border_color = QColor(51, 51, 51)
        self.border_width = 1
 

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._list.setCursor(Qt.CursorShape.PointingHandCursor)
        self._list.setStyleSheet("""
           QListWidget {
    background: transparent;
    color: #cccccc;
    padding: 4px 0;
    border: none;
    outline: none;
}
QListWidget::item {
    padding: 4px 20px; /* Увеличенные отступы слева и справа */
}
QListWidget::item:selected {
    background: #04395e;
    color: white;
}
QListWidget::item:hover {
    background: #2a2d2e;
}
QListWidget::item:!active {
    border-left: 1px solid #2b2b2b;
    border-right: 1px solid #2b2b2b;
    border-top: none;
    border-bottom: none;
}
QListWidget::item:selected:!active {
    background-color: #04395e;
}
        """)
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sb = self._list.verticalScrollBar()
        sb.setStyleSheet("""
            QScrollBar:vertical {
                background: #2b2b2b;
                width: 8px;
                border-radius: 4px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background: #606060;
                border-radius: 4px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: #707070; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self._list.setItemDelegate(AutocompleteItemDelegate(self))
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self._prefix = ""
        self._max_height = 280
        self._current_max_h = 280
        self._min_width = 180
        self._text_padding = 40

    def _updateClipMask(self):
        """Маска на весь фрейм — обрезка по скруглённым углам (включая фон пунктов списка)."""
        r = self.rect()
        if r.isEmpty():
            return
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), self.corner_radius, self.corner_radius)
        poly = path.toFillPolygon()
        self.setMask(QRegion(poly.toPolygon()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._updateClipMask()

    def _on_item_clicked(self, item):
        if item:
            self.itemSelected.emit(item.text())
            self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path.addRoundedRect(rect, self.corner_radius, self.corner_radius)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.bg_color)
        painter.drawPath(path)
        pen = QPen(self.border_color, self.border_width)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def setItems(self, items, prefix="", editor=None):
        self._prefix = prefix
        editor = editor or self.parent()
        if editor:
            ed_font = editor.font()
            self._list.setFont(ed_font)
            scale = max(0.6, min(1.5, ed_font.pointSize() / 10.0))
            self._current_max_h = int(self._max_height * scale)
        else:
            self._current_max_h = self._max_height
        self._list.clear()
        for s in items:
            self._list.addItem(QListWidgetItem(s))
        if self._list.count():
            self._list.setCurrentRow(0)
        # Подогнать размер под содержимое — без лишнего пространства
        n = self._list.count()
        if n > 0:
            row_h = self._list.sizeHintForRow(0)
            content_h = n * row_h + 2 * self._list.frameWidth()
            max_h = getattr(self, '_current_max_h', self._max_height)
            self._list.setFixedHeight(min(content_h, max_h))
            fm = QFontMetrics(self._list.font())
            w = self._min_width
            for i in range(n):
                w = max(w, fm.horizontalAdvance(self._list.item(i).text()) + self._text_padding)
            w = w + 16  # скроллбар + отступы от краёв фрейма
            self.setFixedWidth(w)
            max_h = getattr(self, '_current_max_h', self._max_height)
            self._list.setFixedHeight(min(content_h, max_h))
        else:
            self.setFixedWidth(self._min_width)
            self._list.setFixedHeight(0)

    def syncFontFromEditor(self, editor):
        """Обновить шрифт и размер при изменении масштаба редактора."""
        if not editor or self._list.count() == 0:
            return
        items = [self._list.item(i).text() for i in range(self._list.count())]
        self.setItems(items, self._prefix, editor)
        self.adjustSize()
        self._updateClipMask()
        pw, ph = self.width(), self.height()
        ew, eh = editor.width(), editor.height()
        cursor = editor.textCursor()
        rect = editor.cursorRect(cursor)
        pt = editor.viewport().mapTo(editor, rect.bottomLeft())
        x = max(0, min(pt.x(), ew - pw))
        y = pt.y() + 2
        if y + ph > eh:
            y = pt.y() - ph - 2
        y = max(0, min(y, eh - ph))
        self.move(x, y)

    def showBelowCursor(self, editor):
        """Показать под курсором, не выходя за границы редактора."""
        cursor = editor.textCursor()
        rect = editor.cursorRect(cursor)
        pt = editor.viewport().mapTo(editor, rect.bottomLeft())
        self.adjustSize()

        pw, ph = self.width(), self.height()
        ew, eh = editor.width(), editor.height()

        x = pt.x()
        x = max(0, min(x, ew - pw))
        y = pt.y() + 2
        if y + ph > eh:
            y = pt.y() - ph - 2
        y = max(0, min(y, eh - ph))

        self.move(x, y)
        self._updateClipMask()
        self.raise_()
        self.show()

    def currentText(self):
        row = self._list.currentRow()
        if 0 <= row < self._list.count():
            return self._list.item(row).text()
        return ""

    def selectNext(self):
        n = self._list.count()
        if n == 0:
            return
        row = (self._list.currentRow() + 1) % n
        self._list.setCurrentRow(row)

    def selectPrevious(self):
        n = self._list.count()
        if n == 0:
            return
        row = self._list.currentRow() - 1
        if row < 0:
            row = n - 1
        self._list.setCurrentRow(row)

    def itemCount(self):
        return self._list.count()


def _get_word_before_cursor(editor):
    """Возвращает (слово_до_курсора, start_pos, end_pos)."""
    cursor = editor.textCursor()
    block = cursor.block()
    text = block.text()
    pos = cursor.positionInBlock()
    # Слово: буквы, цифры, подчёркивание, %
    match = re.search(r'[\w%!]+$', text[:pos])
    if match:
        word = match.group(0)
        start = cursor.position() - len(word)
        return word, start, cursor.position()
    return "", cursor.position(), cursor.position()


def _get_labels_from_document(editor):
    """Извлекает метки :name из документа."""
    labels = []
    doc = editor.document()
    for i in range(doc.blockCount()):
        block = doc.findBlockByNumber(i)
        text = block.text().strip()
        m = re.match(r'^\s*:([a-zA-Zа-яА-ЯёЁ0-9_]+)', text)
        if m:
            labels.append(":" + m.group(1))
    return labels


def _get_words_from_document(editor):
    """Все уникальные слова из файла (буквы, цифры, _, точка) — для автодополнения по уже имеющемуся тексту."""
    seen = set()
    doc = editor.document()
    # Слово: буквенно-цифровые, подчёркивание, точка (для hostname/domain)
    word_re = re.compile(r'[\w.]+', re.UNICODE)
    for i in range(doc.blockCount()):
        block = doc.findBlockByNumber(i)
        for word in word_re.findall(block.text()):
            if len(word) >= 2 and word not in seen:
                seen.add(word)
                yield word


def _get_completions(editor, tab_kind, prefix):
    """Возвращает список дополнений для prefix."""
    prefix_lower = prefix.lower()
    completions = []
    seen = set()

    def add(items):
        for item in items:
            if item.lower().startswith(prefix_lower) and item not in seen:
                seen.add(item)
                completions.append(item)

    # Слова, которые уже есть в файле (Pass -> Password и т.д.)
    add(list(_get_words_from_document(editor)))

    if tab_kind == "bat":
        add(BAT_KEYWORDS)
        add(BAT_OPTIONS)
        add(_get_labels_from_document(editor))
    elif tab_kind == "lists":
        add(["#"])
    # etc — дополнения только из документа выше

    return sorted(completions, key=lambda x: (not x.lower().startswith(prefix_lower), x.lower()))


class EditorAutocomplete(QObject):
    """Автодополнение для QPlainTextEdit через popup без взятия фокуса."""

    def __init__(self, editor, tab_kind="lists"):
        super().__init__(editor)
        self.editor = editor
        self.tab_kind = tab_kind
        self._popup = None
        self._prefix_start = 0
        self._prefix_end = 0
        self._auto_timer = QTimer(self)
        self._auto_timer.setSingleShot(True)
        self._auto_timer.setInterval(0)
        self._auto_timer.timeout.connect(self._on_auto_timer)
        editor.installEventFilter(self)
        editor.viewport().installEventFilter(self)

    def _get_popup(self):
        if self._popup is None:
            self._popup = AutocompletePopup(self.editor)
            self._popup.itemSelected.connect(self._on_selected)
        return self._popup

    def _on_auto_timer(self):
        """Показать автодополнение после паузы при наборе текста."""
        word, start, end = _get_word_before_cursor(self.editor)
        if not word:
            return
        completions = _get_completions(self.editor, self.tab_kind, word)
        if completions:
            self._show_completions()

    def _show_completions(self):
        word, start, end = _get_word_before_cursor(self.editor)
        completions = _get_completions(self.editor, self.tab_kind, word)

        if not completions:
            return

        self._prefix_start = start
        self._prefix_end = end

        popup = self._get_popup()
        if popup.isVisible():
            popup.hide()
        popup.setItems(completions[:30], word, self.editor)

        popup.showBelowCursor(self.editor)

    def _on_selected(self, completion):
        if self._popup:
            self._popup.hide()
        cursor = self.editor.textCursor()
        cursor.setPosition(self._prefix_start)
        cursor.setPosition(self._prefix_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(completion)
        self.editor.setTextCursor(cursor)

    def _is_popup_visible(self):
        return self._popup is not None and self._popup.isVisible()

    def on_editor_font_changed(self):
        """Вызывается при изменении масштаба (Ctrl+/Ctrl-/Ctrl+0)."""
        if self._is_popup_visible():
            self._popup.syncFontFromEditor(self.editor)

    def show(self):
        """Показать автодополнение (Ctrl+Space или из меню)."""
        self._show_completions()

    def eventFilter(self, obj, event):
        try:
            if obj not in (self.editor, self.editor.viewport()):
                return False
        except RuntimeError:
            return False
        try:
            if event.type() == QEvent.Type.KeyPress:
                key = event.key()
                mods = event.modifiers()
                if key == Qt.Key.Key_Space and mods & Qt.KeyboardModifier.ControlModifier:
                    self._show_completions()
                    return True
                if self._is_popup_visible():
                    if key == Qt.Key.Key_Down:
                        self._popup.selectNext()
                        return True
                    if key == Qt.Key.Key_Up:
                        self._popup.selectPrevious()
                        return True
                    if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                        text = self._popup.currentText()
                        if text:
                            self._on_selected(text)
                        return True
                    if key == Qt.Key.Key_Escape:
                        self._popup.hide()
                        return True
                    text = event.text()
                    if not text or not (text.isalnum() or text in '%!/_:'):
                        self._popup.hide()
                        return False
                if not mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
                    text = event.text()
                    if text and (text.isalnum() or text in '%!/_:'):
                        if self._is_popup_visible():
                            self._popup.hide()
                        QTimer.singleShot(0, self._on_auto_timer)
                        return False
            elif event.type() == QEvent.Type.FontChange and obj == self.editor:
                if self._is_popup_visible():
                    QTimer.singleShot(0, lambda: self._popup.syncFontFromEditor(self.editor))
            elif event.type() == QEvent.Type.FocusOut:
                self._auto_timer.stop()
                if self._is_popup_visible():
                    self._popup.hide()
            elif event.type() == QEvent.Type.MouseButtonPress and self._is_popup_visible():
                g = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                local = self.editor.mapFromGlobal(g)
                if not self._popup.geometry().contains(local):
                    self._popup.hide()
        except RuntimeError:
            return False
        return False

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QIcon, QWheelEvent
from PyQt6.QtCore import Qt, QRectF, QSize, pyqtSignal, QPoint, QEvent
from PyQt6.QtSvg import QSvgRenderer
from .style_menu import StyleMenu
from src.core.embedded_assets import get_svg_qbytearray


class CustomComboBox(QWidget):
    """Кастомный ComboBox, имитирующий QComboBox, но использующий StyleMenu для выпадающего списка"""
    
    # Сигналы для совместимости с QComboBox
    currentTextChanged = pyqtSignal(str)
    currentIndexChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.items = []
        self.current_index = -1
        self.min_width = 0
        self._menu_visible = False
        self._action_by_index = {}  # индекс элемента -> QAction (для отображения выбранного)
        
        # Создаем layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(0)
        
        # Текст выбранного элемента
        self.text_label = QLabel()
        self.text_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text_label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: #D4D4D4;
                border: none;
            }
        """)
        layout.addWidget(self.text_label, 1)
        
        # Кнопка со стрелкой (вниз/вверх)
        self.arrow_button = QPushButton()
        self.arrow_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.arrow_button.setFixedWidth(20)
        self.arrow_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
        """)
        
        # Иконка стрелки вниз из встроенных ресурсов
        data = get_svg_qbytearray("chevron-down")
        if not data.isEmpty():
            self.chevron_renderer = QSvgRenderer()
            if self.chevron_renderer.load(data):
                self.arrow_button.setFixedSize(20, 20)
            else:
                self.chevron_renderer = None
        else:
            self.chevron_renderer = None
        if self.chevron_renderer is None:
            self.arrow_button.setText("▼")
            self.arrow_button.setStyleSheet(self.arrow_button.styleSheet() + """
                QPushButton {
                    color: #D4D4D4;
                    font-size: 10px;
                }
            """)
        
        layout.addWidget(self.arrow_button)
        
        # Создаем меню
        self.menu = StyleMenu(self)
        
        # Подключаем сигналы
        self.arrow_button.clicked.connect(self.show_menu)
        self.menu.aboutToShow.connect(self._on_menu_about_to_show)
        self.menu.aboutToHide.connect(self._on_menu_about_to_hide)
        
        # Фильтр событий для обработки колёсика мыши над дочерними виджетами
        self.text_label.installEventFilter(self)
        self.arrow_button.installEventFilter(self)
        
        # Убираем автоматическую заливку фона, чтобы виджет был полупрозрачным
        # Это позволяет скроллбару накладываться поверх виджета (как в VSCode)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAutoFillBackground(False)
        
        # Стили для текста (без фона - фон рисуется в paintEvent)
        self._update_text_style()
        
        # Устанавливаем минимальную высоту
        self.setMinimumHeight(26)
        
        # Включаем фокус
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def paintEvent(self, event):
        """Отрисовка виджета с закругленными углами и полупрозрачным фоном"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Создаем путь для закругленного прямоугольника
        path = QPainterPath()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path.addRoundedRect(rect, 6, 6)
        
        # Определяем цвета в зависимости от состояния
        # Используем альфа-канал для полупрозрачности (180/255 ≈ 70% непрозрачности)
        # Это позволяет скроллбару накладываться поверх виджета
        if not self.isEnabled():
            border_color = QColor(50, 50, 50, 200)  # Полупрозрачная граница
            background_color = QColor(35, 35, 35, 180)  # Полупрозрачный фон
        else:
            # Граница: синяя при фокусе, серая без фокуса
            border_color = QColor(0, 122, 204, 220) if self.hasFocus() else QColor(60, 60, 60, 200)
            # Фон: полупрозрачный (#313131 с альфа ~70%)
            background_color = QColor(24, 24, 24)  # #313131 с альфа-каналом
        
        # Рисуем полупрозрачный фон
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(background_color)
        painter.drawPath(path)
        
        # Рисуем границу
        pen = QPen(border_color, 1)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        # Рисуем стрелку на кнопке, если есть рендерер
        if self.chevron_renderer:
            arrow_rect = QRectF(
                self.arrow_button.x() + 2,
                self.arrow_button.y() + 2,
                16,
                16
            )
            # Если меню открыто, поворачиваем стрелку вверх
            if self._menu_visible:
                painter.save()
                center = arrow_rect.center()
                painter.translate(center)
                painter.rotate(180)
                painter.translate(-center)
                self.chevron_renderer.render(painter, arrow_rect)
                painter.restore()
            else:
                self.chevron_renderer.render(painter, arrow_rect)
    
    def focusInEvent(self, event):
        """Обработка получения фокуса"""
        super().focusInEvent(event)
        self.update()  # Перерисовываем для изменения цвета границы
    
    def focusOutEvent(self, event):
        """Обработка потери фокуса"""
        super().focusOutEvent(event)
        self.update()  # Перерисовываем для изменения цвета границы
    
    def mousePressEvent(self, event):
        """Обработка клика мыши - показываем меню"""
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.setFocus()
            self.show_menu()
        super().mousePressEvent(event)
    
    def keyPressEvent(self, event):
        """Обработка нажатий клавиш"""
        if not self.isEnabled():
            event.ignore()
            return
        
        if event.key() == Qt.Key.Key_Space or event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.show_menu()
        elif event.key() == Qt.Key.Key_Up:
            self._step_prev()
        elif event.key() == Qt.Key.Key_Down:
            self._step_next()
        else:
            super().keyPressEvent(event)
    
    def _step_prev(self):
        """Перейти к предыдущему элементу (без разделителей)."""
        new_index = self.current_index - 1
        while new_index >= 0:
            if not self.items[new_index].get('separator', False):
                self.setCurrentIndex(new_index)
                return True
            new_index -= 1
        return False
    
    def _step_next(self):
        """Перейти к следующему элементу (без разделителей)."""
        new_index = self.current_index + 1
        while new_index < len(self.items):
            if not self.items[new_index].get('separator', False):
                self.setCurrentIndex(new_index)
                return True
            new_index += 1
        return False
    
    def wheelEvent(self, event: QWheelEvent):
        """Смена значения колёсиком мыши: вверх — предыдущий, вниз — следующий"""
        if not self.isEnabled() or not self.items:
            super().wheelEvent(event)
            return
        if event.angleDelta().y() > 0:
            if self._step_prev():
                event.accept()
                return
        else:
            if self._step_next():
                event.accept()
                return
        super().wheelEvent(event)
    
    def eventFilter(self, obj, event):
        """Перехват колёсика над label и кнопкой — меняем значение комбобокса"""
        if event.type() == QEvent.Type.Wheel and obj in (self.text_label, self.arrow_button):
            if self.isEnabled() and self.items:
                if event.angleDelta().y() > 0:
                    self._step_prev()
                else:
                    self._step_next()
                return True
        return super().eventFilter(obj, event)
    
    def addItem(self, text, userData=None):
        """Добавить элемент в список"""
        idx = len(self.items)
        self.items.append({'text': text, 'data': userData, 'separator': False})
        
        action = self.menu.addAction(text)
        action.setData(userData)
        action.setCheckable(True)
        action.setChecked(idx == self.current_index)
        action.triggered.connect(lambda checked, i=idx: self._on_item_selected(i))
        self._action_by_index[idx] = action
        
        if self.current_index == -1:
            self.setCurrentIndex(idx)
    
    def addItems(self, texts):
        """Добавить несколько элементов"""
        for text in texts:
            self.addItem(text)
    
    def insertItem(self, index, text, userData=None):
        """Вставить элемент по индексу"""
        self.items.insert(index, {'text': text, 'data': userData, 'separator': False})
        
        # Обновляем меню
        self._rebuild_menu()
        
        # Если вставляем до текущего индекса, обновляем индекс
        if index <= self.current_index:
            self.current_index += 1
    
    def insertSeparator(self, index):
        """Вставить разделитель по индексу"""
        self.items.insert(index, {'text': '', 'data': None, 'separator': True})
        
        # Обновляем меню
        self._rebuild_menu()
        
        # Если вставляем до текущего индекса, обновляем индекс
        if index <= self.current_index:
            self.current_index += 1
    
    def removeItem(self, index):
        """Удалить элемент по индексу"""
        if 0 <= index < len(self.items):
            was_separator = self.items[index].get('separator', False)
            self.items.pop(index)
            self._rebuild_menu()
            
            # Обновляем текущий индекс
            if index < self.current_index:
                self.current_index -= 1
            elif index == self.current_index:
                # Если удалили текущий элемент, ищем следующий не-разделитель
                if len(self.items) > 0:
                    # Ищем следующий не-разделитель
                    new_index = min(self.current_index, len(self.items) - 1)
                    # Если текущий индекс указывает на разделитель, ищем ближайший не-разделитель
                    while new_index >= 0 and new_index < len(self.items) and self.items[new_index].get('separator', False):
                        if new_index < len(self.items) - 1:
                            new_index += 1
                        else:
                            new_index -= 1
                    if new_index >= 0 and new_index < len(self.items) and not self.items[new_index].get('separator', False):
                        self.setCurrentIndex(new_index)
                    else:
                        self.current_index = -1
                        self.text_label.setText("")
                else:
                    self.current_index = -1
                    self.text_label.setText("")
    
    def clear(self):
        """Очистить список"""
        self.items.clear()
        self.menu.clear()
        self._action_by_index.clear()
        self.current_index = -1
        self.text_label.setText("")
    
    def _rebuild_menu(self):
        """Перестроить меню"""
        self.menu.clear()
        self._action_by_index.clear()
        for idx, item in enumerate(self.items):
            if item.get('separator', False):
                self.menu.addSeparator()
            else:
                action = self.menu.addAction(item['text'])
                action.setData(item['data'])
                action.setCheckable(True)
                action.setChecked(idx == self.current_index)
                action.triggered.connect(lambda checked, i=idx: self._on_item_selected(i))
                self._action_by_index[idx] = action
    
    def _on_item_selected(self, index):
        """Обработчик выбора элемента из меню"""
        # Проверяем, что это не разделитель
        if 0 <= index < len(self.items) and not self.items[index].get('separator', False):
            self.setCurrentIndex(index)
    
    def setCurrentIndex(self, index):
        """Установить текущий индекс"""
        if 0 <= index < len(self.items):
            if self.items[index].get('separator', False):
                return
            
            old_index = self.current_index
            self.current_index = index
            self.text_label.setText(self.items[index]['text'])
            
            # Отображаем выбранный элемент в меню (галочка)
            if old_index in self._action_by_index:
                self._action_by_index[old_index].setChecked(False)
            if index in self._action_by_index:
                self._action_by_index[index].setChecked(True)
            
            self._update_text_style()
            
            if old_index != index:
                self.currentIndexChanged.emit(index)
                self.currentTextChanged.emit(self.items[index]['text'])
    
    def setCurrentText(self, text):
        """Установить текущий текст"""
        for idx, item in enumerate(self.items):
            if not item.get('separator', False) and item['text'] == text:
                self.setCurrentIndex(idx)
                return
        # Если текст не найден, ничего не делаем
    
    def findText(self, text):
        """Найти индекс элемента по тексту"""
        for idx, item in enumerate(self.items):
            if not item.get('separator', False) and item['text'] == text:
                return idx
        return -1
    
    def currentIndex(self):
        """Получить текущий индекс"""
        return self.current_index
    
    def currentText(self):
        """Получить текущий текст"""
        if 0 <= self.current_index < len(self.items):
            item = self.items[self.current_index]
            if not item.get('separator', False):
                return item['text']
        return ""
    
    def currentData(self):
        """Получить текущие данные"""
        if 0 <= self.current_index < len(self.items):
            item = self.items[self.current_index]
            if not item.get('separator', False):
                return item['data']
        return None
    
    def itemText(self, index):
        """Получить текст элемента по индексу"""
        if 0 <= index < len(self.items):
            item = self.items[index]
            if not item.get('separator', False):
                return item['text']
        return ""
    
    def itemData(self, index):
        """Получить данные элемента по индексу"""
        if 0 <= index < len(self.items):
            item = self.items[index]
            if not item.get('separator', False):
                return item['data']
        return None
    
    def count(self):
        """Получить количество элементов"""
        return len(self.items)
    
    def show_menu(self):
        """Показать выпадающее меню"""
        if not self.isEnabled():
            return
        # Позиционируем меню под виджетом
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self.menu.exec(pos)

    def _on_menu_about_to_show(self):
        """Меню открывается - переключаем состояние стрелки"""
        self._menu_visible = True
        self.update()

    def _on_menu_about_to_hide(self):
        """Меню закрывается - возвращаем стрелку вниз"""
        self._menu_visible = False
        self.update()
    
    def setMinimumWidth(self, width):
        """Установить минимальную ширину"""
        self.min_width = width
        super().setMinimumWidth(width)
    
    def setEditable(self, editable):
        """Заглушка для совместимости (редактирование не поддерживается)"""
        pass
    
    def setPlaceholderText(self, text):
        """Установить текст-заполнитель"""
        if self.current_index == -1:
            self.text_label.setText(text)
            self._update_text_style(placeholder=True)

    def _update_styles(self):
        """Обновить стили виджета в зависимости от состояния (enabled/disabled)."""
        # Убрали stylesheet для фона - фон теперь рисуется в paintEvent с полупрозрачностью
        # Это позволяет скроллбару накладываться поверх виджета (как в VSCode)
        if self.isEnabled():
            self.arrow_button.setEnabled(True)
        else:
            self.arrow_button.setEnabled(False)
        self._update_text_style()
        # Принудительно обновляем виджет, чтобы перерисовать фон с новым состоянием
        self.update()

    def _update_text_style(self, placeholder: bool = False):
        """Обновить стиль текста в зависимости от состояния и типа (placeholder/обычный)."""
        if not self.isEnabled():
            color = "#555555"
        else:
            color = "#808080" if placeholder or self.current_index == -1 else "#D4D4D4"
        self.text_label.setStyleSheet(f"""
            QLabel {{
                background-color: transparent;
                color: {color};
                padding: 1px 1px;
                border: none;
            }}
        """)

    def setEnabled(self, enabled: bool):
        """Переопределяем setEnabled для обновления стилей."""
        super().setEnabled(enabled)
        self._update_styles()
        self.update()

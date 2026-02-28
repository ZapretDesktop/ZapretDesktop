"""
Виджет, похожий на QLabel, но с меню от StyleMenu при клике.
Используется для отображения настроек редактора (Spaces, Encoding, Line Endings).
"""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from .style_menu import StyleMenu


class LabelMenuWidget(QLabel):
    """QLabel с меню от StyleMenu при клике."""
    
    currentTextChanged = pyqtSignal(str)
    currentIndexChanged = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.items = []
        self.current_index = -1
        self._action_by_index = {}  # индекс элемента -> QAction
        
        # Создаем меню
        self.menu = StyleMenu(self)
        self.menu.aboutToShow.connect(self._on_menu_about_to_show)
        
        # Настройки внешнего вида
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hovered = False
        self._update_style()
        
        # Чеvроны удалены по запросу пользователя
    
    def _update_style(self):
        """Обновляет стиль виджета."""
        color = "#D4D4D4" if self._hovered else "#969696"
        self.setStyleSheet(f"""
            QLabel {{
                background-color: transparent;
                color: {color};
                border: none;
                padding: 2px 6px;
            }}
        """)
    
    def enterEvent(self, event):
        """Обработка наведения мыши."""
        self._hovered = True
        self._update_style()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Обработка ухода мыши."""
        self._hovered = False
        self._update_style()
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        """Отрисовка виджета с текстом."""
        super().paintEvent(event)
    
    def mousePressEvent(self, event):
        """Обработка клика мыши - показываем меню."""
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled() and self.items:
            self.show_menu()
        super().mousePressEvent(event)
    
    def addItem(self, text, userData=None):
        """Добавить элемент в список."""
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
        """Добавить несколько элементов."""
        for text in texts:
            self.addItem(text)
    
    def setCurrentIndex(self, index):
        """Установить текущий индекс."""
        if 0 <= index < len(self.items):
            if self.items[index].get('separator', False):
                return
            
            old_index = self.current_index
            self.current_index = index
            self.setText(self.items[index]['text'])
            
            # Отображаем выбранный элемент в меню (галочка)
            if old_index in self._action_by_index:
                self._action_by_index[old_index].setChecked(False)
            if index in self._action_by_index:
                self._action_by_index[index].setChecked(True)
            
            if old_index != index:
                self.currentIndexChanged.emit(index)
                self.currentTextChanged.emit(self.items[index]['text'])
            
            self.update()  # Перерисовываем для обновления стрелки
    
    def setCurrentText(self, text):
        """Установить текущий текст."""
        for idx, item in enumerate(self.items):
            if not item.get('separator', False) and item['text'] == text:
                self.setCurrentIndex(idx)
                return
    
    def currentIndex(self):
        """Получить текущий индекс."""
        return self.current_index
    
    def currentText(self):
        """Получить текущий текст."""
        if 0 <= self.current_index < len(self.items):
            item = self.items[self.current_index]
            if not item.get('separator', False):
                return item['text']
        return ""
    
    def _on_item_selected(self, index):
        """Обработчик выбора элемента из меню."""
        if 0 <= index < len(self.items) and not self.items[index].get('separator', False):
            self.setCurrentIndex(index)
    
    def show_menu(self):
        """Показать выпадающее меню."""
        if not self.isEnabled() or not self.items:
            return
        # Позиционируем меню под виджетом
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self.menu.exec(pos)
    
    def _on_menu_about_to_show(self):
        """Меню открывается - обновляем галочки."""
        # Галочки уже обновлены в setCurrentIndex, но можно добавить дополнительную логику
        pass
    
    def clear(self):
        """Очистить список."""
        self.items.clear()
        self.menu.clear()
        self._action_by_index.clear()
        self.current_index = -1
        self.setText("")
        self.update()

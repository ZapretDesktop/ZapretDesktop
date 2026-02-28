"""
Custom overlay scrollbar widget that draws on top of content (like VSCode)
"""

from PyQt6.QtCore import (
    QObject, QTimer, QPropertyAnimation, QEasingCurve, 
    pyqtProperty, QEvent, Qt, QPoint, QRect, QRectF, pyqtSignal
)
from PyQt6.QtWidgets import QWidget, QAbstractScrollArea, QApplication, QListView, QTextEdit
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QMouseEvent, QWheelEvent


class OpacityAnimation(QObject):
    """Вспомогательный класс для анимации прозрачности"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._opacity = 0.0
        
    @pyqtProperty(float)
    def opacity(self):
        return self._opacity
        
    @opacity.setter
    def opacity(self, value):
        self._opacity = value


class CustomOverlayScrollBar(QWidget):
    """Кастомный overlay скроллбар, который рисуется поверх контента"""
    
    def __init__(self, parent_widget, orientation=Qt.Orientation.Vertical, parent=None):
        super().__init__(parent_widget if parent is None else parent)
        self.parent_widget = parent_widget
        self.orientation = orientation
        self._opacity = 0.5
        self._is_dragging = False
        self._drag_start_pos = None
        self._drag_start_value = None
        self._viewport_hover_state = None  # Сохраняем состояние hover у viewport
        self._viewport_mouse_tracking = None  # Сохраняем состояние mouse tracking у viewport
        self._cursor_overridden = False  # Флаг для восстановления курсора
        
        # Настройки скроллбара
        self.scrollbar_width = 12 if orientation == Qt.Orientation.Vertical else 0
        self.scrollbar_height = 0 if orientation == Qt.Orientation.Vertical else 12
        self.corner_radius = 0.0  # Без закруглений
        self.margin = 0  # Без отступов
        
        # Анимация прозрачности
        self.opacity_animation = OpacityAnimation(self)
        self.animation = QPropertyAnimation(self.opacity_animation, b"opacity")
        self.animation.valueChanged.connect(self._on_opacity_changed)
        
        # Таймер для скрытия скроллбара (как в VSCode)
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_with_animation)
        
        # Настройка виджета
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        
        # Скрываем по умолчанию
        self.setVisible(False)
        self._opacity = 0.0
        
        # Подключаемся к родительскому виджету для отслеживания изменений
        if isinstance(parent_widget, QAbstractScrollArea):
            self._connect_to_scroll_area()
    
    def _get_viewport(self):
        """Получить viewport родительского scroll area (если есть)"""
        if isinstance(self.parent_widget, QAbstractScrollArea):
            return self.parent_widget.viewport()
        return None
    
    def _suspend_viewport_hover(self):
        """Отключить hover и tracking у viewport, чтобы не подсвечивать элементы под скроллбаром"""
        viewport = self._get_viewport()
        if viewport is None:
            return
        self._viewport_hover_state = viewport.testAttribute(Qt.WidgetAttribute.WA_Hover)
        self._viewport_mouse_tracking = viewport.hasMouseTracking()
        viewport.setAttribute(Qt.WidgetAttribute.WA_Hover, False)
        viewport.setMouseTracking(False)
    
    def _resume_viewport_hover(self):
        """Вернуть hover и tracking viewport в прежнее состояние"""
        viewport = self._get_viewport()
        if viewport is None:
            return
        if self._viewport_hover_state is not None:
            viewport.setAttribute(Qt.WidgetAttribute.WA_Hover, self._viewport_hover_state)
        if self._viewport_mouse_tracking is not None:
            viewport.setMouseTracking(self._viewport_mouse_tracking)
        self._viewport_hover_state = None
        self._viewport_mouse_tracking = None
    
    def _apply_drag_cursor(self):
        """Установить курсор Arrow на время перетаскивания, чтобы не появлялся resize/текстовый"""
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)
            self._cursor_overridden = True
        except Exception:
            self._cursor_overridden = False
    
    def _restore_drag_cursor(self):
        """Вернуть курсор в прежнее состояние"""
        if self._cursor_overridden:
            try:
                QApplication.restoreOverrideCursor()
            except Exception:
                pass
        self._cursor_overridden = False
    
    def _connect_to_scroll_area(self):
        """Подключиться к событиям scroll area"""
        if not isinstance(self.parent_widget, QAbstractScrollArea):
            return
        
        # Отслеживаем изменения прокрутки
        scrollbar = (self.parent_widget.verticalScrollBar() 
                    if self.orientation == Qt.Orientation.Vertical 
                    else self.parent_widget.horizontalScrollBar())
        
        if scrollbar:
            scrollbar.valueChanged.connect(self.update)
            scrollbar.rangeChanged.connect(self._on_range_changed)
            # Обновляем геометрию при изменении диапазона
            scrollbar.rangeChanged.connect(self.update_geometry)
    
    def _on_range_changed(self, min_val, max_val):
        """Обработка изменения диапазона прокрутки"""
        self.update_geometry()
        # В VSCode скроллбар не показывается автоматически при изменении диапазона
        # Он показывается только при взаимодействии пользователя
    
    def _on_opacity_changed(self, value):
        """Обработка изменения прозрачности"""
        self._opacity = value
        self.update()
        if value > 0:
            self.setVisible(True)
        elif value <= 0 and not self._is_dragging:
            self.setVisible(False)
    
    def show_with_animation(self):
        """Показать скроллбар с анимацией (как в VSCode)"""
        # Проверяем, есть ли контент для прокрутки
        min_val, max_val, _, _ = self._get_scroll_info()
        if min_val is None or max_val == min_val:
            return  # Нет контента для прокрутки
        
        if self._opacity >= 1.0:
            return
        
        self.animation.stop()
        self.animation.setDuration(150)  # Быстрое появление как в VSCode
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.setStartValue(self._opacity)
        self.animation.setEndValue(1.0)
        self.animation.start()
    
    def hide_with_animation(self):
        """Скрыть скроллбар с анимацией (как в VSCode)"""
        if self._opacity <= 0.0 or self._is_dragging:
            return
        
        self.animation.stop()
        self.animation.setDuration(400)  # Медленное исчезновение как в VSCode
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.animation.setStartValue(self._opacity)
        self.animation.setEndValue(0.0)
        self.animation.start()
    
    def update_geometry(self):
        """Обновить геометрию скроллбара"""
        if not self.parent_widget:
            return
        
        # Используем geometry() вместо rect() для получения реальных размеров
        parent_geometry = self.parent_widget.geometry()
        if parent_geometry.isEmpty():
            return
        
        if self.orientation == Qt.Orientation.Vertical:
            # Вертикальный скроллбар справа
            x = parent_geometry.width() - self.scrollbar_width - self.margin
            y = self.margin
            w = self.scrollbar_width
            h = parent_geometry.height() - 2 * self.margin
            # Позиционируем относительно родителя
            self.setGeometry(x, y, w, h)
        else:
            # Горизонтальный скроллбар снизу
            x = self.margin
            y = parent_geometry.height() - self.scrollbar_height - self.margin
            w = parent_geometry.width() - 2 * self.margin
            h = self.scrollbar_height
            # Позиционируем относительно родителя
            self.setGeometry(x, y, w, h)
    
    def _get_scrollbar(self):
        """Получить связанный QScrollBar"""
        if not isinstance(self.parent_widget, QAbstractScrollArea):
            return None
        
        if self.orientation == Qt.Orientation.Vertical:
            return self.parent_widget.verticalScrollBar()
        else:
            return self.parent_widget.horizontalScrollBar()
    
    def _get_scroll_info(self):
        """Получить информацию о прокрутке"""
        scrollbar = self._get_scrollbar()
        if not scrollbar:
            return None, None, None
        
        min_val = scrollbar.minimum()
        max_val = scrollbar.maximum()
        value = scrollbar.value()
        page_step = scrollbar.pageStep()
        
        return min_val, max_val, value, page_step
    
    def _get_handle_rect(self):
        """Получить прямоугольник для ручки скроллбара"""
        if not self.parent_widget:
            return QRect()
        
        min_val, max_val, value, page_step = self._get_scroll_info()
        if min_val is None or max_val == min_val:
            return QRect()
        
        total_range = max_val - min_val
        visible_range = page_step
        total_size = total_range + visible_range
        
        # Используем geometry() для получения размеров, так как width/height перекрыты атрибутами
        widget_width = self.geometry().width()
        widget_height = self.geometry().height()
        
        if self.orientation == Qt.Orientation.Vertical:
            # Высота ручки пропорциональна видимой области
            handle_height = max(20, int((visible_range / total_size) * widget_height))
            # Позиция ручки пропорциональна значению прокрутки
            available_height = widget_height - handle_height
            handle_y = int((value - min_val) / total_range * available_height) if total_range > 0 else 0
            return QRect(0, handle_y, widget_width, handle_height)
        else:
            # Ширина ручки пропорциональна видимой области
            handle_width = max(20, int((visible_range / total_size) * widget_width))
            # Позиция ручки пропорциональна значению прокрутки
            available_width = widget_width - handle_width
            handle_x = int((value - min_val) / total_range * available_width) if total_range > 0 else 0
            return QRect(handle_x, 0, handle_width, widget_height)
    
    def paintEvent(self, event):
        """Отрисовка скроллбара"""
        if self._opacity <= 0.0:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Получаем информацию о прокрутке
        min_val, max_val, value, page_step = self._get_scroll_info()
        if min_val is None or max_val == min_val:
            return
        
        # Получаем прямоугольник ручки
        handle_rect = self._get_handle_rect()
        if handle_rect.isEmpty():
            return
        
        # Рисуем ручку с прозрачностью (как в VSCode)
        # Неактивный цвет: #3e3e3e, активный: #4d4d4d
        # Добавляем прозрачность через альфа-канал (примерно 70% непрозрачности)
        opacity_alpha = int(255 * 0.7 * self._opacity)  # 70% непрозрачности с учетом анимации
        inactive_color = QColor(62, 62, 62, opacity_alpha)  # #3e3e3e с прозрачностью
        active_color = QColor(77, 77, 77, opacity_alpha)    # #4d4d4d с прозрачностью
        
        # Определяем цвет в зависимости от состояния
        if self._is_dragging or self.underMouse():
            color = active_color
        else:
            color = inactive_color
        
        # Рисуем ручку без закруглений и без границы
        painter.setPen(Qt.PenStyle.NoPen)  # Без границы
        painter.setBrush(QBrush(color))
        # Убираем adjusted() чтобы не было визуальной границы
        if self.corner_radius > 0:
            painter.drawRoundedRect(
                QRectF(handle_rect),
                self.corner_radius,
                self.corner_radius
            )
        else:
            painter.drawRect(QRectF(handle_rect))
    
    def mousePressEvent(self, event):
        """Обработка нажатия мыши"""
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        
        handle_rect = self._get_handle_rect()
        pos = event.pos()
        if handle_rect.contains(pos):
            # Начало перетаскивания ручки
            self._is_dragging = True
            self._drag_start_pos = pos
            scrollbar = self._get_scrollbar()
            if scrollbar:
                self._drag_start_value = scrollbar.value()
            # Отключаем hover у viewport и фиксируем курсор, чтобы не трогать остальные элементы
            self._suspend_viewport_hover()
            self._apply_drag_cursor()
            # Захватываем мышь, чтобы курсор не взаимодействовал с другими элементами
            self.grabMouse()
            self.update()
        else:
            # Клик вне ручки - прокрутка на страницу
            self._scroll_to_position(pos)
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Обработка движения мыши"""
        if self._is_dragging and self._drag_start_pos is not None:
            # Перетаскивание ручки
            delta = event.pos() - self._drag_start_pos
            scrollbar = self._get_scrollbar()
            if scrollbar:
                min_val, max_val, _, page_step = self._get_scroll_info()
                if min_val is None:
                    return
                
                total_range = max_val - min_val
                widget_width = self.geometry().width()
                widget_height = self.geometry().height()
                handle_rect = self._get_handle_rect()
                
                if self.orientation == Qt.Orientation.Vertical:
                    available_height = widget_height - handle_rect.height()
                    if available_height > 0:
                        value_delta = int((delta.y() / available_height) * total_range)
                        new_value = self._drag_start_value + value_delta
                        scrollbar.setValue(max(min_val, min(max_val, new_value)))
                else:
                    available_width = widget_width - handle_rect.width()
                    if available_width > 0:
                        value_delta = int((delta.x() / available_width) * total_range)
                        new_value = self._drag_start_value + value_delta
                        scrollbar.setValue(max(min_val, min(max_val, new_value)))
            
            self.update()
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания мыши"""
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self._is_dragging
            self._is_dragging = False
            self._drag_start_pos = None
            self._drag_start_value = None
            # Освобождаем мышь, если она была захвачена
            if was_dragging:
                try:
                    self.releaseMouse()
                except:
                    pass  # Игнорируем ошибки, если мышь не была захвачена
            # Возвращаем hover/курсор
            self._resume_viewport_hover()
            self._restore_drag_cursor()
            self.update()
        
        super().mouseReleaseEvent(event)
    
    def _scroll_to_position(self, pos):
        """Прокрутить к позиции"""
        scrollbar = self._get_scrollbar()
        if not scrollbar:
            return
        
        min_val, max_val, _, page_step = self._get_scroll_info()
        if min_val is None or max_val == min_val:
            return
        
        total_range = max_val - min_val
        widget_width = self.geometry().width()
        widget_height = self.geometry().height()
        
        if self.orientation == Qt.Orientation.Vertical:
            ratio = pos.y() / widget_height if widget_height > 0 else 0
            new_value = min_val + int(ratio * total_range)
        else:
            ratio = pos.x() / widget_width if widget_width > 0 else 0
            new_value = min_val + int(ratio * total_range)
        
        scrollbar.setValue(max(min_val, min(max_val, new_value)))
    
    def enterEvent(self, event):
        """Обработка входа курсора на скроллбар"""
        # Останавливаем таймер скрытия
        self.hide_timer.stop()
        self.show_with_animation()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Обработка выхода курсора со скроллбара"""
        if not self._is_dragging:
            # Запускаем таймер на скрытие (как в VSCode - через 1 секунду)
            self.hide_timer.start(1000)
        super().leaveEvent(event)
    
    def focusOutEvent(self, event):
        """Обработка потери фокуса - освобождаем мышь если перетаскивание было активно"""
        if self._is_dragging:
            self._is_dragging = False
            self._drag_start_pos = None
            self._drag_start_value = None
            try:
                self.releaseMouse()
            except:
                pass
            self._resume_viewport_hover()
            self._restore_drag_cursor()
            self.update()
        super().focusOutEvent(event)
    
    def schedule_hide(self, delay=1000):
        """Запланировать скрытие скроллбара через указанное время"""
        if not self._is_dragging:
            self.hide_timer.stop()
            self.hide_timer.start(delay)
    
    def resizeEvent(self, event):
        """Обработка изменения размера"""
        self.update_geometry()
        super().resizeEvent(event)


class OverlayScrollbarManager(QObject):
    """Менеджер для управления overlay скроллбарами (как в VSCode)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scrollbars = {}  # widget -> (vertical_scrollbar, horizontal_scrollbar)
        self.fade_timeout = 1000  # Время до скрытия скроллбара (мс)
        self.scroll_timers = {}  # Таймеры для скрытия после прокрутки
    
    def setup_widget(self, widget):
        """Настроить overlay скроллбары для виджета"""
        if not isinstance(widget, (QAbstractScrollArea, QListView, QTextEdit)):
            return
        
        if widget in self.scrollbars:
            return  # Уже настроен
        
        # Скрываем стандартные скроллбары
        if hasattr(widget, 'setVerticalScrollBarPolicy'):
            widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if hasattr(widget, 'setHorizontalScrollBarPolicy'):
            widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Создаем overlay скроллбары
        vertical_sb = CustomOverlayScrollBar(widget, Qt.Orientation.Vertical)
        horizontal_sb = CustomOverlayScrollBar(widget, Qt.Orientation.Horizontal)
        
        self.scrollbars[widget] = (vertical_sb, horizontal_sb)
        
        # Подключаемся к событиям виджета
        widget.installEventFilter(self)
        
        # Обновляем геометрию при изменении размера через event filter
        # (уже обрабатывается в eventFilter)
    
    def eventFilter(self, obj, event):
        """Фильтр событий для отслеживания виджетов (поведение как в VSCode)"""
        if obj in self.scrollbars:
            vertical_sb, horizontal_sb = self.scrollbars[obj]
            
            if event.type() == QEvent.Type.Enter:
                # При наведении на область прокрутки показываем скроллбары
                vertical_sb.show_with_animation()
                horizontal_sb.show_with_animation()
                # Останавливаем таймеры скрытия
                vertical_sb.hide_timer.stop()
                horizontal_sb.hide_timer.stop()
                if obj in self.scroll_timers:
                    self.scroll_timers[obj].stop()
                    
            elif event.type() == QEvent.Type.Leave:
                # При уходе курсора планируем скрытие (как в VSCode)
                if not vertical_sb._is_dragging and not horizontal_sb._is_dragging:
                    vertical_sb.schedule_hide(self.fade_timeout)
                    horizontal_sb.schedule_hide(self.fade_timeout)
                    
            elif event.type() == QEvent.Type.FocusIn:
                # При получении фокуса показываем скроллбары
                vertical_sb.show_with_animation()
                horizontal_sb.show_with_animation()
                
            elif event.type() == QEvent.Type.FocusOut:
                # При потере фокуса планируем скрытие
                if not vertical_sb._is_dragging and not horizontal_sb._is_dragging:
                    vertical_sb.schedule_hide(self.fade_timeout)
                    horizontal_sb.schedule_hide(self.fade_timeout)
                    
            elif event.type() == QEvent.Type.Wheel:
                # При прокрутке показываем скроллбары и планируем скрытие после окончания
                vertical_sb.show_with_animation()
                horizontal_sb.show_with_animation()
                
                # Останавливаем предыдущий таймер
                if obj in self.scroll_timers:
                    self.scroll_timers[obj].stop()
                
                # Создаем новый таймер для скрытия после окончания прокрутки
                scroll_timer = QTimer(self)
                scroll_timer.setSingleShot(True)
                scroll_timer.timeout.connect(lambda: (
                    vertical_sb.schedule_hide(self.fade_timeout),
                    horizontal_sb.schedule_hide(self.fade_timeout)
                ))
                scroll_timer.start(self.fade_timeout)
                self.scroll_timers[obj] = scroll_timer
                
            elif event.type() == QEvent.Type.MouseMove:
                # При движении мыши показываем скроллбары (если они еще не видны)
                if vertical_sb._opacity < 1.0 or horizontal_sb._opacity < 1.0:
                    vertical_sb.show_with_animation()
                    horizontal_sb.show_with_animation()
                # Останавливаем таймеры скрытия
                vertical_sb.hide_timer.stop()
                horizontal_sb.hide_timer.stop()
                if obj in self.scroll_timers:
                    self.scroll_timers[obj].stop()
                    
            elif event.type() == QEvent.Type.Resize:
                # Обновляем геометрию при изменении размера
                QTimer.singleShot(0, lambda: (
                    vertical_sb.update_geometry(),
                    horizontal_sb.update_geometry()
                ))
        
        return False  # Пропускаем событие дальше


# Глобальный менеджер
_global_manager = None

def get_overlay_scrollbar_manager():
    """Получить глобальный менеджер overlay скроллбаров"""
    global _global_manager
    if _global_manager is None:
        _global_manager = OverlayScrollbarManager()
    return _global_manager

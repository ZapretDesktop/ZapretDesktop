"""
Custom scrollbar implementation with auto-hide when not in focus
Now uses custom overlay scrollbars that draw on top of content (like VSCode)
"""

from PyQt6.QtCore import (
    QObject, QTimer, QPropertyAnimation, QEasingCurve, 
    pyqtProperty, QEvent, Qt
)
from PyQt6.QtWidgets import QAbstractScrollArea, QApplication, QScrollBar, QListView, QTextEdit
from PyQt6.QtGui import *
from .custom_overlay_scrollbar import get_overlay_scrollbar_manager

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
        
class ScrollbarStyler:
    """Class to apply VSCode-like overlay scrollbars to an application"""
    
    @staticmethod
    def apply_scrollbar_style(app, fade_timeout=1000):
        """
        Применить стиль overlay скроллбаров VSCode ко всему приложению
        
        Args:
            app: QApplication - экземпляр приложения
            fade_timeout: int - время в мс до исчезновения скроллбара
        """
        # Получаем глобальный менеджер overlay скроллбаров
        manager = get_overlay_scrollbar_manager()
        manager.fade_timeout = fade_timeout
        
        # Устанавливаем глобальный фильтр событий для отслеживания виджетов
        event_filter = ScrollbarEventFilter(app, fade_timeout, manager)
        app.installEventFilter(event_filter)
        
        # Применяем overlay скроллбары ко всем существующим виджетам сразу
        # Используем несколько задержек, чтобы поймать виджеты, созданные в разных моментах
        QTimer.singleShot(0, lambda: event_filter.apply_styles_to_all_widgets(app))
        QTimer.singleShot(100, lambda: event_filter.apply_styles_to_all_widgets(app))
        QTimer.singleShot(500, lambda: event_filter.apply_styles_to_all_widgets(app))
        
class ScrollbarEventFilter(QObject):
    """Обработчик событий для автоматического скрытия скроллбаров"""
    
    def __init__(self, parent, fade_timeout=1000, overlay_manager=None):
        super().__init__(parent)
        self.fade_timeout = fade_timeout
        self.overlay_manager = overlay_manager or get_overlay_scrollbar_manager()
        self.active_widgets = set()  # Виджеты с активными скроллбарами
        self.fade_timers = {}  # Таймеры исчезновения для каждого виджета
        self.scroll_timers = {}  # Таймеры для обработки скроллинга
        
    def eventFilter(self, obj, event):
        """Фильтр событий для отслеживания скроллбаров"""
        # Обрабатываем только QAbstractScrollArea и их подклассы (QListView, QTextEdit и т.д.)
        if isinstance(obj, (QAbstractScrollArea, QListView, QTextEdit)) or (hasattr(obj, 'viewport') and callable(getattr(obj, 'viewport', None))):
            # Проверяем, что виджет не был удален
            if not self._is_widget_valid(obj):
                self._cleanup_widget(obj)
                return False
            
            # Применяем стили при показе виджета или его полировке (когда виджет готов к отображению)
            if event.type() in (QEvent.Type.Show, QEvent.Type.Polish):
                # Применяем стили сразу, но не показываем скроллбары (они появятся при фокусе)
                self.apply_initial_styles(obj)
            
            # Когда виджет получает фокус или курсор наводится на него
            elif event.type() in (QEvent.Type.Enter, QEvent.Type.FocusIn):
                self.show_scrollbars(obj)
                
            # Когда виджет теряет фокус или курсор уходит
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.FocusOut):
                # Запускаем таймер на скрытие скроллбаров
                self.start_fade_timer(obj)
                
            # Сброс таймера при взаимодействии с виджетом
            elif event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
                if obj in self.active_widgets:
                    self.show_scrollbars(obj)
            
            # Специальная обработка скроллинга - скроллбары должны быть видны во время скроллинга
            elif event.type() == QEvent.Type.Wheel:
                self.handle_scroll_event(obj)
                
        return False  # Всегда пропускаем событие дальше
    
    def handle_scroll_event(self, widget):
        """Обработка события скроллинга"""
        if not self._is_widget_valid(widget):
            self._cleanup_widget(widget)
            return
        
        # Показываем скроллбары
        self.show_scrollbars(widget)
        
        # Остановим предыдущий таймер скроллинга, если он есть
        if widget in self.scroll_timers:
            self.scroll_timers[widget].stop()
        
        # Создаем таймер для скрытия скроллбаров после окончания скроллинга
        scroll_timer = QTimer(self)
        scroll_timer.setSingleShot(True)
        scroll_timer.timeout.connect(lambda: self.start_fade_timer(widget))
        
        # Запускаем таймер
        scroll_timer.start(self.fade_timeout)
        self.scroll_timers[widget] = scroll_timer
    
    def show_scrollbars(self, widget):
        """Показать скроллбары для виджета с анимацией"""
        if not self._is_widget_valid(widget):
            self._cleanup_widget(widget)
            return
        
        # Если таймер на скрытие активен, останавливаем его
        self.stop_fade_timer(widget)
        
        try:
            # Настраиваем overlay скроллбары, если еще не настроены
            self.overlay_manager.setup_widget(widget)
            
            # Показываем overlay скроллбары через менеджер
            if widget in self.overlay_manager.scrollbars:
                vertical_sb, horizontal_sb = self.overlay_manager.scrollbars[widget]
                vertical_sb.show_with_animation()
                horizontal_sb.show_with_animation()
        except (RuntimeError, AttributeError):
            # Виджет был удален
            self._cleanup_widget(widget)
            return
        
        # Добавляем виджет в список активных
        self.active_widgets.add(widget)
    
    def hide_scrollbars(self, widget):
        """Скрыть скроллбары для виджета с анимацией"""
        if not self._is_widget_valid(widget):
            self._cleanup_widget(widget)
            return
        
        if widget in self.active_widgets:
            # Скрываем overlay скроллбары через менеджер
            if widget in self.overlay_manager.scrollbars:
                vertical_sb, horizontal_sb = self.overlay_manager.scrollbars[widget]
                vertical_sb.hide_with_animation()
                horizontal_sb.hide_with_animation()
    
    # Методы update_scrollbar_opacity, animation_finished, stop_animation удалены
    # Overlay скроллбары управляют своей прозрачностью самостоятельно
    
    def start_fade_timer(self, widget):
        """Запустить таймер на скрытие скроллбаров"""
        if not self._is_widget_valid(widget):
            self._cleanup_widget(widget)
            return
        
        # Если таймер уже существует, перезапускаем его
        if widget in self.fade_timers:
            timer = self.fade_timers[widget]
            timer.stop()
        else:
            # Создаем новый таймер и привязываем его к родительскому объекту
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self.hide_scrollbars(widget))
            self.fade_timers[widget] = timer
            
        # Запускаем таймер
        timer.start(self.fade_timeout)
    
    def stop_fade_timer(self, widget):
        """Остановить таймер на скрытие скроллбаров"""
        if widget in self.fade_timers:
            self.fade_timers[widget].stop()
    
    def _is_widget_valid(self, widget):
        """Проверить, что виджет не был удален"""
        try:
            # Пытаемся получить доступ к виджету
            _ = widget.objectName()
            return True
        except RuntimeError:
            # Виджет был удален
            return False
        except Exception:
            # Другие ошибки - считаем виджет валидным
            return True
    
    def _cleanup_widget(self, widget):
        """Очистить все ссылки на удаленный виджет"""
        if widget in self.active_widgets:
            self.active_widgets.discard(widget)
        if widget in self.fade_timers:
            del self.fade_timers[widget]
        if widget in self.scroll_timers:
            del self.scroll_timers[widget]
    
    def set_scrollbar_opacity(self, widget, opacity):
        """Установить прозрачность скроллбаров виджета"""
        if not self._is_widget_valid(widget):
            self._cleanup_widget(widget)
            return
        
        try:
            if hasattr(widget, 'verticalScrollBar') and callable(widget.verticalScrollBar):
                v_scrollbar = widget.verticalScrollBar()
                if v_scrollbar:
                    # Фиксированная ширина и радиус, анимируем только прозрачность
                    width = 12
                    radius = 4.0
                    
                    v_scrollbar.setStyleSheet(f"""
                    QScrollBar:vertical {{
                        background: transparent;
                        width: {width}px;
                        margin: 0px;
                        border: none;
                        border-radius: {radius}px;
                        subcontrol-origin: margin;
                        subcontrol-position: right;
                    }}
                    
                    QScrollBar::handle:vertical {{
                        background-color: rgba(128, 128, 128, {opacity * 0.4});
                        border-radius: {radius}px;
                        min-height: 40px;
                        border: none;
                    }}
                    
                    QScrollBar::handle:vertical:hover {{
                        background-color: rgba(144, 144, 144, {min(opacity * 0.7, 0.7)});
                    }}
                    
                    QScrollBar::handle:vertical:pressed {{
                        background-color: rgba(160, 160, 160, {min(opacity * 0.8, 0.8)});
                    }}
                    
                    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                        height: 0px;
                        background: none;
                        border: none;
                    }}
                    
                    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                        background: transparent;
                        border: none;
                    }}
                    """)
                    # Принудительно обновляем стили
                    v_scrollbar.style().unpolish(v_scrollbar)
                    v_scrollbar.style().polish(v_scrollbar)
                    v_scrollbar.update()
            
            if hasattr(widget, 'horizontalScrollBar') and callable(widget.horizontalScrollBar):
                h_scrollbar = widget.horizontalScrollBar()
                if h_scrollbar:
                    # Фиксированная высота и радиус, анимируем только прозрачность
                    height = 12
                    radius = 0
                    
                    h_scrollbar.setStyleSheet(f"""
                    QScrollBar:horizontal {{
                        background: transparent;
                        height: {height}px;
                        margin: 0px;
                        border: none;
                        border-radius: {radius}px;
                        subcontrol-origin: margin;
                        subcontrol-position: bottom;
                    }}
                    
                    QScrollBar::handle:horizontal {{
                        background-color: rgba(128, 128, 128, {opacity * 0.4});
                        border-radius: {radius}px;
                        min-width: 40px;
                        border: none;
                    }}
                    
                    QScrollBar::handle:horizontal:hover {{
                        background-color: rgba(144, 144, 144, {min(opacity * 0.7, 0.7)});
                    }}
                    
                    QScrollBar::handle:horizontal:pressed {{
                        background-color: rgba(160, 160, 160, {min(opacity * 0.8, 0.8)});
                    }}
                    
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                        width: 0px;
                        background: none;
                        border: none;
                    }}
                    
                    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                        background: transparent;
                        border: none;
                    }}
                    """)
                    # Принудительно обновляем стили
                    h_scrollbar.style().unpolish(h_scrollbar)
                    h_scrollbar.style().polish(h_scrollbar)
                    h_scrollbar.update()
        except (RuntimeError, AttributeError) as e:
            # Виджет был удален или произошла другая ошибка
            self._cleanup_widget(widget)
        except Exception as e:
            # Другие ошибки - просто игнорируем
            pass 
    
    def hide_scrollbars_completely(self, widget):
        """Полностью скрыть скроллбары"""
        if not self._is_widget_valid(widget):
            self._cleanup_widget(widget)
            return
        
        try:
            if hasattr(widget, 'verticalScrollBar') and callable(widget.verticalScrollBar):
                v_scrollbar = widget.verticalScrollBar()
                if v_scrollbar:
                    # Полностью скрываем вертикальный скроллбар
                    v_scrollbar.setVisible(False)  
                    # Устанавливаем политику для удаления из layout
                    widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                    
            if hasattr(widget, 'horizontalScrollBar') and callable(widget.horizontalScrollBar):
                h_scrollbar = widget.horizontalScrollBar()
                if h_scrollbar:
                    # Полностью скрываем горизонтальный скроллбар
                    h_scrollbar.setVisible(False)
                    # Устанавливаем политику для удаления из layout
                    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        except (RuntimeError, AttributeError):
            # Виджет был удален
            self._cleanup_widget(widget)
    
    def _setup_overlay_scrollbar(self, widget):
        """Настроить виджет для overlay скроллбаров (как в VSCode)"""
        if not isinstance(widget, (QAbstractScrollArea, QListView, QTextEdit)):
            return
        
        try:
            # Устанавливаем нулевые отступы для viewport, чтобы скроллбар накладывался поверх
            # Это позволяет скроллбару не сдвигать контент при появлении
            if hasattr(widget, 'setViewportMargins'):
                widget.setViewportMargins(0, 0, 0, 0)
            
            # Переопределяем resizeEvent для поддержания нулевых отступов
            # Qt автоматически меняет отступы при изменении размера, нужно это переопределить
            original_resize = widget.resizeEvent
            
            def overlay_resize_event(event):
                """Переопределенный resizeEvent для поддержания overlay скроллбаров"""
                # Вызываем оригинальный resizeEvent
                original_resize(event)
                # Принудительно устанавливаем нулевые отступы после resize
                widget.setViewportMargins(0, 0, 0, 0)
            
            # Сохраняем оригинальный метод, если еще не переопределен
            if not hasattr(widget, '_overlay_scrollbar_setup'):
                widget._original_resize_event = original_resize
                widget.resizeEvent = overlay_resize_event
                widget._overlay_scrollbar_setup = True
        except (RuntimeError, AttributeError):
            pass
    
    def apply_initial_styles(self, widget):
        """Применить начальные стили к виджету без показа скроллбаров"""
        if not self._is_widget_valid(widget):
            self._cleanup_widget(widget)
            return
        
        try:
            # Настраиваем overlay скроллбары для виджета
            # Overlay скроллбары управляют своей прозрачностью самостоятельно
            self.overlay_manager.setup_widget(widget)
        except (RuntimeError, AttributeError):
            self._cleanup_widget(widget)
    
    def apply_styles_to_all_widgets(self, parent):
        """Применить overlay скроллбары ко всем виджетам с scrollbar в приложении"""
        def find_and_apply(widget):
            """Рекурсивно найти все виджеты с scrollbar и применить overlay скроллбары"""
            if not widget:
                return
            
            try:
                # Проверяем, является ли виджет scroll area (QListView, QTextEdit наследуются от QAbstractScrollArea)
                if isinstance(widget, (QAbstractScrollArea, QListView, QTextEdit)) or (hasattr(widget, 'viewport') and callable(getattr(widget, 'viewport', None))):
                    if self._is_widget_valid(widget):
                        # Настраиваем overlay скроллбары
                        self.overlay_manager.setup_widget(widget)
                
                # Рекурсивно обрабатываем дочерние виджеты
                for child in widget.children():
                    if isinstance(child, QObject):
                        find_and_apply(child)
            except (RuntimeError, AttributeError):
                pass
        
        # Начинаем поиск с главного окна приложения
        for widget in parent.allWidgets():
            find_and_apply(widget)


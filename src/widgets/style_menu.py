from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QPainter, QPainterPath, QColor, QPen, QPalette
from PyQt6.QtCore import Qt, QRectF, QTimer, QEvent
from PyQt6.QtSvg import QSvgRenderer
from src.core.embedded_assets import get_svg_qbytearray


class StyleMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Set up styling
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Configurable properties
        self.corner_radius = 6
        self.bg_color = QColor(31, 31, 31)      # #1f1f1f
        self.border_color = QColor(51, 51, 51)  # #333333
        # Основной цвет текста меню
        self.text_color = QColor(204, 204, 204)  # #cccccc
        # Цвет для горячих клавиш (чуть темнее основного)
        self.shortcut_color = QColor(170, 170, 170)  # ~#aaaaaa
        self.highlight_color = QColor(0, 120, 212)  # VSCode blue #0078d4

        # Настраиваем палитру, чтобы текст и горячие клавиши имели нужные цвета
        palette = self.palette()
        # Основной текст пунктов меню
        palette.setColor(QPalette.ColorRole.WindowText, self.text_color)
        palette.setColor(QPalette.ColorRole.Text, self.text_color)
        palette.setColor(QPalette.ColorRole.ButtonText, self.text_color)
        # Цвет для дополнительных надписей (в т.ч. shortcut'ов)
        palette.setColor(QPalette.ColorRole.Dark, self.shortcut_color)
        palette.setColor(QPalette.ColorRole.Mid, self.shortcut_color)
        self.setPalette(palette)

        # Стрелка вправо из встроенных ресурсов (для ручной отрисовки)
        stylesheet_parts = []
        data = get_svg_qbytearray("chevron-right")
        if not data.isEmpty():
            self.chevron_renderer = QSvgRenderer()
            self.chevron_renderer.load(data)
        else:
            self.chevron_renderer = None
        
        # Fix checkbox indicator padding
        stylesheet_parts.append("""
            QMenu::indicator {
                width: 16px;
                height: 16px;
                padding-left: 0px;
                margin-left: 0px;
            }
            QMenu::item {
                padding: 4px 20px 4px 12px;
            }
        """)
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("".join(stylesheet_parts))
    
        self.border_width = 1
        # Если задан — фокус вернётся этому виджету после показа (для автодополнения)
        self._restore_focus_widget = None
    
    def setRestoreFocusWidget(self, widget):
        """Виджет, которому вернуть фокус после показа меню (меню не забирает фокус)."""
        self._restore_focus_widget = widget
        if widget:
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    
    def restoreFocusWidget(self):
        """Виджет, которому возвращается фокус, или None."""
        return self._restore_focus_widget
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create path for rounded rectangle
        path = QPainterPath()
        # Adjust rectangle to account for pen width
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path.addRoundedRect(rect, self.corner_radius, self.corner_radius)
        
        # Draw background
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.bg_color)
        painter.drawPath(path)
        
        # Draw border with cosmetic pen to ensure 1px regardless of scaling
        pen = QPen(self.border_color, self.border_width)
        pen.setCosmetic(True)  # Ensures consistent 1px width
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        # Set clip path to ensure content stays within rounded corners
        painter.setClipPath(path)
        
        # Let the parent QMenu handle drawing the menu items
        # but don't call the original paintEvent as it would overwrite our custom background
        QMenu.paintEvent(self, event)
        
    def showEvent(self, event):
        # Add extra padding to first and last items
        actions = self.actions()
        if actions:
            # Get first visible action (that's not a separator)
            first_visible = None
            for action in actions:
                if action.isVisible() and not action.isSeparator():
                    first_visible = action
                    break
                    
            # Get last visible action (that's not a separator)
            last_visible = None
            for action in reversed(actions):
                if action.isVisible() and not action.isSeparator():
                    last_visible = action
                    break
                    
            # Add extra spacing by adjusting margins via CSS classes
            if first_visible:
                first_visible.setProperty("class", "first-item")
            if last_visible:
                last_visible.setProperty("class", "last-item")
        
        super().showEvent(event)
        
        # Режим «не забирать фокус»: сразу вернуть фокус заданному виджету
        if self._restore_focus_widget and self._restore_focus_widget.isVisible():
            QTimer.singleShot(0, self._do_restore_focus)
    
    def _do_restore_focus(self):
        if self._restore_focus_widget and self._restore_focus_widget.isVisible():
            self._restore_focus_widget.setFocus()
    
    def focusInEvent(self, event):
        """Если задан виджет для возврата фокуса — не держать фокус на меню."""
        super().focusInEvent(event)
        if self._restore_focus_widget and self._restore_focus_widget.isVisible():
            QTimer.singleShot(0, self._do_restore_focus)


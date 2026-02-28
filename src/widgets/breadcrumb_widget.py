"""
Виджет хлебных крошек с SVG иконками между частями пути.
Folder [chevron] Folder [chevron] Folder [chevron] File.txt
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter
from PyQt6.QtCore import Qt, QRectF, QSize, pyqtSignal
from PyQt6.QtSvg import QSvgRenderer
from src.core.embedded_assets import get_svg_qbytearray


class BreadcrumbWidget(QWidget):
    """Виджет для отображения хлебных крошек с SVG чевронами."""

    partClicked = pyqtSignal(int)  # индекс части пути в исходном списке
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parts = []
        self.modified_text = ""
        self._chevron_renderer = None
        self._hit_regions = []  # список QRectF или None для каждой части пути
        self._hover_index = -1
        
        # Загружаем SVG чеврон (chevron-right для хлебных крошек)
        data = get_svg_qbytearray("chevron-right")
        if not data.isEmpty():
            self._chevron_renderer = QSvgRenderer()
            if not self._chevron_renderer.load(data):
                self._chevron_renderer = None
        
        self.setMinimumHeight(24)
        self.setMouseTracking(True)
        self.setStyleSheet("""
            BreadcrumbWidget {
                background-color: transparent;
             
                color: #969696;
            }
        """)
    
    def set_path(self, path_parts, modified_text=""):
        """Устанавливает части пути и текст о модификации.
        
        Args:
            path_parts: список строк (части пути)
            modified_text: текст для отображения при наличии изменений (например, "(изменен)")
        """
        self.parts = path_parts if path_parts else []
        self.modified_text = modified_text
        self._hit_regions = [None] * len(self.parts)
        self.update()
    
    def sizeHint(self):
        """Возвращает рекомендуемый размер виджета."""
        fm = self.fontMetrics()
        chevron_width = 12 if self._chevron_renderer else 0
        spacing = 4
        
        total_width = 0
        for i, part in enumerate(self.parts):
            total_width += fm.horizontalAdvance(part)
            if i < len(self.parts) - 1:
                total_width += chevron_width + spacing * 2
        
        if self.modified_text:
            total_width += fm.horizontalAdvance(" " + self.modified_text)
        
        total_width += 24  # padding left + right
        
        return QSize(total_width, 24)
    
    def paintEvent(self, event):
        """Отрисовка хлебных крошек с SVG чевронами. При нехватке места — эллипсис в начале."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        fm = self.fontMetrics()
        y = (self.height() - fm.height()) // 2 + fm.ascent()
        x = 8  # padding left
        chevron_size = 12
        chevron_spacing = 4
        avail_width = self.width() - 16
        
        self._hit_regions = [None] * len(self.parts)

        if not self.parts and not self.modified_text:
            return
        
        # Считаем полную ширину
        full_width = 0
        for i, part in enumerate(self.parts):
            full_width += fm.horizontalAdvance(part)
            if i < len(self.parts) - 1 and self._chevron_renderer:
                full_width += chevron_size + chevron_spacing * 2
        if self.modified_text:
            full_width += 4 + fm.horizontalAdvance(self.modified_text)
        
        # Выбираем части для отображения (при нехватке места — только конец пути)
        if full_width <= avail_width:
            display_parts = self.parts
            display_indices = list(range(len(self.parts)))
        else:
            # Показываем ... и последние 2-3 части (папка + файл)
            display_parts = []
            display_indices = []
            part_width = 0
            ellipsis_w = fm.horizontalAdvance("… ")
            for i in range(len(self.parts) - 1, -1, -1):
                w = fm.horizontalAdvance(self.parts[i])
                if i < len(self.parts) - 1:
                    w += chevron_size + chevron_spacing * 2
                if part_width + w + ellipsis_w > avail_width and display_parts:
                    break
                display_parts.insert(0, self.parts[i])
                display_indices.insert(0, i)
                part_width += w
            display_parts = ["…"] + display_parts
            display_indices = [-1] + display_indices
        
        for i, part in enumerate(display_parts):
            idx = display_indices[i]
            w = fm.horizontalAdvance(part)
            # Регистрируем зону клика только для реальных частей (не для "…")
            if idx >= 0:
                rect = QRectF(x, y - fm.ascent(), w, fm.height())
                if 0 <= idx < len(self._hit_regions):
                    self._hit_regions[idx] = rect

            # Цвет текста: при наведении — белый, иначе серый
            if idx == self._hover_index:
                painter.setPen(Qt.GlobalColor.white)
            else:
                painter.setPen(Qt.GlobalColor.gray)

            painter.drawText(int(x), y, part)
            x += w
            
            if i < len(display_parts) - 1 and self._chevron_renderer and display_parts[i] != "…":
                x += chevron_spacing
                chevron_y = (self.height() - chevron_size) // 2
                chevron_rect = QRectF(x, chevron_y, chevron_size, chevron_size)
                self._chevron_renderer.render(painter, chevron_rect)
                x += chevron_size + chevron_spacing
        
        if self.modified_text:
            painter.drawText(int(x) + 4, y, self.modified_text)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        pos = event.position() if hasattr(event, "position") else event.pos()
        x = pos.x()
        y = pos.y()
        for idx, rect in enumerate(self._hit_regions):
            if rect is not None and rect.contains(x, y):
                self.partClicked.emit(idx)
                break
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        x = pos.x()
        y = pos.y()
        new_hover = -1
        for idx, rect in enumerate(self._hit_regions):
            if rect is not None and rect.contains(x, y):
                new_hover = idx
                break
        if new_hover != self._hover_index:
            self._hover_index = new_hover
            if self._hover_index >= 0:
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                self.unsetCursor()
            self.update()
        return super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_index = -1
        self.unsetCursor()
        self.update()
        return super().leaveEvent(event)

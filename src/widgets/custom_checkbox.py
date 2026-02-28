"""
Кастомный CheckBox с отрисовкой галочки из встроенных SVG.
"""
from PyQt6.QtWidgets import QCheckBox, QWidget
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtCore import Qt, QRectF, QSize
from PyQt6.QtSvg import QSvgRenderer
from src.core.embedded_assets import get_svg_qbytearray


class CustomCheckBox(QCheckBox):
    """Кастомный чекбокс с SVG галочкой."""
    
    _check_renderer = None
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._load_renderer()
        self.setStyleSheet("""
            CustomCheckBox {
                color: #D4D4D4;
                spacing: 5px;
            }
            CustomCheckBox::indicator {
                width: 0px;
                height: 0px;
                border: none;
                background: transparent;
            }
        """)
    
    @classmethod
    def _load_renderer(cls):
        if cls._check_renderer is None:
            data = get_svg_qbytearray("check")
            if not data.isEmpty():
                cls._check_renderer = QSvgRenderer()
                cls._check_renderer.load(data)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Размеры
        box_size = 14
        margin = 2
        
        # Позиция чекбокса
        box_rect = QRectF(margin, (self.height() - box_size) / 2, box_size, box_size)
        
        # Фон чекбокса
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(49, 49, 49))
        painter.drawRoundedRect(box_rect, 3, 3)
        
        # Рамка
        painter.setPen(QPen(QColor(60, 60, 60), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(box_rect.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
        
        # Галочка если checked
        if self.isChecked() and self._check_renderer:
            check_rect = box_rect.adjusted(1, 1, -1, -1)
            self._check_renderer.render(painter, check_rect)
        
        # Текст
        text_x = margin + box_size + 6
        text_rect = self.rect().adjusted(int(text_x), 0, 0, 0)
        painter.setPen(QColor(212, 212, 212))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        
        painter.end()
    
    def sizeHint(self):
        fm = self.fontMetrics()
        text_width = fm.horizontalAdvance(self.text())
        return QSize(14 + 6 + text_width + 10, max(20, fm.height() + 4))
    
    def minimumSizeHint(self):
        return self.sizeHint()

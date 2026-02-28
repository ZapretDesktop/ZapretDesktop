"""
Standard (native) dialog implementation for PyQt6.
Uses system window frame instead of frameless custom title bar.
"""

import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QWidget
from PyQt6.QtGui import QIcon, QGuiApplication

import pywinstyles

class _TitleBarCompat:
    """Compatibility object: addLeftWidget/addCenterWidget add to a top bar (for menu bar, etc.)."""
    def __init__(self, layout, top_bar):
        self._layout = layout
        self._top_bar = top_bar

    def addLeftWidget(self, widget):
        self._layout.insertWidget(0, widget)
        self._top_bar.show()

    def addCenterWidget(self, widget):
        self._layout.insertWidget(self._layout.count() - 1, widget, 0, Qt.AlignmentFlag.AlignCenter)
        self._top_bar.show()


class StandardDialog(QDialog):
    """Standard QDialog with system title bar. Provides getContentLayout() and title_bar compat."""
    
    def __init__(self, parent=None, title="Dialog", width=500, height=400, icon_path=None, icon=None, theme="dark"):
        super().__init__(parent)
        pywinstyles.change_header_color(self, color="#181818")  
        self.setWindowTitle(title)
        self.setMinimumSize(300, 200)
        self.resize(width, height)
        if icon is not None and not icon.isNull():
            self.setWindowIcon(icon)
        elif icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
 


        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Top bar for menu bar / center widgets (hidden until widgets added)
        self.top_bar = QWidget()
        self.top_bar_layout = QHBoxLayout(self.top_bar)
        self.top_bar_layout.setContentsMargins(4, 2, 4, 2)
        self.top_bar_layout.setSpacing(4)
        self.top_bar_layout.addStretch(1)
        self.title_bar = _TitleBarCompat(self.top_bar_layout, self.top_bar)
        self.top_bar.hide()
        self.main_layout.addWidget(self.top_bar)
        
        # Content area
        self.content_frame = QWidget()
        self.content_frame.setObjectName("contentFrame")
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(15, 15, 15, 15)
        self.content_layout.setSpacing(10)
        self.main_layout.addWidget(self.content_frame, 1)
        
        # Status bar (optional, added via addStatusBar)
        self.status_bar = None
        
        self.frame_layout = self.main_layout
    
    def addStatusBar(self):
        """Добавляет QStatusBar в структуру окна (внизу, после content_frame)."""
        from PyQt6.QtWidgets import QStatusBar
        if self.status_bar is None:
            self.status_bar = QStatusBar()
            self.main_layout.addWidget(self.status_bar)
        return self.status_bar
    
    def getContentLayout(self):
        return self.content_layout
    
    def showEvent(self, event):
        self._center_on_parent_or_screen()
        super().showEvent(event)
    
    def exec(self):
        self._center_on_parent_or_screen()
        return super().exec()
    
    def _center_on_parent_or_screen(self):
        """Center dialog on parent window or screen."""
        try:
            parent = self.parent()
            screen = None
            if parent and hasattr(parent, "geometry") and parent.isVisible():
                screen = QGuiApplication.screenAt(parent.geometry().center())
            if screen is None:
                screen = QGuiApplication.screenAt(self.geometry().center())
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            available = screen.availableGeometry() if screen else QGuiApplication.primaryScreen().availableGeometry()
            
            if parent and hasattr(parent, "geometry") and parent.isVisible():
                pr = parent.geometry()
                x = pr.x() + (pr.width() - self.width()) // 2
                y = pr.y() + (pr.height() - self.height()) // 2
            else:
                x = available.x() + (available.width() - self.width()) // 2
                y = available.y() + (available.height() - self.height()) // 2
            
            x = max(available.x(), min(x, available.x() + available.width() - self.width()))
            y = max(available.y(), min(y, available.y() + available.height() - self.height()))
            self.move(x, y)
        except Exception:
            pass

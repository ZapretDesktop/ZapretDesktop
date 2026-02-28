"""
Standard (native) main window implementation for PyQt6.
Uses system window frame instead of frameless custom title bar.
"""

import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication
from PyQt6.QtGui import QIcon


class StandardMainWindow(QMainWindow):
    """Standard QMainWindow with system title bar. Provides setContentWidget, getContentLayout."""
    
    def __init__(self, title="Window", width=800, height=600, icon_path=None, icon=None, theme="dark"):
        super().__init__()
        self.default_width = width
        self.default_height = height
        self.setWindowTitle(title)
        self.setFixedSize(width, height)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        if icon is not None and not icon.isNull():
            self.setWindowIcon(icon)
        elif icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Central widget with content layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.content_layout = QVBoxLayout(self.central_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        # Center window on screen
        self._center_window()
    
    def setIconPath(self, icon_path):
        """Set window icon from path (legacy)."""
        if icon_path and os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
    
    def setContentWidget(self, widget):
        """Set the content widget for the window."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.content_layout.addWidget(widget)
    
    def getContentLayout(self):
        """Get the content layout for adding widgets."""
        return self.content_layout
    
    def _center_window(self):
        """Center window on primary screen."""
        try:
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - self.default_width) // 2
            y = (screen.height() - self.default_height) // 2
            self.setGeometry(x, y, self.default_width, self.default_height)
        except Exception as e:
            print(f"Error centering window: {e}")

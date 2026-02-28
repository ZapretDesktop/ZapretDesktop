"""
Animated Progress Bar in VS Code style
"""

from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *


class AnimatedProgressBar(QProgressBar):
    """Progress bar with VS Code-style animation"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self.setTextVisible(False)
        self.setRange(0, 100)
        
        # Animation properties
        self.animation_position = 0
        self.animation_speed = 2.0  # pixels per frame
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._update_animation)
        self.is_indeterminate = False
        
        # VS Code colors
        self.progress_color = QColor("#0078d4")
        self.background_color = QColor(0, 122, 204, 51)  # rgba(0, 122, 204, 0.2)
        
        # Apply base style
        self.setStyleSheet("""
            QProgressBar {
                background-color: transparent;
                border: none;
            }
        """)
    
    def setIndeterminate(self, indeterminate: bool):
        """Set indeterminate mode (infinite animation)"""
        self.is_indeterminate = indeterminate
        if indeterminate:
            self.setRange(0, 0)  # Indeterminate mode
            self.animation_position = 0
            self.animation_timer.start(16)  # ~60 FPS
        else:
            self.animation_timer.stop()
            self.setRange(0, 100)
            self.update()
    
    def _update_animation(self):
        """Update animation position"""
        if self.is_indeterminate:
            self.animation_position += self.animation_speed
            # Cycle position to create infinite loop
            cycle_length = self.width() + 150
            if self.animation_position >= cycle_length:
                self.animation_position = 0
            self.update()
    
    def paintEvent(self, event):
        """Custom paint event for animated progress bar"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        
        if self.is_indeterminate:
            # Draw animated gradient for indeterminate mode (VS Code style)
            # Draw background (subtle blue tint)
            painter.fillRect(rect, self.background_color)
            
            # Create a moving gradient bar
            gradient_width = 150  # Width of the animated bar
            cycle_length = rect.width() + gradient_width
            
            # Calculate current position in cycle
            pos_in_cycle = self.animation_position % cycle_length
            
            # Create gradient that moves across the widget
            gradient = QLinearGradient(pos_in_cycle - gradient_width, 0, pos_in_cycle, 0)
            
            # Smooth fade at edges
            fade_ratio = 0.3  # 30% of gradient width is fade
            gradient.setColorAt(0.0, QColor(0, 0, 0, 0))  # Transparent start
            gradient.setColorAt(fade_ratio, self.progress_color)  # Fade in
            gradient.setColorAt(1.0 - fade_ratio, self.progress_color)  # Full color
            gradient.setColorAt(1.0, QColor(0, 0, 0, 0))  # Transparent end
            
            # Draw the animated gradient
            painter.fillRect(rect, gradient)
        else:
            # Draw normal progress bar
            if self.maximum() > 0 and self.value() > 0:
                progress_width = int((self.value() / self.maximum()) * rect.width())
                
                # Draw background (subtle)
                painter.fillRect(rect, self.background_color)
                
                # Draw progress chunk
                progress_rect = QRect(0, 0, progress_width, rect.height())
                painter.fillRect(progress_rect, self.progress_color)
            else:
                # If no progress, just show background
                painter.fillRect(rect, self.background_color)
    
    def setValue(self, value: int):
        """Override setValue to handle indeterminate mode"""
        if not self.is_indeterminate:
            super().setValue(value)
        else:
            # In indeterminate mode, don't update value
            pass
    
    def startAnimation(self):
        """Start the animation"""
        if self.is_indeterminate:
            self.animation_timer.start(16)  # ~60 FPS
    
    def stopAnimation(self):
        """Stop the animation"""
        self.animation_timer.stop()


#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Preview widget for displaying video frames and handling crop functionality
"""

import numpy as np
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QSizePolicy
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QRect, QTimer, pyqtSignal, QPoint, QSize

class PreviewWidget(QWidget):
    """Widget for displaying video frames and previews with crop functionality"""

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_pixmap = None
        self.preview_frames = []
        self.current_preview_index = 0
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.show_next_preview_frame)
        
        self.crop_mode = False
        self.crop_start = None
        self.crop_end = None
        self.crop_rect = None
        
        # Create display label
        self.frame_label = QLabel()
        self.frame_label.setAlignment(Qt.AlignCenter)
        self.frame_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.frame_label.setMinimumSize(320, 240)
        self.frame_label.setStyleSheet("background-color: black;")
        
        # Set up layout
        layout = QVBoxLayout()
        layout.addWidget(self.frame_label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
    
    def display_frame(self, frame):
        """Display a video frame"""
        if frame is None:
            return
            
        # Stop any preview playback
        self.preview_timer.stop()
        
        # Convert numpy array to QImage
        height, width, channel = frame.shape
        bytes_per_line = channel * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        
        # Create a pixmap and display it
        self.current_pixmap = QPixmap.fromImage(q_img)
        self._update_display()
    
    def play_preview(self, frames, fps):
        """Play a preview with the given frames and fps"""
        if not frames:
            return
            
        self.preview_frames = frames
        self.current_preview_index = 0
        
        # Calculate interval (in ms) based on fps
        interval = int(1000 / fps)
        self.preview_timer.start(interval)
    
    def show_next_preview_frame(self):
        """Show the next frame in the preview sequence"""
        if not self.preview_frames:
            self.preview_timer.stop()
            return
            
        frame = self.preview_frames[self.current_preview_index]
        
        # Convert numpy array to QImage
        height, width, channel = frame.shape
        bytes_per_line = channel * width
        q_img = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        
        # Create a pixmap and display it
        self.current_pixmap = QPixmap.fromImage(q_img)
        self._update_display()
        
        # Move to next frame or loop back to beginning
        self.current_preview_index = (self.current_preview_index + 1) % len(self.preview_frames)
    
    def _update_display(self):
        """Update the display with the current pixmap, considering crop mode"""
        if self.current_pixmap is None:
            return
            
        # Create a scaled version of the pixmap
        label_size = self.frame_label.size()
        scaled_pixmap = self.current_pixmap.scaled(
            label_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # If not in crop mode, just show the scaled pixmap
        if not self.crop_mode:
            self.frame_label.setPixmap(scaled_pixmap)
            return
            
        # In crop mode, work with a copy of the scaled pixmap
        display_pixmap = scaled_pixmap.copy()
        
        # Calculate scaling factors between original and displayed image
        scale_x = self.current_pixmap.width() / scaled_pixmap.width()
        scale_y = self.current_pixmap.height() / scaled_pixmap.height()
        
        # Calculate offsets for centered image
        x_offset = (label_size.width() - scaled_pixmap.width()) / 2
        y_offset = (label_size.height() - scaled_pixmap.height()) / 2
        
        # If we have a crop rectangle, draw it
        if self.crop_start is not None and self.crop_end is not None:
            try:
                painter = QPainter()
                if painter.begin(display_pixmap):
                    try:
                        # Set up the pen for drawing
                        pen = QPen(QColor(255, 0, 0))
                        pen.setWidth(2)
                        painter.setPen(pen)
                        
                        # Convert crop coordinates
                        start_x = self.crop_start.x() - x_offset
                        start_y = self.crop_start.y() - y_offset
                        end_x = self.crop_end.x() - x_offset
                        end_y = self.crop_end.y() - y_offset
                        
                        # Ensure coordinates are within bounds
                        start_x = max(0, min(start_x, scaled_pixmap.width()))
                        start_y = max(0, min(start_y, scaled_pixmap.height()))
                        end_x = max(0, min(end_x, scaled_pixmap.width()))
                        end_y = max(0, min(end_y, scaled_pixmap.height()))
                        
                        # Calculate crop rectangle dimensions
                        crop_x = int(min(start_x, end_x))
                        crop_y = int(min(start_y, end_y))
                        crop_w = int(abs(end_x - start_x))
                        crop_h = int(abs(end_y - start_y))
                        
                        # Store the crop rectangle in original image coordinates
                        self.crop_rect = (
                            int(crop_x * scale_x),
                            int(crop_y * scale_y),
                            int(crop_w * scale_x),
                            int(crop_h * scale_y)
                        )
                        
                        # Draw the rectangle
                        painter.drawRect(crop_x, crop_y, crop_w, crop_h)
                    finally:
                        painter.end()
            except Exception as e:
                print(f"Painting error: {e}")
        
        # Display the result
        self.frame_label.setPixmap(display_pixmap)
    
    def mousePressEvent(self, event):
        """Handle mouse press events for crop selection"""
        if not self.crop_mode or self.current_pixmap is None:
            return super().mousePressEvent(event)
            
        # Start a new crop selection
        self.crop_start = event.pos()
        self.crop_end = None
        self._update_display()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for crop selection"""
        if not self.crop_mode or self.crop_start is None:
            return super().mouseMoveEvent(event)
            
        # Update the crop end position as the mouse moves
        self.crop_end = event.pos()
        self._update_display()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events to finalize crop selection"""
        if not self.crop_mode or self.crop_start is None:
            return super().mouseReleaseEvent(event)
            
        # Set the final crop end position
        self.crop_end = event.pos()
        self._update_display()
    
    def enable_crop_mode(self):
        """Enable crop mode"""
        self.crop_mode = True
        self.crop_start = None
        self.crop_end = None
        self.setCursor(Qt.CrossCursor)
    
    def disable_crop_mode(self):
        """Disable crop mode"""
        self.crop_mode = False
        self.setCursor(Qt.ArrowCursor)
        self._update_display()
    
    def get_crop_rect(self):
        """Return the current crop rectangle"""
        return self.crop_rect
    
    def resizeEvent(self, event):
        """Handle resize events to update the display"""
        super().resizeEvent(event)
        self._update_display()
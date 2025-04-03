#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Timeline widget for video trimming functionality
"""

import numpy as np
from PyQt5.QtWidgets import (QWidget, QLabel, QHBoxLayout, QVBoxLayout, QSlider,
                            QSizePolicy, QPushButton, QStyle, QMenu, QAction, QFrame)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QLinearGradient, QPaintEvent
from PyQt5.QtCore import Qt, QRect, QTimer, pyqtSignal, QPoint, QSize

class ThumbnailStrip(QWidget):
    """Widget for displaying video thumbnails"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnails = []
        self.duration = 0
        self.start_time = 0
        self.end_time = 0
        self.excluded_segments = []  # List of (start, end) tuples to exclude
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
    def set_thumbnails(self, thumbnails, duration, start_time=0, end_time=None):
        """Set thumbnails and timeline parameters"""
        self.thumbnails = thumbnails if thumbnails else []
        self.duration = duration
        self.start_time = start_time
        self.end_time = end_time if end_time is not None else duration
        self.update()  # Request a repaint
    
    def set_excluded_segments(self, segments):
        """Set segments to exclude (trim out)"""
        self.excluded_segments = segments
        self.update()  # Request a repaint
    
    def paintEvent(self, event):
        """Paint the thumbnails and trim indicators"""
        # Call the base class implementation first
        super().paintEvent(event)
        
        # Create a QPainter for this widget
        painter = QPainter(self)
        
        try:
            # Draw background
            painter.fillRect(0, 0, self.width(), self.height(), QColor(34, 34, 34))
            
            # Draw thumbnails
            if self.thumbnails:
                num_thumbnails = len(self.thumbnails)
                thumb_width = self.width() / num_thumbnails
                
                for i, thumbnail in enumerate(self.thumbnails):
                    # Convert numpy array to QImage
                    try:
                        h, w, c = thumbnail.shape
                        bytes_per_line = c * w
                        q_img = QImage(thumbnail.data, w, h, bytes_per_line, QImage.Format_RGB888)
                        
                        # Calculate position
                        x = i * thumb_width
                        
                        # Draw thumbnail
                        painter.drawImage(QRect(int(x), 0, int(thumb_width), self.height()), q_img)
                    except Exception as e:
                        # Handle thumbnail drawing errors gracefully
                        print(f"Error drawing thumbnail {i}: {e}")
            
            # Draw trim indicators if duration is valid
            if self.duration > 0:
                width = self.width()
                height = self.height()
                
                # Draw start trim line
                start_x = int((self.start_time / self.duration) * width)
                painter.setPen(QPen(QColor(0, 255, 0), 2))
                painter.drawLine(start_x, 0, start_x, height)
                
                # Draw end trim line
                end_x = int((self.end_time / self.duration) * width)
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawLine(end_x, 0, end_x, height)
                
                # Shade areas outside the trim region
                fade_color = QColor(0, 0, 0, 150)  # Semi-transparent black
                
                # Shade left of start
                painter.fillRect(0, 0, start_x, height, fade_color)
                
                # Shade right of end
                painter.fillRect(end_x, 0, width - end_x, height, fade_color)
                
                # Shade excluded segments
                exclude_color = QColor(255, 0, 0, 100)  # Semi-transparent red
                for start, end in self.excluded_segments:
                    # Convert time to x positions
                    ex_start = int((start / self.duration) * width)
                    ex_end = int((end / self.duration) * width)
                    # Draw the excluded area
                    painter.fillRect(ex_start, 0, ex_end - ex_start, height, exclude_color)
                    
                    # Draw segment border lines
                    painter.setPen(QPen(QColor(255, 165, 0), 2))  # Orange border
                    painter.drawLine(ex_start, 0, ex_start, height)
                    painter.drawLine(ex_end, 0, ex_end, height)
                    
                    # Draw scissors icon or label
                    painter.setPen(QColor(255, 255, 255))
                    mid_x = (ex_start + ex_end) / 2
                    painter.drawText(int(mid_x - 10), int(height / 2), "✂")
        finally:
            # Ensure painter is properly ended
            painter.end()


class TimelineWidget(QWidget):
    """Widget for timeline display and trim control"""
    
    # Signal to notify when trim values change
    trim_changed = pyqtSignal(float, float)
    # Signal to notify when excluded segments change
    segments_changed = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.thumbnails = []
        self.duration = 0
        self.start_time = 0
        self.end_time = 0
        self.excluded_segments = []  # List of (start, end) tuples to exclude
        self.selecting_exclusion = False
        self.temp_exclusion_start = None
        
        # Minimum height for the timeline
        self.setMinimumHeight(100)
        
        # Create thumbnail strip (custom widget that properly handles painting)
        self.thumbnail_strip = ThumbnailStrip()
        
        # Timeline controls layout
        timeline_controls = QHBoxLayout()
        
        # Sliders for trim control
        self.start_slider = QSlider(Qt.Horizontal)
        self.start_slider.setRange(0, 1000)
        self.start_slider.setValue(0)
        self.start_slider.setTracking(True)
        self.start_slider.valueChanged.connect(self.update_start_trim)
        
        self.end_slider = QSlider(Qt.Horizontal)
        self.end_slider.setRange(0, 1000)
        self.end_slider.setValue(1000)
        self.end_slider.setTracking(True)
        self.end_slider.valueChanged.connect(self.update_end_trim)
        
        # Create buttons for handling trimming segments
        self.trim_button = QPushButton("Trim Out Segment")
        self.trim_button.clicked.connect(self.start_segment_selection)
        self.trim_button.setToolTip("Select a segment of the video to trim out")
        
        self.reset_button = QPushButton("Reset Trims")
        self.reset_button.clicked.connect(self.reset_excluded_segments)
        self.reset_button.setToolTip("Remove all trim segments")
        
        # Add a divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        
        # Add buttons to timeline controls
        timeline_controls.addWidget(self.trim_button)
        timeline_controls.addWidget(self.reset_button)
        timeline_controls.addWidget(divider)
        timeline_controls.addStretch()
        
        # Time display labels
        self.start_time_label = QLabel("00:00.000")
        self.end_time_label = QLabel("00:00.000")
        self.duration_label = QLabel("Duration: 00:00.000")
        
        # Add time labels to timeline controls
        timeline_controls.addWidget(self.start_time_label)
        timeline_controls.addStretch()
        timeline_controls.addWidget(self.duration_label)
        timeline_controls.addStretch()
        timeline_controls.addWidget(self.end_time_label)
        
        # Selection mode indicator
        self.selection_label = QLabel("")
        self.selection_label.setStyleSheet("color: red; font-weight: bold;")
        self.selection_label.setAlignment(Qt.AlignCenter)
        self.selection_label.setVisible(False)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.thumbnail_strip)
        main_layout.addWidget(self.start_slider)
        main_layout.addWidget(self.end_slider)
        main_layout.addWidget(self.selection_label)
        main_layout.addLayout(timeline_controls)
        main_layout.setContentsMargins(5, 0, 5, 0)
        
        self.setEnabled(False)
    
    def setup_timeline(self, duration, thumbnails=None):
        """Setup the timeline with duration and thumbnails"""
        self.duration = duration
        self.start_time = 0
        self.end_time = duration
        self.excluded_segments = []
        
        # Reset sliders
        self.start_slider.blockSignals(True)
        self.end_slider.blockSignals(True)
        
        self.start_slider.setValue(0)
        self.end_slider.setValue(1000)
        
        self.start_slider.blockSignals(False)
        self.end_slider.blockSignals(False)
        
        # Store thumbnails
        if thumbnails:
            self.thumbnails = thumbnails
            
        # Update thumbnail strip
        self.thumbnail_strip.set_thumbnails(self.thumbnails, self.duration, self.start_time, self.end_time)
        self.thumbnail_strip.set_excluded_segments(self.excluded_segments)
        
        # Update time labels
        self.update_time_labels()
        
        # Enable the widget
        self.setEnabled(True)
        
        # Emit the initial trim values
        self.trim_changed.emit(self.start_time, self.end_time)
        self.segments_changed.emit(self.excluded_segments)
    
    def update_thumbnail_strip(self):
        """Update the thumbnail strip with the current thumbnails"""
        # This function is responsible for painting thumbnails and would be more complex
        # For simplicity, we'll trigger a repaint which will then use paintEvent
        self.thumbnail_strip.update()
    
    def update_start_trim(self):
        """Update start trim position from slider value"""
        # Get slider value as percentage of duration
        percent = self.start_slider.value() / 1000.0
        
        # Calculate new start time
        new_start = percent * self.duration
        
        # Ensure start time doesn't exceed end time
        if new_start >= self.end_time:
            new_start = self.end_time - 0.1  # Keep a small gap
            
            # Update slider without triggering signal
            self.start_slider.blockSignals(True)
            self.start_slider.setValue(int(new_start / self.duration * 1000))
            self.start_slider.blockSignals(False)
        
        # Update start time
        self.start_time = new_start
        
        # Update thumbnail strip to reflect new start time
        self.thumbnail_strip.set_thumbnails(self.thumbnails, self.duration, self.start_time, self.end_time)
        
        # Update display
        self.update_time_labels()
        
        # Notify of change
        self.trim_changed.emit(self.start_time, self.end_time)
    
    def update_end_trim(self):
        """Update end trim position from slider value"""
        # Get slider value as percentage of duration
        percent = self.end_slider.value() / 1000.0
        
        # Calculate new end time
        new_end = percent * self.duration
        
        # Ensure end time doesn't go below start time
        if new_end <= self.start_time:
            new_end = self.start_time + 0.1  # Keep a small gap
            
            # Update slider without triggering signal
            self.end_slider.blockSignals(True)
            self.end_slider.setValue(int(new_end / self.duration * 1000))
            self.end_slider.blockSignals(False)
        
        # Update end time
        self.end_time = new_end
        
        # Update thumbnail strip to reflect new end time
        self.thumbnail_strip.set_thumbnails(self.thumbnails, self.duration, self.start_time, self.end_time)
        
        # Update display
        self.update_time_labels()
        
        # Notify of change
        self.trim_changed.emit(self.start_time, self.end_time)
    
    def update_time_labels(self):
        """Update the time display labels"""
        # Format start time
        minutes_start = int(self.start_time / 60)
        seconds_start = self.start_time % 60
        self.start_time_label.setText(f"{minutes_start:02d}:{seconds_start:05.2f}")
        
        # Format end time
        minutes_end = int(self.end_time / 60)
        seconds_end = self.end_time % 60
        self.end_time_label.setText(f"{minutes_end:02d}:{seconds_end:05.2f}")
        
        # Format duration
        trim_duration = self.end_time - self.start_time
        
        # Calculate effective duration by excluding segments
        excluded_duration = 0
        for start, end in self.excluded_segments:
            # Only count segments that overlap with the selected range
            if end > self.start_time and start < self.end_time:
                overlap_start = max(start, self.start_time)
                overlap_end = min(end, self.end_time)
                excluded_duration += (overlap_end - overlap_start)
        
        effective_duration = trim_duration - excluded_duration
        
        minutes_dur = int(effective_duration / 60)
        seconds_dur = effective_duration % 60
        self.duration_label.setText(f"Duration: {minutes_dur:02d}:{seconds_dur:05.2f}")
    
    def get_trim_values(self):
        """Return the current trim values"""
        return self.start_time, self.end_time
    
    def get_excluded_segments(self):
        """Return the list of segments to exclude"""
        return self.excluded_segments
    
    def get_effective_segments(self):
        """Return list of segments to include in final output
        
        Returns a list of (start, end) tuples representing
        segments to keep after trimming out excluded segments
        """
        if not self.excluded_segments:
            # If no exclusions, just return the main segment
            return [(self.start_time, self.end_time)]
        
        # Sort excluded segments by start time
        sorted_exclusions = sorted(self.excluded_segments)
        
        # Start with the primary segment
        effective_segments = []
        current_start = self.start_time
        
        # Iterate through exclusions to create effective segments
        for exclusion_start, exclusion_end in sorted_exclusions:
            # Only process exclusions that overlap with the primary segment
            if exclusion_end <= self.start_time or exclusion_start >= self.end_time:
                continue
                
            # Clip the exclusion to the primary segment boundaries
            exclusion_start = max(exclusion_start, self.start_time)
            exclusion_end = min(exclusion_end, self.end_time)
            
            # Add segment before this exclusion if it has length > 0
            if exclusion_start > current_start:
                effective_segments.append((current_start, exclusion_start))
                
            # Move current start to after this exclusion
            current_start = exclusion_end
        
        # Add final segment if needed
        if current_start < self.end_time:
            effective_segments.append((current_start, self.end_time))
            
        return effective_segments
    
    def mousePressEvent(self, event):
        """Handle mouse press for segment selection"""
        if not self.selecting_exclusion:
            return super().mousePressEvent(event)
            
        # Calculate the time position based on mouse x position
        x_pos = event.pos().x()
        if not (0 <= x_pos <= self.thumbnail_strip.width()):
            return
            
        time_pos = (x_pos / self.thumbnail_strip.width()) * self.duration
        self.temp_exclusion_start = time_pos
        self.selection_label.setText(f"Selecting trim segment: Start={format_time(time_pos)}")
    
    def mouseMoveEvent(self, event):
        """Update selection feedback during dragging"""
        if not self.selecting_exclusion or self.temp_exclusion_start is None:
            return super().mouseMoveEvent(event)
            
        # Calculate current time position
        x_pos = max(0, min(event.pos().x(), self.thumbnail_strip.width()))
        time_pos = (x_pos / self.thumbnail_strip.width()) * self.duration
        
        # Update selection feedback
        start_time = min(self.temp_exclusion_start, time_pos)
        end_time = max(self.temp_exclusion_start, time_pos)
        self.selection_label.setText(
            f"Selecting trim segment: {format_time(start_time)} to {format_time(end_time)}")
            
    def mouseReleaseEvent(self, event):
        """Finalize segment selection"""
        if not self.selecting_exclusion or self.temp_exclusion_start is None:
            return super().mouseReleaseEvent(event)
            
        # Calculate the end time position
        x_pos = max(0, min(event.pos().x(), self.thumbnail_strip.width()))
        time_pos = (x_pos / self.thumbnail_strip.width()) * self.duration
        
        # Ensure segment has minimum width and is ordered correctly
        start_time = min(self.temp_exclusion_start, time_pos)
        end_time = max(self.temp_exclusion_start, time_pos)
        
        # Only add if segment has some duration
        if end_time - start_time > 0.1:
            self.add_excluded_segment(start_time, end_time)
            
        # Exit selection mode
        self.exit_segment_selection_mode()
    
    def add_excluded_segment(self, start_time, end_time):
        """Add a new segment to exclude"""
        from PyQt5.QtWidgets import QMessageBox
        
        # Format times for display
        start_str = format_time(start_time)
        end_str = format_time(end_time)
        duration = end_time - start_time
        duration_str = format_time(duration)
        
        # Show confirmation dialog
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Confirm Trim")
        msg.setText(f"Trim out segment from {start_str} to {end_str}?")
        msg.setInformativeText(f"This will remove {duration_str} from your video.")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        
        if msg.exec_() == QMessageBox.Yes:
            # Add the new segment
            self.excluded_segments.append((start_time, end_time))
            
            # Merge overlapping segments
            self.excluded_segments = merge_overlapping_segments(self.excluded_segments)
            
            # Update display and notify
            self.thumbnail_strip.set_excluded_segments(self.excluded_segments)
            self.update_time_labels()
            self.segments_changed.emit(self.excluded_segments)
            
            # Show success message
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Segment Trimmed")
            msg.setText("The segment has been marked for removal.")
            msg.setInformativeText("Generate a preview to see how your video will look.")
            msg.setStandardButtons(QMessageBox.Ok)
            msg.exec_()
            
            return True
        return False
    
    def start_segment_selection(self):
        """Start the process of selecting a segment to exclude"""
        self.selecting_exclusion = True
        self.temp_exclusion_start = None
        self.selection_label.setText("Click and drag to select segment to trim out")
        self.selection_label.setVisible(True)
        self.setCursor(Qt.CrossCursor)
        
        # Disable controls during selection
        self.start_slider.setEnabled(False)
        self.end_slider.setEnabled(False)
        self.trim_button.setEnabled(False)
        
    def exit_segment_selection_mode(self):
        """Exit the segment selection mode"""
        self.selecting_exclusion = False
        self.temp_exclusion_start = None
        self.selection_label.setVisible(False)
        self.setCursor(Qt.ArrowCursor)
        
        # Re-enable controls
        self.start_slider.setEnabled(True)
        self.end_slider.setEnabled(True)
        self.trim_button.setEnabled(True)
    
    def reset_excluded_segments(self):
        """Clear all excluded segments"""
        if not self.excluded_segments:
            return
            
        self.excluded_segments = []
        self.thumbnail_strip.set_excluded_segments(self.excluded_segments)
        self.update_time_labels()
        self.segments_changed.emit(self.excluded_segments)
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        # Allow canceling segment selection with Escape
        if event.key() == Qt.Key_Escape and self.selecting_exclusion:
            self.exit_segment_selection_mode()
        else:
            super().keyPressEvent(event)


def format_time(seconds):
    """Format time in seconds to MM:SS.ss format"""
    minutes = int(seconds / 60)
    secs = seconds % 60
    return f"{minutes:02d}:{secs:05.2f}"


def merge_overlapping_segments(segments):
    """Merge overlapping time segments"""
    if not segments:
        return []
        
    # Sort segments by start time
    sorted_segments = sorted(segments)
    merged = [sorted_segments[0]]
    
    for current in sorted_segments[1:]:
        previous = merged[-1]
        
        # If current segment overlaps with previous one
        if current[0] <= previous[1]:
            # Merge them by updating the end time of the previous segment
            merged[-1] = (previous[0], max(previous[1], current[1]))
        else:
            # No overlap, add as separate segment
            merged.append(current)
            
    return merged
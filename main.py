#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
GIF Creator - A simple yet powerful video editor for creating optimized GIFs
"""

import sys
import os
import json
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QSlider, QFileDialog, 
                             QLabel, QSpinBox, QDoubleSpinBox, QComboBox, QMessageBox,
                             QSplitter, QCheckBox, QFrame, QSizePolicy, QProgressDialog,
                             QMenu, QAction, QInputDialog, QStyleFactory, QShortcut)
from PyQt5.QtCore import Qt, QTimer, QSize, QUrl, QDir, QSettings
from PyQt5.QtGui import QPixmap, QImage, QIcon, QKeySequence

from video_processor import VideoProcessor
from preview_widget import PreviewWidget
from timeline_widget import TimelineWidget

class PresetManager:
    """Manage output settings presets"""
    def __init__(self, settings):
        self.settings = settings
        self.presets = self._load_presets()
    
    def _load_presets(self):
        """Load presets from settings"""
        presets = self.settings.value("presets", [])
        if not presets:
            # Default presets
            presets = [
                {"name": "High Quality", "fps": 30, "quality": 95, "resolution": "Original", "speed": 100},
                {"name": "Balanced", "fps": 20, "quality": 85, "resolution": "720p", "speed": 100},
                {"name": "Compressed", "fps": 15, "quality": 70, "resolution": "480p", "speed": 100},
            ]
            self.settings.setValue("presets", presets)
        # Add speed value to older presets that might not have it
        for preset in presets:
            if "speed" not in preset:
                preset["speed"] = 100
        return presets
    
    def save_preset(self, name, fps, quality, resolution, speed=100):
        """Save a new preset"""
        preset = {
            "name": name,
            "fps": fps,
            "quality": quality,
            "resolution": resolution,
            "speed": speed
        }
        self.presets.append(preset)
        self.settings.setValue("presets", self.presets)
    
    def get_presets(self):
        """Get all presets"""
        return self.presets
    
    def delete_preset(self, name):
        """Delete a preset by name"""
        self.presets = [p for p in self.presets if p["name"] != name]
        self.settings.setValue("presets", self.presets)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize settings
        self.settings = QSettings("GIFCreator", "GIFEditor")
        self.preset_manager = PresetManager(self.settings)
        self.recent_files = self.settings.value("recent_files", [])
        self.max_recent_files = 5
        
        self.video_processor = VideoProcessor()
        self.current_file = None
        self.output_file = None
        self.excluded_segments = []  # List of time segments to exclude
        self.initUI()
        
        # Restore window geometry
        geometry = self.settings.value("geometry")
        if (geometry):
            self.restoreGeometry(geometry)
            
        # Initialize theme
        self.current_theme = self.settings.value("theme", "Light")
        self.apply_theme(self.current_theme)
    
    def initUI(self):
        """Initialize the user interface"""
        self.setWindowTitle("GIF Creator")
        self.setMinimumSize(1000, 800)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create top toolbar
        toolbar_layout = QHBoxLayout()
        self.open_button = QPushButton("Open Video")
        self.open_button.clicked.connect(self.open_file)
        self.save_button = QPushButton("Save GIF")
        self.save_button.clicked.connect(self.save_file)
        self.save_button.setEnabled(False)
        
        toolbar_layout.addWidget(self.open_button)
        toolbar_layout.addWidget(self.save_button)
        toolbar_layout.addStretch()
        main_layout.addLayout(toolbar_layout)
        
        # Create splitter for preview and controls
        splitter = QSplitter(Qt.Vertical)
        
        # Preview area
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        
        # Create preview widget
        self.preview_widget = PreviewWidget()
        preview_layout.addWidget(self.preview_widget)
        
        # Create timeline widget
        self.timeline_widget = TimelineWidget()
        self.timeline_widget.trim_changed.connect(self.on_trim_changed)
        self.timeline_widget.segments_changed.connect(self.on_segments_changed)
        preview_layout.addWidget(self.timeline_widget)
        
        splitter.addWidget(preview_container)
        
        # Controls area
        controls_container = QWidget()
        controls_layout = QVBoxLayout(controls_container)
        
        # FPS controls
        fps_layout = QHBoxLayout()
        fps_label = QLabel("FPS:")
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(15)
        self.fps_spin.valueChanged.connect(self.update_preview_params)
        fps_layout.addWidget(fps_label)
        fps_layout.addWidget(self.fps_spin)
        fps_layout.addStretch()
        
        # Speed controls
        speed_layout = QHBoxLayout()
        speed_label = QLabel("Speed:")
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(25, 400)  # 0.25x to 4.0x
        self.speed_slider.setValue(100)  # Default 1.0x
        self.speed_slider.valueChanged.connect(self.update_preview_params)
        self.speed_value = QLabel("1.0x")
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_value.setText(f"{v/100:.1f}x"))
            
        speed_layout.addWidget(speed_label)
        speed_layout.addWidget(self.speed_slider)
        speed_layout.addWidget(self.speed_value)
        
        # Add speed controls after FPS controls
        controls_layout.insertLayout(1, speed_layout)
        
        # Resolution controls
        resolution_layout = QHBoxLayout()
        resolution_label = QLabel("Resolution:")
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["Original", "720p", "480p", "360p", "240p", "Custom"])
        self.resolution_combo.currentIndexChanged.connect(self.on_resolution_changed)
        
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 4096)
        self.width_spin.setValue(320)
        self.width_spin.setEnabled(False)
        
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 4096)
        self.height_spin.setValue(240)
        self.height_spin.setEnabled(False)
        
        self.maintain_aspect = QCheckBox("Maintain aspect ratio")
        self.maintain_aspect.setChecked(True)
        
        resolution_layout.addWidget(resolution_label)
        resolution_layout.addWidget(self.resolution_combo)
        resolution_layout.addWidget(self.width_spin)
        resolution_layout.addWidget(QLabel("x"))
        resolution_layout.addWidget(self.height_spin)
        resolution_layout.addWidget(self.maintain_aspect)
        resolution_layout.addStretch()
        
        # Crop controls
        crop_layout = QHBoxLayout()
        crop_label = QLabel("Crop:")
        self.enable_crop = QCheckBox("Enable")
        self.enable_crop.stateChanged.connect(self.on_crop_enabled)
        self.crop_button = QPushButton("Set crop region")
        self.crop_button.setEnabled(False)
        self.crop_button.clicked.connect(self.on_set_crop)
        
        crop_layout.addWidget(crop_label)
        crop_layout.addWidget(self.enable_crop)
        crop_layout.addWidget(self.crop_button)
        crop_layout.addStretch()
        
        # Quality controls
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Quality:")
        self.quality_slider = QSlider(Qt.Horizontal)
        self.quality_slider.setRange(1, 100)
        self.quality_slider.setValue(90)
        self.quality_slider.valueChanged.connect(self.update_preview_params)
        self.quality_value = QLabel("90%")
        self.quality_slider.valueChanged.connect(
            lambda v: self.quality_value.setText(f"{v}%"))
            
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_slider)
        quality_layout.addWidget(self.quality_value)
        
        # Loop control
        loop_layout = QHBoxLayout()
        loop_label = QLabel("GIF Options:")
        self.loop_checkbox = QCheckBox("Loop GIF")
        self.loop_checkbox.setChecked(True)
        self.loop_checkbox.setToolTip("If checked, the GIF will loop continuously. If unchecked, it will play only once.")
        loop_layout.addWidget(loop_label)
        loop_layout.addWidget(self.loop_checkbox)
        loop_layout.addStretch()
        
        # Preview button
        preview_btn_layout = QHBoxLayout()
        self.preview_button = QPushButton("Generate Preview")
        self.preview_button.clicked.connect(self.generate_preview)
        self.preview_button.setEnabled(False)
        preview_btn_layout.addStretch()
        preview_btn_layout.addWidget(self.preview_button)
        preview_btn_layout.addStretch()
        
        # Add all control layouts
        controls_layout.addLayout(fps_layout)
        controls_layout.addLayout(resolution_layout)
        controls_layout.addLayout(crop_layout)
        controls_layout.addLayout(quality_layout)
        controls_layout.addLayout(loop_layout)
        controls_layout.addLayout(preview_btn_layout)
        controls_layout.addStretch()
        
        splitter.addWidget(controls_container)
        
        # Set initial splitter sizes
        splitter.setSizes([700, 300])
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Set up connections
        self.width_spin.valueChanged.connect(self.update_preview_params)
        self.height_spin.valueChanged.connect(self.update_preview_params)
        
        # Add menu bar
        self._create_menu_bar()
        
        # Add preset selector to controls
        preset_layout = QHBoxLayout()
        preset_label = QLabel("Preset:")
        self.preset_combo = QComboBox()
        self.update_preset_combo()
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        
        preset_save_btn = QPushButton("Save Preset")
        preset_save_btn.clicked.connect(self.save_current_preset)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addWidget(preset_save_btn)
        preset_layout.addStretch()
        
        # Add file size estimation label
        self.size_label = QLabel("Estimated size: -")
        
        # Add layouts to controls
        controls_layout.insertLayout(0, preset_layout)
        controls_layout.addWidget(self.size_label)
        
        # Set up keyboard shortcuts
        self._setup_shortcuts()
        
        # Show the window
        self.show()
        
    def _create_menu_bar(self):
        """Create the application menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        open_action = QAction("&Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        
        save_action = QAction("&Save GIF...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.setEnabled(False)
        save_action.triggered.connect(self.save_file)
        file_menu.addAction(save_action)
        self.save_action = save_action
        
        file_menu.addSeparator()
        
        # Recent files submenu
        self.recent_menu = QMenu("Recent Files", self)
        file_menu.addMenu(self.recent_menu)
        self.update_recent_files_menu()
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        theme_action = QAction("Toggle Theme", self)
        theme_action.setShortcut("Ctrl+T")
        theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_action)
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts"""
        shortcuts = [
            (QKeySequence.Open, self.open_file),
            (QKeySequence.Save, self.save_file),
            (Qt.Key_Space, self.toggle_preview),
            ("Ctrl+P", self.generate_preview),
            ("Ctrl+R", self.reset_settings),
        ]
        
        for key, slot in shortcuts:
            shortcut = QShortcut(key, self)
            shortcut.activated.connect(slot)
    
    def update_preset_combo(self):
        """Update the preset combo box"""
        self.preset_combo.clear()
        self.preset_combo.addItem("Custom")
        for preset in self.preset_manager.get_presets():
            self.preset_combo.addItem(preset["name"])
    
    def apply_preset(self, preset_name):
        """Apply the selected preset"""
        if preset_name == "Custom":
            return
            
        for preset in self.preset_manager.get_presets():
            if preset["name"] == preset_name:
                self.fps_spin.setValue(preset["fps"])
                self.quality_slider.setValue(preset["quality"])
                resolution_index = self.resolution_combo.findText(preset["resolution"])
                if resolution_index >= 0:
                    self.resolution_combo.setCurrentIndex(resolution_index)
                # Apply speed setting if available in the preset
                if "speed" in preset:
                    self.speed_slider.setValue(preset["speed"])
                break
    
    def save_current_preset(self):
        """Save current settings as a new preset"""
        name, ok = QInputDialog.getText(self, "Save Preset", "Enter preset name:")
        if ok and name:
            self.preset_manager.save_preset(
                name,
                self.fps_spin.value(),
                self.quality_slider.value(),
                self.resolution_combo.currentText(),
                self.speed_slider.value()  # Add speed value to the preset
            )
            self.update_preset_combo()
            self.preset_combo.setCurrentText(name)
    
    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.current_theme = "Dark" if self.current_theme == "Light" else "Light"
        self.apply_theme(self.current_theme)
        self.settings.setValue("theme", self.current_theme)
    
    def apply_theme(self, theme):
        """Apply the specified theme"""
        if theme == "Dark":
            self.setStyle(QStyleFactory.create("Fusion"))
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            self.setPalette(palette)
        else:
            self.setStyle(QStyleFactory.create("Fusion"))
            self.setPalette(self.style().standardPalette())
    
    def update_recent_files_menu(self):
        """Update the recent files menu"""
        self.recent_menu.clear()
        for file_path in self.recent_files:
            if os.path.exists(file_path):
                action = QAction(os.path.basename(file_path), self)
                action.setData(file_path)
                action.triggered.connect(lambda checked, path=file_path: self.open_recent_file(path))
                self.recent_menu.addAction(action)
    
    def add_recent_file(self, file_path):
        """Add a file to recent files list"""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)
        self.recent_files.insert(0, file_path)
        while len(self.recent_files) > self.max_recent_files:
            self.recent_files.pop()
        self.settings.setValue("recent_files", self.recent_files)
        self.update_recent_files_menu()
    
    def open_recent_file(self, file_path):
        """Open a file from the recent files menu"""
        if os.path.exists(file_path):
            self.load_video_file(file_path)
        else:
            QMessageBox.warning(self, "File Not Found", 
                              f"The file {file_path} no longer exists.")
            self.recent_files.remove(file_path)
            self.settings.setValue("recent_files", self.recent_files)
            self.update_recent_files_menu()
    
    def load_video_file(self, file_path):
        """Load a video file"""
        self.current_file = file_path
        try:
            self.status_bar.showMessage(f"Loading video: {os.path.basename(file_path)}")
            result = self.video_processor.load_video(file_path)
            
            if result:
                # Update UI with video properties
                self.fps_spin.setValue(int(self.video_processor.fps))
                self.save_button.setEnabled(True)
                self.save_action.setEnabled(True)
                self.preview_button.setEnabled(True)
                
                # Setup timeline
                self.timeline_widget.setup_timeline(
                    self.video_processor.duration,
                    self.video_processor.get_thumbnails()
                )
                
                # Show first frame
                first_frame = self.video_processor.get_frame(0)
                self.preview_widget.display_frame(first_frame)
                
                # Set dimensions
                width, height = self.video_processor.get_dimensions()
                self.width_spin.setValue(width)
                self.height_spin.setValue(height)
                
                # Update recent files
                self.add_recent_file(file_path)
                
                # Update status
                self.status_bar.showMessage(
                    f"Loaded: {os.path.basename(file_path)} - {width}x{height}, {self.video_processor.fps} fps"
                )
                
                # Update estimated file size
                self.update_size_estimate()
            else:
                QMessageBox.critical(self, "Error", 
                    "Failed to load video file. The file may be corrupted or in an unsupported format.")
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                f"An error occurred while loading the video: {str(e)}")
    
    def open_file(self):
        """Open a video file"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter(
            "Video files (*.mp4 *.avi *.mov *.mkv *.webm *.wmv *.gif *.flv)")
        
        if file_dialog.exec_():
            file_path = file_dialog.selectedFiles()[0]
            self.load_video_file(file_path)
    
    def update_size_estimate(self):
        """Update the estimated output file size"""
        if not self.current_file:
            self.size_label.setText("Estimated size: -")
            return
            
        try:
            # Get current settings
            fps = self.fps_spin.value()
            width = self.width_spin.value()
            height = self.height_spin.value()
            quality = self.quality_slider.value() / 100.0
            speed_factor = self.speed_slider.value() / 100.0  # Get speed factor
            start_time, end_time = self.timeline_widget.get_trim_values()
            duration = end_time - start_time
            
            # Estimate size based on resolution, duration, fps, and quality
            pixels_per_frame = width * height
            
            # Adjust number of frames based on speed factor
            # Higher speed = fewer frames
            frames = int(duration * fps / speed_factor)
            
            bytes_per_pixel = 3 * quality  # Rough estimate, 3 bytes per pixel at max quality
            
            estimated_size = (pixels_per_frame * frames * bytes_per_pixel) / (1024 * 1024)  # Convert to MB
            
            self.size_label.setText(f"Estimated size: {estimated_size:.1f} MB")
        except Exception as e:
            self.size_label.setText("Estimated size: -")
    
    def save_file(self):
        """Save the edited video as a GIF"""
        if not self.current_file:
            return
            
        # First check if we have preview frames to use
        if not hasattr(self.preview_widget, 'preview_frames') or not self.preview_widget.preview_frames:
            # No preview frames available, prompt the user to generate a preview first
            QMessageBox.information(self, "No Preview", 
                                   "Please generate a preview first so we can save exactly what you see.")
            return
            
        # Get save location
        file_dialog = QFileDialog(self)
        file_dialog.setAcceptMode(QFileDialog.AcceptSave)
        file_dialog.setNameFilter("GIF files (*.gif)")
        file_dialog.setDefaultSuffix("gif")
        
        if file_dialog.exec_():
            output_path = file_dialog.selectedFiles()[0]
            self.output_file = output_path
            
            try:
                # Use the current preview frames and FPS
                frames = self.preview_widget.preview_frames
                fps = self.fps_spin.value() * (self.speed_slider.value() / 100.0)  # Apply speed factor to FPS
                quality = self.quality_slider.value() / 100.0
                loop = self.loop_checkbox.isChecked()
                
                # Create progress dialog
                progress = QProgressDialog("Creating GIF...", "Cancel", 0, 100, self)
                progress.setWindowModality(Qt.WindowModal)
                progress.setWindowTitle("Saving GIF")
                progress.setMinimumDuration(0)
                progress.setValue(10)  # Start progress at 10%
                
                # Show status update
                self.status_bar.showMessage("Saving GIF from preview frames...")
                QApplication.processEvents()
                
                try:
                    # Save the GIF directly from the preview frames
                    import imageio
                    
                    # Use the loop parameter 
                    loop_param = 0 if loop else 1
                    
                    progress.setValue(50)  # Update progress
                    
                    # Save the GIF with the current settings
                    imageio.mimsave(output_path, frames, fps=fps, 
                                   quantizer=int(100-quality*100), 
                                   loop=loop_param)
                    
                    progress.setValue(100)  # Complete progress
                    progress.close()
                    
                    # Show success message
                    QMessageBox.information(self, "Success", 
                                          f"GIF saved successfully to:\n{output_path}\n\nExactly as shown in the preview.")
                    
                    self.status_bar.showMessage(f"GIF saved to: {output_path}")
                
                except Exception as e:
                    progress.close()
                    QMessageBox.critical(self, "Error", 
                                       f"Failed to save GIF: {str(e)}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", 
                                   f"An error occurred while saving the GIF: {str(e)}")
    
    def toggle_preview(self):
        """Toggle preview playback"""
        if hasattr(self.preview_widget, 'preview_timer'):
            if self.preview_widget.preview_timer.isActive():
                self.preview_widget.preview_timer.stop()
            else:
                self.generate_preview()
    
    def reset_settings(self):
        """Reset all settings to defaults"""
        if QMessageBox.question(self, "Reset Settings", 
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            
            self.fps_spin.setValue(15)
            self.quality_slider.setValue(90)
            self.resolution_combo.setCurrentText("Original")
            self.maintain_aspect.setChecked(True)
            self.enable_crop.setChecked(False)
            self.speed_slider.setValue(100)  # Reset speed to normal (1.0x)
            
            if self.current_file:
                width, height = self.video_processor.get_dimensions()
                self.width_spin.setValue(width)
                self.height_spin.setValue(height)
    
    def closeEvent(self, event):
        """Handle application close event"""
        # Save window geometry
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def on_trim_changed(self, start_time, end_time):
        """Handle timeline trim changes"""
        if hasattr(self, 'video_processor') and self.video_processor.is_loaded():
            # Update preview frame
            frame_pos = start_time
            frame = self.video_processor.get_frame_at_time(frame_pos)
            if frame is not None:
                self.preview_widget.display_frame(frame)
    
    def update_preview_params(self):
        """Update preview parameters when controls change"""
        if hasattr(self, 'preview_button'):
            self.preview_button.setEnabled(self.current_file is not None)
            # Update the file size estimate when parameters change
            self.update_size_estimate()
    
    def on_resolution_changed(self, index):
        """Handle resolution dropdown changes"""
        self.width_spin.setEnabled(index == 5)  # 5 is "Custom"
        self.height_spin.setEnabled(index == 5)  # 5 is "Custom"
        
        if index != 5 and self.video_processor.is_loaded():
            orig_width, orig_height = self.video_processor.get_dimensions()
            
            if index == 0:  # Original
                self.width_spin.setValue(orig_width)
                self.height_spin.setValue(orig_height)
            else:
                # Preset resolutions
                heights = [720, 480, 360, 240]
                if index <= len(heights):
                    target_height = heights[index - 1]
                    if self.maintain_aspect.isChecked():
                        aspect_ratio = orig_width / orig_height
                        target_width = int(target_height * aspect_ratio)
                        self.width_spin.setValue(target_width)
                    else:
                        self.width_spin.setValue(int(target_height * 16 / 9))
                    self.height_spin.setValue(target_height)
    
    def on_crop_enabled(self, state):
        """Handle crop checkbox toggle"""
        self.crop_button.setEnabled(state)
        if state and self.current_file:
            QMessageBox.information(self, "Crop Mode", "Click and drag in the preview area to select the crop region.")
            self.preview_widget.enable_crop_mode()
        else:
            self.preview_widget.disable_crop_mode()
    
    def on_set_crop(self):
        """Set crop region button clicked"""
        if self.current_file:
            self.preview_widget.enable_crop_mode()
            QMessageBox.information(self, "Crop Mode", "Click and drag in the preview area to select the crop region.")
    
    def generate_preview(self):
        """Generate a preview GIF with current settings"""
        if not self.current_file:
            return
            
        try:
            # Get current parameters
            fps = self.fps_spin.value()
            width = self.width_spin.value()
            height = self.height_spin.value()
            quality = self.quality_slider.value() / 100.0
            speed_factor = self.speed_slider.value() / 100.0  # Convert from percentage to decimal
            start_time, end_time = self.timeline_widget.get_trim_values()
            
            crop_rect = None
            if self.enable_crop.isChecked() and hasattr(self.preview_widget, 'crop_rect'):
                crop_rect = self.preview_widget.crop_rect
            
            # Generate and show preview
            self.status_bar.showMessage("Generating preview...")
            QApplication.processEvents()
            
            # Check if we have excluded segments to use
            if self.excluded_segments:
                # Get the effective segments (segments we want to keep)
                effective_segments = self.timeline_widget.get_effective_segments()
                
                if effective_segments:
                    # Generate preview using effective segments
                    preview_frames, adjusted_fps = self.video_processor.generate_preview(
                        start_time, end_time, fps, (width, height), quality, crop_rect,
                        segments=effective_segments,
                        speed_factor=speed_factor
                    )
                    
                    if preview_frames:
                        # Use the adjusted FPS that accounts for speed factor
                        self.preview_widget.play_preview(preview_frames, adjusted_fps)
                        self.status_bar.showMessage(f"Preview generated with trimmed segments (Speed: {speed_factor:.1f}x)")
                    else:
                        self.status_bar.showMessage("Failed to generate preview")
                else:
                    self.status_bar.showMessage("No valid segments remain after trimming")
            else:
                # Standard preview without excluded segments
                preview_frames, adjusted_fps = self.video_processor.generate_preview(
                    start_time, end_time, fps, (width, height), quality, crop_rect,
                    speed_factor=speed_factor
                )
                
                if preview_frames:
                    # Use the adjusted FPS that accounts for speed factor
                    self.preview_widget.play_preview(preview_frames, adjusted_fps)
                    self.status_bar.showMessage(f"Preview generated successfully (Speed: {speed_factor:.1f}x)")
                else:
                    self.status_bar.showMessage("Failed to generate preview")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while generating the preview: {str(e)}")

    def on_segments_changed(self, segments):
        """Handle changes to excluded segments"""
        self.excluded_segments = segments
        
        # Update duration calculation and file size estimate
        self.update_size_estimate()
        
        # If we have segments, show a message about the number of trimmed sections
        if segments:
            self.status_bar.showMessage(f"{len(segments)} segment(s) marked for removal")


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = MainWindow()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
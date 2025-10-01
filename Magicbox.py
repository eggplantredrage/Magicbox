import sys
import os
import requests
import webbrowser
import shutil
import random
import math

# --- Imports for sounddevice and numpy ---
import numpy as np
import sounddevice as sd
from scipy.fft import rfft 

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QListWidget, QFileDialog, QSlider, QHBoxLayout,
    QMenuBar, QAction, QMessageBox, QDialog, QRadioButton, QButtonGroup, 
    QLineEdit, QListWidgetItem, QSplitter, QGridLayout, QGroupBox, QComboBox,
    QInputDialog, QSizePolicy
)
from PyQt5.QtCore import Qt, QUrl, QTimer, QSize, QRect, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QPixmap, QImage, QColor, QPainter, QPalette
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaMetaData
from PyQt5.QtMultimediaWidgets import QVideoWidget

# --------------------------------------------------------------------------------------
# NEW/MODIFIED: Sound Monitoring Thread for Visualizer
# --------------------------------------------------------------------------------------

class SoundMonitor(QThread):
    """
    Monitors system audio output using sounddevice's loopback feature 
    (requires OS support like 'Stereo Mix' on Windows) 
    and emits data for FFT processing.
    """
    fft_data_signal = pyqtSignal(np.ndarray)
    
    def __init__(self, fs=44100, blocksize=1024, input_device_index=None):
        super().__init__()
        self.fs = fs
        self.blocksize = blocksize
        self.running = False
        # Allows manual selection of the input device index (for loopback)
        self.input_device_index = input_device_index

    def run(self):
        self.running = True
        try:
            with sd.InputStream(
                samplerate=self.fs,
                channels=2, # Stereo monitoring
                dtype='float32',
                blocksize=self.blocksize,
                device=self.input_device_index 
            ) as stream:
                print(f"Sound monitor started on device: {stream.device}")
                while self.running:
                    data, overflowed = stream.read(self.blocksize)
                    if overflowed:
                        print("Audio buffer overflowed!", file=sys.stderr)
                    
                    if data.size > 0:
                        self.process_fft(data)
        except Exception as e:
            # This is the point of failure if loopback is not available
            print(f"Error starting SoundMonitor (Loopback may not be supported or configured): {e}")
            self.running = False
            # Emit an empty array to indicate failure to the visualizer
            self.fft_data_signal.emit(np.zeros(32)) 

    def process_fft(self, data):
        """Perform simple FFT on the captured data."""
        mono_data = data[:, 0]
        windowed_data = mono_data * np.hanning(len(mono_data))
        spectrum = np.abs(rfft(windowed_data)) 
        self.fft_data_signal.emit(spectrum)

    def stop(self):
        self.running = False
        self.wait() 

# --------------------------------------------------------------------------------------
# NEW: Audio Device Selector Dialog
# --------------------------------------------------------------------------------------

class AudioDeviceSelectorDialog(QDialog):
    """Allows the user to manually select an input device for the SoundMonitor."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Visualizer Input Device")
        self.setMinimumWidth(400)
        self.selected_device_index = None

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Select the device that captures **system audio output** (e.g., 'Stereo Mix', 'Loopback', or 'What U Hear'):"))

        self.device_list = QListWidget()
        self.populate_devices()
        self.device_list.setMinimumHeight(150)
        self.device_list.itemDoubleClicked.connect(self.accept)
        layout.addWidget(self.device_list)
        
        button_box = QHBoxLayout()
        self.ok_button = QPushButton("Select Device")
        self.cancel_button = QPushButton("Cancel")
        
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        
        button_box.addStretch(1)
        button_box.addWidget(self.ok_button)
        button_box.addWidget(self.cancel_button)
        
        layout.addLayout(button_box)
        self.setLayout(layout)
        
    def populate_devices(self):
        self.device_list.clear()
        
        try:
            devices = sd.query_devices()
            # Only list devices that can act as an input (i.e., loopback potential)
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            
            for d in input_devices:
                # Display the device index, name, and host API
                item = QListWidgetItem(f"[{d['index']}] {d['name']} ({d['hostapi']})")
                item.setData(Qt.UserRole, d['index'])
                self.device_list.addItem(item)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not query audio devices: {e}\n\nPlease ensure your audio drivers are properly installed.")
            self.reject()

    def accept(self):
        selected_item = self.device_list.currentItem()
        if selected_item:
            self.selected_device_index = selected_item.data(Qt.UserRole)
            super().accept()
        else:
            QMessageBox.warning(self, "Selection Required", "Please select a device from the list.")

    def get_selected_device_index(self):
        return self.selected_device_index

# --------------------------------------------------------------------------------------
# Helper/Window Classes (EQWindow, VisualizerWindow, AboutDialog) 
# --------------------------------------------------------------------------------------

class EQWindow(QWidget):
    # This class remains a placeholder
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Equalizer (Placeholder)")
        self.setGeometry(200, 200, 350, 300)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Equalizer - Requires Custom Audio Engine (SoundDevice)"))
        self.sliders = []
        bands = ["Bass", "Low-Mid", "Mid", "High-Mid", "Treble"]
        for band in bands:
            band_layout = QHBoxLayout()
            label = QLabel(band)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(-10, 10)
            slider.setValue(0)
            slider.valueChanged.connect(lambda value, b=band: print(f"EQ: {b} set to {value} dB"))
            band_layout.addWidget(label)
            band_layout.addWidget(slider)
            layout.addLayout(band_layout)
            self.sliders.append(slider)
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self.reset_eq)
        layout.addWidget(reset_btn)
        self.setLayout(layout)

    def reset_eq(self):
        for slider in self.sliders:
            slider.setValue(0)

class SimulatedVisualizerWindow(QWidget):
    """Visualizer that uses simulated math/random data, safe for About dialog."""
    def __init__(self):
        super().__init__()
        self.n_bars = 32
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)
        self.bars = [0] * self.n_bars
        self.setMinimumSize(200, 50)

    def animate(self):
        self.phase += 0.15
        # Simulated audio data for visual effect
        for i in range(self.n_bars):
            # Sine wave + random for a more dynamic look
            base = 60 + 40 * math.sin(self.phase + i * 0.3)
            jitter = random.randint(-10, 10)
            self.bars[i] = max(10, min(120, int(base + jitter)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width() // self.n_bars
        for i, h in enumerate(self.bars):
            color = QColor.fromHsv(int(240 - (i * 240 / self.n_bars)), 255, 255)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRect(i * w + 2, self.height() - h, w - 4, h)
            
class VisualizerWindow(QWidget):
    """
    Data-driven Visualizer, connected to SoundMonitor for real audio data.
    Used when opened via the View menu.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visualizer")
        self.setGeometry(250, 250, 400, 200)
        self.n_bars = 32
        self.max_height = 120
        self.bars = np.zeros(self.n_bars)
        self.decay_factor = 0.8
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_bars)
        self.timer.start(50) 

    def update_data(self, spectrum):
        """Receives FFT data from the SoundMonitor thread."""
        if not spectrum.any():
            return

        num_spectrum_points = len(spectrum)
        bar_heights = np.zeros(self.n_bars)
        
        log_min = 2.0
        log_max = num_spectrum_points - 1
        
        indices = np.unique(np.logspace(np.log10(log_min), 
                                        np.log10(log_max), 
                                        self.n_bars + 1).astype(int))
        
        if len(indices) < self.n_bars + 1:
            return 

        for i in range(self.n_bars):
            start = indices[i]
            end = indices[i+1]
            
            if end > start:
                amplitude = np.mean(spectrum[start:end])
                # Convert amplitude to a dB-like scale for visualization
                height_db = 20 * np.log10(amplitude + 1e-9) + 80 
                
                # Apply smoothing/decay
                self.bars[i] = max(height_db, self.bars[i] * 0.9) 

    def update_bars(self):
        """Decays the bars and triggers a repaint."""
        for i in range(self.n_bars):
            self.bars[i] = max(0, self.bars[i] * self.decay_factor)
            
        self.update() 

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width() // self.n_bars
        for i, raw_h in enumerate(self.bars):
            # Clip height to widget size
            h = int(np.clip(raw_h * 2.5, 0, self.height() - 20)) 
            
            color = QColor.fromHsv(int(240 - (i * 240 / self.n_bars)), 255, 255)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRect(i * w + 2, self.height() - h, w - 4, h)


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Magic Box")
        self.setFixedSize(420, 350)
        layout = QVBoxLayout()
        # --- Using the SIMULATED VISUALIZER for reliability ---
        self.visualizer = SimulatedVisualizerWindow() 
        self.visualizer.setFixedHeight(140)
        layout.addWidget(self.visualizer)
        about_text = QLabel(
            "<b>Magic Box Media Player</b><br>"
            "In Memory of Bruno, our beloved music teacher.<br>"
            "Thank you for inspiring us to keep the music alive.<br><br>"
            "2025 XIX Technology<br>"
            "By Eggplant48 (Kevin Leblanc)"
            "<br><br>This Software is licensed under the MIT License."
            "<br><br>Enjoy The Music! 🎵"
        )
        about_text.setWordWrap(True)
        about_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(about_text)
        self.setLayout(layout)

# --------------------------------------------------------------------------------------
# CORE PLAYER CLASS
# --------------------------------------------------------------------------------------

class MagicBoxPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Magic Box 🎶")
        self.setGeometry(100, 100, 750, 550)  
        
        self._original_geometry = self.geometry()
        self._is_mini_player = False

        self.playlist = []
        self.current_index = -1 
        self.playing = False

        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.stateChanged.connect(self.on_state_changed)
        self.media_player.error.connect(self.media_error)
        self.media_player.metaDataAvailableChanged.connect(self.fetch_song_info)
        
        # --- Sound Monitor Initialization (Attempt auto-start) ---
        self.sound_monitor = SoundMonitor()
        self.sound_monitor.start() 
        
        # --- Main Layout (Vertical Stack) ---
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(5, 5, 5, 5)

        # 1. Menu Bar
        self.menu_bar = QMenuBar(self)
        self.setup_menu_bar(self.menu_bar)
        self.main_layout.setMenuBar(self.menu_bar)

        # 2. Top Controls
        top_controls_layout = QHBoxLayout()
        top_controls_layout.setContentsMargins(0, 0, 0, 0)
        top_controls_layout.setSpacing(2)

        self.prev_button = QPushButton("⏮️")
        self.play_button = QPushButton("▶️")
        self.stop_button = QPushButton("⏹️")
        self.next_button = QPushButton("⏭️")
        self.mute_button = QPushButton("🔇")
        
        button_size = QSize(28, 28)
        for btn in [self.prev_button, self.play_button, self.stop_button, self.next_button, self.mute_button]:
            btn.setFixedSize(button_size)
            btn.setFont(QFont("Arial", 8))
            top_controls_layout.addWidget(btn)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setMaximumWidth(120)
        top_controls_layout.addWidget(self.volume_slider)
        
        self.full_ui_button = QPushButton("Full UI")
        self.full_ui_button.setFixedSize(QSize(60, 28))
        self.full_ui_button.setFont(QFont("Arial", 8))
        self.full_ui_button.hide()
        self.full_ui_button.clicked.connect(lambda: self.toggle_mini_player(False)) 
        top_controls_layout.addWidget(self.full_ui_button)

        top_controls_layout.addStretch(1) 
        self.main_layout.addLayout(top_controls_layout)
        
        # 3. Location/Seek Area
        self.location_seek_layout = QHBoxLayout()
        self.location_seek_layout.setContentsMargins(0, 0, 0, 0)
        
        self.location_label = QLabel("Location:")
        self.location_seek_layout.addWidget(self.location_label)
        self.location_bar = QLineEdit()
        self.location_bar.setPlaceholderText("Current media location...")
        self.location_bar.setReadOnly(True) 
        self.location_seek_layout.addWidget(self.location_bar)
        
        self.main_layout.addLayout(self.location_seek_layout)
        
        self.playback_slider = QSlider(Qt.Horizontal)
        self.playback_slider.setRange(0, 1000)
        self.main_layout.addWidget(self.playback_slider)

        # 4. Main Content Area (Horizontal Split: Playlist | Video)
        self.content_splitter = QSplitter(Qt.Horizontal)
        
        # --- Left Side: Channels/Playlist ---
        self.playlist_panel = QWidget()
        playlist_layout = QVBoxLayout(self.playlist_panel)
        playlist_layout.setContentsMargins(0, 0, 0, 0)
        
        channel_label = QLabel("My Media & Channels (IPTV Ready)")
        channel_label.setStyleSheet("background-color: #3333AA; color: white; padding: 4px; border-bottom: 1px solid #000;")
        playlist_layout.addWidget(channel_label)
        
        self.song_list = QListWidget()
        self.song_list.setSelectionMode(QListWidget.SingleSelection)
        playlist_layout.addWidget(self.song_list)
        
        utility_layout = QHBoxLayout()
        load_button = QPushButton("➕ Add Media")
        load_button.clicked.connect(self.load_songs)
        scan_folder_btn = QPushButton("📁 Scan Folder")
        scan_folder_btn.clicked.connect(self.scan_folder)
        utility_layout.addWidget(load_button)
        utility_layout.addWidget(scan_folder_btn)
        playlist_layout.addLayout(utility_layout)
        
        self.content_splitter.addWidget(self.playlist_panel)

        # --- Right Side: Video/Player ---
        self.video_panel = QWidget()
        video_layout = QVBoxLayout(self.video_panel)
        video_layout.setContentsMargins(0, 0, 0, 0)
        
        # --- NEW: Placeholder Widget (QLabel) ---
        self.placeholder_label = QLabel()
        # Look for 'placeholder.png' in the same directory as the script
        placeholder_path = os.path.join(os.path.dirname(__file__), 'placeholder.png')
        
        if os.path.exists(placeholder_path):
            pixmap = QPixmap(placeholder_path)
            self.placeholder_label.setPixmap(pixmap)
            self.placeholder_label.setStyleSheet("background-color: black;")
        else:
            self.placeholder_label.setText("MAGIC BOX 🎶\n(No Media Loaded - Add 'placeholder.png' to the script directory)")
            self.placeholder_label.setStyleSheet("background-color: #333; color: #fff; border: 2px solid #555;")
            
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setScaledContents(True) 
        self.placeholder_label.setMinimumSize(320, 240)
        self.placeholder_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        video_layout.addWidget(self.placeholder_label) # Add the placeholder FIRST
        # --- END NEW ---

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(320, 240) 
        self.media_player.setVideoOutput(self.video_widget)
        video_layout.addWidget(self.video_widget) # Add the video widget SECOND
        
        video_status_bar = QHBoxLayout()
        video_status_bar.setContentsMargins(4, 4, 4, 4)
        video_status_bar.addStretch(1)
        video_layout.addLayout(video_status_bar)
        
        self.content_splitter.addWidget(self.video_panel)
        
        self.content_splitter.setSizes([200, 550]) 
        self.main_layout.addWidget(self.content_splitter, 1) 

        # 5. Bottom Info Panel
        self.info_panel = QWidget()
        self.info_panel.setStyleSheet("background-color: black; color: white; padding: 2px;")
        info_layout = QHBoxLayout(self.info_panel)
        info_layout.setContentsMargins(4, 2, 4, 2)
        info_layout.setSpacing(10)
        
        self.info_clip = QLabel("Clip: (---)")
        self.info_author = QLabel("Author: (---)")
        self.info_show = QLabel("Show: (---)")
        self.info_copyright = QLabel("Copyright: (---)")
        
        info_layout.addWidget(self.info_clip)
        info_layout.addWidget(self.info_author)
        info_layout.addWidget(self.info_show)
        info_layout.addWidget(self.info_copyright)
        info_layout.addStretch(1)
        
        fetch_info_btn = QPushButton("Fetch Info")
        fetch_info_btn.clicked.connect(self.fetch_song_info)
        fetch_info_btn.setStyleSheet("background-color: #555; color: white; border: 1px solid #777;")
        
        info_btn = QPushButton("Song Info")
        info_btn.clicked.connect(self.show_song_info)
        info_btn.setStyleSheet("background-color: #555; color: white; border: 1px solid #777;")

        info_layout.addWidget(fetch_info_btn)
        info_layout.addWidget(info_btn)

        self.main_layout.addWidget(self.info_panel)
        
        # --- Final setup ---
        self.setLayout(self.main_layout)
        self.connect_signals()

        # Timer for updating playback slider
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_position)
        self.timer.start()

        self.eq_window = None
        self.visualizer_window = None
        
        QApplication.instance().aboutToQuit.connect(self.sound_monitor.stop)
        
        # Check if SoundMonitor failed and prompt user for manual selection
        QTimer.singleShot(1000, self.check_visualizer_status)

        # --- NEW: Set initial visibility state ---
        self.update_video_view_visibility(is_playing=False)


    # --------------------------------------------------------------------------------------
    # Visualizer Status Check and Device Selector
    # --------------------------------------------------------------------------------------

    def check_visualizer_status(self):
        """Checks if the SoundMonitor failed and prompts for manual device selection."""
        # Use a small delay to allow the SoundMonitor thread to attempt starting and fail
        if not self.sound_monitor.running and not self.sound_monitor.isFinished():
            QMessageBox.warning(self, "Visualizer Setup Failed", 
                "The system audio monitor (Visualizer) failed to start automatically.\n\n"
                "This usually means the required 'Stereo Mix' or 'Loopback' device is disabled or unavailable.\n\n"
                "Would you like to manually select an audio input device for the Visualizer?"
            )
            # Give the user an option to fix it immediately
            if QMessageBox.Yes == QMessageBox.question(self, "Manual Setup", 
                                                        "Select a loopback/stereo mix device now?", 
                                                        QMessageBox.Yes | QMessageBox.No):
                self.show_audio_device_selector()


    def show_audio_device_selector(self):
        """Opens the dialog for manual audio input device selection."""
        selector = AudioDeviceSelectorDialog(self)
        
        if selector.exec_() == QDialog.Accepted:
            selected_index = selector.get_selected_device_index()
            if selected_index is not None:
                # 1. Stop the currently running/failed thread
                self.sound_monitor.stop()

                # 2. Create a new SoundMonitor with the selected index
                self.sound_monitor = SoundMonitor(input_device_index=selected_index)
                self.sound_monitor.start()
                
                # 3. Reconnect the visualizer if it's already open
                if self.visualizer_window and self.visualizer_window.isVisible():
                    # Attempt to disconnect the old signal, but it's hard without knowing prior state.
                    pass # Keep the connection logic minimal here for stability
                        
                    self.sound_monitor.fft_data_signal.connect(self.visualizer_window.update_data)
                    
                
                if not self.sound_monitor.running:
                    QMessageBox.critical(self, "Monitor Failed", 
                                         f"Failed to start the monitor with device index {selected_index}. Check permissions or select a different device.")
                else:
                     QMessageBox.information(self, "Monitor Fixed", 
                                         f"Visualizer monitor successfully started on device index {selected_index}.")

    # --------------------------------------------------------------------------------------
    # Connect Signals 
    # --------------------------------------------------------------------------------------
    def connect_signals(self):
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.stop_button.clicked.connect(self.stop_song)
        self.next_button.clicked.connect(self.next_song)
        self.prev_button.clicked.connect(self.prev_song)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.song_list.itemDoubleClicked.connect(self.play_selected_song)
        self.playback_slider.sliderMoved.connect(self.set_position)
        self.volume_slider.valueChanged.connect(self.media_player.setVolume)
    
    # --------------------------------------------------------------------------------------
    # Show Window Functions (Revised for Visualizer connection)
    # --------------------------------------------------------------------------------------

    def show_eq(self):
        if self.eq_window is None:
            self.eq_window = EQWindow()
        self.eq_window.show()

    def show_visualizer(self):
        """Opens the Visualizer window and connects the sound monitor."""
        if self.visualizer_window is None:
            self.visualizer_window = VisualizerWindow()
            # Connect the thread's signal to the window's data update slot
            self.sound_monitor.fft_data_signal.connect(self.visualizer_window.update_data)
        self.visualizer_window.show()
        
        if not self.sound_monitor.running:
            QMessageBox.information(self, "Visualizer Warning", 
                                    "The Visualizer is open but the audio monitor is not running. Please use the 'View -> Visualizer Manual Setup' menu to choose a loopback device.")

    # --------------------------------------------------------------------------------------
    # NEW: Video View Management
    # --------------------------------------------------------------------------------------
    def update_video_view_visibility(self, is_playing):
        """Switches between the placeholder and the QVideoWidget."""
        if is_playing:
            self.placeholder_label.hide()
            self.video_widget.show()
        else:
            # Check if the player is truly stopped or has no media before showing the placeholder
            if self.media_player.mediaStatus() == QMediaPlayer.NoMedia or self.media_player.state() == QMediaPlayer.StoppedState:
                self.video_widget.hide()
                self.placeholder_label.show()
            else:
                # Keep video widget visible if it's paused or loading
                self.placeholder_label.hide()
                self.video_widget.show()


    # --------------------------------------------------------------------------------------
    # Remaining Functions 
    # --------------------------------------------------------------------------------------

    def setup_menu_bar(self, menu_bar):
        file_menu = menu_bar.addMenu("File")
        open_action = QAction("Open Media...", self)
        open_action.triggered.connect(self.load_songs)
        stream_action = QAction("Open Stream/IPTV URL...", self)
        stream_action.triggered.connect(self.show_stream_dialog)
        scan_action = QAction("Scan Folder...", self)
        scan_action.triggered.connect(self.scan_folder)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(open_action)
        file_menu.addAction(stream_action)
        file_menu.addAction(scan_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)
        
        view_menu = menu_bar.addMenu("View")
        eq_action = QAction("Equalizer", self)
        eq_action.triggered.connect(self.show_eq)
        vis_action = QAction("Visualizer", self)
        vis_action.triggered.connect(self.show_visualizer)
        
        vis_setup_action = QAction("Visualizer Manual Setup", self)
        vis_setup_action.triggered.connect(self.show_audio_device_selector)
        
        self.mini_player_action = QAction("Mini Player Mode", self)
        self.mini_player_action.setCheckable(True)
        self.mini_player_action.triggered.connect(self.toggle_mini_player)
        
        view_menu.addAction(eq_action)
        view_menu.addAction(vis_action)
        view_menu.addAction(vis_setup_action) # New item for manual fix
        view_menu.addSeparator()
        view_menu.addAction(self.mini_player_action)

        play_menu = menu_bar.addMenu("Play")
        play_menu.addAction("Play/Pause").triggered.connect(self.toggle_play_pause)
        play_menu.addAction("Stop").triggered.connect(self.stop_song)
        play_menu.addAction("Next").triggered.connect(self.next_song)
        play_menu.addAction("Previous").triggered.connect(self.prev_song)
        
        stream_menu = menu_bar.addAction("Stream/IPTV")
        stream_menu.triggered.connect(self.show_stream_dialog)
        
        tools_menu = menu_bar.addMenu("Tools")
        info_action = QAction("Song Info...", self)
        info_action.triggered.connect(self.show_song_info)
        youtube_action = QAction("Find on YouTube", self)
        youtube_action.triggered.connect(self.find_on_youtube)
        copy_action = QAction("Copy to Device/Folder...", self)
        copy_action.triggered.connect(self.copy_to_device)
        tools_menu.addAction(info_action)
        tools_menu.addAction(youtube_action)
        tools_menu.addAction(copy_action)
        
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About MagicBox", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def toggle_mini_player(self, checked):
        self._is_mini_player = checked
        self.mini_player_action.setChecked(checked)

        if checked:
            self._original_geometry = self.geometry()
            self.setFixedSize(QSize(360, 320)) 
            
            # The video panel widgets are managed by visibility, not size limits in this mode
            # We keep the video panel layout intact but hide major UI elements.
            
            self.content_splitter.setSizes([0, 1]) 
            self.playlist_panel.hide()
            
            self.menu_bar.hide()
            self.location_label.hide() 
            self.info_panel.hide()
            
            self.full_ui_button.show()
            
        else:
            self.setFixedSize(QSize(16777215, 16777215)) 
            self.setGeometry(self._original_geometry)
            self.playlist_panel.show()
            self.content_splitter.setSizes([200, 550]) 
            
            self.menu_bar.show()
            self.location_label.show()
            self.info_panel.show()
            
            self.full_ui_button.hide()
            
            # Reset scaling/sizing related to the video area
            self.video_widget.setMinimumSize(320, 240)
            self.video_widget.setMaximumSize(16777215, 16777215) 
            self.video_panel.setMaximumSize(16777215, 16777215)
            self.video_panel.setMinimumSize(0, 0)
            
    def media_error(self, error):
        error_name = self.media_player.errorString()
        QMessageBox.critical(self, "Media Error", f"Failed to play media: {error_name}\n\nCheck URL or file path.")
        self.stop_song()

    def update_location_bar(self):
        if self.current_index != -1 and self.playlist:
            song_path = self.playlist[self.current_index]
            
            if song_path.startswith('http'):
                item = self.song_list.item(self.current_index)
                is_playlist_entry = item and item.data(Qt.UserRole) == 'stream_channel'
                
                if is_playlist_entry:
                    stream_name = item.text()
                    self.location_bar.setText(f"CHANNEL: {stream_name}")
                else:
                    self.location_bar.setText(f"STREAM: {song_path}")
            else:
                self.location_bar.setText(os.path.basename(song_path))
        else:
            self.location_bar.setText("")

    def _add_to_playlist(self, url, name=None, is_channel=False):
        if url not in self.playlist:
            self.playlist.append(url)
            item = QListWidgetItem(name if name else url)
            
            if is_channel:
                item.setData(Qt.UserRole, 'stream_channel') 
            
            self.song_list.addItem(item)
            return len(self.playlist) - 1
        return self.playlist.index(url)

    def _parse_and_load_m3u(self, m3u_url, playlist_name):
        try:
            response = requests.get(m3u_url, timeout=10)
            response.raise_for_status()
            content = response.text
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Network Error", f"Failed to download M3U/M3U8 playlist:\n{e}")
            return -1 

        lines = content.splitlines()
        
        if not content.startswith('#EXTM3U'):
            QMessageBox.warning(self, "Parse Warning", f"File does not look like a standard M3U/M3U8 playlist: {playlist_name}. Trying to play the URL directly.")
            idx = self._add_to_playlist(m3u_url, playlist_name, is_channel=True)
            self.current_index = idx
            self.song_list.setCurrentRow(self.current_index)
            
            self.update_video_view_visibility(is_playing=True) # NEW: Update visibility
            self.media_player.setMedia(QMediaContent(QUrl(m3u_url)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.update_location_bar()
            self.fetch_song_info()
            return idx 

        is_hls_stream = any(line.startswith('#EXT-X-TARGETDURATION') or line.startswith('#EXT-X-MEDIA-SEQUENCE') for line in lines)
        is_multi_channel = any('#EXTINF' in line and (',' in line and len(line.split(',')[-1].strip()) > 0) for line in lines)

        if is_hls_stream and not is_multi_channel:
            idx = self._add_to_playlist(m3u_url, playlist_name, is_channel=True)
            self.current_index = idx
            self.song_list.setCurrentRow(self.current_index)
            
            self.media_player.stop() 
            self.update_video_view_visibility(is_playing=True) # NEW: Update visibility
            self.media_player.setMedia(QMediaContent(QUrl(m3u_url)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.update_location_bar()
            self.fetch_song_info()
            return idx 
        
        channels_added = 0
        last_info = None
        first_index = -1
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('#EXTM3U'):
                continue
            
            if line.startswith('#EXTINF'):
                if ',' in line:
                    last_info = line.split(',')[-1].strip()
                else:
                    last_info = 'Unknown Channel'
                
            elif line.startswith('http') or line.startswith('rtsp') or line.startswith('udp') or line.lower().endswith(('.ts', '.mp4', '.m3u8')):
                stream_url = line
                channel_name = last_info if last_info else f"{playlist_name} Channel {channels_added + 1}"
                
                if not stream_url.startswith('http') and not stream_url.startswith('rtsp') and not stream_url.startswith('udp'):
                    stream_url = requests.compat.urljoin(m3u_url, stream_url)
                
                idx = self._add_to_playlist(stream_url, channel_name, is_channel=True)
                if first_index == -1:
                    first_index = idx 
                    
                channels_added += 1
                last_info = None

        if channels_added > 0:
            QMessageBox.information(self, "Playlist Loaded", f"Successfully loaded {channels_added} channels from {playlist_name}.")
            self.current_index = first_index
            self.song_list.setCurrentRow(self.current_index)
            self.play_selected_song()
            return first_index
        else:
            QMessageBox.warning(self, "Playlist Warning", f"Could not find any *parsable* channels in {playlist_name}. Attempting to play the playlist URL directly.")
            idx = self._add_to_playlist(m3u_url, playlist_name, is_channel=True)
            self.current_index = idx
            self.song_list.setCurrentRow(self.current_index)
            self.update_video_view_visibility(is_playing=True) # NEW: Update visibility
            self.media_player.setMedia(QMediaContent(QUrl(m3u_url)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.update_location_bar()
            self.fetch_song_info()
            return idx
        
    def play_media_url(self, url, name=None):
        if url.lower().endswith(('.m3u', '.m3u8')):
            self._parse_and_load_m3u(url, name if name else os.path.basename(url))
            return 
        
        index = self._add_to_playlist(url, name, is_channel=True)
        self.current_index = index
        self.song_list.setCurrentRow(self.current_index)

        self.media_player.stop() 
        self.update_video_view_visibility(is_playing=True) # NEW: Update visibility
        media_content = QMediaContent(QUrl(url))
        self.media_player.setMedia(media_content)
        self.media_player.play()
        self.play_button.setText("⏸️")
        self.playing = True
        self.update_location_bar()
        self.fetch_song_info()

    def play_selected_song(self, item=None):
        if item:
            self.current_index = self.song_list.row(item)
            
        if self.current_index < 0 or self.current_index >= len(self.playlist):
            return

        media_source = self.playlist[self.current_index]
        
        self.media_player.stop() 
        self.update_video_view_visibility(is_playing=True) # NEW: Update visibility

        if media_source.startswith('http'):
            if media_source.lower().endswith(('.m3u', '.m3u8')):
                is_channel_link = self.song_list.item(self.current_index).data(Qt.UserRole) == 'stream_channel'
                
                if not is_channel_link:
                    self._parse_and_load_m3u(media_source, item.text() if item else os.path.basename(media_source))
                    return 
                
            self.media_player.setMedia(QMediaContent(QUrl(media_source)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.song_list.setCurrentRow(self.current_index)
            self.update_location_bar()
            self.fetch_song_info()
        else:
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(media_source)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.song_list.setCurrentRow(self.current_index)
            self.update_location_bar()
            self.fetch_song_info()
            
    def load_songs(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Open Media Files", "",
            "Media Files (*.wav *.mp3 *.ogg *.flac *.aac *.m4a *.wma *.mp4 *.avi *.mkv *.m3u *.m3u8)"
        )
        if files:
            for file in files:
                if file.lower().endswith(('.m3u', '.m3u8')):
                    QMessageBox.information(self, "Feature Note", "Local M3U/M3U8 files are only added as a single entry for now. Please use the 'Stream/IPTV' menu item for public IPTV URLs.")
                    if file not in self.playlist:
                         self._add_to_playlist(file, os.path.basename(file), is_channel=False)
                elif file not in self.playlist:
                    self._add_to_playlist(file, os.path.basename(file), is_channel=False)
            
            if self.media_player.state() == QMediaPlayer.StoppedState and not self.playing and self.playlist:
                self.current_index = len(self.playlist) - 1
                self.song_list.setCurrentRow(self.current_index)
                self.update_location_bar()
    
    def scan_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Media Folder")
        if folder_path:
            media_extensions = ('.wav', '.mp3', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.mp4', '.avi', '.mkv')
            files_added = 0
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith(media_extensions):
                        full_path = os.path.join(root, file)
                        if full_path not in self.playlist:
                            self._add_to_playlist(full_path, file, is_channel=False)
                            files_added += 1
            
            QMessageBox.information(self, "Folder Scan Complete", f"Found and added {files_added} media files to the playlist.")
            if self.media_player.state() == QMediaPlayer.StoppedState and not self.playing and self.playlist:
                self.current_index = 0
                self.song_list.setCurrentRow(self.current_index)
                self.update_location_bar()

    def show_stream_dialog(self):
        url, ok = QInputDialog.getText(self, "Open Stream/IPTV URL", "Enter Stream/M3U/M3U8 URL:")
        if ok and url:
            name, ok_name = QInputDialog.getText(self, "Stream Name (Optional)", "Enter a name for the stream/playlist (optional):", text=os.path.basename(url))
            self.play_media_url(url, name if ok_name and name else None)

    def on_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.play_button.setText("⏸️")
            self.playing = True
            # NEW: Update visibility to show the video
            self.update_video_view_visibility(is_playing=True)
        elif state == QMediaPlayer.StoppedState:
            self.play_button.setText("▶️")
            self.playing = False
            # NEW: Update visibility to show the placeholder
            self.update_video_view_visibility(is_playing=False)
        
    def toggle_play_pause(self):
        current_state = self.media_player.state()
        
        if current_state == QMediaPlayer.PlayingState:
            self.media_player.pause()
        
        elif current_state == QMediaPlayer.StoppedState or current_state == QMediaPlayer.NoMedia:
            if self.playlist:
                if self.current_index == -1:
                    # If stopped and no index is set, assume the user wants to play the first song
                    self.current_index = 0
                
                # If no media is loaded, force the selection and play routine
                if self.media_player.mediaStatus() == QMediaPlayer.NoMedia:
                    self.play_selected_song()
                else:
                    self.media_player.play()
            else:
                QMessageBox.warning(self, "Cannot Play", "Please add media to the playlist first.")
        
        elif current_state == QMediaPlayer.PausedState:
            self.media_player.play()

    def stop_song(self):
        self.media_player.stop()
        self.playback_slider.setValue(0)
        self.info_clip.setText("Clip: (---)")
        self.info_author.setText("Author: (---)")
        self.info_show.setText("Show/Album: (---)")
        self.info_copyright.setText("Copyright: (---)")
        # NEW: Show placeholder after stopping
        self.update_video_view_visibility(is_playing=False)

    def next_song(self):
        if not self.playlist: return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.play_selected_song()

    def prev_song(self):
        if not self.playlist: return
        self.current_index = (self.current_index - 1 + len(self.playlist)) % len(self.playlist)
        self.play_selected_song()

    def toggle_mute(self):
        is_muted = self.media_player.isMuted()
        self.media_player.setMuted(not is_muted)
        self.mute_button.setText("🔊" if is_muted else "🔇")

    def update_position(self):
        if self.media_player.isSeekable() and self.media_player.state() != QMediaPlayer.StoppedState:
            self.playback_slider.setValue(self.media_player.position() * 1000 // self.media_player.duration())

    def set_position(self, position):
        if self.media_player.isSeekable():
            self.media_player.setPosition(position * self.media_player.duration() // 1000)

    # --- FIX APPLIED HERE: Using QMediaMetaData.ContributingArtist ---
    def fetch_song_info(self):
        title = self.media_player.metaData(QMediaMetaData.Title) or '---'
        # The common, stable key for Artist on various backends is ContributingArtist
        artist = self.media_player.metaData(QMediaMetaData.ContributingArtist) or '---' 
        album = self.media_player.metaData(QMediaMetaData.AlbumTitle) or '---'
        copyright_info = self.media_player.metaData(QMediaMetaData.Copyright) or '---'

        self.info_clip.setText(f"Clip: ({title})")
        self.info_author.setText(f"Author: ({artist})")
        self.info_show.setText(f"Show/Album: ({album})")
        self.info_copyright.setText(f"Copyright: ({copyright_info})")

    def show_song_info(self):
        info_text = ""
        for key in self.media_player.availableMetaData():
            value = self.media_player.metaData(key)
            if value:
                info_text += f"<b>{key}:</b> {value}<br>"
                
        if not info_text:
            info_text = "No detailed metadata available for the current media."
            
        QMessageBox.information(self, "Media Information", info_text)

    # --- FIX APPLIED HERE: Using QMediaMetaData.ContributingArtist ---
    def find_on_youtube(self):
        title = self.media_player.metaData(QMediaMetaData.Title)
        # Use the corrected artist key
        artist = self.media_player.metaData(QMediaMetaData.ContributingArtist)
        
        if title:
            search_query = f"{title} {artist or ''}"
            webbrowser.open(f"https://www.youtube.com/results?search_query={search_query}")
        else:
            QMessageBox.warning(self, "Search Error", "No title metadata available to search.")

    def copy_to_device(self):
        if self.current_index == -1 or not self.playlist:
            QMessageBox.warning(self, "Copy Error", "No media is currently loaded or selected.")
            return

        source_path = self.playlist[self.current_index]
        
        if source_path.startswith('http'):
            QMessageBox.warning(self, "Copy Error", "Cannot copy media from a live stream URL.")
            return
            
        destination_folder = QFileDialog.getExistingDirectory(self, "Select Destination Folder/Device")
        
        if destination_folder:
            try:
                shutil.copy(source_path, destination_folder)
                QMessageBox.information(self, "Copy Complete", f"Successfully copied '{os.path.basename(source_path)}' to:\n{destination_folder}")
            except Exception as e:
                QMessageBox.critical(self, "Copy Failed", f"An error occurred during copying:\n{e}")

    def show_about(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec_()

    def closeEvent(self, event):
        self.sound_monitor.stop()
        if self.eq_window: self.eq_window.close()
        if self.visualizer_window: self.visualizer_window.close()
        super().closeEvent(event)

# --------------------------------------------------------------------------------------
# EXECUTION BLOCK
# --------------------------------------------------------------------------------------

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError:
        QMessageBox.critical(None, "Dependency Error", 
                             "Required libraries 'numpy' and 'python-sounddevice' are missing.\n"
                             "Please install them: pip install numpy python-sounddevice scipy")
        sys.exit(1)
        
    try:
        # Check if any audio devices are available at all
        sd.query_devices() 
    except Exception:
        print("No audio device found or host API setup failed. Visualizer will not work.")

    player = MagicBoxPlayer()
    player.show()
    sys.exit(app.exec_())

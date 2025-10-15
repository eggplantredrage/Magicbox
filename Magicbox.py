import sys
import os
import requests
import webbrowser
import shutil
import math
import warnings
import urllib3
import json 

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QListWidget, QFileDialog, QSlider, QHBoxLayout,
    QMenuBar, QAction, QMessageBox, QDialog, 
    QLineEdit, QListWidgetItem, QSplitter, QInputDialog, QSizePolicy,
    QCheckBox # ADDED: For sync selection list
)
from PyQt5.QtCore import Qt, QUrl, QTimer, QSize
from PyQt5.QtGui import QIcon, QFont, QPixmap, QPainter, QBrush
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaMetaData
from PyQt5.QtMultimediaWidgets import QVideoWidget

# --------------------------------------------------------------------------------------
# GLOBAL SETUP: Suppress warnings and set resource path
# --------------------------------------------------------------------------------------

# Suppress the InsecureRequestWarning caused by using verify=False 
# for M3U/M3U8 playlist downloads from certain public test servers.
warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)

def resource_path(relative_path):
    """
    Get the absolute path to a resource, works for dev and for PyInstaller.
    """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --------------------------------------------------------------------------------------
# Custom Widget: Fake Visualizer (ANIMATED)
# --------------------------------------------------------------------------------------

class FakeVisualizerWidget(QWidget):
    """A custom widget that draws an animated pattern resembling a visualizer."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(350, 100)
        self.setStyleSheet("border: 2px solid #777; background-color: #000;")
        
        self.phase = 0.0
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update_visuals)
        self.animation_timer.start(50) 

    def update_visuals(self):
        """Update the animation phase and trigger a repaint."""
        self.phase += 0.1 
        if self.phase > 2 * math.pi:
            self.phase -= 2 * math.pi
        
        self.repaint()

    def paintEvent(self, event):
        """Draws animated colored bars based on the current phase."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        bar_count = 15
        spacing = 5
        bar_width = (w - (bar_count + 1) * spacing) / bar_count 
        
        colors = [Qt.red, Qt.yellow, Qt.green, Qt.cyan, Qt.blue, Qt.magenta, Qt.white]
        
        for i in range(bar_count):
            bar_height_ratio = abs(math.sin(i * 0.4 + self.phase) * 0.4) + 0.3 
            bar_height = h * bar_height_ratio
            
            x = spacing + i * (bar_width + spacing)
            y = h - bar_height
            
            color = colors[i % len(colors)]
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(color))
            
            painter.drawRect(int(x), int(y), int(bar_width), int(bar_height))
            
        painter.end()

# --------------------------------------------------------------------------------------
# Helper/Window Class (AboutDialog) 
# --------------------------------------------------------------------------------------

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About MagicBoxPlayer")
        self.setFixedSize(400, 450)
        
        main_layout = QVBoxLayout(self)
        
        visualizer_widget = FakeVisualizerWidget()
        main_layout.addWidget(visualizer_widget, alignment=Qt.AlignCenter)
        
        about_text = QLabel(
            "<b>MagicBoxPlayer</b><br>" 
            "In Memory of Bruno, our beloved music teacher.<br>"
            "Thank you for inspiring us to keep the music alive.<br><br>"
            "2025 <span style='color:#FFD700;'>Caution Interactive</span><br>"
            "By Eggplant48 (Kevin Leblanc)"
            "<br><br>This Software is licensed under the MIT License."
            "<br><br>Enjoy The Music! 🎵"
        )
        about_text.setWordWrap(True)
        about_text.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(about_text)
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        main_layout.addWidget(close_button)
        
        self.setLayout(main_layout)

# --------------------------------------------------------------------------------------
# NEW: Sync Selection Dialog
# --------------------------------------------------------------------------------------

class SyncSelectionDialog(QDialog):
    def __init__(self, playlist_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Songs and Device for Sync")
        self.setGeometry(100, 100, 600, 500)
        
        self.playlist_data = playlist_data
        self.selected_files = []
        self.destination_folder = None

        main_layout = QVBoxLayout(self)

        # 1. Selection List
        list_label = QLabel("Select songs from your playlist:")
        main_layout.addWidget(list_label)
        
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.NoSelection)
        self.populate_list()
        main_layout.addWidget(self.list_widget)

        # 2. Destination Folder Selector
        device_layout = QHBoxLayout()
        self.device_label = QLabel("Device Music Folder:")
        device_layout.addWidget(self.device_label)
        
        self.device_path_line = QLineEdit("Select the device's main Music folder...")
        self.device_path_line.setReadOnly(True)
        device_layout.addWidget(self.device_path_line)
        
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.select_device_folder)
        device_layout.addWidget(self.browse_button)
        main_layout.addLayout(device_layout)
        
        # 3. Action Buttons
        button_box = QHBoxLayout()
        self.sync_button = QPushButton("Start Sync")
        self.sync_button.clicked.connect(self.accept_sync)
        self.sync_button.setEnabled(False) # Disable until a folder is selected
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_box.addStretch(1)
        button_box.addWidget(self.sync_button)
        button_box.addWidget(cancel_button)
        main_layout.addLayout(button_box)

    def populate_list(self):
        """Populate the list with playlist items and checkboxes."""
        for url in self.playlist_data:
            # Skip showing streams in the sync list
            if url.startswith('http'):
                continue
                
            # Use the simple filename for display
            display_name = os.path.basename(url)
            
            item = QListWidgetItem(self.list_widget)
            
            # Create a checkbox widget
            checkbox = QCheckBox(display_name)
            checkbox.setChecked(False) # Start unchecked
            
            # Store the path on the checkbox itself
            checkbox.setProperty("file_path", url) 
            
            # Connect checkbox state change to update sync button status
            checkbox.stateChanged.connect(self.update_sync_button_status)
            
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, checkbox)

    def select_device_folder(self):
        """Open a dialog to select the device's music folder."""
        folder = QFileDialog.getExistingDirectory(
            self, 
            "Select Device Music Folder (e.g., ROCKBOX/Music)"
        )
        if folder:
            self.destination_folder = folder
            self.device_path_line.setText(folder)
            self.update_sync_button_status()

    def update_sync_button_status(self):
        """Enable sync button only if songs are selected AND a folder is chosen."""
        any_checked = any(
            self.list_widget.itemWidget(self.list_widget.item(i)).isChecked() 
            for i in range(self.list_widget.count())
        )
        self.sync_button.setEnabled(any_checked and bool(self.destination_folder))

    def accept_sync(self):
        """Collect selected files and accept the dialog."""
        self.selected_files = []
        for i in range(self.list_widget.count()):
            checkbox = self.list_widget.itemWidget(self.list_widget.item(i))
            if checkbox.isChecked():
                # Retrieve the path stored on the checkbox
                self.selected_files.append(checkbox.property("file_path"))
        
        if self.selected_files and self.destination_folder:
            self.accept()
        else:
            # This shouldn't happen if update_sync_button_status works, but safety first
            QMessageBox.warning(self, "Missing Info", "Please select at least one song and the device folder.")
            
# --------------------------------------------------------------------------------------
# CORE PLAYER CLASS
# --------------------------------------------------------------------------------------

class MagicBoxPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MagicBoxPlayer 🎶") 
        self.setGeometry(100, 100, 750, 550)  
        
        self.PLAYLIST_FILE = "saved_playlist.json" 
        
        self._original_geometry = self.geometry()
        self._is_mini_player = False

        self.playlist = []
        self.current_index = -1 
        self.playing = False

        # --- QMediaPlayer Setup ---
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.stateChanged.connect(self.on_state_changed)
        self.media_player.error.connect(self.media_error)
        self.media_player.metaDataAvailableChanged.connect(self.fetch_song_info)
        
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
        
        self.media_player.positionChanged.connect(self.on_position_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)

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
        
        # --- Placeholder Widget (QLabel) ---
        self.placeholder_label = QLabel()
        self.setup_placeholder_image() 
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setScaledContents(True) 
        self.placeholder_label.setMinimumSize(320, 240)
        self.placeholder_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        video_layout.addWidget(self.placeholder_label) 

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(320, 240) 
        self.media_player.setVideoOutput(self.video_widget)
        video_layout.addWidget(self.video_widget) 
        
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
        self.info_show = QLabel("Show/Album: (---)")
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

        # Load the playlist immediately after setup
        self.load_playlist() 

        # Timer for updating playback slider (as a fallback/secondary update)
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_position)
        self.timer.start()

        # --- Set initial visibility state ---
        self.update_video_view_visibility(is_playing=False)

        # -------------------------------------------------------------------
        # PYINSTALLER SPLASH SCREEN CLOSURE HOOK
        if hasattr(sys, '_MEIPASS'):
            try:
                import pyi_splash
                pyi_splash.close() 
            except ImportError:
                pass
        # -------------------------------------------------------------------

    # --- Override Close Event ---
    def closeEvent(self, event):
        """Overrides the standard close event to save the playlist."""
        self.save_playlist()
        self.media_player.stop()
        event.accept() 

    # --- Save/Load Playlist Methods ---
    def save_playlist(self):
        """Saves the current playlist (list of URLs/paths) to a JSON file."""
        try:
            with open(self.PLAYLIST_FILE, 'w') as f:
                json.dump(self.playlist, f)
            print("Playlist saved successfully.")
        except Exception as e:
            print(f"Warning: Could not save playlist: {e}")

    def load_playlist(self):
        """Loads the playlist from the JSON file on startup."""
        if os.path.exists(self.PLAYLIST_FILE):
            try:
                with open(self.PLAYLIST_FILE, 'r') as f:
                    loaded_list = json.load(f)
                    
                self.playlist = []
                self.song_list.clear()

                for url in loaded_list:
                    # Re-add items using the internal _add_to_playlist method
                    name = os.path.basename(url) if not url.startswith('http') else url
                    is_stream = url.startswith('http') or url.lower().endswith(('.m3u', '.m3u8'))
                    self._add_to_playlist(url, name, is_channel=is_stream)
                
                if self.playlist:
                    self.current_index = 0
                    self.song_list.setCurrentRow(0)

                print(f"Playlist loaded with {len(self.playlist)} items.")

            except Exception as e:
                print(f"Error loading playlist file: {e}")
                
    # -------------------------------------

    def setup_placeholder_image(self):
        """Checks for placeholder.png and sets the label content."""
        placeholder_path = resource_path('placeholder.png')
        
        if os.path.exists(placeholder_path):
            pixmap = QPixmap(placeholder_path)
            if not pixmap.isNull():
                self.placeholder_label.setPixmap(pixmap)
                self.placeholder_label.setStyleSheet("background-color: black;")
                return

        self.placeholder_label.setText("MAGIC BOX 🎶\n(No Media Loaded)")
        self.placeholder_label.setStyleSheet("background-color: #333; color: #fff; border: 2px solid #555;")

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
    # Playback Slider/Time Handlers
    # --------------------------------------------------------------------------------------
    def on_duration_changed(self, duration):
        """Sets the maximum value of the slider based on media duration (in milliseconds)."""
        self.playback_slider.setRange(0, duration) 
        
    def on_position_changed(self, position):
        """Updates the slider position as the media plays."""
        if not self.playback_slider.isSliderDown():
            self.playback_slider.setValue(position)

    def set_position(self, position):
        """Sets the media player position when the user moves the slider."""
        self.media_player.setPosition(position)

    # --------------------------------------------------------------------------------------
    # Video View Management
    # --------------------------------------------------------------------------------------
    def update_video_view_visibility(self, is_playing):
        """Switches between the placeholder and the QVideoWidget."""
        if is_playing:
            self.placeholder_label.hide()
            self.video_widget.show()
        else:
            if self.media_player.mediaStatus() == QMediaPlayer.NoMedia or self.media_player.state() == QMediaPlayer.StoppedState:
                self.video_widget.hide()
                self.placeholder_label.show()
            else:
                self.placeholder_label.hide()
                self.video_widget.show()

    # --------------------------------------------------------------------------------------
    # Core Player Functions 
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
        self.mini_player_action = QAction("Mini Player Mode", self)
        self.mini_player_action.setCheckable(True)
        self.mini_player_action.triggered.connect(self.toggle_mini_player)
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
        
        # UPDATED: Sync to Device Action
        copy_action = QAction("Sync Media to Device...", self) 
        copy_action.triggered.connect(self.sync_to_device)
        
        tools_menu.addAction(info_action)
        tools_menu.addAction(youtube_action)
        tools_menu.addAction(copy_action)
        
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About MagicBoxPlayer", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def toggle_mini_player(self, checked):
        self._is_mini_player = checked
        self.mini_player_action.setChecked(checked)

        if checked:
            self._original_geometry = self.geometry()
            self.setFixedSize(QSize(360, 320)) 
            
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
            # FIX: Use verify=False to bypass SSL hostname mismatch errors for public streams
            response = requests.get(m3u_url, timeout=10, verify=False)
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
            
            self.update_video_view_visibility(is_playing=True) 
            self.media_player.setMedia(QMediaContent(QUrl(m3u_url)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.update_location_bar()
            self.fetch_song_info()
            return idx 

        is_hls_stream = any(line.startswith('#EXT-X-TARGETDURATION') for line in lines)
        is_multi_channel = any('#EXTINF' in line and (',' in line and len(line.split(',')[-1].strip()) > 0) for line in lines)

        if is_hls_stream and not is_multi_channel:
            idx = self._add_to_playlist(m3u_url, playlist_name, is_channel=True)
            self.current_index = idx
            self.song_list.setCurrentRow(self.current_index)
            
            self.media_player.stop() 
            self.update_video_view_visibility(is_playing=True) 
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
            self.update_video_view_visibility(is_playing=True) 
            self.media_player.setMedia(QMediaContent(QUrl(m3u_url)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.update_location_bar()
            self.fetch_song_info()
            return idx
        
    def play_media_url(self, url, name=None):
        if url.lower().endswith(('.m3u', '.m3u8')):
            if '://' in url and not any(ext in url.lower() for ext in ['.ts', '.mp4']):
                 parse_result = self._parse_and_load_m3u(url, name if name else os.path.basename(url))
                 if parse_result != -1:
                     return
            
        index = self._add_to_playlist(url, name, is_channel=True)
        self.current_index = index
        self.song_list.setCurrentRow(self.current_index)

        self.media_player.stop() 
        self.update_video_view_visibility(is_playing=True) 
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
        self.update_video_view_visibility(is_playing=True) 

        if media_source.startswith('http'):
            self.media_player.setMedia(QMediaContent(QUrl(media_source)))
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
                if file not in self.playlist:
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
            self.update_video_view_visibility(is_playing=True)
        elif state == QMediaPlayer.StoppedState:
            self.play_button.setText("▶️")
            self.playing = False
            self.update_video_view_visibility(is_playing=False)
        
    def toggle_play_pause(self):
        current_state = self.media_player.state()
        
        if current_state == QMediaPlayer.PlayingState:
            self.media_player.pause()
        
        elif current_state == QMediaPlayer.StoppedState or current_state == QMediaPlayer.NoMedia:
            if self.playlist:
                if self.current_index == -1:
                    self.current_index = 0
                
                self.play_selected_song() 
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
        if self.media_player.isSeekable() and self.media_player.duration() > 0:
            if not self.playback_slider.isSliderDown():
                self.playback_slider.setValue(self.media_player.position())

    def fetch_song_info(self):
        title = self.media_player.metaData(QMediaMetaData.Title)
        artist = self.media_player.metaData(QMediaMetaData.ContributingArtist) 
        album = self.media_player.metaData(QMediaMetaData.AlbumTitle) 
        copyright_info = self.media_player.metaData(QMediaMetaData.Copyright)

        self.info_clip.setText(f"Clip: ({title or '---'})")
        self.info_author.setText(f"Author: ({artist or '---'})")
        self.info_show.setText(f"Show/Album: ({album or '---'})")
        self.info_copyright.setText(f"Copyright: ({copyright_info or '---'})")

    def show_song_info(self):
        info_text = ""
        for key in self.media_player.availableMetaData():
            value = self.media_player.metaData(key)
            if value:
                info_text += f"<b>{key}:</b> {value}<br>"
                
        if not info_text:
            info_text = "No detailed metadata available for the current media."
            
        QMessageBox.information(self, "Media Information", info_text)

    def find_on_youtube(self):
        title = self.media_player.metaData(QMediaMetaData.Title)
        artist = self.media_player.metaData(QMediaMetaData.ContributingArtist)
        
        if title:
            search_query = f"{title} {artist or ''}"
            webbrowser.open(f"https://www.youtube.com/results?search_query={search_query}")
        else:
            QMessageBox.warning(self, "Search Error", "No title metadata available to search.")

    # UPDATED: Sync to Device function to open selection dialog
    def sync_to_device(self):
        """
        Opens the selection dialog and executes the file copy for selected files.
        """
        if not self.playlist:
            QMessageBox.warning(self, "Sync Error", "The playlist is empty. Please add media first.")
            return

        # 1. Open the selection dialog
        dialog = SyncSelectionDialog(self.playlist, self)
        
        if dialog.exec_() == QDialog.Accepted:
            selected_files = dialog.selected_files
            destination_folder = dialog.destination_folder
            
            if not selected_files or not destination_folder:
                return

            files_synced = 0
            files_skipped = 0
            
            # 2. Loop through selected files and sync
            for source_path in selected_files:
                # Streams are filtered in the dialog's populate_list, but check here too
                if source_path.startswith('http'):
                    files_skipped += 1
                    continue
                
                try:
                    base_name = os.path.basename(source_path)
                    final_destination = os.path.join(destination_folder, base_name)
                    
                    # Ensure the copy operation is successful
                    shutil.copy(source_path, final_destination)
                    files_synced += 1
                except Exception as e:
                    QMessageBox.critical(self, "Sync Failed", f"Failed to copy '{base_name}':\n{e}")
                    files_skipped += 1

            # 3. Report results
            if files_synced > 0:
                QMessageBox.information(
                    self, 
                    "Sync Complete", 
                    f"Successfully synced {files_synced} file(s) to the device.\n"
                    f"(Skipped {files_skipped} file(s) - e.g., streams or errors).\n\n"
                    "NOTE: For classic iPod/Zune, a dedicated tool (like Rockbox Utility) may be required to update the internal music database."
                )
            elif files_skipped > 0 and files_synced == 0:
                 QMessageBox.warning(
                    self, 
                    "Sync Canceled", 
                    f"No files were synced. {files_skipped} file(s) were skipped due to being streams or copy errors."
                )
        
    def show_about(self):
        about_dialog = AboutDialog(self)
        about_dialog.exec_()

if __name__ == '__main__':
    if hasattr(sys, 'frozen') and sys.platform == 'win32':
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    
    app = QApplication(sys.argv)
    
    app.setApplicationName("MagicBoxPlayer")

    player = MagicBoxPlayer()
    player.show()
    sys.exit(app.exec_())

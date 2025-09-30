import sys
import os
import requests
import webbrowser
import shutil
import random
import math

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QListWidget, QFileDialog, QSlider, QHBoxLayout,
    QMenuBar, QAction, QMessageBox, QDialog, QRadioButton, QButtonGroup, 
    QLineEdit, QListWidgetItem, QSplitter, QGridLayout, QGroupBox, QComboBox
)
from PyQt5.QtCore import Qt, QUrl, QTimer, QSize
from PyQt5.QtGui import QIcon, QFont, QPixmap, QImage, QColor, QPainter
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

# --------------------------------------------------------------------------------------
# Helper/Window Classes (Unchanged for brevity)
# --------------------------------------------------------------------------------------

class EQWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Equalizer")
        self.setGeometry(200, 200, 350, 300)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Equalizer"))
        self.sliders = []
        bands = ["Bass", "Low-Mid", "Mid", "High-Mid", "Treble"]
        for band in bands:
            band_layout = QHBoxLayout()
            label = QLabel(band)
            slider = QSlider(Qt.Horizontal)
            slider.setRange(-10, 10)
            slider.setValue(0)
            slider.valueChanged.connect(lambda value, b=band: print(f"{b} set to {value} dB"))
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

class VisualizerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Visualizer")
        self.setGeometry(250, 250, 400, 200)
        self.n_bars = 32
        self.phase = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)
        self.bars = [0] * self.n_bars

    def animate(self):
        self.phase += 0.15
        for i in range(self.n_bars):
            # Sine wave + random for a more dynamic look
            base = 60 + 40 * math.sin(self.phase + i * 0.3)
            jitter = random.randint(-10, 10)
            self.bars[i] = max(10, min(120, int(base + jitter)))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        w = self.width() // self.n_bars
        for i, h in enumerate(self.bars):
            color = QColor.fromHsv(int(240 - (i * 240 / self.n_bars)), 200, 255)
            painter.setBrush(color)
            painter.setPen(Qt.NoPen)
            painter.drawRect(i * w + 2, self.height() - h, w - 4, h)


class VideoWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Output")
        self.setGeometry(300, 200, 420, 380)
        self.parent = parent
        layout = QVBoxLayout()
        self.video_widget = QVideoWidget()
        layout.addWidget(self.video_widget)
        # Controls
        controls = QHBoxLayout()
        self.play_btn = QPushButton("▶️")
        self.pause_btn = QPushButton("⏸️")
        self.stop_btn = QPushButton("⏹️")
        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.seek_slider)
        layout.addLayout(controls)
        self.setLayout(layout)
        # Connect controls
        self.play_btn.clicked.connect(self.play_video)
        self.pause_btn.clicked.connect(self.pause_video)
        self.stop_btn.clicked.connect(self.stop_video)
        self.seek_slider.sliderMoved.connect(self.set_position)
        # Timer for updating seek bar
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_position)
        self.timer.start()

    def play_video(self):
        self.parent.media_player.play()

    def pause_video(self):
        self.parent.media_player.pause()

    def stop_video(self):
        self.parent.media_player.stop()

    def set_position(self, pos):
        duration = self.parent.media_player.duration()
        if duration > 0:
            new_pos = (pos / 1000) * duration
            self.parent.media_player.setPosition(int(new_pos))

    def update_position(self):
        player = self.parent.media_player
        if player.state() == QMediaPlayer.PlayingState:
            duration = player.duration()
            pos = player.position()
            if duration > 0:
                slider_val = int((pos / duration) * 1000)
                if not self.seek_slider.isSliderDown():
                    self.seek_slider.setValue(slider_val)

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Magic Box")
        self.setFixedSize(420, 350)
        layout = QVBoxLayout()
        self.visualizer = VisualizerWindow()
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

        self.playlist = []
        self.current_index = -1 # Start at -1 to indicate no selection
        self.playing = False
        self.video_in_separate_window = False
        self.video_window = None

        # Media player
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.stateChanged.connect(self.on_state_changed)
        self.media_player.error.connect(self.media_error)
        
        # --- Main Layout (Vertical Stack) ---
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # 1. Menu Bar
        menu_bar = QMenuBar(self)
        self.setup_menu_bar(menu_bar)
        main_layout.setMenuBar(menu_bar)

        # 2. Top Controls (Transport, Volume, Fast Seek)
        top_controls_layout = QHBoxLayout()
        top_controls_layout.setContentsMargins(0, 0, 0, 0)
        top_controls_layout.setSpacing(2)

        # Transport Buttons (Left side, small)
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
        
        # Small Volume Slider (Center-Top)
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.setMaximumWidth(120)
        top_controls_layout.addWidget(self.volume_slider)

        top_controls_layout.addStretch(1) # Push everything left
        
        main_layout.addLayout(top_controls_layout)
        
        # 3. Location/Seek Area
        location_seek_layout = QHBoxLayout()
        location_seek_layout.setContentsMargins(0, 0, 0, 0)
        
        # Location Label and Text Box
        location_seek_layout.addWidget(QLabel("Location:"))
        self.location_bar = QLineEdit()
        self.location_bar.setPlaceholderText("Current media location...")
        self.location_bar.setReadOnly(True) 
        location_seek_layout.addWidget(self.location_bar)
        
        main_layout.addLayout(location_seek_layout)
        
        # Seek Bar (Full width, below location)
        self.playback_slider = QSlider(Qt.Horizontal)
        self.playback_slider.setRange(0, 1000)
        main_layout.addWidget(self.playback_slider)

        # 4. Main Content Area (Horizontal Split: Playlist | Video)
        content_splitter = QSplitter(Qt.Horizontal)
        
        # --- Left Side: Channels/Playlist ---
        playlist_panel = QWidget()
        playlist_layout = QVBoxLayout(playlist_panel)
        playlist_layout.setContentsMargins(0, 0, 0, 0)
        
        channel_label = QLabel("My Media & Channels (IPTV Ready)")
        channel_label.setStyleSheet("background-color: #3333AA; color: white; padding: 4px; border-bottom: 1px solid #000;")
        playlist_layout.addWidget(channel_label)
        
        # Playlist area
        self.song_list = QListWidget()
        self.song_list.setSelectionMode(QListWidget.SingleSelection)
        playlist_layout.addWidget(self.song_list)
        
        # Playlist Controls (Add/Scan) below the list
        utility_layout = QHBoxLayout()
        load_button = QPushButton("➕ Add Media")
        load_button.clicked.connect(self.load_songs)
        scan_folder_btn = QPushButton("📁 Scan Folder")
        scan_folder_btn.clicked.connect(self.scan_folder)
        utility_layout.addWidget(load_button)
        utility_layout.addWidget(scan_folder_btn)
        playlist_layout.addLayout(utility_layout)
        
        content_splitter.addWidget(playlist_panel)

        # --- Right Side: Video/Player ---
        video_panel = QWidget()
        video_layout = QVBoxLayout(video_panel)
        video_layout.setContentsMargins(0, 0, 0, 0)
        
        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(320, 240) 
        self.media_player.setVideoOutput(self.video_widget)
        video_layout.addWidget(self.video_widget)
        
        # Placeholder for small controls/status bar below video
        video_status_bar = QHBoxLayout()
        video_status_bar.setContentsMargins(4, 4, 4, 4)
        
        # status_label = QLabel("Ready") # REMOVED in previous step
        # status_label.setToolTip("Player Status")
        # video_status_bar.addWidget(status_label) # REMOVED in previous step
        video_status_bar.addStretch(1)
        
        video_layout.addLayout(video_status_bar)
        
        content_splitter.addWidget(video_panel)
        
        content_splitter.setSizes([200, 550]) 
        main_layout.addWidget(content_splitter, 1) 

        # 5. Bottom Info Panel (Black Status Bar)
        info_panel = QWidget()
        info_panel.setStyleSheet("background-color: black; color: white; padding: 2px;")
        info_layout = QHBoxLayout(info_panel)
        info_layout.setContentsMargins(4, 2, 4, 2)
        info_layout.setSpacing(10)
        
        # Info labels
        self.info_clip = QLabel("Clip: (none)")
        self.info_author = QLabel("Author: (none)")
        self.info_show = QLabel("Show: (none)")
        self.info_copyright = QLabel("Copyright: (none)")
        
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

        main_layout.addWidget(info_panel)
        
        # --- Final setup ---
        self.setLayout(main_layout)
        self.connect_signals()

        # Timer for updating playback slider
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_position)
        self.timer.start()

        self.eq_window = None
        self.visualizer_window = None

    # --------------------------------------------------------------------------------------
    # Connect Signals
    # --------------------------------------------------------------------------------------
    def connect_signals(self):
        """Connects all UI element signals to their respective slot methods."""
        
        # Connect transport buttons
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.stop_button.clicked.connect(self.stop_song)
        self.next_button.clicked.connect(self.next_song)
        self.prev_button.clicked.connect(self.prev_song)
        self.mute_button.clicked.connect(self.toggle_mute)
        
        # Connect playlist interaction
        self.song_list.itemDoubleClicked.connect(self.play_selected_song)
        
        # Connect seeking
        self.playback_slider.sliderMoved.connect(self.set_position)
        
        # Connect volume
        self.volume_slider.valueChanged.connect(self.media_player.setVolume)
    
    # --------------------------------------------------------------------------------------
    # Menu Bar Setup (Unchanged for brevity)
    # --------------------------------------------------------------------------------------
    def setup_menu_bar(self, menu_bar):
        # File Menu
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
        
        # View Menu
        view_menu = menu_bar.addMenu("View")
        eq_action = QAction("Equalizer", self)
        eq_action.triggered.connect(self.show_eq)
        vis_action = QAction("Visualizer", self)
        vis_action.triggered.connect(self.show_visualizer)
        video_sep_action = QAction("Video in Separate Window", self)
        video_sep_action.setCheckable(True)
        video_sep_action.triggered.connect(self.toggle_video_window)
        view_menu.addAction(eq_action)
        view_menu.addAction(vis_action)
        view_menu.addSeparator()
        view_menu.addAction(video_sep_action)

        # Play Menu
        play_menu = menu_bar.addMenu("Play")
        play_menu.addAction("Play/Pause").triggered.connect(self.toggle_play_pause)
        play_menu.addAction("Stop").triggered.connect(self.stop_song)
        play_menu.addAction("Next").triggered.connect(self.next_song)
        play_menu.addAction("Previous").triggered.connect(self.prev_song)
        
        # Stream Menu
        stream_menu = menu_bar.addAction("Stream/IPTV")
        stream_menu.triggered.connect(self.show_stream_dialog)
        
        # Tools Menu
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
        
        # Help Menu
        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About MagicBox", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def media_error(self, error):
        """Handle errors from the QMediaPlayer."""
        error_name = self.media_player.errorString()
        QMessageBox.critical(self, "Media Error", f"Failed to play media: {error_name}\n\nCheck URL or file path.")
        self.stop_song()

    def update_location_bar(self):
        if self.current_index != -1 and self.playlist:
            song_path = self.playlist[self.current_index]
            
            # Check if it's a stream (starts with http)
            if song_path.startswith('http'):
                 item = self.song_list.item(self.current_index)
                 # Check if the list item has custom data indicating it's a playlist entry
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
        """Adds a URL to the internal playlist and ListWidget, checking for duplicates."""
        if url not in self.playlist:
            self.playlist.append(url)
            item = QListWidgetItem(name if name else url)
            
            # Use UserRole to mark M3U/M3U8 entries for special handling
            if is_channel:
                item.setData(Qt.UserRole, 'stream_channel') 
            
            self.song_list.addItem(item)
            return len(self.playlist) - 1
        return self.playlist.index(url)

    def _parse_and_load_m3u(self, m3u_url, playlist_name):
        """
        Downloads and parses an M3U/M3U8 file, adding channels to the playlist.
        Returns the index of the first channel added, or -1 on total failure.
        """
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
            
            # Play directly instead of calling play_selected_song to avoid recursion
            self.media_player.setMedia(QMediaContent(QUrl(m3u_url)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.update_location_bar()
            self.fetch_song_info()
            return idx # Return the index of the played item

        # --- LOGIC FOR SINGLE-VIDEO HLS DETECTION (Silent if detected) ---
        is_hls_stream = any(line.startswith('#EXT-X-TARGETDURATION') or line.startswith('#EXT-X-MEDIA-SEQUENCE') for line in lines)
        is_multi_channel = any('#EXTINF' in line and (',' in line and len(line.split(',')[-1].strip()) > 0) for line in lines)

        if is_hls_stream and not is_multi_channel:
            idx = self._add_to_playlist(m3u_url, playlist_name, is_channel=True)
            self.current_index = idx
            self.song_list.setCurrentRow(self.current_index)
            
            # *** FIX: Play directly instead of calling play_selected_song to avoid recursion ***
            self.media_player.stop() 
            self.media_player.setMedia(QMediaContent(QUrl(m3u_url)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.update_location_bar()
            self.fetch_song_info()
            return idx # Exit the function immediately after playing the direct URL
        
        # --- END LOGIC ---

        channels_added = 0
        last_info = None
        first_index = -1
        
        # --- IPTV Channel Parsing Logic (Only runs if not detected as a single video) ---
        for line in lines:
            line = line.strip()
            
            if line.startswith('#EXTM3U'):
                continue
            
            # Store channel metadata (name, group, etc.)
            if line.startswith('#EXTINF'):
                if ',' in line:
                    last_info = line.split(',')[-1].strip()
                else:
                    last_info = 'Unknown Channel'
                
            # Process stream URL
            elif line.startswith('http') or line.startswith('rtsp') or line.startswith('udp') or line.lower().endswith(('.ts', '.mp4', '.m3u8')):
                stream_url = line
                channel_name = last_info if last_info else f"{playlist_name} Channel {channels_added + 1}"
                
                # Use base URL for relative paths
                if not stream_url.startswith('http') and not stream_url.startswith('rtsp') and not stream_url.startswith('udp'):
                     stream_url = requests.compat.urljoin(m3u_url, stream_url)
                
                idx = self._add_to_playlist(stream_url, channel_name, is_channel=True)
                if first_index == -1:
                    first_index = idx 
                    
                channels_added += 1
                last_info = None # Clear info for the next channel

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
            # Play directly instead of calling play_selected_song to avoid recursion
            self.media_player.setMedia(QMediaContent(QUrl(m3u_url)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.update_location_bar()
            self.fetch_song_info()
            return idx
        
    def play_media_url(self, url, name=None):
        """A dedicated function to handle playing a URL/stream."""
        
        # Check if the URL is an M3U/M3U8 playlist file (or similar, like a general stream list)
        if url.lower().endswith(('.m3u', '.m3u8')):
            self._parse_and_load_m3u(url, name if name else os.path.basename(url))
            return # Parsing now handles starting playback
        
        # Handle single stream URL (not a playlist)
        index = self._add_to_playlist(url, name, is_channel=True)
        self.current_index = index
        self.song_list.setCurrentRow(self.current_index)

        # Stop previous media before setting new content (Crash Fix)
        self.media_player.stop() 
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
        
        # Stop previous media before setting new content (Crash Fix)
        self.media_player.stop() 
        
        if media_source.startswith('http'):
            # Check if it's an M3U/M3U8 file itself, or a direct channel link
            if media_source.lower().endswith(('.m3u', '.m3u8')):
                # Only re-parse if the selected item is the M3U/M3U8 file itself, 
                # NOT if it's an actual channel URL already parsed and added to the list.
                
                # If the item doesn't have the 'stream_channel' role, it must be the original
                # entry from the Stream Dialog or a local M3U file, so we parse it.
                is_channel_link = self.song_list.item(self.current_index).data(Qt.UserRole) == 'stream_channel'
                
                if not is_channel_link:
                    # The selected item is the M3U/M3U8 *file*. Parse it.
                    self._parse_and_load_m3u(media_source, item.text() if item else os.path.basename(media_source))
                    return # Exit: The parser will set playback on the first channel it finds.
                
            # Direct stream link or a single video M3U8 that was played directly
            self.media_player.setMedia(QMediaContent(QUrl(media_source)))
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.song_list.setCurrentRow(self.current_index)
            self.update_location_bar()
            self.fetch_song_info()
        else:
            # Local file
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
                    # Local M3U/M3U8 file parsing (simplified, assumes simple file structure)
                    QMessageBox.information(self, "Feature Note", "Local M3U/M3U8 file loading is a work in progress. For now, please use the 'Stream/IPTV' menu item for public IPTV URLs.")
                elif file not in self.playlist:
                    self._add_to_playlist(file, os.path.basename(file), is_channel=False)
            
            if self.media_player.state() == QMediaPlayer.StoppedState and not self.playing and self.playlist:
                self.current_index = len(self.playlist) - 1
                self.song_list.setCurrentRow(self.current_index)
                self.update_location_bar()


    def toggle_play_pause(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.play_button.setText("▶️")
            self.playing = False
        else:
            if not self.playlist and self.media_player.state() == QMediaPlayer.StoppedState:
                self.show_stream_dialog()
                return

            selected_row = self.song_list.currentRow()
            if selected_row != -1 and selected_row != self.current_index and self.media_player.state() != QMediaPlayer.PlayingState:
                self.current_index = selected_row
                self.play_selected_song()
                
            elif self.media_player.state() == QMediaPlayer.PausedState:
                self.media_player.play()
            elif self.media_player.state() == QMediaPlayer.StoppedState:
                if self.current_index != -1:
                    self.play_selected_song()
                else: 
                    if self.playlist:
                        self.current_index = 0
                        self.song_list.setCurrentRow(self.current_index)
                        self.play_selected_song()

            self.play_button.setText("⏸️")
            self.playing = True

    def stop_song(self):
        self.media_player.stop()
        self.play_button.setText("▶️")
        self.playing = False
        self.location_bar.setText("")

    def next_song(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.song_list.setCurrentRow(self.current_index)
        self.play_selected_song()

    def prev_song(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.song_list.setCurrentRow(self.current_index)
        self.play_selected_song()

    def toggle_mute(self):
        is_muted = not self.media_player.isMuted()
        self.media_player.setMuted(is_muted)
        self.mute_button.setText("🔊" if not is_muted else "🔇")

    def set_position(self, position):
        duration = self.media_player.duration()
        if duration > 0:
            new_pos = (position / 1000) * duration
            self.media_player.setPosition(int(new_pos))

    def update_position(self):
        if self.current_index == -1 or not self.playlist:
            return

        is_stream = self.playlist[self.current_index].startswith('http')
        
        if is_stream:
            # Streams (especially live) usually don't support seeking/duration reporting well
            self.playback_slider.setEnabled(False)
            return

        if self.media_player.state() == QMediaPlayer.PlayingState or self.media_player.state() == QMediaPlayer.PausedState:
            duration = self.media_player.duration()
            pos = self.media_player.position()
            
            self.playback_slider.setEnabled(True)
            if duration > 0:
                slider_val = int((pos / duration) * 1000)
                if not self.playback_slider.isSliderDown():
                    self.playback_slider.setValue(slider_val)
                    
    def on_state_changed(self, state):
        if state == QMediaPlayer.StoppedState:
            self.play_button.setText("▶️")
            if self.media_player.mediaStatus() == QMediaPlayer.EndOfMedia:
                # Auto-advance only for local files/streams that truly end
                if self.current_index != -1 and not self.playlist[self.current_index].startswith('http'):
                    self.next_song()

        elif state == QMediaPlayer.PlayingState:
            self.play_button.setText("⏸️")
            self.update_location_bar()

        elif state == QMediaPlayer.PausedState:
            self.play_button.setText("▶️")
            
    # --------------------------------------------------------------------------------------
    # show_stream_dialog (Unchanged)
    # --------------------------------------------------------------------------------------
    def show_stream_dialog(self):
        """Shows the combined Internet Radio and IPTV Stream dialog with presets."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Stream/IPTV Channels (M3U/M3U8 Support)")
        dlg.setFixedSize(450, 450)
        layout = QVBoxLayout()
        
        # 1. Preset Channels
        label_presets = QLabel("Choose a Preset Playlist or Channel:")
        layout.addWidget(label_presets)
        
        station_list = QListWidget()
        
        # --- FREE & PUBLIC IPTV CHANNELS AND PLAYLISTS ---
        stations = [
            ("IPTV-Org Main Playlist (M3U - Worldwide)", "https://iptv-org.github.io/iptv/index.m3u"),
            ("Pluto TV US Playlist (M3U8 - Free TV)", "https://i.mjh.nz/PlutoTV/us.m3u8"),
            ("Samsung TV Plus US Playlist (M3U8 - Free TV)", "https://i.mjh.nz/SamsungTVPlus/us.m3u8"),
            ("NASA TV Public (Live Video)", "https://nasa-tv.s.llnwi.net/nasa-tv-public/playlist.m3u8"),
            ("BBC Radio 1 (Audio)", "http://bbcmedia.ic.llnwd.net/stream/bbcmedia_radio1_mf_p"),
            ("Public Domain Big Buck Bunny (Test Video)", "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"),
        ]
        # --------------------------------------------------
        
        for name, url in stations:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, url)
            station_list.addItem(item)
        layout.addWidget(station_list)
        
        # 2. Manual URL Entry
        layout.addWidget(QLabel("--- OR ---"))
        label_manual = QLabel("Enter a Stream URL or M3U/M3U8 Playlist URL:")
        layout.addWidget(label_manual)
        
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste stream URL or Playlist URL here (starts with http)")
        layout.addWidget(self.url_input)
        
        # 3. Play Button
        play_btn = QPushButton("▶️ Play Stream/Channel")
        play_btn.clicked.connect(lambda: self.handle_stream_play(dlg, station_list))
        layout.addWidget(play_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.reject)
        layout.addWidget(close_btn)
        
        dlg.setLayout(layout)
        dlg.exec_()
    # --------------------------------------------------------------------------------------
        
    def handle_stream_play(self, dialog, station_list):
        """Logic to determine which stream to play and start playback."""
        url = self.url_input.text().strip()
        name = None
        
        if not url:
            # Try to get from preset list
            item = station_list.currentItem()
            if item:
                url = item.data(Qt.UserRole)
                name = item.text()
        
        if url and url.lower().startswith(('http', 'https', 'rtsp')):
            # The play_media_url method now handles M3U/M3U8 detection and parsing
            self.play_media_url(url, name)
            dialog.accept()
        else:
            QMessageBox.warning(dialog, "Error", "Please select a valid preset or enter a valid URL (starting with http, https, or rtsp).")

    # (Other methods remain the same for brevity)
    def show_about(self):
        dlg = AboutDialog(self)
        dlg.exec_()

    def show_eq(self):
        if self.eq_window is None:
            self.eq_window = EQWindow()
        self.eq_window.show()
        self.eq_window.raise_()
        self.eq_window.activateWindow()

    def show_visualizer(self):
        if self.visualizer_window is None:
            self.visualizer_window = VisualizerWindow()
        self.visualizer_window.show()
        self.visualizer_window.raise_()
        self.visualizer_window.activateWindow()
        
    def find_rockbox_mounts(self):
        # Placeholder for platform-specific Rockbox detection
        return []

    def fetch_song_info(self):
        if not self.playlist or self.current_index == -1:
            self._clear_info_labels()
            return
            
        song_path = self.playlist[self.current_index]
        item = self.song_list.item(self.current_index)
        is_stream = song_path.startswith('http')
        is_channel = item and item.data(Qt.UserRole) == 'stream_channel'
        
        if is_stream:
            stream_name = item.text() if item else song_path
            self.info_clip.setText(f"Clip: {stream_name}")
            self.info_author.setText("Author: (Stream Source)")
            self.info_show.setText("Show: (Live Broadcast)")
            self.info_copyright.setText("Copyright: (N/A)")
            return
            
        # Local file metadata fetch logic
        song_name = os.path.splitext(os.path.basename(song_path))[0]
        search_query = song_name.replace(" - ", " ").split('.')[0].strip()
        
        try:
            url = f"https://musicbrainz.org/ws/2/recording/?query={search_query}&fmt=json&limit=1"
            resp = requests.get(url, headers={"User-Agent": "MagicBoxPlayer/1.0 ( eggplant48@example.com )"}) 
            
            if resp.status_code == 200:
                data = resp.json()
                if data['recordings']:
                    rec = data['recordings'][0]
                    title = rec.get('title', '(none)')
                    artist = rec['artist-credit'][0]['name'] if rec.get('artist-credit') else '(none)'
                    release = rec['releases'][0]['title'] if rec.get('releases') else '(none)'
                    copyright_year = rec['releases'][0].get('date', '(none)').split('-')[0] if rec['releases'][0].get('date') else '(none)'
                    
                    self.info_clip.setText(f"Clip: {title}")
                    self.info_author.setText(f"Author: {artist}")
                    self.info_show.setText(f"Show: {release}")
                    self.info_copyright.setText(f"Copyright: {copyright_year}")
                else:
                    self._set_default_local_info(song_name)
            else:
                self._set_default_local_info(song_name)
        except Exception as e:
            self._set_default_local_info(song_name)
    
    def _clear_info_labels(self):
        self.info_clip.setText("Clip: (none)")
        self.info_author.setText("Author: (none)")
        self.info_show.setText("Show: (none)")
        self.info_copyright.setText("Copyright: (none)")

    def _set_default_local_info(self, song_name):
        self.info_clip.setText(f"Clip: {song_name}")
        self.info_author.setText("Author: (none)")
        self.info_show.setText("Show: (none)")
        self.info_copyright.setText("Copyright: (none)")


    def find_on_youtube(self):
        if not self.playlist or self.current_index == -1 or self.playlist[self.current_index].startswith('http'):
            QMessageBox.information(self, "Info", "No local song loaded or cannot search live streams.")
            return
        
        title = self.info_clip.text().replace("Clip: ", "").strip()
        artist = self.info_author.text().replace("Author: ", "").strip()
        
        if title and title != "(none)":
            query = f"{title} {artist}" if artist and artist != "(none)" else title
        else:
            song_path = self.playlist[self.current_index]
            query = os.path.splitext(os.path.basename(song_path))[0]
            
        url = f"https://www.youtube.com/results?search_query={requests.utils.quote(query)}"
        webbrowser.open(url)

    def copy_to_device(self):
        if not self.playlist or self.current_index == -1 or self.playlist[self.current_index].startswith('http'):
            QMessageBox.information(self, "Info", "Cannot copy streams, only local files.")
            return

        rockbox_mounts = self.find_rockbox_mounts()
        if rockbox_mounts:
            msg = "Rockbox device detected! You can copy music directly to this device.\n\n"
            msg += "\n".join(rockbox_mounts)
            QMessageBox.information(self, "Rockbox Alert", msg)

        song_path = self.playlist[self.current_index]
        dest_dir = QFileDialog.getExistingDirectory(self, "Select Device or Folder to Copy To")
        if dest_dir:
            try:
                dest_path = os.path.join(dest_dir, os.path.basename(song_path))
                shutil.copy2(song_path, dest_path)
                QMessageBox.information(self, "Success", f"Copied to: {dest_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to copy file:\n{e}")

    def scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Scan for Music")
        if folder:
            exts = ('.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.mp4', '.avi', '.mkv')
            new_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(exts):
                        full_path = os.path.join(root, file)
                        if full_path not in self.playlist:
                            self._add_to_playlist(full_path, os.path.basename(full_path), is_channel=False)
                            new_files.append(full_path)
            if new_files:
                QMessageBox.information(self, "Scan Complete", f"Added {len(new_files)} files.")
            else:
                QMessageBox.information(self, "Scan Complete", "No new music files found.")

    def show_song_info(self):
        if not self.playlist or self.current_index == -1:
            QMessageBox.information(self, "Info", "No media loaded.")
            return

        is_stream = self.playlist[self.current_index].startswith('http')
        
        if is_stream:
            QMessageBox.information(self, "Stream Info", 
                                    f"Current Stream URL:\n{self.playlist[self.current_index]}\n\n"
                                    "Metadata (Title, Author, etc.) is not available for all live streams."
                                    )
            return
            
        title = self.info_clip.text().replace("Clip: ", "").strip()
        artist = self.info_author.text().replace("Author: ", "").strip()
        show = self.info_show.text().replace("Show: ", "").strip()
        copyright = self.info_copyright.text().replace("Copyright: ", "").strip()

        info_dict = {
            'Title': title if title != '(none)' else 'Unknown',
            'Artist': artist if artist != '(none)' else 'Unknown',
            'Album/Show': show if show != '(none)' else 'Unknown',
            'Year/Copyright': copyright if copyright != '(none)' else 'Unknown',
        }
        
        dlg = QDialog(self)
        dlg.setWindowTitle("Song Info Selector")
        dlg.setFixedSize(350, 300)
        layout = QVBoxLayout()
        label = QLabel("Select info to display:")
        layout.addWidget(label)
        group = QButtonGroup(dlg)
        radios = {}
        
        for i, key in enumerate(info_dict):
            rb = QRadioButton(key)
            group.addButton(rb, i)
            layout.addWidget(rb)
            radios[key] = rb
            
        info_label = QLabel("")
        info_label.setFont(QFont("Arial", 10))
        info_label.setStyleSheet("border: 1px solid gray; padding: 5px;")
        layout.addWidget(info_label)
        
        def update_info():
            selected_key = ""
            for key, rb in radios.items():
                if rb.isChecked():
                    selected_key = key
                    break
            info_label.setText(f"<b>{selected_key}:</b> {info_dict.get(selected_key, 'N/A')}")
            
        group.buttonClicked.connect(update_info)
        if radios:
            list(radios.values())[0].setChecked(True)
        update_info()

        search_btn = QPushButton("Search on Google")
        def search_google():
            query = ""
            for key, rb in radios.items():
                if rb.isChecked():
                    query = f"{info_dict[key]} {artist if key != 'Artist' and artist != 'Unknown' else ''}".strip()
                    break
            if query and query != "Unknown":
                url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
                webbrowser.open(url)
            else:
                QMessageBox.warning(dlg, "Search Error", "Cannot search for unknown information.")

        search_btn.clicked.connect(search_google)
        layout.addWidget(search_btn)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn)
        
        dlg.setLayout(layout)
        dlg.exec_()


    def toggle_video_window(self, checked):
        if checked:
            if not self.video_window:
                self.video_window = VideoWindow(self)
            self.media_player.setVideoOutput(self.video_window.video_widget)
            self.video_window.show()
            self.play_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            self.playback_slider.setEnabled(False)
        else:
            self.media_player.setVideoOutput(self.video_widget)
            if self.video_window:
                self.video_window.hide()
            self.play_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.prev_button.setEnabled(True)
            self.next_button.setEnabled(True)
            self.playback_slider.setEnabled(True)

if __name__ == '__main__':
    if sys.platform.startswith('win'):
        # On Windows, using the default 'windowsmediafoundation' can be less stable 
        # than alternatives like 'directshow' for certain streams, but we'll stick 
        # with the default unless issues persist to maintain compatibility.
        os.environ['QT_MULTIMEDIA_PREFERRED_PLUGINS'] = 'windowsmediafoundation' 
        
    app = QApplication(sys.argv)
    player = MagicBoxPlayer()
    player.show()
    sys.exit(app.exec_())

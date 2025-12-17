import os
import sys
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
    QCheckBox
)
from PyQt5.QtCore import Qt, QUrl, QTimer, QSize
from PyQt5.QtGui import QIcon, QFont, QPixmap
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaMetaData
from PyQt5.QtMultimediaWidgets import QVideoWidget

# --------------------------------------------------------------------------------------
# GLOBAL SETUP
# --------------------------------------------------------------------------------------
warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# --------------------------------------------------------------------------------------
# About Dialog — with PNG logo support
# --------------------------------------------------------------------------------------
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About MagicBoxPlayer")
        self.setFixedSize(400, 500)
        main_layout = QVBoxLayout(self)

        # --- PNG Logo ---
        logo_label = QLabel()
        logo_path = resource_path("logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
                logo_label.setAlignment(Qt.AlignCenter)
                main_layout.addWidget(logo_label)
            else:
                placeholder = QLabel("🖼️ Logo (corrupted)")
                placeholder.setAlignment(Qt.AlignCenter)
                main_layout.addWidget(placeholder)
        else:
            placeholder = QLabel("🖼️ [logo.png not found]")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet("color: gray;")
            main_layout.addWidget(placeholder)

        # --- About Text ---
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
# CORE PLAYER CLASS — NO VISUALIZERS, NO OPENGL
# --------------------------------------------------------------------------------------
class MagicBoxPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MagicBoxPlayer 🎶") 
        self.setGeometry(100, 100, 750, 550)  
        self.PLAYLIST_FILE = "saved_playlist.json" 
        self._original_geometry = self.geometry()
        self._is_mini_player = False
        self._is_fullscreen = False  
        self._video_widget_parent_layout = None 
        self.playlist = []
        self.current_index = -1 
        self.playing = False
        self.media_player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.media_player.stateChanged.connect(self.on_state_changed)
        self.media_player.error.connect(self.media_error)
        self.media_player.metaDataAvailableChanged.connect(self.fetch_song_info) 
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.menu_bar = QMenuBar(self)
        self.setup_menu_bar(self.menu_bar)
        self.main_layout.setMenuBar(self.menu_bar)

        # Top Controls
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

        self.fullscreen_button = QPushButton("📺")
        self.fullscreen_button.setToolTip("Toggle Fullscreen (F11)")
        self.fullscreen_button.setFixedSize(button_size)
        self.fullscreen_button.setFont(QFont("Arial", 8))
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        top_controls_layout.addWidget(self.fullscreen_button)

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

        # Location Bar
        self.location_seek_layout = QHBoxLayout()
        self.location_label = QLabel("Location:")
        self.location_seek_layout.addWidget(self.location_label)
        self.location_bar = QLineEdit()
        self.location_bar.setPlaceholderText("Current media location...")
        self.location_bar.setReadOnly(True) 
        self.location_seek_layout.addWidget(self.location_bar)
        self.main_layout.addLayout(self.location_seek_layout)

        # Playback Slider
        self.playback_slider = QSlider(Qt.Horizontal)
        self.playback_slider.setRange(0, 1000)
        self.media_player.positionChanged.connect(self.on_position_changed)
        self.media_player.durationChanged.connect(self.on_duration_changed)
        self.main_layout.addWidget(self.playback_slider)

        # Playlist + Video Splitter
        self.content_splitter = QSplitter(Qt.Horizontal)
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

        # Video Panel
        self.video_panel = QWidget()
        video_layout = QVBoxLayout(self.video_panel)
        video_layout.setContentsMargins(0, 0, 0, 0)
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
        self._video_widget_parent_layout = video_layout 

        video_status_bar = QHBoxLayout()
        video_status_bar.setContentsMargins(4, 4, 4, 4)
        video_status_bar.addStretch(1)
        video_layout.addLayout(video_status_bar)
        self.content_splitter.addWidget(self.video_panel)
        self.content_splitter.setSizes([200, 550]) 
        self.main_layout.addWidget(self.content_splitter, 1) 

        # Info Panel
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

        self.setLayout(self.main_layout)
        self.connect_signals()
        self.load_playlist() 
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_position)
        self.timer.start()
        self.update_video_view_visibility(is_playing=False)
        if hasattr(sys, '_MEIPASS'):
            try:
                import pyi_splash
                pyi_splash.close() 
            except ImportError:
                pass

    # -----------------------------
    # Core Methods
    # -----------------------------
    def closeEvent(self, event):
        if self._is_fullscreen:
            self.toggle_fullscreen()
        self.save_playlist()
        self.media_player.stop()
        event.accept() 

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.toggle_fullscreen()
        super().keyPressEvent(event)

    def save_playlist(self):
        try:
            with open(self.PLAYLIST_FILE, 'w') as f:
                json.dump(self.playlist, f)
            print("Playlist saved successfully.")
        except Exception as e:
            print(f"Warning: Could not save playlist: {e}")

    def load_playlist(self):
        if os.path.exists(self.PLAYLIST_FILE):
            try:
                with open(self.PLAYLIST_FILE, 'r') as f:
                    loaded_list = json.load(f)
                self.playlist = []
                self.song_list.clear()
                for url in loaded_list:
                    name = os.path.basename(url) if not url.startswith('http') else url
                    is_stream = url.startswith('http') or url.lower().endswith(('.m3u', '.m3u8'))
                    self._add_to_playlist(url, name, is_channel=is_stream)
                if self.playlist:
                    self.current_index = 0
                    self.song_list.setCurrentRow(0)
                print(f"Playlist loaded with {len(self.playlist)} items.")
            except Exception as e:
                print(f"Error loading playlist file: {e}")

    def setup_placeholder_image(self):
        placeholder_path = resource_path('placeholder.png')
        if os.path.exists(placeholder_path):
            pixmap = QPixmap(placeholder_path)
            if not pixmap.isNull():
                self.placeholder_label.setPixmap(pixmap)
                self.placeholder_label.setStyleSheet("background-color: black;")
                return
        self.placeholder_label.setText("MAGIC BOX 🎶\n(No Media Loaded)")
        self.placeholder_label.setStyleSheet("background-color: #333; color: #fff; border: 2px solid #555;")

    def connect_signals(self):
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.stop_button.clicked.connect(self.stop_song)
        self.next_button.clicked.connect(self.next_song)
        self.prev_button.clicked.connect(self.prev_song)
        self.mute_button.clicked.connect(self.toggle_mute)
        self.song_list.itemDoubleClicked.connect(self.play_selected_song)
        self.playback_slider.sliderMoved.connect(self.set_position)
        self.volume_slider.valueChanged.connect(self.media_player.setVolume)

    def on_duration_changed(self, duration):
        self.playback_slider.setRange(0, duration) 

    def on_position_changed(self, position):
        if not self.playback_slider.isSliderDown():
            self.playback_slider.setValue(position)

    def set_position(self, position):
        self.media_player.setPosition(position)

    def update_video_view_visibility(self, is_playing):
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
        self.fullscreen_action = QAction("Toggle Fullscreen", self)
        self.fullscreen_action.setShortcut("F11")
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        view_menu.addAction(self.fullscreen_action)

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
        copy_action = QAction("Sync Media to Device...", self) 
        copy_action.triggered.connect(self.sync_to_device)
        tools_menu.addAction(info_action)
        tools_menu.addAction(youtube_action)
        tools_menu.addAction(copy_action)

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About MagicBoxPlayer", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def toggle_fullscreen(self):
        if self._is_mini_player:
            QMessageBox.warning(self, "Mode Conflict", "Please exit Mini Player Mode before entering Fullscreen.")
            return
        if self._is_fullscreen:
            self.showNormal() 
            self.main_layout.removeWidget(self.video_widget) 
            self._video_widget_parent_layout.addWidget(self.video_widget)
            self.menu_bar.show()
            self.playback_slider.show()
            self.content_splitter.show()
            self.info_panel.show()
            self.fullscreen_action.setChecked(False)
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
            self.setGeometry(self._original_geometry) 
            self._is_fullscreen = False
        else:
            self._original_geometry = self.geometry()
            self.menu_bar.hide()
            self.playback_slider.hide()
            self.content_splitter.hide()
            self.info_panel.hide()
            self._video_widget_parent_layout.removeWidget(self.video_widget)
            self.main_layout.addWidget(self.video_widget)
            self.showFullScreen()
            self.fullscreen_action.setChecked(True)
            self._is_fullscreen = True

    def toggle_mini_player(self, checked):
        if self._is_fullscreen and checked:
            QMessageBox.warning(self, "Mode Conflict", "Please exit Fullscreen Mode (F11) before entering Mini Player.")
            self.mini_player_action.setChecked(False)
            return
        self._is_mini_player = checked
        self.mini_player_action.setChecked(checked)
        if checked:
            self._original_geometry = self.geometry()
            self.setFixedSize(QSize(360, 320)) 
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
        QMessageBox.critical(self, "Media Error", f"Failed to play media: {error_name}\nCheck URL or file path.")
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
            self.play_media_url(m3u_url, name=playlist_name, is_channel=True, skip_add=True)
            return idx 
        is_hls_stream = any(line.startswith('#EXT-X-TARGETDURATION') for line in lines)
        is_multi_channel = any('#EXTINF' in line and (',' in line and len(line.split(',')[-1].strip()) > 0) for line in lines)
        if is_hls_stream and not is_multi_channel:
            idx = self._add_to_playlist(m3u_url, playlist_name, is_channel=True)
            self.current_index = idx
            self.song_list.setCurrentRow(self.current_index)
            self.media_player.stop() 
            self.update_video_view_visibility(is_playing=True) 
            self.play_media_url(m3u_url, name=playlist_name, is_channel=True, skip_add=True)
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
            self.play_media_url(m3u_url, name=playlist_name, is_channel=True, skip_add=True)
            return idx 

    def play_media_url(self, url, name=None, is_channel=False, skip_add=False):
        if url.startswith('http') or is_channel:
            media_url = QUrl(url)
        else:
            media_url = QUrl.fromLocalFile(url) 
        if not skip_add:
            idx = self._add_to_playlist(url, name=name, is_channel=is_channel)
        else:
            idx = self.current_index
        if idx != -1:
            self.current_index = idx
            self.song_list.setCurrentRow(self.current_index)
            self.media_player.stop()
            self.update_video_view_visibility(is_playing=True)
            self.media_player.setMedia(QMediaContent(media_url)) 
            self.media_player.play()
            self.play_button.setText("⏸️")
            self.playing = True
            self.update_location_bar()
            self.fetch_song_info()
            return True
        return False

    def load_songs(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Open Media File(s)", "", 
            "Media Files (*.mp3 *.wav *.flac *.m4a *.mp4 *.avi *.mkv);;All Files (*)"
        )
        if files:
            for file in files:
                self._add_to_playlist(file, os.path.basename(file))
            if self.current_index == -1:
                self.current_index = 0
                self.song_list.setCurrentRow(0)
                self.play_selected_song()

    def scan_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Scan")
        if folder:
            media_extensions = ('.mp3', '.wav', '.flac', '.m4a', '.mp4', '.avi', '.mkv', '.m3u', '.m3u8')
            files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(media_extensions)]
            for file in sorted(files):
                self._add_to_playlist(file, os.path.basename(file))
            if self.current_index == -1:
                self.current_index = 0
                self.song_list.setCurrentRow(0)
                self.play_selected_song()

    def show_stream_dialog(self):
        url, ok = QInputDialog.getText(self, "Open Stream/IPTV URL", "Enter URL (e.g., http://stream.m3u8):")
        if ok and url:
            name, ok = QInputDialog.getText(self, "Stream Name", "Enter a name for this stream/channel:")
            name = name if name else url
            if ok:
                if url.lower().endswith(('.m3u', '.m3u8')):
                    self._parse_and_load_m3u(url, name)
                else:
                    self.play_media_url(url, name=name, is_channel=True)

    def toggle_play_pause(self):
        if not self.playlist: return
        if self.playing:
            self.media_player.pause()
            self.play_button.setText("▶️")
            self.playing = False
        else:
            if self.media_player.state() == QMediaPlayer.PausedState:
                self.media_player.play()
            elif self.current_index != -1:
                self.play_selected_song()
            else:
                self.current_index = 0
                self.play_selected_song()

    def stop_song(self):
        self.media_player.stop()
        self.playing = False
        self.play_button.setText("▶️")
        self.update_video_view_visibility(is_playing=False)
        self.update_location_bar()
        self.media_player.blockSignals(True)
        self.media_player.blockSignals(False)

    def next_song(self):
        if not self.playlist: return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.song_list.setCurrentRow(self.current_index)
        self.play_selected_song()

    def prev_song(self):
        if not self.playlist: return
        self.current_index = (self.current_index - 1 + len(self.playlist)) % len(self.playlist)
        self.song_list.setCurrentRow(self.current_index)
        self.play_selected_song()

    def toggle_mute(self):
        is_muted = self.media_player.isMuted()
        self.media_player.setMuted(not is_muted)
        self.mute_button.setText("🔊" if is_muted else "🔇")

    def play_selected_song(self, item=None):
        if item is None:
            item = self.song_list.currentItem()
        if item is None:
            return
        self.current_index = self.song_list.row(item)
        url = self.playlist[self.current_index]
        self.play_media_url(url, name=item.text(), is_channel=item.data(Qt.UserRole) == 'stream_channel')

    def on_state_changed(self, state):
        if state == QMediaPlayer.EndOfMedia:
            if self.playing:
                self.playing = False
                self.play_button.setText("▶️")
                QTimer.singleShot(100, self.next_song)
        elif state == QMediaPlayer.PlayingState:
            self.playing = True
            self.play_button.setText("⏸️")
            self.update_video_view_visibility(is_playing=True)
        elif state == QMediaPlayer.PausedState:
            self.playing = False
            self.play_button.setText("▶️")

    def update_position(self):
        self.on_position_changed(self.media_player.position())

    def fetch_song_info(self):
        if not self.media_player.isMetaDataAvailable():
            self.info_clip.setText("Clip: (Loading...)")
            self.info_author.setText("Author: (Loading...)")
            self.info_show.setText("Show/Album: (Loading...)")
            self.info_copyright.setText("Copyright: (Loading...)")
            return
        def get_meta(key):
            try:
                value = self.media_player.metaData(key)
                return str(value) if value is not None else '(---)'
            except Exception:
                return '(---)'
        title = get_meta(QMediaMetaData.Title)
        author = get_meta(QMediaMetaData.Author)
        album = get_meta(QMediaMetaData.AlbumTitle)
        copyright_info = get_meta(QMediaMetaData.Copyright)
        self.info_clip.setText(f"Clip: {title}")
        self.info_author.setText(f"Author: {author}")
        self.info_show.setText(f"Show/Album: {album}")
        self.info_copyright.setText(f"Copyright: {copyright_info}")

    def show_song_info(self):
        if not self.media_player.isMetaDataAvailable():
            QMessageBox.information(self, "Current Media Info", "No Metadata available.")
            return
        info_lines = []
        keys_to_check = [
            (QMediaMetaData.Title, "Title"), 
            (QMediaMetaData.Author, "Author"), 
            (QMediaMetaData.AlbumTitle, "Album"),
            (QMediaMetaData.Date, "Date"),
            (QMediaMetaData.Duration, "Duration (ms)"),
            (QMediaMetaData.Resolution, "Resolution"),
            (QMediaMetaData.UserRating, "User Rating"),
            (QMediaMetaData.Comment, "Comment")
        ]
        for key_enum, key_name in keys_to_check:
            try:
                value = self.media_player.metaData(key_enum)
                if value:
                    info_lines.append(f"{key_name}: {value}")
            except Exception:
                continue 
        QMessageBox.information(self, "Current Media Info", "\n".join(info_lines) if info_lines else "No Metadata available.")

    def find_on_youtube(self):
        title = self.media_player.metaData(QMediaMetaData.Title)
        if title:
            webbrowser.open(f"https://www.youtube.com/results?search_query={title}")
        else:
            QMessageBox.warning(self, "Search Error", "No media title available to search.")

    def sync_to_device(self):
        import subprocess
        sync_script = resource_path("sync.py")
        if not os.path.exists(sync_script):
            QMessageBox.critical(
                self,
                "Sync Script Missing",
                f"The sync script 'sync.py' was not found at:\n{sync_script}"
            )
            return
        try:
            subprocess.Popen([sys.executable, sync_script])
        except Exception as e:
            QMessageBox.critical(
                self,
                "Sync Launch Failed",
                f"Failed to launch sync.py:\n{str(e)}"
            )

    def show_about(self):
        dialog = AboutDialog(self)
        dialog.exec_()

# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    player = MagicBoxPlayer()
    player.show()
    sys.exit(app.exec_())

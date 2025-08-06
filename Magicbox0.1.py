import sys
import os
import threading
import pygame
import requests
from io import BytesIO
from mutagen import File as MutagenFile
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QListWidget, QFileDialog, QSlider, QHBoxLayout,
    QMenuBar, QAction, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QImage


class MagicBoxPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Magic Box 🎶")
        self.setGeometry(100, 100, 600, 500)

        self.playlist = []
        self.current_index = 0
        self.duration = 0  # in seconds
        self.playing = False
        self.audio_thread = None

        pygame.mixer.init()

        main_layout = QVBoxLayout()

        # Menu bar
        menu_bar = QMenuBar(self)
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        menu_bar.addAction(about_action)
        main_layout.setMenuBar(menu_bar)

        # Now playing label
        self.now_playing = QLabel("Now Playing: None")
        main_layout.addWidget(self.now_playing)

        # Album art label
        self.album_art_label = QLabel()
        self.album_art_label.setFixedSize(200, 200)
        self.album_art_label.setScaledContents(True)
        main_layout.addWidget(self.album_art_label, alignment=Qt.AlignCenter)
        self.set_album_art_placeholder()

        # Playlist
        self.song_list = QListWidget()
        main_layout.addWidget(self.song_list)

        # Add songs button
        load_button = QPushButton("Add Songs")
        load_button.clicked.connect(self.load_songs)
        main_layout.addWidget(load_button)

        # Playback controls
        controls = QHBoxLayout()
        self.play_button = QPushButton("▶️")
        self.play_button.clicked.connect(self.play_song)
        controls.addWidget(self.play_button)

        self.stop_button = QPushButton("⏹️")
        self.stop_button.clicked.connect(self.stop_song)
        controls.addWidget(self.stop_button)

        self.next_button = QPushButton("⏭️")
        self.next_button.clicked.connect(self.next_song)
        controls.addWidget(self.next_button)

        self.prev_button = QPushButton("⏮️")
        self.prev_button.clicked.connect(self.prev_song)
        controls.addWidget(self.prev_button)

        main_layout.addLayout(controls)

        # Playback slider (seek bar)
        main_layout.addWidget(QLabel("Playback"))
        self.playback_slider = QSlider(Qt.Horizontal)
        self.playback_slider.setRange(0, 1000)  # 0-1000 scale for finer control
        self.playback_slider.sliderMoved.connect(self.seek_position)
        main_layout.addWidget(self.playback_slider)

        # Volume slider
        volume_layout = QHBoxLayout()
        volume_label = QLabel("Volume")
        volume_layout.addWidget(volume_label)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self.change_volume)
        volume_layout.addWidget(self.volume_slider)
        main_layout.addLayout(volume_layout)

        self.setLayout(main_layout)

        # Timer for playback slider update
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_playback_slider)
        self.timer.start()

    def show_about(self):
        QMessageBox.information(
            self,
            "About Magic Box",
            "Magic Box Music Player\n"
            "In Memory of Bruno, our beloved music teacher.\n"
            "Thank you for inspiring us to keep the music alive.\n\n"
            "2025 XIX Technology\n"
            "By Eggplant48 (Kevin Leblanc)"
        )

    def set_album_art_placeholder(self):
        size = 200
        image = QImage(size, size, QImage.Format_RGB32)
        image.fill(Qt.gray)
        pixmap = QPixmap.fromImage(image)
        self.album_art_label.setPixmap(pixmap)

    def load_songs(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open Music Files", "", "Audio Files (*.wav *.mp3 *.ogg)")
        if files:
            self.playlist.extend(files)
            for file in files:
                self.song_list.addItem(os.path.basename(file))

    def play_song(self):
        if not self.playlist:
            return
        if self.song_list.currentRow() != -1:
            self.current_index = self.song_list.currentRow()
        song = self.playlist[self.current_index]
        try:
            pygame.mixer.music.load(song)
            pygame.mixer.music.play()
            self.now_playing.setText(f"Now Playing: {os.path.basename(song)}")
            self.fetch_and_set_album_art(song)
            self.duration = self.get_audio_length(song)
            self.playback_slider.setValue(0)
            self.playing = True
        except Exception as e:
            QMessageBox.warning(self, "Playback Error", f"Cannot play file:\n{e}")

    def fetch_and_set_album_art(self, filepath):
        try:
            audio = MutagenFile(filepath)
            artist = None
            album = None
            if audio:
                artist = audio.tags.get('TPE1')
                if artist:
                    artist = artist.text[0]
                else:
                    artist = audio.tags.get('artist')
                    if isinstance(artist, list):
                        artist = artist[0]
                album = audio.tags.get('TALB')
                if album:
                    album = album.text[0]
                else:
                    album = audio.tags.get('album')
                    if isinstance(album, list):
                        album = album[0]

            if artist and album:
                query = f"{artist} {album}"
                url = f"https://itunes.apple.com/search?term={requests.utils.quote(query)}&entity=album&limit=1"
                response = requests.get(url)
                data = response.json()
                if data["resultCount"] > 0:
                    art_url = data["results"][0]["artworkUrl100"]
                    art_url = art_url.replace("100x100", "300x300")
                    img_response = requests.get(art_url)
                    img_data = img_response.content
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_data)
                    self.album_art_label.setPixmap(pixmap)
                    return
        except Exception as e:
            print(f"Error fetching album art: {e}")

        self.set_album_art_placeholder()

    def stop_song(self):
        pygame.mixer.music.stop()
        self.now_playing.setText("Now Playing: None")
        self.playing = False
        self.playback_slider.setValue(0)

    def next_song(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.song_list.setCurrentRow(self.current_index)
        self.play_song()

    def prev_song(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.song_list.setCurrentRow(self.current_index)
        self.play_song()

    def change_volume(self, value):
        pygame.mixer.music.set_volume(value / 100)

    def seek_position(self, position):
        if self.duration == 0:
            return
        pos_in_seconds = (position / 1000) * self.duration
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.play(start=pos_in_seconds)
            self.playing = True
        except Exception:
            pass

    def update_playback_slider(self):
        if self.playing and self.duration > 0 and not self.playback_slider.isSliderDown():
            pos_ms = pygame.mixer.music.get_pos()
            if pos_ms == -1:
                self.playing = False
                self.playback_slider.setValue(0)
                return
            pos = (pos_ms / 1000) / self.duration * 1000
            self.playback_slider.setValue(int(pos))

    def get_audio_length(self, filepath):
        try:
            audio = MutagenFile(filepath)
            if audio is not None and hasattr(audio.info, 'length'):
                return audio.info.length
        except Exception:
            pass
        return 0


if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = MagicBoxPlayer()
    player.show()
    sys.exit(app.exec_())

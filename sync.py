#!/usr/bin/env python3
import os
import sys
import shutil
import hashlib
import threading
from pathlib import Path

# Auto-select PyQt5 or PyQt6
try:
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QFileDialog, QLabel, QListWidget, QMessageBox,
        QStatusBar, QAbstractItemView, QFrame
    )
    from PyQt5.QtCore import Qt, pyqtSignal, QObject
    from PyQt5.QtGui import QFont
    USE_PYQT6 = False
except ImportError:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QFileDialog, QLabel, QListWidget, QMessageBox,
        QStatusBar, QAbstractItemView, QFrame
    )
    from PyQt6.QtCore import Qt, pyqtSignal, QObject
    from PyQt6.QtGui import QFont
    USE_PYQT6 = True

# Device detection markers
ROCKBOX_INDICATORS = ['.rockbox']
S1MP3_INDICATORS = ['SYSTEM', 'VOICE']

def is_rockbox_device(path):
    return any((path / ind).exists() for ind in ROCKBOX_INDICATORS)

def is_s1mp3_device(path):
    return any((path / ind).exists() for ind in S1MP3_INDICATORS)

def file_md5(filepath):
    hash_md5 = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except (OSError, IOError):
        return None

def find_device_mounts():
    candidates = []
    if sys.platform == "win32":
        import string
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        for drive in drives:
            p = Path(drive)
            if is_rockbox_device(p):
                candidates.append(('Rockbox', p))
            elif is_s1mp3_device(p):
                candidates.append(('S1MP3', p))
    else:
        for base in [Path('/media'), Path('/mnt'), Path('/Volumes')]:
            if base.exists():
                for user_dir in base.iterdir():
                    if user_dir.is_dir():
                        for dev in user_dir.iterdir():
                            if dev.is_dir():
                                if is_rockbox_device(dev):
                                    candidates.append(('Rockbox', dev))
                                elif is_s1mp3_device(dev):
                                    candidates.append(('S1MP3', dev))
    return candidates

class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(int, str)
    error = pyqtSignal(str)

class SyncWorker(QObject):
    def __init__(self, file_list):
        super().__init__()
        self.file_list = file_list
        self.signals = WorkerSignals()

    def run(self):
        try:
            copied = 0
            total = len(self.file_list)
            for i, (src, dest) in enumerate(self.file_list, 1):
                self.signals.progress.emit(f"Syncing ({i}/{total}): {src.name}")
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                    copied += 1
                except Exception as e:
                    self.signals.progress.emit(f"⚠️ Failed: {src.name}")
                    continue
            self.signals.finished.emit(copied, "Sync completed!")
        except Exception as e:
            self.signals.error.emit(str(e))

class MusicSyncWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MagicBox Music Sync")
        self.resize(800, 600)
        self.source_dir = None
        self.target_dir = None
        self.flatten_for_s1mp3 = False

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top controls
        top_frame = QFrame()
        top_layout = QHBoxLayout(top_frame)
        self.btn_select_source = QPushButton("📁 Select Music Folder")
        self.btn_select_source.clicked.connect(self.select_source)
        self.btn_select_target = QPushButton("💾 Select Device")
        self.btn_select_target.clicked.connect(self.select_target)
        self.lbl_device = QLabel("No device selected")
        self.lbl_device.setStyleSheet("color: gray; font-style: italic;")
        top_layout.addWidget(self.btn_select_source)
        top_layout.addWidget(self.btn_select_target)
        top_layout.addWidget(self.lbl_device)
        top_layout.addStretch()
        layout.addWidget(top_frame)

        # Music library list (read-only preview)
        list_label = QLabel("<b>Your Music Library</b>")
        layout.addWidget(list_label)
        self.music_list = QListWidget()
        self.music_list.setSelectionMode(QAbstractItemView.NoSelection)
        layout.addWidget(self.music_list)

        # Sync button
        self.btn_sync = QPushButton("🚀 Sync to Device")
        self.btn_sync.clicked.connect(self.start_sync)
        self.btn_sync.setEnabled(False)
        self.btn_sync.setFixedHeight(40)
        layout.addWidget(self.btn_sync)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Auto-detect device on startup
        self.auto_detect_device()

    def auto_detect_device(self):
        devices = find_device_mounts()
        if devices:
            typ, path = devices[0]
            self.target_dir = path
            self.lbl_device.setText(f"{typ} device: {path}")
            self.lbl_device.setStyleSheet("color: green;")
            self.flatten_for_s1mp3 = (typ == "S1MP3")
            self.check_sync_ready()

    def select_source(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Your Music Folder")
        if folder:
            self.source_dir = Path(folder)
            self.load_music_list()
            self.check_sync_ready()

    def select_target(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Your Device Root")
        if folder:
            self.target_dir = Path(folder)
            self.lbl_device.setText(f"Manual device: {folder}")
            self.lbl_device.setStyleSheet("color: blue;")
            self.flatten_for_s1mp3 = is_s1mp3_device(self.target_dir)
            self.check_sync_ready()

    def load_music_list(self):
        self.music_list.clear()
        if not self.source_dir:
            return
        try:
            files = []
            for item in sorted(self.source_dir.rglob('*')):
                if item.is_file() and item.suffix.lower() in {'.mp3', '.flac', '.ogg', '.wav', '.m4a'}:
                    files.append(str(item.relative_to(self.source_dir)))
            self.music_list.addItems(files)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load music folder:\n{e}")

    def check_sync_ready(self):
        self.btn_sync.setEnabled(bool(self.source_dir and self.target_dir))

    def analyze_sync_files(self):
        to_sync = []
        if not self.source_dir or not self.target_dir:
            return to_sync

        # Build map of existing files on device
        existing = {}
        try:
            for item in self.target_dir.rglob('*'):
                if item.is_file():
                    try:
                        rel = str(item.relative_to(self.target_dir)).lower()
                        existing[rel] = file_md5(item)
                    except:
                        pass
        except Exception:
            pass

        for src_file in self.source_dir.rglob('*'):
            if not src_file.is_file():
                continue
            if src_file.suffix.lower() not in {'.mp3', '.flac', '.ogg', '.wav', '.m4a'}:
                continue

            if self.flatten_for_s1mp3:
                dest_file = self.target_dir / src_file.name
            else:
                dest_file = self.target_dir / src_file.relative_to(self.source_dir)

            rel_key = str(dest_file.relative_to(self.target_dir)).lower()
            src_hash = file_md5(src_file)
            if src_hash is None:
                continue

            if rel_key not in existing or existing[rel_key] != src_hash:
                to_sync.append((src_file, dest_file))

        return to_sync

    def start_sync(self):
        self.status_bar.showMessage("Analyzing music files...")
        sync_files = self.analyze_sync_files()

        if not sync_files:
            QMessageBox.information(self, "Sync", "All files are up to date — nothing to sync!")
            self.status_bar.showMessage("Ready")
            return

        # Optional: ask for confirmation (remove this block if you want auto-sync)
        reply = QMessageBox.question(
            self,
            "Confirm Sync",
            f"Sync {len(sync_files)} new or updated file(s) to the device?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != (QMessageBox.Yes if not USE_PYQT6 else QMessageBox.StandardButton.Yes):
            self.status_bar.showMessage("Sync cancelled")
            return

        # Run sync in background
        self.btn_sync.setEnabled(False)
        self.worker = SyncWorker(sync_files)
        self.thread = threading.Thread(target=self.worker.run, daemon=True)
        self.worker.signals.progress.connect(self.update_status)
        self.worker.signals.finished.connect(self.sync_finished)
        self.worker.signals.error.connect(self.sync_error)
        self.thread.start()

    def update_status(self, msg):
        self.status_bar.showMessage(msg)

    def sync_finished(self, copied, msg):
        self.btn_sync.setEnabled(True)
        self.status_bar.showMessage(f"✅ {msg} ({copied} files)")
        QMessageBox.information(self, "Done", f"Sync complete!\n{copied} file(s) copied.")

    def sync_error(self, error_msg):
        self.btn_sync.setEnabled(True)
        self.status_bar.showMessage("❌ Sync failed")
        QMessageBox.critical(self, "Error", f"Sync error:\n{error_msg}")

def main():
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10) if sys.platform == "win32" else QFont("Sans", 10)
    app.setFont(font)
    window = MusicSyncWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
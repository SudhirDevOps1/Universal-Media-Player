import sys
import os
import random
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QSlider, QLabel, QListWidget, QFileDialog, 
                             QTabWidget, QFrame, QShortcut, QListWidgetItem, QComboBox, QLineEdit,
                             QMenu, QAction, QSizeGrip)
from PyQt5.QtCore import Qt, QTimer, QSize, QPoint, QRect, QEvent
from PyQt5.QtGui import QKeySequence, QPalette, QColor, QPainter, QPen, QBrush, QLinearGradient, QCursor

import vlc
from player import VLCPlayer
from playlist import PlaylistManager
from scanner import scan_folder, get_media_type
from settings import load_settings, save_settings
from utils import format_time, get_file_name, is_audio_file, is_video_file

class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            val = self.minimum() + ((self.maximum() - self.minimum()) * event.x()) / self.width()
            self.setValue(int(val))
            self.sliderMoved.emit(int(val))
        super().mousePressEvent(event)

class MusicVisualizer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)  # Faster refresh for smoothness
        self.is_playing = False
        self.mode = "bars" 
        self.hue = 0 # For color cycling
        self.bar_heights = [0] * 50 # Smooth bar transitions
        self.particles = [{"x": random.randint(0, 800), "y": random.randint(0, 200), "s": random.randint(2, 5)} for _ in range(50)]
        
    def set_playing(self, state):
        self.is_playing = state
        
    def set_mode(self, mode):
        self.mode = mode

    def update_animation(self):
        if self.is_playing:
            self.hue = (self.hue + 2) % 360
            self.update()

    def get_dynamic_color(self, offset=0, alpha=255):
        color = QColor()
        color.setHsv((self.hue + offset) % 360, 200, 255, alpha)
        return color

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        # Create a deep space background with a subtle radial glow
        bg_grad = QLinearGradient(0, 0, 0, h)
        bg_grad.setColorAt(0, QColor(5, 5, 8))
        bg_grad.setColorAt(1, QColor(0, 0, 0))
        painter.fillRect(self.rect(), bg_grad)
        
        # Draw a subtle nebula glow in the center
        center_glow = QLinearGradient(w//2, h//2, w, h)
        center_glow.setColorAt(0, self.get_dynamic_color(0, 20))
        center_glow.setColorAt(1, QColor(0,0,0,0))
        painter.setBrush(center_glow)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QPoint(w//2, h//2), w//2, h//2)

        if self.mode == "bars":
            count = 50
            bar_w = w // count - 4
            for i in range(count):
                target = random.randint(20, h - 40) if self.is_playing else 10
                if i < len(self.bar_heights):
                    self.bar_heights[i] = self.bar_heights[i] * 0.8 + target * 0.2
                    curr_h = self.bar_heights[i]
                else:
                    curr_h = target
                
                grad = QLinearGradient(0, float(h), 0, float(h - curr_h))
                grad.setColorAt(0, self.get_dynamic_color(i * 4))
                grad.setColorAt(1, self.get_dynamic_color(i * 4 + 60, 150))
                
                painter.setBrush(grad)
                painter.drawRoundedRect(int(i * (bar_w + 4)), int(h - curr_h), int(bar_w), int(curr_h), 5, 5)
                
        elif self.mode == "wave":
            painter.setPen(QPen(self.get_dynamic_color(0, 200), 5))
            points = []
            for i in range(0, w + 40, 40):
                offset = random.randint(-60, 60) if self.is_playing else 0
                points.append(QPoint(i, h // 2 + offset))
            
            for i in range(len(points) - 1):
                # Main Wave
                painter.setPen(QPen(self.get_dynamic_color(i*2), 4))
                painter.drawLine(points[i], points[i+1])
                # Outer Glow
                painter.setPen(QPen(self.get_dynamic_color(i*2 + 30, 80), 8))
                painter.drawLine(points[i], points[i+1])
        
        elif self.mode == "disco":
            for i in range(20):
                x = random.randint(0, w) if self.is_playing else w//2
                y = random.randint(0, h) if self.is_playing else h//2
                size = random.randint(20, 100) if self.is_playing else 20
                painter.setBrush(QBrush(self.get_dynamic_color(i * 15, 100)))
                painter.drawEllipse(QPoint(x, y), size, size)

        elif self.mode == "particles":
            for p in self.particles:
                if self.is_playing:
                    p["y"] = (p["y"] - p["s"]) % h
                    p["x"] = (p["x"] + random.randint(-3, 3)) % w
                painter.setBrush(QBrush(self.get_dynamic_color(int(p["y"]), 180)))
                painter.drawEllipse(QPoint(int(p["x"]), int(p["y"])), int(p["s"]), int(p["s"]))

class UniversalMediaPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setWindowTitle("Universal Media Player")
        self.resize(1000, 700)
        self.setMouseTracking(True) # Required for edge detection
        self.resizing = False
        self.resize_edge = None
        self.margin = 8 # Border for resizing
        
        # Ensure necessary directories exist automatically
        self.ensure_directories()
        
        # Load Settings
        self.settings = load_settings()
        
        # Managers
        self.playlist = PlaylistManager()
        self.playlist.add_items(self.settings.get("last_playlist", []))
        
        self.init_ui()
        
        # Player (After video_frame is created)
        self.player = VLCPlayer(int(self.video_frame.winId()))
        self.player.set_volume(self.settings.get("volume", 70))
        self.volume_slider.setValue(self.settings.get("volume", 70))
        
        # VLC Events
        self.player.set_callback(vlc.EventType.MediaPlayerEndReached, self.on_media_end)

        # Effect States
        self.current_pitch = 1.0
        self.current_speed = 1.0

        # Timer for UI updates
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui_state)
        self.timer.start()
        
        # Resume last state if available
        last_path = self.settings.get("last_media_path", "")
        if last_path and os.path.exists(last_path):
            self.play_media(last_path)
            self.player.set_time(self.settings.get("last_position", 0))
            self.player.pause() # Start paused
        
        self.apply_dark_theme()
        self.update_playlist_ui()
        
        # Install Event Filter on app level to catch resizing hover everywhere
        QApplication.instance().installEventFilter(self)

    def ensure_directories(self):
        """Automatically create necessary folders for the app."""
        folders = ["screenshots", "media", "vlc"]
        for folder in folders:
            if not os.path.exists(folder):
                try:
                    os.makedirs(folder)
                except Exception as e:
                    print(f"Error creating directory {folder}: {e}")

    def create_divider(self):
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Plain)
        line.setStyleSheet("background-color: #1A1A1A; max-height: 1px; margin: 5px 0px;")
        return line

    def init_ui(self):
        # Remove standard title bar for a truly professional look
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint)
        
        # Enable Mouse Tracking recursively for resizing
        self.setMouseTracking(True)
        
        central_widget = QWidget()
        central_widget.setMouseTracking(True)
        self.setCentralWidget(central_widget)
        main_v_layout = QVBoxLayout(central_widget)
        main_v_layout.setContentsMargins(5, 5, 5, 5) 
        main_v_layout.setSpacing(0)

        # --- Custom Title Bar ---
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(40)
        self.title_bar.setObjectName("TitleBar")
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(15, 0, 5, 0)

        app_logo = QLabel("🎬 UNIVERSAL MEDIA PLAYER")
        app_logo.setStyleSheet("font-weight: 800; color: #00FFC2; font-size: 9pt; letter-spacing: 2px;")
        title_layout.addWidget(app_logo)
        title_layout.addStretch()

        self.always_top_btn_main = QPushButton("📌")
        self.always_top_btn_main.setCheckable(True)
        self.always_top_btn_main.setFixedSize(46, 32)
        self.always_top_btn_main.setObjectName("SysBtn")
        self.always_top_btn_main.setToolTip("Always on Top (T)")
        self.always_top_btn_main.clicked.connect(self.toggle_always_on_top)
        title_layout.addWidget(self.always_top_btn_main)

        # Window Controls
        self.min_btn = QPushButton("—")
        self.max_btn = QPushButton("▢")
        self.close_btn = QPushButton("✕")
        
        for btn in [self.min_btn, self.max_btn, self.close_btn]:
            btn.setFixedSize(46, 32)
            btn.setObjectName("SysBtn")
        
        self.close_btn.setObjectName("CloseSysBtn")
        
        self.min_btn.clicked.connect(self.showMinimized)
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.close_btn.clicked.connect(self.close)
        
        title_layout.addWidget(self.min_btn)
        title_layout.addWidget(self.max_btn)
        title_layout.addWidget(self.close_btn)
        main_v_layout.addWidget(self.title_bar)

        # Main Content Layout
        main_layout = QHBoxLayout()
        self.left_container = QWidget()
        self.left_container.setMouseTracking(True)
        main_v_layout.addLayout(main_layout)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        left_panel = QVBoxLayout(self.left_container)
        left_panel.setContentsMargins(10, 10, 10, 10)
        main_layout.addWidget(self.left_container, stretch=3)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        left_panel.addWidget(self.tabs)

        # 🎬 Cinema Tab
        cinema_tab = QWidget()
        cinema_layout = QVBoxLayout(cinema_tab)
        cinema_layout.setContentsMargins(0, 0, 0, 0)
        cinema_layout.setSpacing(0)

        self.video_container = QFrame()
        self.video_container.setStyleSheet("background-color: #000; border-radius: 12px; border: 1px solid #1A1A1A;")
        video_vbox = QVBoxLayout(self.video_container)
        video_vbox.setContentsMargins(0, 0, 0, 0)

        self.video_frame = QFrame()
        self.video_frame.setMouseTracking(True)
        self.video_frame.mouseDoubleClickEvent = self.video_double_click
        self.video_frame.setContextMenuPolicy(Qt.NoContextMenu)
        video_vbox.addWidget(self.video_frame)
        cinema_layout.addWidget(self.video_container)
        self.tabs.addTab(cinema_tab, "🎬 Cinema")

        # 🎵 Studio Tab
        music_tab = QWidget()
        music_layout = QVBoxLayout(music_tab)
        music_layout.setContentsMargins(0, 0, 0, 0)
        
        self.visualizer = MusicVisualizer()
        self.visualizer.mouseDoubleClickEvent = self.video_double_click
        music_layout.addWidget(self.visualizer)
        
        self.music_info = QLabel("🎵 Ready to Stream")
        self.music_info.setObjectName("MediaTitle")
        self.music_info.setAlignment(Qt.AlignCenter)
        self.music_info.setStyleSheet("padding: 10px; font-size: 14pt; color: #00FFC2; font-weight: 700;")
        music_layout.addWidget(self.music_info)
        self.tabs.addTab(music_tab, "🎵 Studio")

        # --- Controls Area (VLC Style) ---
        self.controls_container = QWidget()
        controls = QVBoxLayout(self.controls_container)
        controls.setContentsMargins(0, 5, 0, 0)
        controls.setSpacing(5)
        left_panel.addWidget(self.controls_container)

        # Seek Bar
        seek_layout = QHBoxLayout()
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("TimeLabel")
        self.seek_slider = ClickableSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self.set_position)
        seek_layout.addWidget(self.seek_slider)
        seek_layout.addWidget(self.time_label)
        controls.addLayout(seek_layout)

        # Toolbar
        self.controls_toolbar = QWidget()
        self.controls_toolbar.setObjectName("ControlsToolbar")
        btn_layout = QHBoxLayout(self.controls_toolbar)
        btn_layout.setSpacing(10)
        btn_layout.setContentsMargins(10, 5, 10, 5)
        
        # Group 1: Toggle Buttons
        self.shuffle_btn = QPushButton("🔀")
        self.shuffle_btn.setCheckable(True)
        self.shuffle_btn.setObjectName("ControlBtn")
        self.shuffle_btn.setToolTip("Shuffle (S)")
        self.shuffle_btn.clicked.connect(self.toggle_shuffle)
        
        self.repeat_btn = QPushButton("🔁")
        self.repeat_btn.setObjectName("ControlBtn")
        self.repeat_btn.setToolTip("Repeat Mode (R)")
        self.repeat_btn.clicked.connect(self.toggle_repeat)
        
        # Group 2: Playback
        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setObjectName("ControlBtn")
        self.prev_btn.clicked.connect(self.play_previous)
        
        self.rev_btn = QPushButton("⏪")
        self.rev_btn.setObjectName("ControlBtn")
        self.rev_btn.clicked.connect(lambda: self.seek_relative(-10000))

        self.play_btn = QPushButton("▶")
        self.play_btn.setObjectName("ActionBtn")
        self.play_btn.setFixedSize(40, 40)
        self.play_btn.clicked.connect(self.toggle_play)
        
        self.fwd_btn = QPushButton("⏩")
        self.fwd_btn.setObjectName("ControlBtn")
        self.fwd_btn.clicked.connect(lambda: self.seek_relative(10000))

        self.next_btn = QPushButton("⏭")
        self.next_btn.setObjectName("ControlBtn")
        self.next_btn.clicked.connect(self.play_next)
        
        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setObjectName("ControlBtn")
        self.stop_btn.clicked.connect(self.stop_media)

        btn_layout.addStretch()
        btn_layout.addWidget(self.shuffle_btn)
        btn_layout.addWidget(self.repeat_btn)
        btn_layout.addSpacing(15)
        btn_layout.addWidget(self.prev_btn)
        btn_layout.addWidget(self.rev_btn)
        btn_layout.addWidget(self.play_btn)
        btn_layout.addWidget(self.fwd_btn)
        btn_layout.addWidget(self.next_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addSpacing(15)
        
        # Settings & Volume
        self.settings_btn = QPushButton("⚙️")
        self.settings_btn.setObjectName("ControlBtn")
        self.settings_btn.setToolTip("Advanced Settings")
        self.settings_btn.clicked.connect(self.toggle_settings_panel)
        btn_layout.addWidget(self.settings_btn)
        
        btn_layout.addStretch()
        
        # Right Side (Volume)
        volume_container = QWidget()
        volume_layout = QHBoxLayout(volume_container)
        volume_layout.setContentsMargins(0, 0, 0, 0)
        volume_layout.setSpacing(5)
        
        vol_label = QLabel("VOL")
        vol_label.setStyleSheet("color: #666; font-size: 8pt; font-weight: bold;")
        volume_layout.addWidget(vol_label)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setObjectName("VolumeSlider")
        self.volume_slider.valueChanged.connect(self.set_volume)
        volume_layout.addWidget(self.volume_slider)
        
        self.boost_label = QLabel("")
        self.boost_label.setStyleSheet("color: #FF4B2B; font-weight: bold; font-size: 8pt;")
        volume_layout.addWidget(self.boost_label)
        
        btn_layout.addWidget(volume_container)
        
        self.playback_timer = QLabel("00:00:00")
        self.playback_timer.setStyleSheet("font-family: Consolas; color: #888; font-size: 9pt;")
        btn_layout.addWidget(self.playback_timer)
        
        controls.addWidget(self.controls_toolbar)

        # --- Settings Overlay Panel ---
        self.settings_panel = QFrame(self)
        self.settings_panel.setObjectName("SettingsPanel")
        self.settings_panel.setFixedWidth(300)
        self.settings_panel.hide()
        
        settings_layout = QVBoxLayout(self.settings_panel)
        settings_layout.setContentsMargins(15, 15, 15, 15)
        
        settings_header = QLabel("⚡ STUDIO SETTINGS")
        settings_header.setStyleSheet("color: #00FFC2; font-weight: 800; font-size: 10pt; margin-bottom: 10px;")
        settings_layout.addWidget(settings_header)
        
        speed_header = QHBoxLayout()
        speed_header.addWidget(QLabel("PLAYBACK SPEED"))
        self.speed_label = QLabel("1.0x")
        self.speed_label.setStyleSheet("color: #00FFC2; font-weight: bold;")
        speed_header.addStretch()
        speed_header.addWidget(self.speed_label)
        settings_layout.addLayout(speed_header)
        
        speed_layout = QHBoxLayout()
        for s in [0.5, 1.0, 1.5, 2.0]:
            btn = QPushButton(f"{s}x")
            btn.clicked.connect(lambda checked, val=s: self.change_speed(val))
            speed_layout.addWidget(btn)
        settings_layout.addLayout(speed_layout)
        
        settings_layout.addWidget(QLabel("VOICE ENGINE"))
        self.voice_preset = QComboBox()
        self.voice_preset.addItems(["Normal", "Girl/Child", "Boy/Man", "Demon", "Chipmunk", "Radio", "Echo/Deep", "Robot"])
        self.voice_preset.currentTextChanged.connect(self.apply_voice_preset)
        settings_layout.addWidget(self.voice_preset)

        settings_layout.addWidget(QLabel("VISUALIZER MODE"))
        self.viz_preset = QComboBox()
        self.viz_preset.addItems(["bars", "wave", "disco", "particles"])
        self.viz_preset.currentTextChanged.connect(self.visualizer.set_mode)
        settings_layout.addWidget(self.viz_preset)
        
        pitch_header = QHBoxLayout()
        pitch_header.addWidget(QLabel("PITCH"))
        self.pitch_label = QLabel("1.0")
        self.pitch_label.setStyleSheet("color: #00FFC2; font-weight: bold;")
        pitch_header.addStretch()
        pitch_header.addWidget(self.pitch_label)
        settings_layout.addLayout(pitch_header)
        
        self.pitch_slider = QSlider(Qt.Horizontal)
        self.pitch_slider.setRange(50, 200)
        self.pitch_slider.setValue(100)
        self.pitch_slider.valueChanged.connect(self.set_pitch)
        settings_layout.addWidget(self.pitch_slider)
        
        settings_layout.addWidget(self.create_divider())
        
        self.loop_btn = QPushButton("🔁 AB LOOP: OFF")
        self.loop_btn.clicked.connect(self.toggle_ab_loop)
        settings_layout.addWidget(self.loop_btn)
        
        self.adj_btn = QPushButton("💡 ADJUST VIDEO")
        self.adj_btn.clicked.connect(self.toggle_brightness_control)
        settings_layout.addWidget(self.adj_btn)
        
        self.reset_btn = QPushButton("🔄 RESET ALL EFFECTS")
        self.reset_btn.setStyleSheet("background: #221111; color: #FF5555; border: 1px solid #442222; padding: 10px;")
        self.reset_btn.clicked.connect(self.reset_audio_effects)
        settings_layout.addWidget(self.reset_btn)

        settings_layout.addWidget(self.create_divider())
        
        # Additional Video Controls
        settings_layout.addWidget(QLabel("VIDEO EFFECTS"))
        
        sat_layout = QHBoxLayout()
        sat_layout.addWidget(QLabel("Saturation"))
        self.sat_minus = QPushButton("-")
        self.sat_minus.clicked.connect(lambda: self.adjust_video('Saturation', -0.1))
        self.sat_plus = QPushButton("+")
        self.sat_plus.clicked.connect(lambda: self.adjust_video('Saturation', 0.1))
        sat_layout.addWidget(self.sat_minus)
        sat_layout.addWidget(self.sat_plus)
        settings_layout.addLayout(sat_layout)

        con_layout = QHBoxLayout()
        con_layout.addWidget(QLabel("Contrast"))
        self.con_minus = QPushButton("-")
        self.con_minus.clicked.connect(lambda: self.adjust_video('Contrast', -0.1))
        self.con_plus = QPushButton("+")
        self.con_plus.clicked.connect(lambda: self.adjust_video('Contrast', 0.1))
        con_layout.addWidget(self.con_minus)
        con_layout.addWidget(self.con_plus)
        settings_layout.addLayout(con_layout)

        settings_layout.addStretch()

        # Right Panel (Playlist)
        self.right_container = QWidget()
        self.right_container.setMouseTracking(True)
        self.right_container.setObjectName("SidePanel")
        self.right_container.setFixedWidth(280)
        right_panel = QVBoxLayout(self.right_container)
        right_panel.setContentsMargins(15, 20, 15, 20)
        main_layout.addWidget(self.right_container)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("QUEUE"))
        header_layout.addStretch()
        self.item_count_label = QLabel("0 Items")
        header_layout.addWidget(self.item_count_label)
        right_panel.addLayout(header_layout)
        
        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search your media...")
        self.search_input.textChanged.connect(self.filter_playlist)
        right_panel.addWidget(self.search_input)
        
        self.playlist_widget = QListWidget()
        self.playlist_widget.setAcceptDrops(True)
        self.playlist_widget.setDragEnabled(True)
        self.playlist_widget.setDragDropMode(QListWidget.InternalMove)
        self.playlist_widget.model().rowsMoved.connect(self.on_playlist_reordered)
        self.playlist_widget.itemDoubleClicked.connect(self.play_selected)
        right_panel.addWidget(self.playlist_widget)

        file_btns = QHBoxLayout()
        open_file_btn = QPushButton("Add Files")
        open_file_btn.clicked.connect(self.open_file)
        open_folder_btn = QPushButton("Add Folder")
        open_folder_btn.clicked.connect(self.open_folder)
        file_btns.addWidget(open_file_btn)
        file_btns.addWidget(open_folder_btn)
        right_panel.addLayout(file_btns)

        playlist_ctrls = QHBoxLayout()
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self.remove_selected)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_playlist)
        playlist_ctrls.addWidget(remove_btn)
        playlist_ctrls.addWidget(clear_btn)
        right_panel.addLayout(playlist_ctrls)

        # Footer Branding
        footer = QLabel("Designed by Sudhir Kumar")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("color: #333; font-size: 8pt; margin-top: 10px; font-style: italic;")
        right_panel.addWidget(footer)

        # Size Grip for resizing in frameless mode
        self.sizegrip = QSizeGrip(self)
        self.sizegrip.setFixedSize(16, 16)
        self.sizegrip.setStyleSheet("background: transparent;")
        right_panel.addWidget(self.sizegrip, 0, Qt.AlignRight | Qt.AlignBottom)

        # Shortcuts
        self.sc_space = QShortcut(QKeySequence("Space"), self)
        self.sc_space.setContext(Qt.ApplicationShortcut)
        self.sc_space.activated.connect(self.toggle_play)
        
        self.sc_f = QShortcut(QKeySequence("F"), self)
        self.sc_f.setContext(Qt.ApplicationShortcut)
        self.sc_f.activated.connect(self.toggle_fullscreen)
        
        self.sc_m = QShortcut(QKeySequence("M"), self)
        self.sc_m.setContext(Qt.ApplicationShortcut)
        self.sc_m.activated.connect(self.toggle_mute)
        
        self.sc_esc = QShortcut(QKeySequence("Esc"), self)
        self.sc_esc.setContext(Qt.ApplicationShortcut)
        self.sc_esc.activated.connect(self.exit_fullscreen)
        
        self.sc_search = QShortcut(QKeySequence("Ctrl+F"), self)
        self.sc_search.setContext(Qt.ApplicationShortcut)
        self.sc_search.activated.connect(lambda: self.search_input.setFocus())
        
        self.sc_mini = QShortcut(QKeySequence("P"), self)
        self.sc_mini.setContext(Qt.ApplicationShortcut)
        self.sc_mini.activated.connect(self.toggle_mini_player)
        
        self.sc_alt_enter = QShortcut(QKeySequence("Alt+Enter"), self)
        self.sc_alt_enter.setContext(Qt.ApplicationShortcut)
        self.sc_alt_enter.activated.connect(self.toggle_fullscreen)
        
        self.sc_close = QShortcut(QKeySequence("Ctrl+W"), self)
        self.sc_close.setContext(Qt.ApplicationShortcut)
        self.sc_close.activated.connect(self.close)
        
        self.sc_minimize = QShortcut(QKeySequence("Ctrl+M"), self)
        self.sc_minimize.setContext(Qt.ApplicationShortcut)
        self.sc_minimize.activated.connect(self.showMinimized)
        
        self.sc_left = QShortcut(QKeySequence("Left"), self)
        self.sc_left.setContext(Qt.ApplicationShortcut)
        self.sc_left.activated.connect(lambda: self.seek_relative(-10000))
        
        self.sc_right = QShortcut(QKeySequence("Right"), self)
        self.sc_right.setContext(Qt.ApplicationShortcut)
        self.sc_right.activated.connect(lambda: self.seek_relative(10000))
        
        self.sc_up = QShortcut(QKeySequence("Up"), self)
        self.sc_up.setContext(Qt.ApplicationShortcut)
        self.sc_up.activated.connect(lambda: self.volume_slider.setValue(self.volume_slider.value() + 5))
        
        self.sc_down = QShortcut(QKeySequence("Down"), self)
        self.sc_down.setContext(Qt.ApplicationShortcut)
        self.sc_down.activated.connect(lambda: self.volume_slider.setValue(self.volume_slider.value() - 5))
        
        self.sc_snap = QShortcut(QKeySequence("Ctrl+S"), self)
        self.sc_snap.setContext(Qt.ApplicationShortcut)
        self.sc_snap.activated.connect(self.take_screenshot)
        
        self.sc_top = QShortcut(QKeySequence("T"), self)
        self.sc_top.setContext(Qt.ApplicationShortcut)
        self.sc_top.activated.connect(self.toggle_always_on_top)
        
        self.sc_loop = QShortcut(QKeySequence("A"), self)
        self.sc_loop.setContext(Qt.ApplicationShortcut)
        self.sc_loop.activated.connect(self.toggle_ab_loop)
        
        self.sc_bright = QShortcut(QKeySequence("B"), self)
        self.sc_bright.setContext(Qt.ApplicationShortcut)
        self.sc_bright.activated.connect(self.toggle_brightness_control)
        
        self.sc_playlist = QShortcut(QKeySequence("Ctrl+L"), self)
        self.sc_playlist.setContext(Qt.ApplicationShortcut)
        self.sc_playlist.activated.connect(self.toggle_playlist)
        
        self.setMinimumWidth(800)
        self.setMinimumHeight(500)

    def apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #050505; }
            QWidget { 
                background-color: #050505; 
                color: #E0E0E0; 
                font-family: 'Segoe UI', system-ui, sans-serif; 
            }
            
            /* Custom Title Bar Styling */
            QWidget#TitleBar { 
                background-color: #0A0A0A; 
                border-bottom: 2px solid #1A1A1A; 
            }
            
            QTabWidget::pane { 
                border: none; 
                background: #050505; 
                margin-top: -1px;
            }
            QTabBar::tab {
                background: #0F0F0F;
                color: #666;
                padding: 10px 30px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                margin-right: 5px;
                font-weight: bold;
                border-top: 3px solid transparent;
                font-size: 9pt;
                letter-spacing: 1px;
            }
            QTabBar::tab:selected {
                background: #050505;
                color: #00FFC2;
                border-top: 3px solid #00FFC2;
            }
            QTabBar::tab:hover {
                background: #151515;
                color: #AAA;
            }

            /* ScrollBar Styling */
            QScrollBar:vertical {
                border: none;
                background: #0A0A0A;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #252525;
                min-height: 25px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00FFC2;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }

            /* Search & Inputs */
            QLineEdit {
                background: #101010;
                border: 1px solid #252525;
                padding: 10px;
                border-radius: 8px;
                color: white;
                font-size: 9pt;
            }
            QLineEdit:focus {
                border: 1px solid #00FFC2;
                background: #151515;
            }

            /* Playlist Cards */
            QListWidget {
                background: #050505;
                border: none;
                outline: none;
                padding: 10px;
            }
            QListWidget::item {
                background: #151515;
                margin-bottom: 10px;
                padding: 18px;
                border-radius: 12px;
                color: #CCC;
                border: 1px solid #222;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00FFC2, stop:1 #008F6B);
                color: #000;
                font-weight: 800;
                border: 1px solid #FFF;
            }
            QListWidget::item:hover {
                background: #252525;
                border: 1px solid #444;
            }

            /* Global Button Styling */
            QPushButton {
                background: #1A1A1A;
                border: 1px solid #333;
                border-radius: 8px;
                padding: 8px 12px;
                color: #EEE;
                font-weight: 700;
                font-size: 10pt;
            }
            QPushButton:hover {
                background: #2A2A2A;
                color: #00FFC2;
                border-color: #00FFC2;
            }
            QPushButton:pressed {
                background: #00FFC2;
                color: #000;
            }
                        
            /* Main Play Button */
            QPushButton#ActionBtn {
                background: #1A1A1A;
                border: 2px solid #00FFC2;
                border-radius: 20px;
                font-size: 16pt;
                color: #00FFC2;
                min-width: 40px;
                min-height: 40px;
                margin: 0px 4px;
            }
            QPushButton#ActionBtn:hover {
                background: #00FFC2;
                color: #000;
                border: 2px solid #FFF;
            }
                        
            /* System Title Bar Buttons */
            #SysBtn {
                background: transparent;
                border: none;
                border-radius: 0px;
                font-size: 10pt;
                color: #FFF;
            }
            #SysBtn:hover {
                background: #333;
            }
            #SysBtn:checked {
                background: #00FFC2;
                color: #000;
            }
            #CloseSysBtn {
                background: transparent;
                border: none;
                border-radius: 0px;
                font-size: 10pt;
                color: #FFF;
            }
            #CloseSysBtn:hover {
                background: #E81123;
                color: #FFF;
            }

            /* Controls Toolbar Buttons */
            #ControlBtn {
                min-width: 32px;
                min-height: 32px;
                font-size: 12pt;
                background: #1A1A1A;
                border: 1px solid #333;
                border-radius: 16px;
            }
            #ControlBtn:hover {
                background: #252525;
                color: #00FFC2;
                border: 1px solid #00FFC2;
            }
            #ControlBtn:checked {
                background: #00FFC2;
                color: #000;
            }
            
            /* Toolbar Container */
            #ControlsToolbar {
                background: #0A0A0A;
                border-top: 1px solid #1A1A1A;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
            }
            
            /* Sliders */
            QSlider::groove:horizontal {
                border: none;
                height: 6px;
                background: #1A1A1A;
                margin: 2px 0;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #00FFC2;
                border: 2px solid #FFF;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider#VolumeSlider::handle:horizontal {
                width: 12px;
                height: 12px;
                margin: -3px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00FFC2, stop:1 #008F6B);
                border-radius: 3px;
            }

            QLabel {
                font-size: 9pt;
                font-weight: 500;
                background: transparent;
            }
            QStatusBar {
                background-color: #080808;
                color: #00FFC2;
                font-weight: bold;
                border-top: 1px solid #1A1A1A;
                padding: 5px;
            }
            
            QComboBox {
                background: #121212;
                border: 1px solid #252525;
                border-radius: 6px;
                padding: 5px 10px;
                color: white;
            }
            QComboBox:hover {
                border: 1px solid #00FFC2;
            }
            QComboBox::drop-down { border: none; }
            QComboBox QAbstractItemView {
                background: #121212;
                selection-background-color: #00FFC2;
                selection-color: black;
                border: 1px solid #333;
                outline: none;
                padding: 5px;
            }
            
            /* Container Frames */
            #CinemaToolbar {
                background: #080808;
                border-top: 1px solid #1F1F1F;
            }
            
            /* Settings Panel */
            #SettingsPanel {
                background: #0F0F0F;
                border: 2px solid #252525;
                border-radius: 15px;
            }
            #SettingsPanel QLabel {
                color: #AAA;
                font-size: 9pt;
            }
            #SettingsPanel QPushButton {
                background: #1A1A1A;
                border: 1px solid #333;
                font-size: 9pt;
                padding: 6px;
            }
            #SettingsPanel QPushButton:hover {
                border-color: #00FFC2;
                color: #00FFC2;
            }
            
            QPushButton#SmallBtn {
                padding: 4px 8px;
                font-size: 8pt;
                background: #151515;
                border: 1px solid #252525;
            }
            QPushButton#SmallBtn:hover {
                border-color: #00FFC2;
            }
        """)

    def open_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Open Media", "", "Media (*.mp3 *.wav *.mp4 *.mkv *.avi *.mov *.flac *.ogg)")
        if files:
            self.playlist.add_items(files)
            self.update_playlist_ui()
            self.play_media(files[0])

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            files = scan_folder(folder)
            self.playlist.add_items(files)
            self.update_playlist_ui()

    def toggle_settings_panel(self):
        """Toggles the visibility and position of the advanced settings panel."""
        if self.settings_panel.isVisible():
            self.settings_panel.hide()
        else:
            self.settings_panel.show() 
            self.settings_panel.adjustSize()
            
            # Position the panel above the settings button
            pos = self.settings_btn.mapTo(self, QPoint(0, 0))
            x = pos.x() - self.settings_panel.width() + self.settings_btn.width()
            y = pos.y() - self.settings_panel.height() - 10
            
            # Ensure panel stays within window bounds
            x = max(10, min(x, self.width() - self.settings_panel.width() - 10))
            y = max(10, min(y, self.height() - self.settings_panel.height() - 10))
            
            self.settings_panel.move(x, y)
            self.settings_panel.raise_()

    def update_playlist_ui(self):
        self.playlist_widget.clear()
        for path in self.playlist.items:
            icon = "🎬" if get_media_type(path) == 'video' else "🎵"
            item = QListWidgetItem(f"{icon} {get_file_name(path)}")
            item.setData(Qt.UserRole, path)
            self.playlist_widget.addItem(item)
        self.item_count_label.setText(f"{len(self.playlist.items)} Items")

    def filter_playlist(self):
        """Filters the playlist based on search input."""
        query = self.search_input.text().lower()
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            item.setHidden(query not in item.text().lower())

    def play_media(self, path):
        if not path: return
        self.player.play(path)
        self.play_btn.setText("⏸")
        self.visualizer.set_playing(True)
        self.update_playlist_selection()
        
        file_name = get_file_name(path)
        self.music_info.setText(file_name)
        
        media_type = get_media_type(path)
        if media_type == 'video':
            self.tabs.setCurrentIndex(0)
        else:
            self.tabs.setCurrentIndex(1) 

    def update_playlist_selection(self):
        """Highlights the currently playing item with a professional card style."""
        current_idx = self.playlist.current_index
        if 0 <= current_idx < self.playlist_widget.count():
            self.playlist_widget.setCurrentRow(current_idx)
            self.playlist_widget.scrollToItem(self.playlist_widget.currentItem())
            
            for i in range(self.playlist_widget.count()):
                item = self.playlist_widget.item(i)
                is_current = (i == current_idx)
                
                # We use the stylesheet classes for professional look, 
                # but we can fine-tune individual item properties here if needed.
                font = item.font()
                font.setBold(is_current)
                item.setFont(font)
                
                if is_current:
                    item.setText(item.text().replace("🎵 ", "🔊 ").replace("🎬 ", "🎞️ "))
                else:
                    item.setText(item.text().replace("🔊 ", "🎵 ").replace("🎞️ ", "🎬 "))

    def on_media_end(self, event):
        """Called when a media file finishes playing."""
        # Use QTimer to call next from main thread
        QTimer.singleShot(0, self.play_next)

    def toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
            self.play_btn.setText("▶")
            self.visualizer.set_playing(False)
        else:
            self.player.play()
            self.play_btn.setText("⏸")
            self.visualizer.set_playing(True)

    def toggle_shuffle(self):
        self.playlist.shuffle = self.shuffle_btn.isChecked()
        if self.playlist.shuffle:
            self.shuffle_btn.setStyleSheet("background-color: #42a2da;")
        else:
            self.shuffle_btn.setStyleSheet("")

    def toggle_repeat(self):
        modes = ['none', 'one', 'all']
        icons = {'none': '🔁', 'one': '🔂', 'all': '🔁'}
        colors = {'none': '', 'one': '#42a2da', 'all': '#42a2da'}
        
        current = self.playlist.repeat
        next_idx = (modes.index(current) + 1) % len(modes)
        new_mode = modes[next_idx]
        
        self.playlist.repeat = new_mode
        self.repeat_btn.setText(icons[new_mode])
        self.repeat_btn.setStyleSheet(f"background-color: {colors[new_mode]};")

    def stop_media(self):
        self.player.stop()
        self.play_btn.setText("▶")
        self.visualizer.set_playing(False)

    def play_next(self):
        path = self.playlist.get_next()
        if path: self.play_media(path)

    def play_previous(self):
        path = self.playlist.get_previous()
        if path: self.play_media(path)

    def on_playlist_reordered(self, parent, start, end, destination, row):
        """Updates the internal playlist when the UI list is reordered."""
        new_items = []
        for i in range(self.playlist_widget.count()):
            path = self.playlist_widget.item(i).data(Qt.UserRole)
            new_items.append(path)
        self.playlist.items = new_items
        
    def play_selected(self, item):
        index = self.playlist_widget.row(item)
        path = self.playlist.set_current(index)
        self.play_media(path)

    def remove_selected(self):
        idx = self.playlist_widget.currentRow()
        if idx >= 0:
            self.playlist.remove_item(idx)
            self.update_playlist_ui()

    def clear_playlist(self):
        self.playlist.clear()
        self.update_playlist_ui()
        self.stop_media()
        self.music_info.setText("🎵 Ready to play...")
        self.time_label.setText("00:00 / 00:00")
        self.seek_slider.setValue(0)

    def set_volume(self, value):
        self.player.set_volume(value)
        self.volume_slider.setToolTip(f"Volume: {value}%")
        if value > 100:
            self.boost_label.setText(f"BOOST! {value}%")
        else:
            self.boost_label.setText("")

    def set_pitch(self, value):
        """Unified method for pitch slider changes."""
        self.current_pitch = value / 100.0
        self.update_playback_rate()

    def change_speed(self, val):
        """Unified method for speed button changes."""
        self.current_speed = val
        self.update_playback_rate()

    def apply_voice_preset(self, preset):
        """Applies voice character presets without changing user speed."""
        presets = {
            "Normal": 1.0, 
            "Girl/Child": 1.3, 
            "Boy/Man": 0.85,
            "Demon": 0.6, 
            "Chipmunk": 1.7,
            "Radio": 1.1,
            "Echo/Deep": 0.75,
            "Robot": 0.9
        }
        self.current_pitch = presets.get(preset, 1.0)
        self.update_playback_rate()
        self.music_info.setText(f"🎭 Voice: {preset}")

    def update_playback_rate(self, rate=None):
        """The single source of truth for all Speed/Pitch/Voice changes.
        Now decouples speed from pitch logic correctly."""
        # Use provided rate or calculate from current states
        final_rate = self.current_speed * self.current_pitch
        
        self.player.set_rate(final_rate)
        self.speed_label.setText(f"{self.current_speed:.1f}x")
        self.pitch_label.setText(f"{self.current_pitch:.1f}")
        
        # Block signals to prevent recursion when updating slider
        self.pitch_slider.blockSignals(True)
        self.pitch_slider.setValue(int(self.current_pitch * 100))
        self.pitch_slider.blockSignals(False)

    def reset_audio_effects(self):
        """Resets all audio modifications to default."""
        self.voice_preset.setCurrentText("Normal")
        self.current_pitch = 1.0
        self.current_speed = 1.0
        self.update_playback_rate()
        self.music_info.setText("🎵 Audio effects reset")

    def toggle_brightness_control(self):
        """Toggles a simple UI overlay or VLC filter for brightness (requires adjustment)"""
        current = self.player.player.video_get_adjust_int(vlc.VideoAdjustOption.Enable)
        self.player.player.video_set_adjust_int(vlc.VideoAdjustOption.Enable, 1 if not current else 0)
        self.music_info.setText(f"💡 Video Adjust: {'ON' if not current else 'OFF'}")

    def adjust_video(self, option, delta):
        """Dynamically adjusts video parameters like Saturation and Contrast."""
        # Enable adjustment if not already enabled
        self.player.player.video_set_adjust_int(vlc.VideoAdjustOption.Enable, 1)
        
        mapping = {
            'Saturation': vlc.VideoAdjustOption.Saturation,
            'Contrast': vlc.VideoAdjustOption.Contrast,
            'Brightness': vlc.VideoAdjustOption.Brightness,
            'Hue': vlc.VideoAdjustOption.Hue
        }
        
        opt = mapping.get(option)
        if opt is not None:
            current = self.player.player.video_get_adjust_float(opt)
            self.player.player.video_set_adjust_float(opt, current + delta)
            self.music_info.setText(f"🎬 {option}: {(current+delta):.1f}")

    def set_position(self):
        self.player.set_position(self.seek_slider.value() / 1000.0)

    def take_screenshot(self):
        """Captures a screenshot of the video."""
        if not os.path.exists("screenshots"):
            os.makedirs("screenshots")
        from datetime import datetime
        filename = f"screenshots/snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        self.player.player.video_take_snapshot(0, filename, 0, 0)
        self.music_info.setText(f"📸 Screenshot saved:\n{os.path.basename(filename)}")

    def toggle_always_on_top(self):
        """Toggles 'Always on Top' window state smoothly without breaking controls."""
        is_top = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        new_state = not is_top
        
        # Capture current geometry and state to restore them
        curr_geo = self.geometry()
        is_max = self.isMaximized()
        
        self.setWindowFlag(Qt.WindowStaysOnTopHint, new_state)
        
        # Sync all pin buttons
        style = "background-color: #00FFC2; color: #000;" if new_state else ""
        for btn_attr in ['always_top_btn', 'always_top_btn_main']:
            if hasattr(self, btn_attr):
                btn = getattr(self, btn_attr)
                btn.blockSignals(True)
                btn.setChecked(new_state)
                btn.setStyleSheet(style)
                btn.blockSignals(False)
            
        self.show() # Refresh window
        
        # Restore state if it was maximized
        if is_max:
            self.showMaximized()
        else:
            self.setGeometry(curr_geo)
            
        state = "ON" if new_state else "OFF"
        if self.music_info.isVisible():
            self.music_info.setText(f"📌 Always on Top: {state}")
        self.statusBar().showMessage(f"Always on Top: {state}", 2000)

    def toggle_ab_loop(self):
        """Toggle A-B repeat functionality."""
        if not hasattr(self, 'loop_a'):
            self.loop_a = self.player.get_time()
            self.loop_btn.setText("AB Loop: A Set")
            self.loop_btn.setStyleSheet("background-color: #f39c12;")
        elif not hasattr(self, 'loop_b'):
            self.loop_b = self.player.get_time()
            if self.loop_b <= self.loop_a:
                del self.loop_a
                del self.loop_b
                self.loop_btn.setText("AB Loop: OFF")
                self.loop_btn.setStyleSheet("")
                return
            self.loop_btn.setText("AB Loop: ON")
            self.loop_btn.setStyleSheet("background-color: #27ae60;")
        else:
            del self.loop_a
            del self.loop_b
            self.loop_btn.setText("AB Loop: OFF")
            self.loop_btn.setStyleSheet("")

    def seek_relative(self, ms):
        current = self.player.get_time()
        self.player.set_time(current + ms)

    def toggle_fullscreen(self):
        # Determine if we are in Music mode
        is_music = self.tabs.currentIndex() == 1
        
        # If it's music, we disable fullscreen to keep controls accessible as per user request
        if is_music:
            self.music_info.setText("🎵 Fullscreen is disabled for Music to keep controls visible.")
            QTimer.singleShot(2000, lambda: self.music_info.setText(get_file_name(self.playlist.get_current()) if self.playlist.get_current() else "🎵 Ready to Stream"))
            return

        # VLC Fullscreen (handles the video layer)
        is_full = self.player.get_fullscreen()
        new_state = not is_full
        
        # Window Fullscreen (handles the GUI)
        if new_state:
            self.title_bar.hide()
            self.showFullScreen()
            self.right_container.hide()
            self.controls_container.hide()
            self.tabs.tabBar().hide()
            # Set central widget layout margins to 0
            self.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
            self.player.set_fullscreen(True)
        else:
            self.title_bar.show()
            self.showNormal()
            self.right_container.show()
            self.controls_container.show()
            self.tabs.tabBar().show()
            self.centralWidget().layout().setContentsMargins(0, 0, 0, 0) # Keep 0 for modern look
            self.player.set_fullscreen(False)

    def toggle_mini_player(self):
        """Toggles a compact mini player mode."""
        if self.right_container.isVisible():
            self.right_container.hide()
            self.tabs.setCurrentIndex(1) # Switch to studio/music view
            self.setFixedWidth(400)
            self.setFixedHeight(300)
        else:
            self.right_container.show()
            self.setMinimumWidth(800)
            self.setMinimumHeight(500)
            self.resize(1000, 700)

    def toggle_playlist(self):
        """Toggles the visibility of the playlist side panel."""
        if self.right_container.isVisible():
            self.right_container.hide()
            self.statusBar().showMessage("Playlist Hidden (Ctrl+L)", 2000)
        else:
            self.right_container.show()
            self.statusBar().showMessage("Playlist Shown (Ctrl+L)", 2000)

    def exit_fullscreen(self):
        if self.isFullScreen():
            self.toggle_fullscreen()

    def show_context_menu(self, pos):
        """Right-click menu for controls, especially useful in fullscreen."""
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1A1A1A; color: white; border: 1px solid #333; } QMenu::item:selected { background-color: #00FFC2; color: black; }")
        
        fs_text = "Exit Fullscreen (Esc)" if self.isFullScreen() else "Enter Fullscreen (F)"
        fs_action = menu.addAction(fs_text)
        fs_action.triggered.connect(self.toggle_fullscreen)
        
        menu.addSeparator()
        
        min_action = menu.addAction("Minimize")
        min_action.triggered.connect(self.showMinimized)
        
        close_action = menu.addAction("Close App (Alt+F4)")
        close_action.triggered.connect(self.close)
        
        menu.exec_(self.mapToGlobal(pos))

    def video_double_click(self, event):
        self.toggle_fullscreen()

    def toggle_mute(self):
        if self.player.get_volume() > 0:
            self.last_vol = self.player.get_volume()
            self.volume_slider.setValue(0)
        else:
            self.volume_slider.setValue(getattr(self, 'last_vol', 70))

    def update_ui_state(self):
        try:
            if not self.player:
                return
            
            # Update System Clock
            from datetime import datetime
            self.playback_timer.setText(datetime.now().strftime("%H:%M:%S"))
            
            pos = self.player.get_position()
            if not self.seek_slider.isSliderDown():
                self.seek_slider.setValue(int(pos * 1000))
            
            curr = self.player.get_time()
            # A-B Loop Logic
            if hasattr(self, 'loop_a') and hasattr(self, 'loop_b'):
                if curr >= self.loop_b or curr < self.loop_a:
                    self.player.set_time(self.loop_a)
            
            length = self.player.get_length()
            if length > 0:
                self.time_label.setText(f"{format_time(curr)} / {format_time(length)}")
        except Exception as e:
            print(f"UI Update error: {e}")

    def closeEvent(self, event):
        # Save State
        self.settings["last_media_path"] = self.playlist.get_current() or ""
        self.settings["last_position"] = self.player.get_time()
        self.settings["volume"] = self.player.get_volume()
        self.settings["last_playlist"] = self.playlist.items
        save_settings(self.settings)
        super().closeEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        valid_files = [f for f in files if (is_audio_file(f) or is_video_file(f))]
        if valid_files:
            self.playlist.add_items(valid_files)
            self.update_playlist_ui()

    # --- Window Control & Resize Logic ---
    def eventFilter(self, obj, event):
        """Global event filter to detect mouse move for cursor changes anywhere."""
        if event.type() in [QEvent.MouseMove, QEvent.HoverMove]:
            pos = self.mapFromGlobal(QCursor.pos())
            edge = self.get_resize_edge(pos)
            if not self.resizing:
                self.update_cursor(edge)
        return False

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("▢")
        else:
            self.showMaximized()
            self.max_btn.setText("❐")

    def get_resize_edge(self, pos):
        """Detect which edge of the window the mouse is over."""
        w = self.width()
        h = self.height()
        m = self.margin
        
        edge = 0
        if pos.x() < m: edge |= Qt.LeftSection
        elif pos.x() > w - m: edge |= Qt.RightSection
        
        if pos.y() < m: edge |= Qt.TopSection
        elif pos.y() > h - m: edge |= Qt.BottomSection
        
        return edge

    def update_cursor(self, edge):
        """Change cursor shape based on edge."""
        if edge == (Qt.LeftSection | Qt.TopSection) or edge == (Qt.RightSection | Qt.BottomSection):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge == (Qt.RightSection | Qt.TopSection) or edge == (Qt.LeftSection | Qt.BottomSection):
            self.setCursor(Qt.SizeBDiagCursor)
        elif edge & (Qt.LeftSection | Qt.RightSection):
            self.setCursor(Qt.SizeHorCursor)
        elif edge & (Qt.TopSection | Qt.BottomSection):
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            edge = self.get_resize_edge(pos)
            if edge:
                self.resizing = True
                self.resize_edge = edge
                # Fix: Use windowHandle() safely and check for None
                handle = self.windowHandle()
                if handle:
                    handle.startSystemResize(Qt.Edges(edge))
                event.accept()
            elif hasattr(self, 'title_bar') and self.title_bar.underMouse():
                self.dragPos = event.globalPos()
                handle = self.windowHandle()
                if handle:
                    handle.startSystemMove()
                event.accept()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        edge = self.get_resize_edge(pos)
        
        if not self.resizing:
            self.update_cursor(edge)
            
        if event.buttons() == Qt.LeftButton:
            if self.resizing:
                rect = self.geometry()
                global_pos = event.globalPos()
                
                if self.resize_edge & Qt.LeftSection:
                    rect.setLeft(global_pos.x())
                elif self.resize_edge & Qt.RightSection:
                    rect.setRight(global_pos.x())
                    
                if self.resize_edge & Qt.TopSection:
                    rect.setTop(global_pos.y())
                elif self.resize_edge & Qt.BottomSection:
                    rect.setBottom(global_pos.y())
                
                if rect.width() >= self.minimumWidth() and rect.height() >= self.minimumHeight():
                    self.setGeometry(rect)
                event.accept()
            elif hasattr(self, 'dragPos'):
                if self.isMaximized():
                    self.showNormal()
                    self.max_btn.setText("▢")
                self.move(self.pos() + event.globalPos() - self.dragPos)
                self.dragPos = event.globalPos()
                event.accept()

    def mouseReleaseEvent(self, event):
        self.resizing = False
        self.resize_edge = None
        if hasattr(self, 'dragPos'):
            del self.dragPos
        self.setCursor(Qt.ArrowCursor)

    def keyPressEvent(self, event):
        """Handle escape key for fullscreen and other basic keyboard navigation."""
        if event.key() == Qt.Key_Escape:
            self.exit_fullscreen()
        super().keyPressEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UniversalMediaPlayer()
    window.show()
    sys.exit(app.exec_())

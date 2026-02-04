import os
import sys

# --- FIX START: VLC Path Setup (Standalone Support) ---
# 1. Check if running as PyInstaller EXE
if hasattr(sys, '_MEIPASS'):
    local_vlc = os.path.join(sys._MEIPASS, "vlc")
else:
    local_vlc = os.path.join(os.path.dirname(__file__), "vlc")

vlc_path = None

if os.path.exists(local_vlc):
    vlc_path = local_vlc
else:
    # 2. Check standard system paths if local folder not found
    vlc_path = r"C:\Program Files\VideoLAN\VLC"
    if not os.path.exists(vlc_path):
        vlc_path = r"C:\Program Files (x86)\VideoLAN\VLC"

if vlc_path and os.path.exists(vlc_path):
    os.add_dll_directory(vlc_path)
    print(f"VLC loaded from: {vlc_path}")
else:
    print("ERROR: VLC not found locally or in Program Files.")
# --- FIX END ---

import vlc  # Ab library import karein

class VLCPlayer:
    def __init__(self, canvas_id=None):
        # Create VLC instance with standard arguments to avoid video output issues
        # -vvv for verbose debugging if needed, but keeping it clean for now
        args = [
            '--no-xlib',
            '--no-video-title-show',
            '--avcodec-hw=none',
            '--vout=direct2d',
            '--no-audio-time-stretch', 
            '--audio-filter=scaletempo', 
            '--no-stats',
            '--no-osd',
            '--quiet',
        ]
        self.instance = vlc.Instance(args)
        self.player = self.instance.media_player_new()
        self.event_manager = self.player.event_manager()
        
        if canvas_id:
            if sys.platform.startswith('linux'):
                self.player.set_xwindow(canvas_id)
            elif sys.platform == "win32":
                self.player.set_hwnd(canvas_id)
            elif sys.platform == "darwin":
                self.player.set_nsobject(canvas_id)

    def set_callback(self, event_type, callback):
        """Register a callback for a VLC event."""
        self.event_manager.event_attach(event_type, callback)

    def play(self, path=None):
        if path:
            media = self.instance.media_new(path)
            self.player.set_media(media)
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

    def set_volume(self, volume):
        self.player.audio_set_volume(max(0, min(volume, 200))) # Up to 200% boost

    def get_volume(self):
        return self.player.audio_get_volume()

    def set_position(self, ratio):
        """Set position by ratio (0.0 to 1.0)"""
        self.player.set_position(ratio)

    def get_position(self):
        """Get position ratio (0.0 to 1.0)"""
        return self.player.get_position()

    def get_time(self):
        """Get current time in ms"""
        return self.player.get_time()

    def get_length(self):
        """Get total length in ms"""
        return self.player.get_length()

    def is_playing(self):
        return self.player.is_playing()

    def set_rate(self, rate):
        """Set playback speed (e.g. 1.0, 1.5, 2.0)"""
        self.player.set_rate(rate)

    def set_pitch_shift(self, shift):
        """Sets the pitch shift filter value (Requires pitch_shifter filter)"""
        # Note: Pitch shifting without speed change is advanced in VLC.
        # Most reliable way across versions is 'rate' but that affects speed.
        pass

    def set_audio_delay(self, ms):
        """Set audio delay in ms (positive or negative)"""
        self.player.audio_set_delay(ms * 1000) # VLC expects microseconds

    def get_audio_delay(self):
        """Get audio delay in ms"""
        return self.player.audio_get_delay() / 1000.0

    def set_time(self, ms):
        """Set absolute time in ms"""
        self.player.set_time(ms)

    def set_fullscreen(self, b):
        self.player.set_fullscreen(b)

    def get_fullscreen(self):
        return self.player.get_fullscreen()
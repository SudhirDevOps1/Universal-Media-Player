import os

def format_time(ms):
    """Formats milliseconds to HH:MM:SS or MM:SS."""
    seconds = int(ms / 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"

def get_file_name(path):
    """Returns the file name from a path."""
    return os.path.basename(path)

def is_audio_file(path):
    """Checks if a file is an audio file."""
    audio_exts = {'.mp3', '.wav', '.ogg', '.flac'}
    return os.path.splitext(path)[1].lower() in audio_exts

def is_video_file(path):
    """Checks if a file is a video file."""
    video_exts = {'.mp4', '.mkv', '.avi', '.mov'}
    return os.path.splitext(path)[1].lower() in video_exts

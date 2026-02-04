import os
from utils import is_audio_file, is_video_file

def scan_folder(folder_path):
    """Scans a folder for audio and video files."""
    media_files = []
    if not os.path.exists(folder_path):
        return media_files

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            full_path = os.path.join(root, file)
            if is_audio_file(full_path) or is_video_file(full_path):
                media_files.append(full_path)
    
    return sorted(media_files)

def get_media_type(path):
    """Returns 'audio', 'video' or None for a file path."""
    if is_audio_file(path):
        return 'audio'
    if is_video_file(path):
        return 'video'
    return None

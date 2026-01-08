import os
import subprocess
import platform
from typing import List, Optional, Dict, Any, Tuple
from .filemanager import check_file_exists
from ..core.config import get_default_music_path

class FFmpegWrapper:
    def __init__(self):
        self.ffmpeg_path = self._get_ffmpeg_path()
    
    def _get_ffmpeg_path(self) -> str:
        """
        Locate ffmpeg executable. Checks system PATH first, then ~/.sexify dir.
        """
        # Check system PATH
        if shutil.which("ffmpeg"):
            return "ffmpeg"
        
        # Check ~/.sexify directory (legacy/fallback)
        home = Path.home()
        custom_path = home / ".sexify" / ("ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg")
        if custom_path.exists():
            return str(custom_path)
            
        return "ffmpeg" # Default expectation

    def is_installed(self) -> bool:
        try:
            subprocess.run([self.ffmpeg_path, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def convert_audio(self, input_file: str, output_format: str, bitrate: str = "320k", codec: str = "aac") -> Tuple[bool, str, str]:
        """
        Convert audio file. Returns (success, error_message, output_file_path).
        """
        if not check_file_exists(input_file):
            return False, "Input file does not exist", ""
        
        input_file = str(Path(input_file).resolve())
        input_dir = os.path.dirname(input_file)
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        ext = os.path.splitext(input_file)[1].lower()
        
        # Output directory structure: input_dir/FORMAT/filename.ext
        output_format_upper = output_format.upper()
        output_dir = os.path.join(input_dir, output_format_upper)
        os.makedirs(output_dir, exist_ok=True)
        
        output_ext = f".{output_format.lower()}"
        output_file = os.path.join(output_dir, f"{base_name}{output_ext}")
        
        if ext == output_ext:
            return False, "Input and output formats are the same", ""

        cmd = [self.ffmpeg_path, "-i", input_file, "-y"]
        
        if output_format.lower() == "mp3":
            cmd.extend([
                "-codec:a", "libmp3lame",
                "-b:a", bitrate,
                "-map", "0:a",
                "-map_metadata", "0",
                "-id3v2_version", "3"
            ])
            # Cover art mapping if video stream exists
            cmd.extend(["-map", "0:v?", "-c:v", "copy"])
            
        elif output_format.lower() == "m4a":
            if codec == "alac":
                cmd.extend([
                    "-codec:a", "alac",
                    "-map", "0:a",
                    "-map_metadata", "0"
                ])
            else: # AAC
                cmd.extend([
                    "-codec:a", "aac",
                    "-b:a", bitrate,
                    "-map", "0:a",
                    "-map_metadata", "0"
                ])
            cmd.extend(["-map", "0:v?", "-c:v", "copy", "-disposition:v:0", "attached_pic"])
            
        cmd.append(output_file)
        
        try:
            # Hide window on Windows
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, startupinfo=startupinfo)
            return True, "", output_file
        except subprocess.CalledProcessError as e:
            return False, f"Conversion failed: {e.stderr.decode() if e.stderr else str(e)}", ""

import shutil
from pathlib import Path

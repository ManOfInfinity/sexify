import os
import platform
import subprocess
import shutil

def open_folder_in_explorer(path: str) -> None:
    """Open a folder in the system's default file explorer."""
    if not os.path.exists(path):
        return

    system = platform.system()
    try:
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", path], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", path], check=True)
    except Exception as e:
        print(f"Error opening folder: {e}")

def check_file_exists(path: str) -> bool:
    """Check if a file exists."""
    return os.path.exists(path) and os.path.isfile(path)

def remove_file(path: str) -> None:
    """Remove a file if it exists."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"Error removing file {path}: {e}")

def ensure_dir(path: str):
    """Ensure directory exists."""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

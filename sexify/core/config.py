import os
import yaml
import platform
import shutil
from pathlib import Path
from typing import Dict, Any

DEFAULT_CONFIG = {
    "output_dir": "",
    "folder_template": "{album} - {album_artist} - {year} {source}",
    "filename_template": "{track}. {title} - {artist}",
    "include_track_numbers": True,
    "service": "tidal",
    "tidal": {
        "quality": "HI_RES_LOSSLESS",
        "token": ""
    },
    "qobuz": {
        "quality": "27",
        "token": "",
        "app_id": ""
    },
    "amazon": {
        "region": "US"
    },
    "spotify": {
        "client_id": "",
        "client_secret": ""
    },
    "save_cover_art": True,
    "cover_filename": "cover.png",
    "embed_max_quality_cover": True,
    "embed_lyrics": True,
    "skip_existing": True,
    "show_progress": True,
    "concurrent_downloads": 5
}

class ConfigManager:
    def __init__(self):
        self.config_dir = Path.home() / ".sexify"
        self.system_config_file = self.config_dir / "config.yaml"
        self.local_config_file = Path.cwd() / "config.yaml"
        self.config = DEFAULT_CONFIG.copy()
        self._load()

    def _get_default_music_path(self) -> str:
        home = Path.home()
        if platform.system() == "Windows":
            return str(home / "Music")
        return str(home / "Music")

    def _load(self):
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)

        if self.system_config_file.exists():
            self._load_from_path(self.system_config_file)
        else:
            if not self.local_config_file.exists():
                self._save(self.system_config_file)

        if self.local_config_file.exists():
            self._load_from_path(self.local_config_file)

        if not self.config['output_dir']:
            self.config['output_dir'] = self._get_default_music_path()

    def _load_from_path(self, path: Path):
        try:
            with open(path, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    self._merge(self.config, user_config)
        except Exception as e:
            print(f"Error loading config from {path}: {e}")

    def _merge(self, default: Dict, user: Dict):
        for k, v in user.items():
            if k in default and isinstance(default[k], dict) and isinstance(v, dict):
                self._merge(default[k], v)
            else:
                default[k] = v

    def _save(self, path: Path):
        try:
            with open(path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)
        except Exception as e:
            print(f"Error saving config to {path}: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split('.')
        val = self.config
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

config = ConfigManager()

def get_default_music_path() -> str:
    return config.get('download.output_path')

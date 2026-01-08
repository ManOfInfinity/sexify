import requests
import json
import time
import base64
from typing import Optional, Dict
from ..core.config import config
from ..utils.logger import log_info, log_sub, log_error
from ..utils.progress import ProgressManager
from ..constants import SEARCH_TIMEOUT, COVER_TIMEOUT, DOWNLOAD_TIMEOUT, DOWNLOAD_CHUNK_SIZE

class QobuzDownloader:
    def __init__(self):
        self.quality = config.get("qobuz.quality", "27")
        self.session = requests.Session()
        self.progress = ProgressManager.get_instance()
        self.search_api = base64.b64decode("aHR0cHM6Ly9xb2J1ei5zcXVpZC53dGYvYXBpL2dldC1tdXNpYw==").decode()
        self.download_apis = [
            base64.b64decode("aHR0cHM6Ly9xb2J1ei5zcXVpZC53dGYvYXBpL2Rvd25sb2FkLW11c2lj").decode(),
            base64.b64decode("aHR0cHM6Ly9kYWIueWVldC5zdS9hcGkvc3RyZWFt").decode(),
            base64.b64decode("aHR0cHM6Ly9kYWJtdXNpYy54eXovYXBpL3N0cmVhbQ==").decode()
        ]
        
    def search_isrc(self, isrc: str) -> Optional[Dict]:
        """Search for track by ISRC using squid.wtf API."""
        log_sub(f"Searching ISRC: {isrc}", 'qobuz')
        
        url = f"{self.search_api}?q={isrc}&offset=0"
        
        try:
            resp = self.session.get(url, timeout=SEARCH_TIMEOUT)
            
            if resp.status_code == 200:
                data = resp.json()
                
                if data.get("success") and data.get("data"):
                    tracks = data["data"].get("tracks", {}).get("items", [])
                else:
                    tracks = data.get("tracks", {}).get("items", [])
                
                if tracks:
                    track = tracks[0]
                    track_id = track.get("id")
                    title = track.get("title", "Unknown")
                    artist = track.get("performer", {}).get("name", "Unknown")
                    log_sub(f"Found: {title} by {artist} (ID: {track_id})", 'qobuz')
                    return track
                else:
                    log_error("No tracks found for ISRC", 'qobuz')
        except (requests.RequestException, KeyError, ValueError) as e:
            log_error(f"Search failed: {e}", 'qobuz')
        
        return None
        
    def get_download_url(self, track_id: int, quality: str = None) -> Optional[str]:
        """Get download URL using multiple APIs with fallback."""
        if quality is None:
            quality = self.quality
        
        for api_base in self.download_apis:
            try:
                if "squid.wtf" in api_base:
                    url = f"{api_base}?track_id={track_id}&quality={quality}"
                else:
                    url = f"{api_base}?trackId={track_id}&quality={quality}"
                
                resp = self.session.get(url, timeout=COVER_TIMEOUT)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    download_url = (
                        data.get("url") or 
                        data.get("download_url") or 
                        data.get("stream_url") or
                        (data.get("data", {}).get("url") if isinstance(data.get("data"), dict) else None)
                    )
                    
                    if download_url:
                        return download_url
                        
            except (requests.RequestException, ValueError, KeyError) as e:
                log_error(f"API request failed: {e}", 'qobuz')
                continue
        
        log_error("Failed to get download URL", 'qobuz')
        return None
        
    def download(self, url: str, output_path: str) -> bool:
        """Download track from URL with progress bar."""
        log_sub("Downloading...", 'qobuz')
        
        try:
            with self.session.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
                r.raise_for_status()
                
                total_size = int(r.headers.get('content-length', 0))
                self.progress.start_download("Qobuz", total_size)
                
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                        self.progress.update(len(chunk))
                
                self.progress.finish()
            
            return True
        except (requests.RequestException, IOError) as e:
            log_error(f"Download failed: {e}", 'qobuz')
            return False

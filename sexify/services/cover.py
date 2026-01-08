import requests
import os
import re
import tempfile
from typing import Optional, Tuple
from ..utils.filename import build_expected_filename
from ..core.config import get_default_music_path
from ..utils.logger import log_info, log_error, log_debug, log_warn
from ..constants import SEARCH_TIMEOUT, COVER_TIMEOUT

class CoverClient:
    def __init__(self):
        self.session = requests.Session()
        self._apple_artwork_base_url: Optional[str] = None  # Cache for album
        self._tag_cover_cache: Optional[bytes] = None  # Cache tag cover bytes for album
        self._tag_cover_album_key: Optional[str] = None  # Track which album cache is for

    
    def get_apple_music_artwork_base(self, apple_music_url: str) -> Optional[str]:
        """
        Fetch Apple Music page and extract artwork base URL.
        Returns the base URL which can be modified for any size/format.
        """
        if not apple_music_url:
            return None
            
        try:
            resp = self.session.get(apple_music_url, timeout=SEARCH_TIMEOUT, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if resp.status_code != 200:
                return None
            
            patterns = [
                r'(https://is\d+-ssl\.mzstatic\.com/image/thumb/Music[^"\']+/)\d+x\d+[a-z]*\.[a-z]+',
                r'"artworkUrl100"\s*:\s*"([^"]+)"',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, resp.text)
                if match:
                    base_url = match.group(1)
                    if 'x' in base_url and not base_url.endswith('/'):
                        base_url = re.sub(r'\d+x\d+[a-z]*\.[a-z]+$', '', base_url)
                    self._apple_artwork_base_url = base_url
                    return base_url
                    
        except (requests.RequestException, ValueError, re.error) as e:
            print(f"Apple Music artwork fetch error: {e}")
            
        return None
    
    def _try_download_apple_artwork(self, base_url: str, size: int, ext: str) -> Optional[bytes]:
        """Try to download Apple Music artwork at specific size and format."""
        if not base_url:
            return None
        
        artwork_url = f"{base_url}{size}x{size}.{ext}"
        log_debug(f"Trying artwork: {artwork_url}", 'apple')
        
        try:
            resp = self.session.get(artwork_url, timeout=COVER_TIMEOUT)
            if resp.status_code == 200 and len(resp.content) > 5000:
                return resp.content
        except requests.RequestException as e:
            log_error(f"- Artwork download failed ({size}x{size}.{ext}): {e}", 'apple')
        
        return None
    
    def download_album_cover(self, output_path: str, spotify_url: str = None, 
                             apple_music_url: str = None) -> bool:
        """
        Download lossless PNG album cover for archival.
        Priority: Apple 5000x5000.png → 3000x3000.png → Spotify max quality
        Saves as Album-Cover.png
        """
        if os.path.exists(output_path):
            filename = os.path.basename(output_path)
            log_warn(f"Skipping (exists): {filename}", 'cover')
            return True
        
        apple_base = None
        if apple_music_url:
            apple_base = self.get_apple_music_artwork_base(apple_music_url)
        
        if apple_base:
            for size in [5000, 3000]:
                content = self._try_download_apple_artwork(apple_base, size, 'png')
                if content:
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(content)
                    log_info(f"Downloaded lossless cover ({size}x{size}.png)", 'apple')
                    return True
        
        if spotify_url:
            if "ab67616d0000b273" in spotify_url:
                spotify_url = spotify_url.replace("ab67616d0000b273", "ab67616d000082c1")
            
            try:
                resp = self.session.get(spotify_url, timeout=COVER_TIMEOUT)
                if resp.status_code == 200:
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    with open(output_path, 'wb') as f:
                        f.write(resp.content)
                    log_info("Downloaded cover from Spotify (fallback)", 'spotify')
                    return True
            except requests.RequestException as e:
                log_error(f"- Spotify cover fallback failed: {e}", 'spotify')
        
        return False
    
    def get_tag_cover_data(self, spotify_url: str = None, 
                           apple_music_url: str = None,
                           album_key: str = None) -> Optional[bytes]:
        """
        Get 1000x1000 JPG cover data for embedding in audio file metadata.
        Does not save to disk - returns bytes directly for embedding.
        Priority: Apple 1000x1000bb.jpg → Spotify max
        Caches result for album to avoid re-downloading for each track.
        """
        if album_key and self._tag_cover_album_key == album_key and self._tag_cover_cache:
            return self._tag_cover_cache
        
        if album_key != self._tag_cover_album_key:
            self._apple_artwork_base_url = None
        
        cover_data = None
        
        apple_base = None
        if apple_music_url:
            apple_base = self.get_apple_music_artwork_base(apple_music_url)
        
        if apple_base:
            content = self._try_download_apple_artwork(apple_base, 1000, 'jpg')
            if content:
                log_info("Using cover for metadata (1000x1000.jpg)", 'apple')
                cover_data = content
        
        if not cover_data and spotify_url:
            if "ab67616d0000b273" in spotify_url:
                spotify_url = spotify_url.replace("ab67616d0000b273", "ab67616d000082c1")
            
            try:
                resp = self.session.get(spotify_url, timeout=COVER_TIMEOUT)
                if resp.status_code == 200:
                    log_info("Using Spotify max cover for metadata", 'spotify')
                    cover_data = resp.content

            except requests.RequestException:
                pass
        
        if cover_data and album_key:
            self._tag_cover_cache = cover_data
            self._tag_cover_album_key = album_key
        
        return cover_data

    
    def download_cover(self, url: str, output_path: str, max_quality: bool = True,
                       apple_music_url: Optional[str] = None) -> bool:
        return self.download_album_cover(output_path, spotify_url=url, apple_music_url=apple_music_url)

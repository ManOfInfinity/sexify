import requests
import base64
import time
import urllib.parse
from typing import Dict, Optional
from ..constants import (
    SONGLINK_MAX_CALLS_PER_MINUTE,
    SONGLINK_RATE_LIMIT_WINDOW,
    SONGLINK_MIN_DELAY_BETWEEN_CALLS,
    SONGLINK_API_TIMEOUT,
    DEFAULT_TIMEOUT
)

class SongLinkClient:
    def __init__(self):
        self.session = requests.Session()
        self.last_call_time = 0
        self.call_count = 0
        self.reset_time = time.time()
        
    def get_links(self, spotify_id: str) -> Dict[str, str]:
        """
        Get platform links (Tidal, Amazon) for a Spotify ID.
        Returns dict with keys 'tidal', 'amazon' containing URLs.
        """
        self._rate_limit()
        
        base_api_b64 = "aHR0cHM6Ly9hcGkuc29uZy5saW5rL3YxLWFscGhhLjEvbGlua3M/dXJsPQ=="
        base_api = base64.b64decode(base_api_b64).decode()
        
        spotify_base = base64.b64decode("aHR0cHM6Ly9vcGVuLnNwb3RpZnkuY29tL3RyYWNrLw==").decode()
        spotify_url = f"{spotify_base}{spotify_id}"
        api_url = f"{base_api}{urllib.parse.quote(spotify_url)}"
        
        links = {}
        try:
            resp = self.session.get(api_url, timeout=SONGLINK_API_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                links_by_platform = data.get("linksByPlatform", {})
                
                if "tidal" in links_by_platform:
                    links["tidal"] = links_by_platform["tidal"].get("url", "")
                    
                if "amazonMusic" in links_by_platform:
                    links["amazon"] = links_by_platform["amazonMusic"].get("url", "")
                
                if "appleMusic" in links_by_platform:
                    links["apple"] = links_by_platform["appleMusic"].get("url", "")
                    
            elif resp.status_code == 429:
                print("Song.link rate limit active")
                
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Song.link error: {e}")
            
        return links


    def _rate_limit(self) -> None:
        """Enforce Song.link API rate limiting (max 9 calls per minute)."""
        now = time.time()
        if now - self.reset_time >= SONGLINK_RATE_LIMIT_WINDOW:
            self.call_count = 0
            self.reset_time = now
            
        if self.call_count >= SONGLINK_MAX_CALLS_PER_MINUTE:
            sleep_time = SONGLINK_RATE_LIMIT_WINDOW - (now - self.reset_time)
            if sleep_time > 0:
                time.sleep(sleep_time + 1)
            self.call_count = 0
            self.reset_time = time.time()
            
        if hasattr(self, 'last_call_time') and now - self.last_call_time < SONGLINK_MIN_DELAY_BETWEEN_CALLS:
            time.sleep(SONGLINK_MIN_DELAY_BETWEEN_CALLS - (now - self.last_call_time))
            
        self.last_call_time = time.time()
        self.call_count += 1

    def get_tidal_url(self, spotify_id: str) -> Optional[str]:
        """Get Tidal URL for a Spotify track ID."""
        links = self.get_links(spotify_id)
        return links.get("tidal")
    
    def get_amazon_url(self, spotify_id: str) -> Optional[str]:
        """Get Amazon Music URL for a Spotify track ID."""
        links = self.get_links(spotify_id)
        return links.get("amazon")
    
    def get_apple_music_url(self, spotify_id: str) -> Optional[str]:
        """Get Apple Music URL for a Spotify track ID."""
        links = self.get_links(spotify_id)
        return links.get("apple")

import base64
import time
import random
import requests
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse
from ..core.config import config
from ..utils.logger import log_error, log_warn, log_info
from ..constants import AUTH_TIMEOUT, DEFAULT_TIMEOUT

class SpotifyClient:
    def __init__(self):
        self.client_id = config.get("spotify.client_id", "")
        self.client_secret = config.get("spotify.client_secret", "")
        self.configured_token = config.get("spotify.token", "")
        self.session = requests.Session()
        self.token = ""
        self.token_expiry = 0
        
        _open_spotify = base64.b64decode("aHR0cHM6Ly9vcGVuLnNwb3RpZnkuY29tLw==").decode()
        self.session.headers.update({
            "User-Agent": self._random_user_agent(),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": _open_spotify,
            "Origin": _open_spotify.rstrip('/'),
        })
        self._api_base = base64.b64decode("aHR0cHM6Ly9hcGkuc3BvdGlmeS5jb20vdjEv").decode()
        self._auth_url = base64.b64decode("aHR0cHM6Ly9hY2NvdW50cy5zcG90aWZ5LmNvbS9hcGkvdG9rZW4=").decode()
    
    def _random_user_agent(self) -> str:
        mac_major = random.randint(11, 15)
        mac_minor = random.randint(4, 9)
        webkit_major = random.randint(530, 537)
        webkit_minor = random.randint(30, 37)
        chrome_major = random.randint(80, 105)
        chrome_build = random.randint(3000, 4500)
        chrome_patch = random.randint(60, 125)
        safari_major = random.randint(530, 537)
        safari_minor = random.randint(30, 36)
        return f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{mac_major}_{mac_minor}) AppleWebKit/{webkit_major}.{webkit_minor} (KHTML, like Gecko) Chrome/{chrome_major}.0.{chrome_build}.{chrome_patch} Safari/{safari_major}.{safari_minor}"
        
    def _get_token(self) -> str:
        if self.configured_token:
            return self.configured_token
            
        if self.token and time.time() < self.token_expiry:
             return self.token
             
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}
        data = {"grant_type": "client_credentials"}
        
        try:
            resp = self.session.post(self._auth_url, headers=headers, data=data, timeout=AUTH_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                self.token = data["access_token"]
                self.token_expiry = time.time() + data["expires_in"] - 60
                return self.token
        except (requests.RequestException, KeyError, ValueError) as e:
            log_error(f"Spotify auth failed: {e}", 'spotify')
            
        return ""
    
    def _api_request(self, url: str, max_retries: int = 3) -> Optional[requests.Response]:
        token = self._get_token()
        if not token:
            return None
            
        headers = {"Authorization": f"Bearer {token}"}
        
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
                
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "5")
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = 5
                    log_warn(f"Rate limited. Refreshing session and waiting {wait_time}s...", 'spotify')
                    
                    self.session.headers.update({"User-Agent": self._random_user_agent()})
                    self.token = "" 
                    self.token_expiry = 0
                    token = self._get_token()
                    headers = {"Authorization": f"Bearer {token}"}
                    
                    time.sleep(wait_time)
                    continue
                else:
                    log_warn(f"Spotify API error: {resp.status_code}", 'spotify')
                    return None
            except (requests.RequestException, ValueError, KeyError) as e:
                log_error(f"Spotify request failed: {e}", 'spotify')
                return None
        
        log_error("Spotify API rate limit exceeded after retries. Please wait a few minutes.", 'spotify')
        return None

    def get_track(self, track_id: str) -> Optional[Dict[str, Any]]:
        resp = self._api_request(f"{self._api_base}tracks/{track_id}")
        if resp:
            return resp.json()
        return None

    def get_album(self, album_id: str) -> Optional[Dict[str, Any]]:
        resp = self._api_request(f"{self._api_base}albums/{album_id}")
        if resp:
            return resp.json()
        return None

    def get_album_tracks(self, album_id: str) -> List[Dict[str, Any]]:
        tracks = []
        url = f"{self._api_base}albums/{album_id}/tracks?limit=50"
        
        while url:
            resp = self._api_request(url)
            if resp:
                data = resp.json()
                tracks.extend(data.get("items", []))
                url = data.get("next")
            else:
                break
        return tracks

    def get_playlist_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        items = []
        url = f"{self._api_base}playlists/{playlist_id}/tracks?limit=100"
        
        while url:
            resp = self._api_request(url)
            if resp:
                data = resp.json()
                items.extend(data.get("items", []))
                url = data.get("next")
            else:
                break
                
        return [item['track'] for item in items if item.get('track')]

    def get_playlist(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self._api_base}playlists/{playlist_id}?fields=name,description,owner,images"
        resp = self._api_request(url)
        if resp:
            return resp.json()
        return None

    def parse_url(self, url: str) -> Dict[str, str]:
        import re
        isrc_pattern = r'^[A-Z]{2}[A-Z0-9]{3}[0-9]{7}$'
        if re.match(isrc_pattern, url.upper()):
            return {"type": "isrc", "id": url.upper()}
        
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) >= 2:
            track_id = path_parts[-1].split('?')[0]
            return {"type": path_parts[-2], "id": track_id}
        return {}


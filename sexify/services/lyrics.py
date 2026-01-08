import requests
import base64
import time
import urllib.parse
from typing import Optional, Dict, List, Tuple
from ..utils.logger import log_warn
from ..constants import DEFAULT_TIMEOUT

class LyricsClient:
    def __init__(self):
        self.session = requests.Session()
        
    def fetch_lyrics(self, track_name: str, artist_name: str) -> Optional[str]:
        """
        Fetch lyrics from LRCLIB using track details.
        Returns synced lyrics (LRC) if available, otherwise plain text or None.
        """
        lyrics = self._fetch_lrc_lib(track_name, artist_name)
        if lyrics:
            return lyrics
            
        simple_track = track_name.split('(')[0].split('-')[0].strip()
        if simple_track != track_name:
             lyrics = self._fetch_lrc_lib(simple_track, artist_name)
             if lyrics:
                 return lyrics
                 
        return None

    def _fetch_lrc_lib(self, track: str, artist: str, retries: int = 2) -> Optional[str]:
        base_url_b64 = "aHR0cHM6Ly9scmNsaWIubmV0L2FwaS9nZXQ="
        base_url = base64.b64decode(base_url_b64).decode()
        
        params = {
            "artist_name": artist,
            "track_name": track
        }
        
        for attempt in range(retries + 1):
            try:
                resp = self.session.get(base_url, params=params, timeout=DEFAULT_TIMEOUT)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("syncedLyrics"):
                        return data["syncedLyrics"]
                    elif data.get("plainLyrics"):
                        return data["plainLyrics"]
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < retries:
                    time.sleep(2)
                    continue
                pass
            except Exception:
                break
            
        return self._search_lrc_lib(track, artist)
        
    def _search_lrc_lib(self, track: str, artist: str, retries: int = 2) -> Optional[str]:
        """Search for lyrics using LRCLIB search API with retry support."""
        base_url_b64 = "aHR0cHM6Ly9scmNsaWIubmV0L2FwaS9zZWFyY2g="
        base_url = base64.b64decode(base_url_b64).decode()
        
        query = f"{artist} {track}"
        
        for attempt in range(retries + 1):
            try:
                resp = self.session.get(base_url, params={"q": query}, timeout=DEFAULT_TIMEOUT)
                if resp.status_code == 200:
                    results = resp.json()
                    if results and len(results) > 0:
                        # synced lyrics >> plain lyrics
                        for res in results:
                            if res.get("syncedLyrics"):
                                return res["syncedLyrics"]
                        if results[0].get("plainLyrics"):
                            return results[0]["plainLyrics"]
                break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                if attempt < retries:
                    time.sleep(2)
                    continue
                pass
            except Exception:
                break
            
        return None


import requests
import base64
import json
import os
import time
import binascii
from typing import Optional, Dict
from ..utils.analysis import AnalysisResult
from ..utils.logger import log_info, log_sub, log_error
from ..utils.progress import ProgressManager
from ..core.config import config
from ..constants import AUTH_TIMEOUT, STREAM_TIMEOUT, DOWNLOAD_CHUNK_SIZE, DOWNLOAD_TIMEOUT, SEARCH_TIMEOUT

class TidalDownloader:
    def __init__(self):
        self.client_id = config.get("tidal.client_id", "")
        self.client_secret = config.get("tidal.client_secret", "")
        self.session = requests.Session()
        self.token = config.get("tidal.token", "")
        self.api_url = base64.b64decode("aHR0cHM6Ly9hcGkudGlkYWwuY29tL3Yx").decode()

    def _get_token(self) -> str:
        if self.token: return self.token
        
        auth_url = base64.b64decode("aHR0cHM6Ly9hdXRoLnRpZGFsLmNvbS92MS9vYXV0aDIvdG9rZW4=").decode()
        data = {
            "client_id": self.client_id,
            "grant_type": "client_credentials"
        }
        auth = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}"}
        
        try:
            resp = self.session.post(auth_url, data=data, headers=headers, timeout=AUTH_TIMEOUT)
            if resp.status_code == 200:
                self.token = resp.json()["access_token"]
                return self.token
        except (requests.RequestException, KeyError, ValueError) as e:
            log_error(f"Tidal auth failed: {e}", 'tidal')
        return ""

    def search_track(self, query: str) -> Optional[Dict]:
        token = self._get_token()
        if not token: return None
        
        url = f"{self.api_url}/search/tracks"
        params = {"query": query, "limit": 10, "countryCode": "US"}
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=SEARCH_TIMEOUT)
            if resp.status_code == 200:
                items = resp.json().get("tracks", {}).get("items", [])
                if items: return items[0]
        except (requests.RequestException, KeyError, ValueError):
            pass
        return None

    def get_stream_url(self, track_id: int, quality: str = "LOSSLESS") -> Optional[str]:
        api_hosts = [
            "dm9nZWxmLnFxZGwuc2l0ZQ==",
            "bWF1cy5xcWRsLnNpdGU=",
            "aHVuZC5xcWRsLnNpdGU=",
            "a2F0emUucXFkbC5zaXRl",
            "d29sZi5xcWRsLnNpdGU=",
            "dGlkYWwtYXBpLmJpbmlubXVtLm9yZw==",
            "dHJpdG9uLnNxdWlkLnd0Zg=="
        ]
        
        for host_c in api_hosts:
            try:
                api_host = base64.b64decode(host_c).decode()
                url = f"https://{api_host}/track/?id={track_id}&quality={quality}"
                resp = self.session.get(url, timeout=STREAM_TIMEOUT)
                
                if resp.status_code == 200:
                    data = resp.json()
                    
                    # V2 res
                    if isinstance(data, dict) and "data" in data and "manifest" in data["data"]:
                        manifest = data["data"]["manifest"]
                        return "MANIFEST:" + manifest
                    # V1 res list
                    if isinstance(data, list):
                        for item in data:
                            if item.get("OriginalTrackUrl"):
                                return item["OriginalTrackUrl"]
            except (requests.RequestException, KeyError, ValueError):
                continue
        return None
    
    def _parse_manifest(self, manifest_b64: str):
        """Parse base64 manifest - supports BTS (JSON) and DASH (XML) formats."""
        import re
        
        try:
            manifest_bytes = base64.b64decode(manifest_b64)
            manifest_str = manifest_bytes.decode('utf-8')
        except (binascii.Error, UnicodeDecodeError) as e:
            return None, None, None, f"Failed to decode manifest: {e}"
        
        if manifest_str.startswith('{'):
            # BTS format with direct URLs
            try:
                bts = json.loads(manifest_str)
                urls = bts.get('urls', [])
                if urls:
                    log_sub(f"Manifest: BTS format ({bts.get('mimeType', 'unknown')}, {bts.get('codecs', 'unknown')})", 'tidal')
                    return urls[0], None, None, None  # Direct URL
                return None, None, None, "No URLs in BTS manifest"
            except json.JSONDecodeError as e:
                return None, None, None, f"Failed to parse BTS manifest: {e}"
        
        # DASH format with XML segments
        log_sub("Manifest: DASH format", 'tidal')
        
        init_match = re.search(r'initialization="([^"]+)"', manifest_str)
        media_match = re.search(r'media="([^"]+)"', manifest_str)
        
        if not init_match:
            return None, None, None, "No initialization URL found in manifest"
        
        init_url = init_match.group(1).replace('&amp;', '&')
        media_template = media_match.group(1).replace('&amp;', '&') if media_match else None
        
        if not media_template:
            return None, None, None, "No media template found in manifest"
        
        segment_count = 0
        for match in re.finditer(r'<S d="\d+"(?: r="(\d+)")?', manifest_str):
            repeat = int(match.group(1)) if match.group(1) else 0
            segment_count += repeat + 1
        
        if segment_count == 0:
            segment_count = 50
        
        media_urls = []
        for i in range(1, segment_count + 1):
            media_url = media_template.replace('$Number$', str(i))
            media_urls.append(media_url)
        
        return None, init_url, media_urls, None  # DASH format
    
    def _download_from_manifest(self, manifest_b64: str, output_path: str, progress=None) -> bool:
        """Download from DASH/BTS manifest with segment handling."""
        import subprocess
        import tempfile
        
        direct_url, init_url, media_urls, error = self._parse_manifest(manifest_b64)
        
        if error:
            log_error(f"Manifest error: {error}", 'tidal')
            return False
        
        progress_mgr = ProgressManager.get_instance()
        filename = os.path.basename(output_path)
        
        if direct_url:
            log_sub("Downloading file (BTS format)...", 'tidal')
            try:
                resp = self.session.get(direct_url, stream=True, timeout=120)
                resp.raise_for_status()
                total = int(resp.headers.get('content-length', 0))
                
                progress_mgr.start_download(filename, total)
                
                with open(output_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                        progress_mgr.update(len(chunk))
                
                progress_mgr.finish()
                return True
            except (requests.RequestException, IOError, OSError) as e:
                log_error(f"Download failed: {e}", 'tidal')
                return False
        
        log_sub(f"Downloading {len(media_urls)} segments (DASH format)...", 'tidal')
        
        temp_path = output_path + ".m4a.tmp"
        
        try:
            log_sub("Downloading init segment...", 'tidal')
            resp = self.session.get(init_url, timeout=60)
            resp.raise_for_status()
            
            with open(temp_path, 'wb') as f:
                f.write(resp.content)
            
            total_bytes = len(resp.content)
            progress_mgr.start_download(f"{filename} (segments)", 0)
            
            with open(temp_path, 'ab') as f:
                for i, media_url in enumerate(media_urls, 1):
                    resp = self.session.get(media_url, timeout=60)
                    resp.raise_for_status()
                    f.write(resp.content)
                    total_bytes += len(resp.content)
                    
                    progress_mgr.set_total(total_bytes)
                    progress_mgr.update(len(resp.content))
            
            progress_mgr.finish()
            log_sub(f"Downloaded: {total_bytes / (1024 * 1024):.2f} MB", 'tidal')
            
            log_sub("Converting to FLAC...", 'tidal')
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", temp_path, "-vn", "-c:a", "copy", output_path],
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", temp_path, "-vn", "-c:a", "flac", output_path],
                    capture_output=True, text=True
                )
            
            if result.returncode != 0:
                log_error(f"FFmpeg conversion failed", 'tidal')
                m4a_path = output_path.rsplit('.flac', 1)[0] + '.m4a.tmp'
                try:
                    os.rename(temp_path, m4a_path)
                    log_error(f"M4A saved as: {m4a_path}", 'tidal')
                except Exception:
                    pass
                return False
            
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            return True
            
        except (requests.RequestException, IOError, OSError, subprocess.CalledProcessError) as e:
            log_error(f"DASH download failed: {e}", 'tidal')
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return False
        
    def download(self, stream_url: str, output_path: str, progress=None) -> bool:
        if stream_url.startswith("MANIFEST:"):
            manifest_b64 = stream_url[len("MANIFEST:"):]
            return self._download_from_manifest(manifest_b64, output_path, progress)
            
        try:
            with self.session.get(stream_url, stream=True, timeout=120) as r:
                r.raise_for_status()
                total = int(r.headers.get('content-length', 0))
                
                if progress:
                    progress.set_total(total)
                
                with open(output_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                        if progress:
                            progress.update(len(chunk))
            return True
        except (requests.RequestException, IOError, OSError) as e:
            log_error(f"Tidal download failed: {e}", 'tidal')
            return False

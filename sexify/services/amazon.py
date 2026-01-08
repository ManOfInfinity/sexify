import requests
import time
import base64
import os
import urllib.parse
from typing import Optional
from .songlink import SongLinkClient
from ..utils.progress import ProgressManager
from ..utils.logger import log_info, log_error, log_sub
from ..core.config import config
from ..constants import (
    AMAZON_MAX_POLL_ATTEMPTS,
    AMAZON_POLL_INTERVAL,
    DOWNLOAD_CHUNK_SIZE,
    DEFAULT_TIMEOUT,
    DOWNLOAD_TIMEOUT
)

class AmazonDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.songlink = SongLinkClient()
        primary_region = config.get("amazon.region", "US").lower()
        self.regions = [primary_region] if primary_region in ["us", "eu"] else ["us"]
        if "eu" not in self.regions:
            self.regions.append("eu")
        elif "us" not in self.regions:
            self.regions.append("us")
        self.progress = ProgressManager.get_instance()
        
    def get_amazon_url(self, spotify_id: str) -> Optional[str]:
        """Get Amazon Music URL for a Spotify track using SongLink."""
        log_info("Obtaining Amazon URL via SongLink", 'amazon')
        links = self.songlink.get_links(spotify_id)
        if "amazon" in links and links["amazon"]:
            url = links["amazon"]
            log_sub(f"+ {url}", 'amazon')
            if "trackAsin=" in url:
                try:
                    parsed = urllib.parse.urlparse(url)
                    params = urllib.parse.parse_qs(parsed.query)
                    track_asin = params.get('trackAsin', [None])[0]
                    if track_asin:
                        base = base64.b64decode("aHR0cHM6Ly9tdXNpYy5hbWF6b24uY29tL3RyYWNrcy8=").decode()
                        return f"{base}{track_asin}?musicTerritory=US"
                except (KeyError, IndexError, ValueError) as e:
                    log_sub(f"Failed to parse track ASIN, using original URL: {e}", 'amazon')
            return url
        log_error("- No Amazon URL found", 'amazon')
        return None

    def download(self, amazon_url: str, output_path: str) -> bool:
        """
        Download track from Amazon Music using DoubleDouble service.
        
        Attempts download from configured regions in order, with automatic
        fallback to alternative regions if primary fails.
        """
        for region in self.regions:
            try:
                log_sub(f"+ Region: {region.upper()}", 'amazon')
                svc_base = base64.b64decode("aHR0cHM6Ly8=").decode()
                svc_domain = base64.b64decode("LmRvdWJsZWRvdWJsZS50b3A=").decode()
                base_url = f"{svc_base}{region}{svc_domain}"
                
                submit_url = f"{base_url}/dl?url={urllib.parse.quote(amazon_url)}"
                log_sub("Submitting download request", 'amazon')
                resp = self.session.get(submit_url, timeout=DEFAULT_TIMEOUT * 3)
                if resp.status_code != 200:
                    continue
                
                data = resp.json()
                if not data.get("success"):
                    continue
                
                dl_id = data["id"]
                log_sub(f"+ Download ID: {dl_id}", 'amazon')
                
                status_url = f"{base_url}/dl/{dl_id}"
                log_sub("Waiting for download to complete...", 'amazon')
                for _ in range(AMAZON_MAX_POLL_ATTEMPTS):
                    time.sleep(AMAZON_POLL_INTERVAL)
                    stat_resp = self.session.get(status_url, timeout=DEFAULT_TIMEOUT)
                    if stat_resp.status_code != 200:
                        continue
                    
                    stat = stat_resp.json()
                    if stat["status"] == "done":
                        file_url = stat["url"]
                        if file_url.startswith("./"):
                            file_url = f"{base_url}/{file_url[2:]}"
                        elif file_url.startswith("/"):
                            file_url = f"{base_url}{file_url}"
                        
                        log_sub("Downloading file...", 'amazon')
                        
                        with self.session.get(file_url, stream=True, timeout=DOWNLOAD_TIMEOUT) as r:
                            r.raise_for_status()
                            total_size = int(r.headers.get('content-length', 0))
                            
                            filename = os.path.basename(output_path)
                            self.progress.start_download(filename, total_size)
                            
                            with open(output_path, 'wb') as f:
                                for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                                    f.write(chunk)
                                    self.progress.update(len(chunk))
                        
                        self.progress.finish()
                        return True

                    elif stat["status"] == "error":
                        log_error(f"- Download failed: {stat.get('error', 'Unknown')}", 'amazon')
                        break
                        
            except (requests.RequestException, ValueError, KeyError) as e:
                log_error(f"- Download attempt failed ({region}): {e}", 'amazon')
                continue
                
        return False

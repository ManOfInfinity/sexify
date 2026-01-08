import os
import time
import uuid
import shutil
import atexit
from dataclasses import dataclass, field
from typing import Optional
from ..services.spotify import SpotifyClient
from ..services.amazon import AmazonDownloader
from ..services.tidal import TidalDownloader
from ..services.qobuz import QobuzDownloader
from ..services.lyrics import LyricsClient
from ..services.cover import CoverClient
from ..utils.metadata import embed_metadata, embed_lyrics, extract_isrc
from ..utils.filename import build_expected_filename, sanitize_filename, build_folder_path
from ..utils.progress import ProgressManager
from ..utils.filemanager import check_file_exists, ensure_dir
from ..utils.logger import log_info, log_error, log_success, log_warn, log_sub
from ..core.config import config

@dataclass
class DownloadRequest:
    isrc: str
    service: str = "amazon"
    spotify_id: str = ""
    track_name: str = ""
    artist_name: str = ""
    album_name: str = ""
    album_artist: str = ""
    release_date: str = ""
    cover_url: str = ""
    output_dir: str = "."
    audio_format: str = "LOSSLESS"
    filename_format: str = "{title} - {artist}"
    track_number: int = 0
    total_tracks: int = 0
    disc_number: int = 1
    position: int = 0
    embed_lyrics: bool = True
    embed_max_quality_cover: bool = True
    
    is_playlist: bool = False
    playlist_name: str = "" 
    
    description: str = ""

class Downloader:
    def __init__(self):
        self.spotify = SpotifyClient()
        self.amazon = AmazonDownloader()
        self.tidal = TidalDownloader()
        self.qobuz = QobuzDownloader()
        self.lyrics = LyricsClient()
        self.cover = CoverClient()
        self.progress = ProgressManager.get_instance()
        
        self.session_id = str(uuid.uuid4())[:8]
        self._temp_dir = None
        
        atexit.register(self._cleanup_temp)
    
    def _get_temp_dir(self, base_dir: str) -> str:
        if self._temp_dir is None:
            temp_base = os.path.join(base_dir, "temp_download")
            self._temp_dir = os.path.join(temp_base, f"session_{self.session_id}")
            ensure_dir(self._temp_dir)
        return self._temp_dir
    
    def _cleanup_temp(self):
        if self._temp_dir and os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
            except Exception:
                pass

    def download_track(self, req: DownloadRequest) -> bool:
        if req.is_playlist and req.playlist_name:
            from ..utils.filename import sanitize_filename
            safe_playlist_name = sanitize_filename(req.playlist_name)
            final_output_dir = os.path.join(req.output_dir, safe_playlist_name)
        else:
            folder_template = config.get("folder_template", "")
            if folder_template:
                subfolder = build_folder_path(
                    folder_template,
                    req.artist_name,
                    req.album_name,
                    req.album_artist,
                    req.release_date,
                    req.service
                )
                final_output_dir = os.path.join(req.output_dir, subfolder)
            else:
                final_output_dir = req.output_dir
            
        ensure_dir(final_output_dir)
        
        expected_filename = build_expected_filename(
            req.track_name, req.artist_name, req.album_name, req.album_artist,
            req.release_date, req.filename_format, True, req.position,
            req.disc_number,
            False,
            req.service # service_name
        )
        if not expected_filename.endswith(".flac"):
            expected_filename += ".flac"
            
        output_path = os.path.join(final_output_dir, expected_filename)
        
        if check_file_exists(output_path):
            existing_isrc = extract_isrc(output_path)
            if existing_isrc and existing_isrc == req.isrc:
                 log_warn(f"Skipping (exists): {expected_filename}", 'sexify')
                 return True

        temp_dir = self._get_temp_dir(req.output_dir)
        temp_filename = f"{req.service}_{int(time.time())}_{expected_filename}"
        temp_path = os.path.join(temp_dir, temp_filename)
        
        success = False
        used_service = req.service
        
        fallback_order = {
            "tidal": ["qobuz", "amazon"],
            "amazon": ["tidal", "qobuz"],
            "qobuz": ["tidal", "amazon"]
        }
        
        services_to_try = [req.service] + fallback_order.get(req.service, [])
        
        for service in services_to_try:
            if service == "tidal":
                success = self._download_tidal(req, temp_path)
            elif service == "amazon":
                success = self._download_amazon(req, temp_path)
            elif service == "qobuz":
                success = self._download_qobuz(req, temp_path)
            
            if success and check_file_exists(temp_path):
                used_service = service
                break
            elif service != services_to_try[-1]:
                log_warn(f"Trying fallback: {services_to_try[services_to_try.index(service)+1].upper()}", 'sexify')
        
        if success and check_file_exists(temp_path):
            shutil.move(temp_path, output_path)
            
            self._apply_metadata(output_path, req, final_output_dir)
            
            log_success(f"Completed: {expected_filename}", 'sexify')
            print()  # Empty line after each track for cleaner logs
            return True

            
        if check_file_exists(temp_path):
            os.remove(temp_path)
            
        log_error(f"- Failed to download: {req.track_name} (all services tried)", 'sexify')
        return False

    def _download_tidal(self, req: DownloadRequest, output_path: str) -> bool:
        if not req.spotify_id:
            log_error("No Spotify ID for TIDAL lookup", 'tidal')
            return False
        
        # Use SongLink to get Tidal URL (like V4 does)
        from ..services.songlink import SongLinkClient
        songlink = SongLinkClient()
        
        log_info("Obtaining Tidal URL via SongLink", 'tidal')
        tidal_url = songlink.get_tidal_url(req.spotify_id)
        
        if not tidal_url:
            log_error("Tidal URL not found via SongLink", 'tidal')
            return False
        
        log_sub(f"+ {tidal_url}", 'tidal')
        
        # Extract track ID from URL (e.g., https://listen.tidal.com/track/381170482)
        import re
        match = re.search(r'/track/(\d+)', tidal_url)
        if not match:
            log_error(f"Could not extract track ID from: {tidal_url}", 'tidal')
            return False
        
        track_id = int(match.group(1))
        log_sub(f"+ Track ID: {track_id}", 'tidal')
        
        log_sub("Getting stream URL...", 'tidal')
        
        # Quality fallback chain for TIDAL
        quality_chain = [req.audio_format]
        if req.audio_format == "HI_RES_LOSSLESS":
            quality_chain.extend(["LOSSLESS", "HIGH"])
        elif req.audio_format == "LOSSLESS":
            quality_chain.append("HIGH")
        
        stream_url = None
        for quality in quality_chain:
            stream_url = self.tidal.get_stream_url(track_id, quality)
            if stream_url:
                if quality != req.audio_format:
                    log_warn(f"Quality fallback: {quality}", 'tidal')
                break
        
        if not stream_url:
            log_error("Could not get stream URL from Tidal APIs", 'tidal')
            return False
        
        log_sub("Downloading...", 'tidal')
        return self.tidal.download(stream_url, output_path)

    def _download_amazon(self, req: DownloadRequest, output_path: str) -> bool:
        if not req.spotify_id:
            return False
        
        url = self.amazon.get_amazon_url(req.spotify_id)
        if url:
             return self.amazon.download(url, output_path)
        return False

    def _download_qobuz(self, req: DownloadRequest, output_path: str) -> bool:
        if not req.isrc:
            return False
            
        track = self.qobuz.search_isrc(req.isrc)
        if track:
             url = self.qobuz.get_download_url(track['id'])
             if url:
                 return self.qobuz.download(url, output_path)
        return False

    def _apply_metadata(self, filepath: str, req: DownloadRequest, album_dir: str):
        apple_music_url = None
        if req.spotify_id:
            from ..services.songlink import SongLinkClient
            songlink = SongLinkClient()
            links = songlink.get_links(req.spotify_id)
            apple_music_url = links.get('apple', '')
        
        if not req.is_playlist:
            album_cover_path = os.path.join(album_dir, 'Album-Cover.png')
            if req.cover_url:
                if not check_file_exists(album_cover_path):
                    self.cover.download_album_cover(
                        album_cover_path,
                        spotify_url=req.cover_url,
                        apple_music_url=apple_music_url
                    )
        
        tag_cover_data = None
        if req.embed_max_quality_cover:
            if req.is_playlist:
                track_key = f"playlist-{req.spotify_id}"
                tag_cover_data = self.cover.get_tag_cover_data(
                    spotify_url=req.cover_url,
                    apple_music_url=apple_music_url,
                    album_key=track_key
                )
            else:
                album_key = f"{req.album_artist}-{req.album_name}"
                tag_cover_data = self.cover.get_tag_cover_data(
                    spotify_url=req.cover_url,
                    apple_music_url=apple_music_url,
                    album_key=album_key
                )

        
        meta = {
            "title": req.track_name,
            "artist": req.artist_name,
            "album": req.album_name,
            "album_artist": req.album_artist,
            "date": req.release_date,
            "track_number": str(req.track_number),
            "total_tracks": str(req.total_tracks),
            "disc_number": str(req.disc_number),
            "isrc": req.isrc,
            "description": "Downloaded with Sexify"
        }
        
        if req.embed_lyrics:
            log_sub("Fetching lyrics...", 'sexify')
            lyrics = self.lyrics.fetch_lyrics(req.track_name, req.artist_name)
            if lyrics:
                log_sub("Lyrics found", 'sexify')
                meta["lyrics"] = lyrics
            else:
                log_sub("No lyrics found", 'sexify')
                
        embed_metadata(filepath, meta, cover_data=tag_cover_data)



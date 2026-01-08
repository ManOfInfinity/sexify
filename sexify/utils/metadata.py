import os
from typing import Optional, Dict
from mutagen.flac import FLAC, Picture
from mutagen.id3 import ID3, APIC, USLT, ID3NoHeaderError
from .filemanager import check_file_exists

def embed_metadata(filepath: str, metadata: Dict[str, str], cover_path: Optional[str] = None,
                   cover_data: Optional[bytes] = None) -> bool:
    """
    Embed metadata into a FLAC file.
    metadata dict keys: title, artist, album, album_artist, date, track_number, total_tracks, disc_number, isrc, lyrics, description
    cover_data: raw bytes of cover image (takes priority over cover_path)
    """
    if not check_file_exists(filepath):
        return False

    try:
        audio = FLAC(filepath)
        
        # Map metadata to FLAC tags
        if "title" in metadata: audio["TITLE"] = metadata["title"]
        if "artist" in metadata: audio["ARTIST"] = metadata["artist"]
        if "album" in metadata: audio["ALBUM"] = metadata["album"]
        if "album_artist" in metadata: audio["ALBUMARTIST"] = metadata["album_artist"]
        if "date" in metadata: audio["DATE"] = metadata["date"]
        if "track_number" in metadata: audio["TRACKNUMBER"] = str(metadata["track_number"])
        if "total_tracks" in metadata: audio["TOTALTRACKS"] = str(metadata["total_tracks"])
        if "disc_number" in metadata: audio["DISCNUMBER"] = str(metadata["disc_number"])
        if "isrc" in metadata: audio["ISRC"] = metadata["isrc"]
        if "description" in metadata: audio["DESCRIPTION"] = metadata["description"]
        if "lyrics" in metadata and metadata["lyrics"]: audio["LYRICS"] = metadata["lyrics"]

        # Embed cover art (prefer cover_data bytes over file path)
        # Clear existing pictures first to avoid duplicates
        if cover_data:
            audio.clear_pictures()  # Remove any existing covers from downloaded file
            image = Picture()
            image.type = 3  # Front cover
            image.mime = "image/jpeg"  # Tag cover is always JPG
            image.desc = "Cover"
            image.data = cover_data
            audio.add_picture(image)
        elif cover_path and check_file_exists(cover_path):
            audio.clear_pictures()  # Remove any existing covers from downloaded file
            image = Picture()
            image.type = 3  # Front cover
            image.mime = "image/jpeg"
            if cover_path.lower().endswith(".png"):
                image.mime = "image/png"
            image.desc = "Cover"
            
            with open(cover_path, "rb") as f:
                image.data = f.read()
            
            audio.add_picture(image)

        audio.save()
        return True
    except Exception as e:
        print(f"Error embedding metadata: {e}")
        return False


def extract_isrc(filepath: str) -> Optional[str]:
    """Read ISRC from FLAC file."""
    if not check_file_exists(filepath):
        return None
        
    try:
        audio = FLAC(filepath)
        if "ISRC" in audio:
            return audio["ISRC"][0]
        return None
    except Exception:
        return None

def embed_lyrics(filepath: str, lyrics: str) -> bool:
    """Embed lyrics into an audio file (FLAC/MP3)."""
    if not check_file_exists(filepath) or not lyrics:
        return False
        
    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        if ext == ".flac":
            audio = FLAC(filepath)
            audio["LYRICS"] = lyrics
            audio.save()
            return True
        elif ext == ".mp3":
            try:
                tags = ID3(filepath)
            except ID3NoHeaderError:
                tags = ID3()
            
            # Remove existing lyrics
            tags.delall("USLT")
            
            tags.add(USLT(encoding=3, lang='eng', desc='', text=lyrics))
            tags.save(filepath)
            return True
            
        return False
    except Exception as e:
        print(f"Error embedding lyrics: {e}")
        return False

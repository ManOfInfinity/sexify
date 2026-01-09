import os
from typing import Optional, Dict
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, APIC, USLT, ID3NoHeaderError, TIT2, TPE1, TALB, TPE2, TDRC, TRCK, TPOS, TSRC, COMM
from mutagen.mp3 import MP3
from .filemanager import check_file_exists

def embed_metadata(filepath: str, metadata: Dict[str, str], cover_path: Optional[str] = None,
                   cover_data: Optional[bytes] = None) -> bool:
    """
    Embed metadata into a FLAC, M4A, or MP3 file.
    metadata dict keys: title, artist, album, album_artist, date, track_number, total_tracks, disc_number, isrc, lyrics, description
    cover_data: raw bytes of cover image (takes priority over cover_path)
    """
    if not check_file_exists(filepath):
        return False

    ext = os.path.splitext(filepath)[1].lower()
    
    try:
        if ext == ".flac":
            return _embed_flac_metadata(filepath, metadata, cover_path, cover_data)
        elif ext in [".m4a", ".mp4", ".aac"]:
            return _embed_m4a_metadata(filepath, metadata, cover_path, cover_data)
        elif ext == ".mp3":
            return _embed_mp3_metadata(filepath, metadata, cover_path, cover_data)
        else:
            print(f"Unsupported format for metadata embedding: {ext}")
            return False
    except Exception as e:
        print(f"Error embedding metadata: {e}")
        return False

def _embed_flac_metadata(filepath: str, metadata: Dict[str, str], cover_path: Optional[str] = None,
                         cover_data: Optional[bytes] = None) -> bool:
    """Embed metadata into a FLAC file."""
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

    # Embed cover art
    if cover_data:
        audio.clear_pictures()
        image = Picture()
        image.type = 3  # Front cover
        image.mime = "image/jpeg"
        image.desc = "Cover"
        image.data = cover_data
        audio.add_picture(image)
    elif cover_path and check_file_exists(cover_path):
        audio.clear_pictures()
        image = Picture()
        image.type = 3
        image.mime = "image/jpeg"
        if cover_path.lower().endswith(".png"):
            image.mime = "image/png"
        image.desc = "Cover"
        with open(cover_path, "rb") as f:
            image.data = f.read()
        audio.add_picture(image)

    audio.save()
    return True

def _embed_m4a_metadata(filepath: str, metadata: Dict[str, str], cover_path: Optional[str] = None,
                        cover_data: Optional[bytes] = None) -> bool:
    """Embed metadata into an M4A/MP4 file."""
    audio = MP4(filepath)
    
    # MP4 tag mapping (iTunes-style atoms)
    if "title" in metadata: audio["\xa9nam"] = [metadata["title"]]
    if "artist" in metadata: audio["\xa9ART"] = [metadata["artist"]]
    if "album" in metadata: audio["\xa9alb"] = [metadata["album"]]
    if "album_artist" in metadata: audio["aART"] = [metadata["album_artist"]]
    if "date" in metadata: audio["\xa9day"] = [metadata["date"]]
    if "description" in metadata: audio["\xa9cmt"] = [metadata["description"]]
    if "lyrics" in metadata and metadata["lyrics"]: audio["\xa9lyr"] = [metadata["lyrics"]]
    
    # Track number (tuple: track, total)
    try:
        track_num = int(metadata.get("track_number", 0))
        total_tracks = int(metadata.get("total_tracks", 0))
        if track_num > 0:
            audio["trkn"] = [(track_num, total_tracks)]
    except (ValueError, TypeError):
        pass
    
    # Disc number
    try:
        disc_num = int(metadata.get("disc_number", 0))
        if disc_num > 0:
            audio["disk"] = [(disc_num, 0)]
    except (ValueError, TypeError):
        pass

    # Embed cover art
    cover_bytes = None
    if cover_data:
        cover_bytes = cover_data
    elif cover_path and check_file_exists(cover_path):
        with open(cover_path, "rb") as f:
            cover_bytes = f.read()
    
    if cover_bytes:
        # Detect image format
        if cover_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            imageformat = MP4Cover.FORMAT_PNG
        else:
            imageformat = MP4Cover.FORMAT_JPEG
        audio["covr"] = [MP4Cover(cover_bytes, imageformat=imageformat)]

    audio.save()
    return True

def _embed_mp3_metadata(filepath: str, metadata: Dict[str, str], cover_path: Optional[str] = None,
                        cover_data: Optional[bytes] = None) -> bool:
    """Embed metadata into an MP3 file using ID3v2 tags."""
    audio = MP3(filepath)
    
    # Ensure ID3 tags exist
    if audio.tags is None:
        audio.add_tags()
    
    tags = audio.tags
    
    # ID3v2 tag mapping
    if "title" in metadata: tags.add(TIT2(encoding=3, text=[metadata["title"]]))
    if "artist" in metadata: tags.add(TPE1(encoding=3, text=[metadata["artist"]]))
    if "album" in metadata: tags.add(TALB(encoding=3, text=[metadata["album"]]))
    if "album_artist" in metadata: tags.add(TPE2(encoding=3, text=[metadata["album_artist"]]))
    if "date" in metadata: tags.add(TDRC(encoding=3, text=[metadata["date"]]))
    if "isrc" in metadata: tags.add(TSRC(encoding=3, text=[metadata["isrc"]]))
    if "description" in metadata: tags.add(COMM(encoding=3, lang='eng', desc='', text=metadata["description"]))
    if "lyrics" in metadata and metadata["lyrics"]: tags.add(USLT(encoding=3, lang='eng', desc='', text=metadata["lyrics"]))
    
    # Track number
    try:
        track_num = int(metadata.get("track_number", 0))
        total_tracks = int(metadata.get("total_tracks", 0))
        if track_num > 0:
            track_str = f"{track_num}/{total_tracks}" if total_tracks > 0 else str(track_num)
            tags.add(TRCK(encoding=3, text=[track_str]))
    except (ValueError, TypeError):
        pass
    
    # Disc number
    try:
        disc_num = int(metadata.get("disc_number", 0))
        if disc_num > 0:
            tags.add(TPOS(encoding=3, text=[str(disc_num)]))
    except (ValueError, TypeError):
        pass

    # Embed cover art
    cover_bytes = None
    if cover_data:
        cover_bytes = cover_data
    elif cover_path and check_file_exists(cover_path):
        with open(cover_path, "rb") as f:
            cover_bytes = f.read()
    
    if cover_bytes:
        # Detect image format
        if cover_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"
        tags.add(APIC(encoding=3, mime=mime_type, type=3, desc='Cover', data=cover_bytes))

    audio.save()
    return True


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

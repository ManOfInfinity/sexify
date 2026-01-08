import os
import re
import unicodedata

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a string to be safe for filenames.
    """
    # Replace illegal characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove control characters
    filename = "".join(ch for ch in filename if unicodedata.category(ch)[0] != "C")
    return filename.strip()

def build_expected_filename(
    track_name: str,
    artist_name: str,
    album_name: str,
    album_artist: str,
    release_date: str,
    filename_format: str,
    track_number: int = 0,
    position: int = 0,
    disc_number: int = 0,
    use_album_track_number: bool = False,
    service_name: str = ""
) -> str:
    """
    Build a filename based on the provided format and metadata.
    Supported placeholders:
    {title}, {artist}, {album}, {album_artist}, {release_date},
    {track_number}, {position}, {disc_number}, {service}
    """
    if not filename_format:
        filename_format = "{title} - {artist}"

    # Determine which track number to use
    tn = track_number if use_album_track_number else position
    
    # Format track/disc numbers with leading zeros (e.g. 01)
    tn_str = f"{tn:02d}"
    dn_str = f"{disc_number:02d}"

    # Replace placeholders
    filename = filename_format.format(
        title=track_name,
        artist=artist_name,
        album=album_name,
        album_artist=album_artist,
        release_date=release_date,
        track_number=tn_str,
        track=tn_str,  # Alias for {track} placeholder used in config
        position=f"{position:02d}",
        disc_number=dn_str,
        service=service_name
    )


    return sanitize_filename(filename) + ".flac"

def build_folder_path(
    folder_template: str,
    artist_name: str,
    album_name: str,
    album_artist: str,
    release_date: str,
    service_name: str = ""
) -> str:
    """
    Build folder path from template.
    Supported placeholders: {artist}, {album}, {album_artist}, {year}, {service}
    """
    if not folder_template:
        return ""
        
    # Extract year from release_date (YYYY-MM-DD)
    year = release_date.split('-')[0] if release_date else ""
    
    # Clean up service name for folder (e.g. [TIDAL], [AMZN])
    service_abbrev = {
        "amazon": "AMZN",
        "tidal": "TIDAL",
        "qobuz": "QOBUZ",
    }
    short_name = service_abbrev.get(service_name.lower(), service_name.upper()) if service_name else ""
    svc_tag = f"[{short_name}]" if short_name else ""
    
    # Manually handle {service} or {source} if user uses that
    # The config comment said {source} -> [TIDAL]
    # So we'll provide source=svc_tag, service=short_name
    
    folder_path = folder_template.format(
        artist=artist_name,
        album=album_name,
        album_artist=album_artist,
        year=year,
        service=short_name,
        source=svc_tag
    )
    
    # Sanitize each component
    parts = folder_path.split('/')
    sanitized_parts = [sanitize_filename(p) for p in parts]
    return os.path.join(*sanitized_parts)

def normalize_path(path: str) -> str:
    """Normalize a filesystem path."""
    return os.path.normpath(path)

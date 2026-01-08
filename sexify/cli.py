import click
import sys
import os
from .core.downloader import Downloader, DownloadRequest
from .services.spotify import SpotifyClient
from .utils.analysis import analyze_track
from .core.config import config
from .utils.logger import log_info, log_error, log_success

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

class RecursiveHelpGroup(click.Group):
    def format_help(self, ctx, formatter):
        super().format_help(ctx, formatter)
        formatter.write('\n')
        formatter.write('--- Subcommands Details ---\n')
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd:
                formatter.write('\n')
                formatter.write(f'Command: {subcommand}\n')
                with click.Context(cmd, info_name=subcommand, parent=ctx) as sub_ctx:
                    cmd.format_help(sub_ctx, formatter)
                formatter.write('\n')

@click.group(cls=RecursiveHelpGroup, context_settings=CONTEXT_SETTINGS)
def cli():
    """Sexify - Lossless. Effortless. 💿 Your Music, Uncompressed."""
    pass

@cli.command('download', context_settings=CONTEXT_SETTINGS)
@click.argument('url')
@click.option('--service', '-s', default=lambda: config.get('service', 'tidal'), help='Download service')
@click.option('--quality', '-q', default=None, help='Audio quality (LOSSLESS, HI_RES, MP3_320)')
@click.option('--output', '-o', default=lambda: config.get('output_dir'), help='Output directory')
@click.option('--lyrics/--no-lyrics', default=lambda: config.get('embed_lyrics', True), help='Embed lyrics')
@click.option('--cover-max/--no-cover-max', default=lambda: config.get('embed_max_quality_cover', True), help='Embed max quality cover')
def download(url, service, quality, output, lyrics, cover_max):
    """Download track, album, or playlist from Spotify URL."""

    if not quality:
        quality = config.get(f"{service}.quality") or "LOSSLESS"

    log_info(f"Starting download using {service.upper()} (Quality: {quality})", 'sexify')
    
    spotify = SpotifyClient()
    parsed = spotify.parse_url(url)
    if not parsed:
        log_error("Invalid Spotify URL", 'sexify')
        sys.exit(1)
        
    downloader = Downloader()
    
    items = []
    is_playlist = False
    playlist_name = ""
    
    if parsed['type'] == 'track':
        track = spotify.get_track(parsed['id'])
        if track: items.append(track)
        else: log_error("Track not found", 'spotify')
        
    elif parsed['type'] == 'album':
        log_info("Fetching album tracks...", 'spotify')
        items = spotify.get_album_tracks(parsed['id'])
        
    elif parsed['type'] == 'playlist':
        log_info("Fetching playlist tracks...", 'spotify')
        playlist_info = spotify.get_playlist(parsed['id'])
        playlist_name = playlist_info.get('name', 'Playlist') if playlist_info else 'Playlist'
        is_playlist = True
        log_info(f"Playlist: {playlist_name}", 'spotify')
        items = spotify.get_playlist_tracks(parsed['id'])
    
    elif parsed['type'] == 'isrc':
        log_info(f"Downloading by ISRC: {parsed['id']}", 'sexify')
        items.append({
            'id': '',
            'name': 'Unknown',
            'artists': [{'name': 'Unknown'}],
            'album': {'name': '', 'artists': [], 'release_date': '', 'images': [], 'total_tracks': 1},
            'external_ids': {'isrc': parsed['id']},
            'track_number': 1,
            'disc_number': 1
        })
        
    if not items:
        log_error("No tracks found to download.", 'sexify')
        sys.exit(1)

    
    if parsed['type'] == 'album':
        album_info = spotify.get_album(parsed['id'])
        if album_info:
            log_info(f"Album: {album_info.get('name')} by {', '.join([a['name'] for a in album_info.get('artists', [])])}", 'spotify')
            for item in items:
                item['album'] = {
                    'name': album_info.get('name', ''),
                    'artists': album_info.get('artists', []),
                    'release_date': album_info.get('release_date', ''),
                    'images': album_info.get('images', []),
                    'total_tracks': album_info.get('total_tracks', 0)
                }
                if not item.get('external_ids'):
                    full_track = spotify.get_track(item.get('id'))
                    if full_track:
                        item['external_ids'] = full_track.get('external_ids', {})
        
    log_info(f"Found {len(items)} tracks. Starting download...", 'sexify')

    
    success_count = 0
    fail_count = 0
    
    total_tracks = len(items)
    for i, item in enumerate(items):
        artists = item.get('artists', [])
        artist_name = ", ".join([a['name'] for a in artists])
        album = item.get('album', {})
        
        req = DownloadRequest(
            isrc=item.get('external_ids', {}).get('isrc', ''),
            service=service,
            spotify_id=item.get('id', ''),
            track_name=item.get('name', ''),
            artist_name=artist_name,
            album_name=album.get('name', ''),
            album_artist=", ".join([a['name'] for a in album.get('artists', [])]),
            release_date=album.get('release_date', ''),
            cover_url=album.get('images', [{}])[0].get('url', '') if album.get('images') else '',
            output_dir=output,
            audio_format=quality,
            filename_format=config.get('filename_template', '{title} - {artist}'),
            track_number=item.get('track_number', 0),
            total_tracks=album.get('total_tracks', 0),
            disc_number=item.get('disc_number', 1),
            position=i+1,
            embed_lyrics=lyrics,
            embed_max_quality_cover=cover_max,
            is_playlist=is_playlist,
            playlist_name=playlist_name
        )

        
        log_info(f"Processing: [{i+1}/{total_tracks}] {artist_name} - {req.track_name}", 'sexify')
        if downloader.download_track(req):
            success_count += 1
        else:
            fail_count += 1
            
    log_success(f"Download complete. Success: {success_count}, Failed: {fail_count}", 'sexify')

# Alias: dl -> download
cli.add_command(download, name='dl')

@cli.command(context_settings=CONTEXT_SETTINGS)
@click.argument('path', type=click.Path(exists=True))
def analyze(path):
    """Analyze a FLAC file."""
    if os.path.isdir(path):
        click.echo("Bulk analysis not yet supported.")
        return
        
    res = analyze_track(path)
    if res:
        click.echo(f"File: {res.file_path}")
        click.echo(f"Sample Rate: {res.sample_rate} Hz")
        click.echo(f"Bit Depth: {res.bit_depth}")
        click.echo(f"Channels: {res.channels}")
        click.echo(f"Duration: {res.duration:.2f} s")
    else:
        click.echo("Failed to analyze file.")

def main():
    cli()

if __name__ == '__main__':
    main()

"""
Constants used throughout the Sexify application.
"""

# Network timeouts (seconds)
DEFAULT_TIMEOUT = 10
DOWNLOAD_TIMEOUT = 120
STREAM_TIMEOUT = 15
AUTH_TIMEOUT = 10
SEARCH_TIMEOUT = 15  # For search/API requests
COVER_TIMEOUT = 30  # For cover art downloads

# Download settings
DOWNLOAD_CHUNK_SIZE = 8192  # 8KB chunks for memory efficiency

# Amazon Music polling
AMAZON_MAX_POLL_ATTEMPTS = 60  # Maximum number of status checks
AMAZON_POLL_INTERVAL = 3  # Seconds between status checks
AMAZON_TOTAL_TIMEOUT = AMAZON_MAX_POLL_ATTEMPTS * AMAZON_POLL_INTERVAL  # 180 seconds

# SongLink API rate limiting
SONGLINK_MAX_CALLS_PER_MINUTE = 9
SONGLINK_RATE_LIMIT_WINDOW = 60  # seconds
SONGLINK_MIN_DELAY_BETWEEN_CALLS = 7  # seconds between individual calls
SONGLINK_API_TIMEOUT = 30  # seconds for API requests

# Retry settings
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2

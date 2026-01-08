"""
Structured logging utility for Sexify.
Uses Python's logging module with rich for colored output.
Format matches vinetrimmer style with service prefixes.
"""
import logging
import sys
from datetime import datetime
from typing import Optional

# Try to use Rich for colored output, fallback to basic logging
try:
    from rich.logging import RichHandler
    from rich.console import Console
    from rich.theme import Theme
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Log format: "HH:MM:SS LEVEL    SERVICE: Message"
LOG_FORMAT = "{name}: {message}"
LOG_DATE_FORMAT = "%H:%M:%S"

# Service name abbreviations
SERVICE_NAMES = {
    'sexify': 'SEXIFY',
    'spotify': 'SPFY',
    'amazon': 'AMZN',
    'tidal': 'TIDAL',
    'qobuz': 'QOBUZ',
    'apple': 'APPLE',
    'lyrics': 'LYRICS',
    'cover': 'COVER',
    'meta': 'META',
}

_configured = False
_loggers = {}
_console = None


def setup_logging(verbose: bool = False, debug: bool = False):
    """Configure logging with rich output (call once at startup)."""
    global _configured, _console
    if _configured:
        return
    
    if HAS_RICH:
        # Rich handler with custom theme
        _console = Console(
            theme=Theme({
                "logging.level.info": "blue",
                "logging.level.warning": "yellow", 
                "logging.level.error": "red",
                "logging.level.debug": "dim",
            }),
            force_terminal=True,
            width=120,
            soft_wrap=True,
        )
        
        handler = RichHandler(
            console=_console,
            level=logging.DEBUG if debug else logging.INFO,
            show_path=debug,
            rich_tracebacks=True,
            markup=True,
            show_time=True,
            omit_repeated_times=True,
            log_time_format="[%H:%M:%S]",
        )

    else:
        _console = None
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt=LOG_DATE_FORMAT
        ))
    
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        style="{",
        handlers=[handler],
    )
    
    _configured = True


def get_logger(service: str = 'sexify') -> logging.Logger:
    """Get a logger for the specified service."""
    if not _configured:
        setup_logging()
    
    name = SERVICE_NAMES.get(service.lower(), service.upper())
    
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)
    
    return _loggers[name]


def log_info(message: str, service: str = 'sexify'):
    """Log info message (blue)."""
    get_logger(service).info(message)


def log_sub(message: str, service: str = 'sexify'):
    """
    Log sub-item - uses same format as log_info for consistency.
    Used for continuation info like '+ Region: US', '+ Download ID: xxx'.
    """
    get_logger(service).info(message)




def log_error(message: str, service: str = 'sexify'):
    """Log error message (red)."""
    get_logger(service).error(message)


def log_debug(message: str, service: str = 'sexify'):
    """Log debug message (dim/grey)."""
    get_logger(service).debug(message)


def log_warn(message: str, service: str = 'sexify'):
    """Log warning message (yellow)."""
    get_logger(service).warning(message)


def log_success(message: str, service: str = 'sexify'):
    """Log success message (shown as info with checkmark)."""
    get_logger(service).info(f"✓ {message}")


# Initialize logging when module is imported
setup_logging()


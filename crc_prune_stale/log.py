"""Logging setup and configuration."""

import logging
from pathlib import Path

__all__ = ("configure_logging", )

LOG_PATH = Path("/var/log/prune_stale/prune_stale.log")
LOG_FORMAT = logging.Formatter(
    fmt="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def configure_logging(log_path: Path = LOG_PATH) -> None:
    """Initialize the application logger.

    Configures the root logger with a console handler first, then attempts to
    add a file handler. If the log directory does not exist or the file cannot
    be opened, a warning is emitted to the console and the application continues
    with console-only logging.

    Args:
        log_path: Path to the log file.
    """

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(LOG_FORMAT)
    root.addHandler(console_handler)

    try:
        file_handler = logging.FileHandler(str(log_path))

    except Exception:
        logging.warning("Could not open log file %s", log_path)
        return

    else:
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(LOG_FORMAT)
        root.addHandler(file_handler)

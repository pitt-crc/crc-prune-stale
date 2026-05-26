"""Logging setup and configuration."""

import logging.config
from pathlib import Path

__all__ = ["configure_logging"]


def configure_logging(log_path: Path = Path('/var/log/prune_stale/prune_stale.log')) -> None:
    """Initialize the application logger.

    Initializes the root logging handler with the following log handlers:
      - A file handler logging to the provided path.
      - A console handler.

    Args:
        log_path: Path to the log file.

    Raises:
        FileNotFoundError: If the parent directory of `log_path` does not exist.
    """

    if not log_path.parent.exists():
        raise FileNotFoundError(f'Log directory does not exist: {log_path.parent}')

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "standard",
            },
            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": str(log_path),
            },
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
        },
    })

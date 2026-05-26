"""Logging setup and configuration."""

import logging.config

__all__ = ["configure_logging"]


def configure_logging() -> None:
    """Initialize the application logger.

    Initializes the root logging handler with the following log handlers:
      - A file handler logging to /var/log/prune_stale/prune_stale.log.
      - A console handler.
    """

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
                "class": "logging.handlers.FileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": "/var/log/prune_stale/prune_stale.log",
            },
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
        },
    })

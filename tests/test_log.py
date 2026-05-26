"""Unit tests for the `log` module."""

import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from crc_prune_stale.log import configure_logging


class ConfigureLogging(TestCase):
    """Verify that `configure_logging` initialises the root logger correctly."""

    def setUp(self) -> None:
        """Instantiate a parser instance."""

        self.log_dir = TemporaryDirectory()

        self._reset_logging_config()
        configure_logging(Path(self.log_dir.name) / 'prune_stale.log')

    def tearDown(self) -> None:
        """Clean up the temporary log directory."""

        self._reset_logging_config()
        self.log_dir.cleanup()

    def _reset_logging_config(self) -> None:
        """Clear any existing logging configuration."""

        root = logging.getLogger()
        root.handlers.clear()

    def test_root_logger_level_is_debug(self) -> None:
        """Verify that the root logger level is set to `DEBUG`."""

        self.assertEqual(logging.getLogger().level, logging.DEBUG)

    def test_has_console_handler(self) -> None:
        """Verify that the root logger has a `StreamHandler` attached."""

        handler_types = [type(h) for h in logging.getLogger().handlers]
        self.assertIn(logging.StreamHandler, handler_types)

    def test_has_file_handler(self) -> None:
        """Verify that the root logger has a `FileHandler` attached."""

        handler_types = [type(h) for h in logging.getLogger().handlers]
        self.assertIn(logging.FileHandler, handler_types)

    def test_raises_on_inaccessible_log_directory(self) -> None:
        """Verify that a `FileNotFoundError` is raised when the log directory does not exist."""

        with self.assertRaises(FileNotFoundError):
            configure_logging(Path('/nonexistent/directory/prune_stale.log'))

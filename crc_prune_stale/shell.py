"""Utility functions for interacting with the underlying runtime environemnt."""

import logging
import subprocess

__all__ = ("run_subprocess",)

logger = logging.getLogger(__name__)


def run_subprocess(command: list[str]) -> subprocess.CompletedProcess:
    """Run a shell command, log it at DEBUG level, and return the completed process.

    Raises `subprocess.CalledProcessError` if the command exits with a non-zero
    return code.

    Args:
        command: The command and its arguments as a list of strings.

    Returns:
        result: The completed process with stdout and stderr captured as text.
    """

    logger.debug("Running command: %s", " ".join(command))
    return subprocess.run(command, capture_output=True, text=True, check=True)

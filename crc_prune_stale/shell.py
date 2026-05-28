"""Utility functions for interacting with the underlying runtime environemnt."""

import logging
import subprocess

__all__ = ("run_subprocess",)

logger = logging.getLogger(__name__)


def run_subprocess(command: list[str]) -> subprocess.CompletedProcess:
    """Run a shell command, log it at DEBUG level, and return the completed process.

    Execution errors are logged and raised.

    Args:
        command: The command and its arguments as a list of strings.

    Returns:
        result: The completed process with stdout and stderr captured as text.
    """

    cmd_str = " ".join(command)
    logger.debug("Running command: %s", cmd_str)

    try:
        return subprocess.run(command, capture_output=True, text=True, check=True)

    except Exception as exc:
        logger.error("Command %r exited with error: %s", cmd_str, exc)

        raise

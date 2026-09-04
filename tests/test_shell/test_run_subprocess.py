"""Unit tests for the `run_subprocess` function."""

import subprocess
from unittest import TestCase

from crc_prune_stale.shell import run_subprocess


class SuccessfulCommand(TestCase):
    """Verify the return value of a command that exits successfully."""

    def test_returns_completed_process_for_valid_command(self) -> None:
        """Verify a successful command returns a `CompletedProcess` with captured output."""

        result = run_subprocess(["echo", "hello"])
        self.assertIsInstance(result, subprocess.CompletedProcess)
        self.assertEqual(0, result.returncode)
        self.assertEqual("hello", result.stdout.strip())


class ErrorHandling(TestCase):
    """Verify the exceptions raised when a command cannot be run successfully."""

    def test_raises_called_process_error_on_nonzero_exit(self) -> None:
        """Verify a command that exits with a nonzero status raises `CalledProcessError`."""

        with self.assertRaises(subprocess.CalledProcessError):
            run_subprocess(["false"])

    def test_raises_on_missing_executable(self) -> None:
        """Verify an unknown executable raises a non-subprocess exception."""

        with self.assertRaises(Exception) as ctx:
            run_subprocess(["this-command-does-not-exist-xyz"])

        self.assertNotIsInstance(
            ctx.exception,
            subprocess.CalledProcessError,
            "Missing executable should raise FileNotFoundError, not CalledProcessError",
        )

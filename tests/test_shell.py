"""Tests for the `shell` module."""

import subprocess
from unittest import TestCase

from crc_prune_stale.shell import run_subprocess


class RunSubprocess(TestCase):
    """Verify subprocess invocation and error handling via `run_subprocess`."""

    def test_returns_completed_process_for_valid_command(self) -> None:
        """Verify a successful command returns a `CompletedProcess` with captured output."""

        result = run_subprocess(["echo", "hello"])
        self.assertIsInstance(result, subprocess.CompletedProcess)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "hello")

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

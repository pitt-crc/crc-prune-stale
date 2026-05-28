"""Tests for the `shell` module."""

import subprocess
from unittest import TestCase

from crc_prune_stale.shell import run_subprocess


class RunSubprocess(TestCase):
    """Verify subprocess invocation and error handling via `run_subprocess`."""

    def test_returns_completed_process_for_valid_command(self) -> None:
        """Verify that a successful command returns a `CompletedProcess` with captured output."""

        result = run_subprocess(["echo", "hello"])
        self.assertIsInstance(result, subprocess.CompletedProcess)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "hello")

    def test_raises_on_command_error(self) -> None:
        """Verify that an unknown command raises a subprocess error."""

        with self.assertRaises(Exception):
            run_subprocess(["this-command-does-not-exist-xyz"])

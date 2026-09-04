"""Unit tests for the `main` function."""

import logging
import subprocess
from io import StringIO
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale.__main__ import main

from .common import DEFAULT_CLUSTER


@patch("crc_prune_stale.__main__.configure_logging")
@patch("crc_prune_stale.__main__.fetch_cluster_name")
@patch("crc_prune_stale.__main__.run")
class ArgumentResolution(TestCase):
    """Verify how default and command line argument values are resolved."""

    def test_resolved_defaults_passed_to_run(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify the cluster resolved from Slurm is used when no arguments are given."""

        mock_cluster.return_value = DEFAULT_CLUSTER

        with patch("sys.argv", ["prune-stale"]):
            main()

        kwargs = mock_run.call_args.kwargs
        self.assertEqual(DEFAULT_CLUSTER, kwargs["cluster"])

    def test_partitions_are_not_resolved(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify partitions are left unresolved so every partition on the cluster is queried."""

        mock_cluster.return_value = DEFAULT_CLUSTER

        with patch("sys.argv", ["prune-stale", "--cluster", "mpi"]):
            main()

        kwargs = mock_run.call_args.kwargs
        self.assertIsNone(kwargs["partitions"], "Partitions must not be resolved from the local node")

    def test_command_line_arguments_override_resolved_defaults(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify command line targeting arguments take precedence over the resolved defaults."""

        mock_cluster.return_value = DEFAULT_CLUSTER

        with patch("sys.argv", ["prune-stale", "--cluster", "mpi", "--partition", "opa"]):
            main()

        kwargs = mock_run.call_args.kwargs
        self.assertEqual("mpi", kwargs["cluster"])
        self.assertEqual(["opa"], kwargs["partitions"])


@patch("crc_prune_stale.__main__.configure_logging")
@patch("crc_prune_stale.__main__.fetch_cluster_name")
@patch("crc_prune_stale.__main__.run")
class ErrorHandling(TestCase):
    """Verify how errors raised during execution are handled."""

    def test_keyboard_interrupt_is_suppressed(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify a `KeyboardInterrupt` during execution does not propagate to the caller."""

        mock_cluster.return_value = DEFAULT_CLUSTER
        mock_run.side_effect = KeyboardInterrupt()

        with patch("sys.argv", ["prune-stale"]):
            main()

    def test_execution_error_is_logged_as_critical(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify an error raised during execution is logged instead of propagating."""

        mock_cluster.return_value = DEFAULT_CLUSTER
        mock_run.side_effect = RuntimeError("boom")

        with patch("sys.argv", ["prune-stale"]):
            with self.assertLogs("crc_prune_stale.__main__", level=logging.CRITICAL):
                with self.assertRaises(SystemExit):
                    main()

    def test_resolution_error_is_logged_as_critical(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify a failure resolving the default targeting values is logged instead of propagating."""

        mock_cluster.side_effect = subprocess.CalledProcessError(1, "scontrol", stderr="error")

        with patch("sys.argv", ["prune-stale"]):
            with self.assertLogs("crc_prune_stale.__main__", level=logging.CRITICAL):
                with self.assertRaises(SystemExit):
                    main()

        mock_run.assert_not_called()

    def test_help_flag_exits_cleanly(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify `--help` exits the runtime rather than being caught as an error."""

        mock_cluster.return_value = DEFAULT_CLUSTER

        with patch("sys.argv", ["prune-stale", "--help"]), patch("sys.stdout", new=StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                main()

        self.assertEqual(0, ctx.exception.code, "The help flag should exit with a success status")
        mock_run.assert_not_called()

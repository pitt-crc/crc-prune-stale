"""Unit tests for the `fetch_cluster_name` function."""

import subprocess

from crc_prune_stale.slurm import fetch_cluster_name

from .common import _make_result, SCONTROL_OUTPUT, SubprocessTestCase


class ScontrolArguments(SubprocessTestCase):
    """Verify the arguments used to invoke `scontrol`."""

    def test_scontrol_called_with_correct_arguments(self) -> None:
        """Verify `scontrol` is invoked with the expected command-line flags."""

        self.mock_run.return_value = _make_result(SCONTROL_OUTPUT)
        fetch_cluster_name()

        args = self.mock_run.call_args[0][0]
        self.assertEqual(["scontrol", "show", "config"], args)


class ClusterNameParsing(SubprocessTestCase):
    """Verify the cluster name parsed from the scontrol output."""

    def test_returns_configured_cluster_name(self) -> None:
        """Verify the configured cluster name is parsed from the scontrol output."""

        self.mock_run.return_value = _make_result(SCONTROL_OUTPUT)
        self.assertEqual("htc", fetch_cluster_name())

    def test_strips_whitespace_from_cluster_name(self) -> None:
        """Verify surrounding whitespace is stripped from the parsed cluster name."""

        self.mock_run.return_value = _make_result("  ClusterName  =   htc   \n")
        self.assertEqual("htc", fetch_cluster_name())

    def test_ignores_keys_ending_in_cluster_name(self) -> None:
        """Verify keys that merely end in `ClusterName` are not treated as a match."""

        self.mock_run.return_value = _make_result(
            "SlurmClusterName        = wrong\n"
            "ClusterName             = htc\n"
        )

        self.assertEqual("htc", fetch_cluster_name(), "Cluster name should be matched on the exact key")


class ErrorHandling(SubprocessTestCase):
    """Verify behavior when the cluster name cannot be determined."""

    def test_error_on_missing_cluster_name(self) -> None:
        """Verify a `RuntimeError` is raised when the cluster name is not configured."""

        self.mock_run.return_value = _make_result("ControlMachine          = mgmt01\n")
        with self.assertRaises(RuntimeError):
            fetch_cluster_name()

    def test_error_on_empty_cluster_name(self) -> None:
        """Verify a `RuntimeError` is raised when the cluster name is configured as empty."""

        self.mock_run.return_value = _make_result("ClusterName             = \n")
        with self.assertRaises(RuntimeError):
            fetch_cluster_name()

    def test_raises_on_subprocess_error(self) -> None:
        """Verify a `CalledProcessError` from scontrol propagates to the caller."""

        self.mock_run.side_effect = subprocess.CalledProcessError(1, "scontrol", stderr="error")

        with self.assertRaises(subprocess.CalledProcessError):
            fetch_cluster_name()

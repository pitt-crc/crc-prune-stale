"""Unit tests for the `__main__` module."""

import logging
import subprocess
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale.__main__ import main, run
from crc_prune_stale.slurm import JobRecord

DEFAULT_CLUSTER = "htc"
DEFAULT_PARTITIONS = ["smp", "gpu"]


def _make_job(days_ago: int) -> JobRecord:
    """Return a `JobRecord` with a submit time the given number of days in the past.

    Args:
        days_ago: Number of days before the current time to use as the submit time.

    Returns:
        job: A job record populated with mock data.
    """

    return JobRecord(
        job_id="12345",
        username="testuser",
        submit_time=datetime.now(tz=timezone.utc) - timedelta(days=days_ago),
        job_name="my_job",
        partition="gpu",
        state="PENDING",
    )


@patch("crc_prune_stale.__main__.fetch_pending_jobs")
@patch("crc_prune_stale.__main__.cancel_job")
@patch("crc_prune_stale.__main__.notify_users")
class RunFunction(TestCase):
    """Verify the orchestration behaviour of the `run` function."""

    @staticmethod
    def _call(**kwargs) -> None:
        """Call `run` with default test arguments, allowing overrides."""

        defaults = dict(
            cluster=DEFAULT_CLUSTER,
            partitions=DEFAULT_PARTITIONS,
            dry_run=False,
            threshold=10,
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
        )

        run(**{**defaults, **kwargs})

    def test_targeting_passed_to_fetch_pending_jobs(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Verify the cluster and partition names are passed through to `fetch_pending_jobs`."""

        mock_fetch.return_value = []
        self._call(cluster="mpi", partitions=["opa"])

        mock_fetch.assert_called_once_with(cluster="mpi", partitions=["opa"])

    def test_cluster_passed_to_cancel_job(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Verify the cluster name is passed through to `cancel_job`."""

        stale_job = _make_job(days_ago=20)
        mock_fetch.return_value = [stale_job]
        self._call(cluster="mpi", partitions=["opa"])

        mock_cancel.assert_called_once_with(stale_job, cluster="mpi", dry_run=False)

    def test_stale_job_is_cancelled(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Verify a job older than the threshold is passed to `cancel_job`."""

        stale_job = _make_job(days_ago=20)
        mock_fetch.return_value = [stale_job]
        self._call()

        mock_cancel.assert_called_once_with(stale_job, cluster=DEFAULT_CLUSTER, dry_run=False)

    def test_fresh_job_is_not_cancelled(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Verify a job newer than the threshold is not passed to `cancel_job`."""

        mock_fetch.return_value = [_make_job(days_ago=1)]
        self._call()

        mock_cancel.assert_not_called()

    def test_dry_run_passes_flag_to_cancel_job(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Verify `cancel_job` is called with `dry_run=True` when dry run is enabled."""

        stale_job = _make_job(days_ago=20)
        mock_fetch.return_value = [stale_job]
        self._call(dry_run=True)

        mock_cancel.assert_called_once_with(stale_job, cluster=DEFAULT_CLUSTER, dry_run=True)

    def test_notify_called_with_successfully_cancelled_jobs(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Verify `notify_users` receives only jobs for which `cancel_job` returned `True`."""

        stale_job = _make_job(days_ago=20)
        mock_fetch.return_value = [stale_job]
        mock_cancel.return_value = True
        self._call()

        notify_jobs = mock_notify.call_args.kwargs["jobs"]
        self.assertEqual([stale_job], notify_jobs)

    def test_notify_not_called_when_smtp_host_is_none(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Verify `notify_users` is not called when `smtp_host` is `None`."""

        mock_fetch.return_value = [_make_job(days_ago=20)]
        mock_cancel.return_value = True
        self._call(smtp_host=None)

        mock_notify.assert_not_called()

    def test_notify_not_called_on_dry_run(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Verify `notify_users` is not called when `dry_run` is `True`."""

        mock_fetch.return_value = [_make_job(days_ago=20)]
        mock_cancel.return_value = True
        self._call(dry_run=True)

        mock_notify.assert_not_called()


@patch("crc_prune_stale.__main__.configure_logging")
@patch("crc_prune_stale.__main__.fetch_partition_names")
@patch("crc_prune_stale.__main__.fetch_cluster_name")
@patch("crc_prune_stale.__main__.run")
class MainFunction(TestCase):
    """Verify the argument resolution and error handling behaviour of the `main` function."""

    def test_resolved_defaults_passed_to_run(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_partitions: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify targeting values resolved from Slurm are used when no arguments are given."""

        mock_cluster.return_value = DEFAULT_CLUSTER
        mock_partitions.return_value = DEFAULT_PARTITIONS

        with patch("sys.argv", ["prune-stale"]):
            main()

        kwargs = mock_run.call_args.kwargs
        self.assertEqual(DEFAULT_CLUSTER, kwargs["cluster"])
        self.assertEqual(DEFAULT_PARTITIONS, kwargs["partitions"])

    def test_command_line_arguments_override_resolved_defaults(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_partitions: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify command line targeting arguments take precedence over the resolved defaults."""

        mock_cluster.return_value = DEFAULT_CLUSTER
        mock_partitions.return_value = DEFAULT_PARTITIONS

        with patch("sys.argv", ["prune-stale", "--cluster", "mpi", "--partition", "opa"]):
            main()

        kwargs = mock_run.call_args.kwargs
        self.assertEqual("mpi", kwargs["cluster"])
        self.assertEqual(["opa"], kwargs["partitions"])

    def test_keyboard_interrupt_is_suppressed(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_partitions: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify a `KeyboardInterrupt` during execution does not propagate to the caller."""

        mock_cluster.return_value = DEFAULT_CLUSTER
        mock_partitions.return_value = DEFAULT_PARTITIONS
        mock_run.side_effect = KeyboardInterrupt()

        with patch("sys.argv", ["prune-stale"]):
            main()

    def test_execution_error_is_logged_as_critical(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_partitions: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify an error raised during execution is logged instead of propagating."""

        mock_cluster.return_value = DEFAULT_CLUSTER
        mock_partitions.return_value = DEFAULT_PARTITIONS
        mock_run.side_effect = RuntimeError("boom")

        with patch("sys.argv", ["prune-stale"]):
            with self.assertLogs("crc_prune_stale.__main__", level=logging.CRITICAL):
                main()

    def test_resolution_error_is_logged_as_critical(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_partitions: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify a failure resolving the default targeting values is logged instead of propagating."""

        mock_cluster.side_effect = subprocess.CalledProcessError(1, "scontrol", stderr="error")

        with patch("sys.argv", ["prune-stale"]):
            with self.assertLogs("crc_prune_stale.__main__", level=logging.CRITICAL):
                main()

        mock_run.assert_not_called()

    def test_help_flag_exits_cleanly(
        self,
        mock_run: MagicMock,
        mock_cluster: MagicMock,
        mock_partitions: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify `--help` exits the runtime rather than being caught as an error."""

        mock_cluster.return_value = DEFAULT_CLUSTER
        mock_partitions.return_value = DEFAULT_PARTITIONS

        with patch("sys.argv", ["prune-stale", "--help"]), patch("sys.stdout", new=StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                main()

        self.assertEqual(0, ctx.exception.code, "The help flag should exit with a success status")
        mock_run.assert_not_called()

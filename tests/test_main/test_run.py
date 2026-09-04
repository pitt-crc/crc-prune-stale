"""Unit tests for the `run` function."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from .common import _make_job, DEFAULT_CLUSTER, RunTestCase


@patch("crc_prune_stale.__main__.fetch_pending_jobs")
@patch("crc_prune_stale.__main__.cancel_job")
@patch("crc_prune_stale.__main__.notify_users")
class TargetingArguments(RunTestCase, TestCase):
    """Verify targeting arguments are forwarded to the Slurm layer."""

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

    def test_unset_partitions_passed_through_as_none(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
    ) -> None:
        """Verify an unset partition list is forwarded to `fetch_pending_jobs` unresolved."""

        mock_fetch.return_value = []
        self._call(cluster="mpi", partitions=None)

        mock_fetch.assert_called_once_with(cluster="mpi", partitions=None)

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


@patch("crc_prune_stale.__main__.fetch_pending_jobs")
@patch("crc_prune_stale.__main__.cancel_job")
@patch("crc_prune_stale.__main__.notify_users")
class StaleJobSelection(RunTestCase, TestCase):
    """Verify which pending jobs are selected for cancellation."""

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


@patch("crc_prune_stale.__main__.fetch_pending_jobs")
@patch("crc_prune_stale.__main__.cancel_job")
@patch("crc_prune_stale.__main__.notify_users")
class UserNotifications(RunTestCase, TestCase):
    """Verify the conditions under which affected users are notified."""

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

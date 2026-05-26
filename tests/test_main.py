"""Tests for the `__main__` module."""

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale import main
from crc_prune_stale.slurm import JobRecord


@patch('prune_stale.__main__.configure_logging')
@patch('prune_stale.__main__.fetch_pending_jobs')
@patch('prune_stale.__main__.cancel_job')
@patch('prune_stale.__main__.notify_user')
class Main(TestCase):
    """Verify the orchestration behaviour of the `main` function."""

    @staticmethod
    def _make_job(days_ago: int) -> JobRecord:
        """Return a `JobRecord` with a submit time the given number of days in the past."""

        return JobRecord(
            job_id='12345',
            username='testuser',
            submit_time=datetime.now(tz=timezone.utc) - timedelta(days=days_ago),
            job_name='my_job',
            partition='gpu',
        )

    def test_dry_run_does_not_cancel_jobs(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify that `cancel_job` is not called when `--dry-run` is set."""

        mock_fetch.return_value = [self._make_job(days_ago=20)]

        with patch('sys.argv', ['prune-stale', '--dry-run']):
            main()

        mock_cancel.assert_not_called()

    def test_dry_run_does_not_notify_users(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify that `notify_user` is not called when `--dry-run` is set."""

        mock_fetch.return_value = [self._make_job(days_ago=20)]

        with patch('sys.argv', ['prune-stale', '--dry-run']):
            main()

        mock_notify.assert_not_called()

    def test_stale_job_is_cancelled(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify that a job older than the threshold is passed to `cancel_job`."""

        stale_job = self._make_job(days_ago=20)
        mock_fetch.return_value = [stale_job]
        mock_cancel.return_value = True

        with patch('sys.argv', ['prune-stale']):
            main()

        mock_cancel.assert_called_once_with(stale_job)

    def test_fresh_job_is_not_cancelled(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify that a job newer than the threshold is not passed to `cancel_job`."""

        mock_fetch.return_value = [self._make_job(days_ago=1)]

        with patch('sys.argv', ['prune-stale']):
            main()

        mock_cancel.assert_not_called()

    def test_notify_called_after_successful_cancel(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify that `notify_user` is called when `cancel_job` returns `True`."""

        mock_fetch.return_value = [self._make_job(days_ago=20)]
        mock_cancel.return_value = True

        with patch('sys.argv', ['prune-stale']):
            main()

        mock_notify.assert_called_once()

    def test_notify_not_called_after_failed_cancel(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify that `notify_user` is not called when `cancel_job` returns `False`."""

        mock_fetch.return_value = [self._make_job(days_ago=20)]
        mock_cancel.return_value = False

        with patch('sys.argv', ['prune-stale']):
            main()

        mock_notify.assert_not_called()

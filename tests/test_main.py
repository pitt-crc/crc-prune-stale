"""Unit tests for the `__main__` module."""

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale.__main__ import run
from crc_prune_stale.slurm import JobRecord


@patch("crc_prune_stale.__main__.configure_logging")
@patch("crc_prune_stale.__main__.fetch_pending_jobs")
@patch("crc_prune_stale.__main__.cancel_job")
@patch("crc_prune_stale.__main__.notify_users")
class RunFunction(TestCase):
    """Verify the orchestration behaviour of the `run` function."""

    @staticmethod
    def _make_job(days_ago: int) -> JobRecord:
        """Return a `JobRecord` with a submit time the given number of days in the past."""

        return JobRecord(
            job_id="12345",
            username="testuser",
            submit_time=datetime.now(tz=timezone.utc) - timedelta(days=days_ago),
            job_name="my_job",
            partition="gpu",
            state="PENDING",
        )

    def _call(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
        **kwargs,
    ) -> None:
        """Call `run` with default arguments, allowing overrides."""

        defaults = dict(
            dry_run=False,
            threshold=10,
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
        )
        run(**{**defaults, **kwargs})

    def test_stale_job_is_cancelled(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify a job older than the threshold is passed to `cancel_job`."""

        stale_job = self._make_job(days_ago=20)
        mock_fetch.return_value = [stale_job]

        self._call(mock_notify, mock_cancel, mock_fetch, mock_configure_logging)

        mock_cancel.assert_called_once_with(stale_job, dry_run=False)

    def test_fresh_job_is_not_cancelled(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify a job newer than the threshold is not passed to `cancel_job`."""

        mock_fetch.return_value = [self._make_job(days_ago=1)]

        self._call(mock_notify, mock_cancel, mock_fetch, mock_configure_logging)

        mock_cancel.assert_not_called()

    def test_dry_run_passes_flag_to_cancel_job(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify `cancel_job` is called with `dry_run=True` when dry run is enabled."""

        stale_job = self._make_job(days_ago=20)
        mock_fetch.return_value = [stale_job]

        self._call(mock_notify, mock_cancel, mock_fetch, mock_configure_logging, dry_run=True)

        mock_cancel.assert_called_once_with(stale_job, dry_run=True)

    def test_notify_called_with_successfully_cancelled_jobs(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify `notify_users` receives only jobs for which `cancel_job` returned `True`."""

        stale_job = self._make_job(days_ago=20)
        mock_fetch.return_value = [stale_job]
        mock_cancel.return_value = True

        self._call(mock_notify, mock_cancel, mock_fetch, mock_configure_logging)

        notify_jobs = mock_notify.call_args.kwargs["jobs"]
        self.assertEqual(notify_jobs, [stale_job])

    def test_notify_not_called_after_failed_cancel(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify `notify_users` is not called when `cancel_job` returns `False`."""

        mock_fetch.return_value = [self._make_job(days_ago=20)]
        mock_cancel.return_value = False

        self._call(mock_notify, mock_cancel, mock_fetch, mock_configure_logging)

        mock_notify.assert_not_called()

    def test_notify_not_called_when_smtp_host_is_none(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify `notify_users` is not called when `smtp_host` is `None`."""

        mock_fetch.return_value = [self._make_job(days_ago=20)]
        mock_cancel.return_value = True

        self._call(mock_notify, mock_cancel, mock_fetch, mock_configure_logging, smtp_host=None)

        mock_notify.assert_not_called()

    def test_notify_not_called_on_dry_run(
        self,
        mock_notify: MagicMock,
        mock_cancel: MagicMock,
        mock_fetch: MagicMock,
        mock_configure_logging: MagicMock,
    ) -> None:
        """Verify `notify_users` is not called when `dry_run` is `True`."""

        mock_fetch.return_value = [self._make_job(days_ago=20)]
        mock_cancel.return_value = True

        self._call(mock_notify, mock_cancel, mock_fetch, mock_configure_logging, dry_run=True)

        mock_notify.assert_not_called()

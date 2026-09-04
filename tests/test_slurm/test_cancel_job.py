"""Unit tests for the `cancel_job` function."""

import logging
import subprocess
from dataclasses import replace
from datetime import datetime, timezone

from crc_prune_stale.slurm import cancel_job, JobRecord

from .common import (
    _make_result,
    SCANCEL_DENIED_STDERR,
    SCANCEL_FATAL_STDERR,
    SCANCEL_VERBOSE_STDERR,
    SLURM_LOGGER,
    SubprocessTestCase,
    THROTTLED_ARRAY_ID,
    THROTTLED_ARRAY_ID_NORMALIZED,
    UNTHROTTLED_ARRAY_ID,
)


class CancelJobTestCase(SubprocessTestCase):
    """Base class providing a pending job record targeted for cancellation."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        super().setUp()
        self.mock_run.return_value = _make_result()
        self.job = JobRecord(
            job_id="12345",
            username="testuser",
            submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            job_name="my_job",
            partition="gpu",
            state="PENDING",
            reason="Resources",
        )


class ScancelArguments(CancelJobTestCase):
    """Verify the arguments used to invoke `scancel`."""

    def test_scancel_called_with_job_id(self) -> None:
        """Verify `scancel` is invoked with the job ID."""

        cancel_job(self.job)

        args = self.mock_run.call_args[0][0]
        self.assertEqual("scancel", args[0])
        self.assertIn("12345", args)

    def test_scancel_called_with_normalized_array_job_id(self) -> None:
        """Verify the array task throttle is stripped from the ID passed to `scancel`."""

        cancel_job(replace(self.job, job_id=THROTTLED_ARRAY_ID))

        args = self.mock_run.call_args[0][0]
        self.assertIn(
            THROTTLED_ARRAY_ID_NORMALIZED, args, "Slurm rejects the concurrency limit reported by squeue"
        )

    def test_scancel_called_with_unmodified_unthrottled_array_id(self) -> None:
        """Verify an array job ID without a concurrency limit is passed to `scancel` unchanged."""

        cancel_job(replace(self.job, job_id=UNTHROTTLED_ARRAY_ID))

        args = self.mock_run.call_args[0][0]
        self.assertIn(UNTHROTTLED_ARRAY_ID, args)

    def test_job_record_id_is_not_modified(self) -> None:
        """Verify normalizing the ID for `scancel` leaves the job record untouched."""

        job = replace(self.job, job_id=THROTTLED_ARRAY_ID)
        cancel_job(job)

        self.assertEqual(THROTTLED_ARRAY_ID, job.job_id, "Notifications should report the ID squeue reported")

    def test_cluster_flag_included_when_specified(self) -> None:
        """Verify the `--clusters` flag is included when a cluster is given."""

        cancel_job(self.job, cluster="mpi")

        args = self.mock_run.call_args[0][0]
        self.assertIn("--clusters=mpi", args, "Cancellation must target the cluster the job was queried from")

    def test_cluster_flag_omitted_by_default(self) -> None:
        """Verify no `--clusters` flag is passed when no cluster is given."""

        cancel_job(self.job)

        args = self.mock_run.call_args[0][0]
        self.assertFalse(
            any(arg.startswith("--clusters") for arg in args),
            "Cluster scope should defer to the local node configuration",
        )


class ReturnValues(CancelJobTestCase):
    """Verify the value returned for each cancellation outcome."""

    def test_returns_true_on_success(self) -> None:
        """Verify `True` is returned when scancel exits without error."""

        self.assertTrue(cancel_job(self.job))

    def test_throttled_array_job_returns_true(self) -> None:
        """Verify a throttled array job is reported as cancelled."""

        self.assertTrue(cancel_job(replace(self.job, job_id=THROTTLED_ARRAY_ID)))

    def test_returns_false_on_error_in_stderr(self) -> None:
        """Verify `False` is returned when scancel logs an error but exits successfully."""

        self.mock_run.return_value = _make_result(stderr=SCANCEL_DENIED_STDERR)
        self.assertFalse(cancel_job(self.job, cluster="mpi"))

    def test_returns_false_on_fatal_in_stderr(self) -> None:
        """Verify `False` is returned when scancel logs a fatal error but exits successfully."""

        self.mock_run.return_value = _make_result(stderr=SCANCEL_FATAL_STDERR)
        self.assertFalse(cancel_job(self.job, cluster="mpi"))

    def test_verbose_stderr_produces_no_failure(self) -> None:
        """Verify non-error messages in stderr are not treated as an error."""

        self.mock_run.return_value = _make_result(stderr=SCANCEL_VERBOSE_STDERR)
        self.assertTrue(cancel_job(self.job))

    def test_error_within_message_body_produces_no_failure(self) -> None:
        """Verify the word `error` inside a non-error message is not treated as an error."""

        self.mock_run.return_value = _make_result(stderr="scancel: Terminating job 12345 after error recovery")

        self.assertTrue(cancel_job(self.job))

    def test_returns_false_on_subprocess_error(self) -> None:
        """Verify `False` is returned when scancel raises an exception."""

        self.mock_run.side_effect = subprocess.CalledProcessError(1, "scancel", stderr="error")
        self.assertFalse(cancel_job(self.job))

    def test_returns_false_on_non_subprocess_error(self) -> None:
        """Verify `False` is returned when scancel raises a non-subprocess exception."""

        self.mock_run.side_effect = OSError("command not found")
        self.assertFalse(cancel_job(self.job))


class LogRecords(CancelJobTestCase):
    """Verify the log records emitted for each cancellation outcome."""

    def test_stderr_error_is_logged(self) -> None:
        """Verify the error returned by the controller is logged against the job ID."""

        self.mock_run.return_value = _make_result(stderr=SCANCEL_DENIED_STDERR)

        with self.assertLogs(SLURM_LOGGER, level=logging.ERROR) as captured:
            cancel_job(self.job, cluster="mpi")

        combined = "\n".join(captured.output)
        self.assertIn("12345", combined, "Log record should identify the job that was not cancelled")
        self.assertIn(
            "Access/permission denied", combined, "Log record should include the message reported by Slurm"
        )

    def test_success_log_reports_unnormalized_job_id(self) -> None:
        """Verify the cancellation log record identifies the job by its original ID."""

        with self.assertLogs(SLURM_LOGGER, level=logging.INFO) as captured:
            cancel_job(replace(self.job, job_id=THROTTLED_ARRAY_ID))

        self.assertIn(THROTTLED_ARRAY_ID, "\n".join(captured.output))

    def test_dry_run_log_reports_unnormalized_job_id(self) -> None:
        """Verify the dry run log record identifies the job by its original ID."""

        with self.assertLogs(SLURM_LOGGER, level=logging.INFO) as captured:
            cancel_job(replace(self.job, job_id=THROTTLED_ARRAY_ID), dry_run=True)

        self.assertIn(THROTTLED_ARRAY_ID, "\n".join(captured.output))


class DryRun(CancelJobTestCase):
    """Verify cancellation is not attempted when running in dry run mode."""

    def test_dry_run_does_not_invoke_scancel(self) -> None:
        """Verify `scancel` is not invoked when `dry_run` is True."""

        cancel_job(self.job, dry_run=True)
        self.mock_run.assert_not_called()

    def test_dry_run_with_cluster_does_not_invoke_scancel(self) -> None:
        """Verify `scancel` is not invoked on a dry run even when a cluster is given."""

        cancel_job(self.job, cluster="mpi", dry_run=True)
        self.mock_run.assert_not_called()

    def test_dry_run_returns_true(self) -> None:
        """Verify `True` is returned when `dry_run` is True."""

        self.assertTrue(cancel_job(self.job, dry_run=True))

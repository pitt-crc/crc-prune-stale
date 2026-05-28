"""Tests for the `slurm` module."""

import subprocess
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale.slurm import cancel_job, fetch_pending_jobs, JobRecord


class FetchPendingJobs(TestCase):
    """Verify the subprocess call and output parsing behaviour of `fetch_pending_jobs`."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.subprocess_patch = patch("crc_prune_stale.slurm.run_subprocess")
        self.mock_run = self.subprocess_patch.start()

    def tearDown(self) -> None:
        """Close any open server connections."""

        self.subprocess_patch.stop()

    @staticmethod
    def _make_result(stdout: str) -> MagicMock:
        """Return a mock `subprocess.CompletedProcess` with the given stdout."""

        result = MagicMock()
        result.stdout = stdout
        return result

    def test_squeue_called_with_correct_arguments(self) -> None:
        """Verify that `squeue` is invoked with the expected command-line flags."""

        self.mock_run.return_value = self._make_result("")
        fetch_pending_jobs()

        args = self.mock_run.call_args[0][0]
        self.assertEqual(args[0], "squeue")
        self.assertIn("--states=PENDING", args)
        self.assertIn("--noheader", args)

    def test_raises_on_subprocess_error(self) -> None:
        """Verify that a `CalledProcessError` from squeue propagates to the caller."""

        self.mock_run.side_effect = subprocess.CalledProcessError(1, "squeue", stderr="error")

        with self.assertRaises(subprocess.CalledProcessError):
            fetch_pending_jobs()

    def test_returns_list_of_job_records(self) -> None:
        """Verify that a valid squeue line is parsed into a `JobRecord`."""

        self.mock_run.return_value = self._make_result(
            "12345|testuser|2024-01-01T12:00:00|my_job|gpu\n"
        )

        jobs = fetch_pending_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertIsInstance(jobs[0], JobRecord)

    def test_parses_job_fields_correctly(self) -> None:
        """Verify that all fields of a parsed `JobRecord` match the squeue output."""

        self.mock_run.return_value = self._make_result(
            "12345|testuser|2024-01-01T12:00:00|my_job|gpu\n"
        )

        job = fetch_pending_jobs()[0]
        self.assertEqual(job.job_id, "12345")
        self.assertEqual(job.username, "testuser")
        self.assertEqual(job.submit_time, datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(job.job_name, "my_job")
        self.assertEqual(job.partition, "gpu")

    def test_parses_multiple_jobs(self) -> None:
        """Verify that multiple output lines are each parsed into a `JobRecord`."""

        self.mock_run.return_value = self._make_result(
            "12345|testuser|2024-01-01T12:00:00|my_job|gpu\n"
            "67890|otheruser|2024-02-01T08:00:00|other_job|cpu\n"
        )

        self.assertEqual(len(fetch_pending_jobs()), 2)

    def test_returns_empty_list_when_no_output(self) -> None:
        """Verify that an empty squeue output returns an empty list."""

        self.mock_run.return_value = self._make_result("")
        self.assertEqual(fetch_pending_jobs(), [])

    def test_skips_blank_lines(self) -> None:
        """Verify that blank lines in squeue output are ignored."""

        self.mock_run.return_value = self._make_result(
            "\n12345|testuser|2024-01-01T12:00:00|my_job|gpu\n\n"
        )

        self.assertEqual(len(fetch_pending_jobs()), 1)

    def test_skips_malformed_lines(self) -> None:
        """Verify that lines with the wrong number of fields are skipped."""

        self.mock_run.return_value = self._make_result(
            "12345|testuser|2024-01-01T12:00:00\n"
        )

        self.assertEqual(fetch_pending_jobs(), [])

    def test_skips_lines_with_unparseable_submit_time(self) -> None:
        """Verify that lines with an invalid submit time are skipped."""

        self.mock_run.return_value = self._make_result(
            "12345|testuser|not-a-date|my_job|gpu\n"
        )

        self.assertEqual(fetch_pending_jobs(), [])

    def test_strips_whitespace_from_fields(self) -> None:
        """Verify that leading and trailing whitespace is stripped from each field."""

        self.mock_run.return_value = self._make_result(
            " 12345 | testuser | 2024-01-01T12:00:00 | my_job | gpu \n"
        )

        job = fetch_pending_jobs()[0]
        self.assertEqual(job.job_id, "12345")
        self.assertEqual(job.username, "testuser")
        self.assertEqual(job.partition, "gpu")


class CancelJob(TestCase):
    """Verify the subprocess call and return value behaviour of `cancel_job`."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.job = JobRecord(
            job_id="12345",
            username="testuser",
            submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            job_name="my_job",
            partition="gpu",
        )

        self.subprocess_patch = patch("crc_prune_stale.slurm.run_subprocess")
        self.mock_run = self.subprocess_patch.start()

    def tearDown(self) -> None:
        """Close any open server connections."""

        self.subprocess_patch.stop()

    def test_scancel_called_with_job_id(self) -> None:
        """Verify that `scancel` is invoked with the job ID."""

        cancel_job(self.job)

        args = self.mock_run.call_args[0][0]
        self.assertEqual(args[0], "scancel")
        self.assertIn("12345", args)

    def test_returns_true_on_success(self) -> None:
        """Verify that `True` is returned when scancel exits without error."""

        self.assertTrue(cancel_job(self.job))

    def test_returns_false_on_subprocess_error(self) -> None:
        """Verify that `False` is returned when scancel raises a `CalledProcessError`."""

        self.mock_run.side_effect = subprocess.CalledProcessError(1, "scancel", stderr="error")
        self.assertFalse(cancel_job(self.job))

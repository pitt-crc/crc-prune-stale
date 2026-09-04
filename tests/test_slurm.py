"""Tests for the `slurm` module."""

import logging
import subprocess
from dataclasses import replace
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale.slurm import cancel_job, fetch_cluster_name, fetch_pending_jobs, JobRecord, normalize_job_id

# Logger name targeted when asserting against emitted log records
SLURM_LOGGER = "crc_prune_stale.slurm"

# Mock stdout streams returned by `squeue` and `scontrol`
PENDING_LINE = "12345|testuser|2024-01-01T12:00:00|my_job|gpu|PENDING\n"
CLUSTER_BANNER = "CLUSTER: htc\n"
SCONTROL_OUTPUT = (
    "Configuration data as of 2024-01-01T12:00:00\n"
    "AccountingStorageHost   = mgmt01\n"
    "ClusterName             = htc\n"
    "ControlMachine          = mgmt01\n"
)

# Mock stderr streams returned by `scancel` alongside a zero exit status
SCANCEL_DENIED_STDERR = "scancel: error: Kill job error on job id 12345: Access/permission denied\n"
SCANCEL_FATAL_STDERR = "scancel: fatal: Unable to contact slurm controller (connect failure)\n"
SCANCEL_VERBOSE_STDERR = "scancel: verbose: Terminating job 12345\n"

# Array job IDs as reported by `squeue`, with and without a concurrency limit
THROTTLED_ARRAY_ID = "3237889_[0-15%16]"
THROTTLED_ARRAY_ID_NORMALIZED = "3237889_[0-15]"
UNTHROTTLED_ARRAY_ID = "20916495_[100-140]"


def _make_result(stdout: str = "", stderr: str = "") -> MagicMock:
    """Return a mock `subprocess.CompletedProcess` with the given output streams.

    Args:
        stdout: The standard output captured from the mock process.
        stderr: The standard error captured from the mock process.

    Returns:
        result: A mock completed process.
    """

    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    return result


class NormalizeJobId(TestCase):
    """Verify the job ID rewriting behaviour of `normalize_job_id`."""

    def test_array_task_throttle_is_removed(self) -> None:
        """Verify the concurrency limit is stripped from a throttled array job ID."""

        self.assertEqual(THROTTLED_ARRAY_ID_NORMALIZED, normalize_job_id(THROTTLED_ARRAY_ID))

    def test_single_digit_throttle_is_removed(self) -> None:
        """Verify a single digit concurrency limit is stripped."""

        self.assertEqual("3237889_[0-15]", normalize_job_id("3237889_[0-15%1]"))

    def test_multi_range_throttle_is_removed(self) -> None:
        """Verify the concurrency limit is stripped from an array job with several task ranges."""

        self.assertEqual("3237889_[1-3,7,9-11]", normalize_job_id("3237889_[1-3,7,9-11%4]"))

    def test_unthrottled_array_range_is_unchanged(self) -> None:
        """Verify an array job ID without a concurrency limit is returned unchanged."""

        self.assertEqual(UNTHROTTLED_ARRAY_ID, normalize_job_id(UNTHROTTLED_ARRAY_ID))

    def test_single_array_task_is_unchanged(self) -> None:
        """Verify the ID of an individual array task is returned unchanged."""

        self.assertEqual("22747001_6", normalize_job_id("22747001_6"))

    def test_plain_job_id_is_unchanged(self) -> None:
        """Verify a non-array job ID is returned unchanged."""

        self.assertEqual("20140070", normalize_job_id("20140070"))

    def test_percent_outside_task_range_is_preserved(self) -> None:
        """Verify a percent sign not terminating a task range is not stripped."""

        self.assertEqual("12345%16", normalize_job_id("12345%16"), "Only array task throttles should be removed")


class FetchClusterName(TestCase):
    """Verify the subprocess call and output parsing behaviour of `fetch_cluster_name`."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.subprocess_patch = patch("crc_prune_stale.slurm.run_subprocess")
        self.mock_run = self.subprocess_patch.start()

    def tearDown(self) -> None:
        """Close any open server connections."""

        self.subprocess_patch.stop()

    def test_scontrol_called_with_correct_arguments(self) -> None:
        """Verify `scontrol` is invoked with the expected command-line flags."""

        self.mock_run.return_value = _make_result(SCONTROL_OUTPUT)
        fetch_cluster_name()

        args = self.mock_run.call_args[0][0]
        self.assertEqual(["scontrol", "show", "config"], args)

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


class FetchPendingJobs(TestCase):
    """Verify the subprocess call and output parsing behaviour of `fetch_pending_jobs`."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.subprocess_patch = patch("crc_prune_stale.slurm.run_subprocess")
        self.mock_run = self.subprocess_patch.start()

    def tearDown(self) -> None:
        """Close any open server connections."""

        self.subprocess_patch.stop()

    def test_squeue_called_with_correct_arguments(self) -> None:
        """Verify `squeue` is invoked with the expected command-line flags."""

        self.mock_run.return_value = _make_result("")
        fetch_pending_jobs()

        args = self.mock_run.call_args[0][0]
        self.assertEqual("squeue", args[0])
        self.assertIn("--state=PENDING", args)
        self.assertIn("--noheader", args)

    def test_cluster_flag_included_when_specified(self) -> None:
        """Verify the `--clusters` flag is included when a cluster is given."""

        self.mock_run.return_value = _make_result("")
        fetch_pending_jobs(cluster="mpi")

        args = self.mock_run.call_args[0][0]
        self.assertIn("--clusters=mpi", args)

    def test_cluster_flag_omitted_by_default(self) -> None:
        """Verify no `--clusters` flag is passed when no cluster is given."""

        self.mock_run.return_value = _make_result("")
        fetch_pending_jobs()

        args = self.mock_run.call_args[0][0]
        self.assertFalse(
            any(arg.startswith("--clusters") for arg in args),
            "Cluster scope should defer to the local node configuration",
        )

    def test_single_partition_included_in_flag(self) -> None:
        """Verify a single partition name is passed as the `--partition` value."""

        self.mock_run.return_value = _make_result("")
        fetch_pending_jobs(partitions=["smp"])

        args = self.mock_run.call_args[0][0]
        self.assertIn("--partition=smp", args)

    def test_multiple_partitions_joined_with_commas(self) -> None:
        """Verify multiple partition names are joined into a single comma delimited value."""

        self.mock_run.return_value = _make_result("")
        fetch_pending_jobs(partitions=["smp", "gpu", "opa"])

        args = self.mock_run.call_args[0][0]
        self.assertIn("--partition=smp,gpu,opa", args)

    def test_partition_flag_omitted_by_default(self) -> None:
        """Verify no `--partition` flag is passed when no partitions are given."""

        self.mock_run.return_value = _make_result("")
        fetch_pending_jobs()

        args = self.mock_run.call_args[0][0]
        self.assertFalse(
            any(arg.startswith("--partition") for arg in args),
            "Partition scope should defer to the local node configuration",
        )

    def test_empty_partition_list_omits_flag(self) -> None:
        """Verify no `--partition` flag is passed when the partition list is empty."""

        self.mock_run.return_value = _make_result("")
        fetch_pending_jobs(partitions=[])

        args = self.mock_run.call_args[0][0]
        self.assertFalse(any(arg.startswith("--partition") for arg in args))

    def test_raises_on_subprocess_error(self) -> None:
        """Verify a `CalledProcessError` from squeue propagates to the caller."""

        self.mock_run.side_effect = subprocess.CalledProcessError(1, "squeue", stderr="error")

        with self.assertRaises(subprocess.CalledProcessError):
            fetch_pending_jobs()

    def test_returns_list_of_job_records(self) -> None:
        """Verify a valid squeue line is parsed into a `JobRecord`."""

        self.mock_run.return_value = _make_result(PENDING_LINE)

        jobs = fetch_pending_jobs()
        self.assertEqual(1, len(jobs))
        self.assertIsInstance(jobs[0], JobRecord)

    def test_parses_job_fields_correctly(self) -> None:
        """Verify all fields of a parsed `JobRecord` match the squeue output."""

        self.mock_run.return_value = _make_result(PENDING_LINE)

        job = fetch_pending_jobs()[0]
        self.assertEqual("12345", job.job_id)
        self.assertEqual("testuser", job.username)
        self.assertEqual(datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc), job.submit_time)
        self.assertEqual("my_job", job.job_name)
        self.assertEqual("gpu", job.partition)
        self.assertEqual("PENDING", job.state)

    def test_parses_multiple_jobs(self) -> None:
        """Verify multiple output lines are each parsed into a `JobRecord`."""

        self.mock_run.return_value = _make_result(
            "12345|testuser|2024-01-01T12:00:00|my_job|gpu|PENDING\n"
            "67890|otheruser|2024-02-01T08:00:00|other_job|cpu|PENDING\n"
        )

        self.assertEqual(2, len(fetch_pending_jobs()))

    def test_returns_empty_list_when_no_output(self) -> None:
        """Verify an empty squeue output returns an empty list."""

        self.mock_run.return_value = _make_result("")
        self.assertEqual([], fetch_pending_jobs())

    def test_skips_blank_lines(self) -> None:
        """Verify blank lines in squeue output are ignored."""

        self.mock_run.return_value = _make_result(
            f"\n{PENDING_LINE}\n"
        )

        self.assertEqual(1, len(fetch_pending_jobs()))

    def test_skips_cluster_banner(self) -> None:
        """Verify the cluster banner emitted by `--clusters` scoped queries is ignored."""

        self.mock_run.return_value = _make_result(f"{CLUSTER_BANNER}{PENDING_LINE}")

        jobs = fetch_pending_jobs(cluster="htc")
        self.assertEqual(1, len(jobs), "Banner line should not be parsed as a job record")

    def test_skips_malformed_lines(self) -> None:
        """Verify lines with the wrong number of fields are skipped."""

        self.mock_run.return_value = _make_result(
            "12345|testuser|2024-01-01T12:00:00\n"
        )

        self.assertEqual([], fetch_pending_jobs())

    def test_skips_lines_with_unparseable_submit_time(self) -> None:
        """Verify lines with an invalid submit time are skipped."""

        self.mock_run.return_value = _make_result(
            "12345|testuser|not-a-date|my_job|gpu|PENDING\n"
        )

        self.assertEqual([], fetch_pending_jobs())

    def test_strips_whitespace_from_fields(self) -> None:
        """Verify leading and trailing whitespace is stripped from each field."""

        self.mock_run.return_value = _make_result(
            " 12345 | testuser | 2024-01-01T12:00:00 | my_job | gpu | PENDING \n"
        )

        job = fetch_pending_jobs()[0]
        self.assertEqual("12345", job.job_id)
        self.assertEqual("testuser", job.username)
        self.assertEqual("gpu", job.partition)
        self.assertEqual("PENDING", job.state)


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
            state="PENDING",
        )

        self.subprocess_patch = patch("crc_prune_stale.slurm.run_subprocess")
        self.mock_run = self.subprocess_patch.start()
        self.mock_run.return_value = _make_result()

    def tearDown(self) -> None:
        """Close any open server connections."""

        self.subprocess_patch.stop()

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

    def test_throttled_array_job_returns_true(self) -> None:
        """Verify a throttled array job is reported as cancelled."""

        self.assertTrue(cancel_job(replace(self.job, job_id=THROTTLED_ARRAY_ID)))

    def test_job_record_id_is_not_modified(self) -> None:
        """Verify normalizing the ID for `scancel` leaves the job record untouched."""

        job = replace(self.job, job_id=THROTTLED_ARRAY_ID)
        cancel_job(job)

        self.assertEqual(THROTTLED_ARRAY_ID, job.job_id, "Notifications should report the ID squeue reported")

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

    def test_returns_true_on_success(self) -> None:
        """Verify `True` is returned when scancel exits without error."""

        self.assertTrue(cancel_job(self.job))

    def test_returns_false_on_error_in_stderr(self) -> None:
        """Verify `False` is returned when scancel logs an error but exits successfully."""

        self.mock_run.return_value = _make_result(stderr=SCANCEL_DENIED_STDERR)
        self.assertFalse(cancel_job(self.job, cluster="mpi"))

    def test_returns_false_on_fatal_in_stderr(self) -> None:
        """Verify `False` is returned when scancel logs a fatal error but exits successfully."""

        self.mock_run.return_value = _make_result(stderr=SCANCEL_FATAL_STDERR)
        self.assertFalse(cancel_job(self.job, cluster="mpi"))

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

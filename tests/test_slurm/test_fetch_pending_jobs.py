"""Unit tests for the `fetch_pending_jobs` function."""

import os
import subprocess
import time
from datetime import datetime, timezone

from crc_prune_stale.slurm import fetch_pending_jobs, JobRecord, SLURM_TIME_FORMAT, SQUEUE_FORMAT

from .common import _make_result, CLUSTER_BANNER, NODE_TIMEZONE, PENDING_LINE, SubprocessTestCase


class PendingJobsTestCase(SubprocessTestCase):
    """Base class pinning the local timezone used to interpret Slurm timestamps."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.original_tz = os.environ.get("TZ")
        self._apply_timezone(NODE_TIMEZONE)
        super().setUp()

    def tearDown(self) -> None:
        """Close any open server connections."""

        super().tearDown()
        self._apply_timezone(self.original_tz)

    @staticmethod
    def _apply_timezone(name: str | None) -> None:
        """Set the local timezone of the running process.

        Args:
            name: The timezone name to apply, or `None` to restore the system default.
        """

        if name is None:
            os.environ.pop("TZ", None)

        else:
            os.environ["TZ"] = name

        time.tzset()

    def _fetch_submit_time(self, submit_time_str: str) -> datetime:
        """Return the parsed submit time of a single mock squeue record.

        Args:
            submit_time_str: The submit time as rendered by `squeue`.

        Returns:
            submit_time: The submit time parsed from the mock output.
        """

        self.mock_run.return_value = _make_result(
            f"12345|testuser|{submit_time_str}|my_job|gpu|PENDING|Resources\n"
        )

        return fetch_pending_jobs()[0].submit_time


class SqueueArguments(PendingJobsTestCase):
    """Verify the arguments used to invoke `squeue`."""

    def test_squeue_called_with_correct_arguments(self) -> None:
        """Verify `squeue` is invoked with the expected command-line flags."""

        self.mock_run.return_value = _make_result("")
        fetch_pending_jobs()

        args = self.mock_run.call_args[0][0]
        self.assertEqual("squeue", args[0])
        self.assertIn("--state=PENDING", args)
        self.assertIn("--noheader", args)

    def test_pending_reason_is_requested(self) -> None:
        """Verify the pending reason is included in the requested output format."""

        self.mock_run.return_value = _make_result("")
        fetch_pending_jobs()

        args = self.mock_run.call_args[0][0]
        self.assertIn(f"--format={SQUEUE_FORMAT}", args)

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


class JobRecordParsing(PendingJobsTestCase):
    """Verify how squeue output lines are parsed into job records."""

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
        self.assertEqual(datetime(2024, 1, 1, 17, 0, 0, tzinfo=timezone.utc), job.submit_time)
        self.assertEqual("my_job", job.job_name)
        self.assertEqual("gpu", job.partition)
        self.assertEqual("PENDING", job.state)
        self.assertEqual("Resources", job.reason)

    def test_multi_word_pending_reason_is_parsed(self) -> None:
        """Verify a pending reason containing spaces is preserved in full."""

        self.mock_run.return_value = _make_result(
            "12345|testuser|2024-01-01T12:00:00|my_job|gpu|PENDING|QOSMaxJobsPerUserLimit\n"
        )

        self.assertEqual("QOSMaxJobsPerUserLimit", fetch_pending_jobs()[0].reason)

    def test_parses_multiple_jobs(self) -> None:
        """Verify multiple output lines are each parsed into a `JobRecord`."""

        self.mock_run.return_value = _make_result(
            "12345|testuser|2024-01-01T12:00:00|my_job|gpu|PENDING|Resources\n"
            "67890|otheruser|2024-02-01T08:00:00|other_job|cpu|PENDING|Priority\n"
        )

        self.assertEqual(2, len(fetch_pending_jobs()))

    def test_returns_empty_list_when_no_output(self) -> None:
        """Verify an empty squeue output returns an empty list."""

        self.mock_run.return_value = _make_result("")
        self.assertEqual([], fetch_pending_jobs())

    def test_strips_whitespace_from_fields(self) -> None:
        """Verify leading and trailing whitespace is stripped from each field."""

        self.mock_run.return_value = _make_result(
            " 12345 | testuser | 2024-01-01T12:00:00 | my_job | gpu | PENDING | Resources \n"
        )

        job = fetch_pending_jobs()[0]
        self.assertEqual("12345", job.job_id)
        self.assertEqual("testuser", job.username)
        self.assertEqual("gpu", job.partition)
        self.assertEqual("PENDING", job.state)


class MalformedOutput(PendingJobsTestCase):
    """Verify how unparseable squeue output lines are handled."""

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

    def test_skips_lines_missing_pending_reason(self) -> None:
        """Verify a line without a pending reason field is skipped as malformed."""

        self.mock_run.return_value = _make_result(
            "12345|testuser|2024-01-01T12:00:00|my_job|gpu|PENDING\n"
        )

        self.assertEqual([], fetch_pending_jobs())

    def test_skips_lines_with_unparseable_submit_time(self) -> None:
        """Verify lines with an invalid submit time are skipped."""

        self.mock_run.return_value = _make_result(
            "12345|testuser|not-a-date|my_job|gpu|PENDING|Resources\n"
        )

        self.assertEqual([], fetch_pending_jobs())


class SubmitTimeParsing(PendingJobsTestCase):
    """Verify submit times are interpreted in the local time of the node."""

    def test_standard_time_submit_time_is_converted(self) -> None:
        """Verify a submit time outside daylight saving time is offset by five hours."""

        self.assertEqual(
            datetime(2024, 1, 1, 17, 0, 0, tzinfo=timezone.utc),
            self._fetch_submit_time("2024-01-01T12:00:00"),
            "Submit times are reported in the local time of the node, not UTC",
        )

    def test_daylight_time_submit_time_is_converted(self) -> None:
        """Verify a submit time within daylight saving time is offset by four hours."""

        self.assertEqual(
            datetime(2024, 7, 1, 16, 0, 0, tzinfo=timezone.utc),
            self._fetch_submit_time("2024-07-01T12:00:00"),
            "The offset must follow daylight saving time rather than being fixed",
        )

    def test_submit_time_is_timezone_aware(self) -> None:
        """Verify the parsed submit time carries an explicit timezone."""

        self.assertIsNotNone(self._fetch_submit_time("2024-01-01T12:00:00").tzinfo)

    def test_recent_submit_time_is_not_aged(self) -> None:
        """Verify a job submitted moments ago is not aged by the local time offset."""

        submitted = datetime.now().replace(microsecond=0)
        age = datetime.now(tz=timezone.utc) - self._fetch_submit_time(
            submitted.strftime(SLURM_TIME_FORMAT)
        )

        self.assertLess(
            abs(age.total_seconds()), 60, "A job submitted moments ago should register a near zero age"
        )


class ErrorHandling(PendingJobsTestCase):
    """Verify behavior when the squeue invocation fails."""

    def test_raises_on_subprocess_error(self) -> None:
        """Verify a `CalledProcessError` from squeue propagates to the caller."""

        self.mock_run.side_effect = subprocess.CalledProcessError(1, "squeue", stderr="error")

        with self.assertRaises(subprocess.CalledProcessError):
            fetch_pending_jobs()

"""Unit tests for the `normalize_job_id` function."""

from unittest import TestCase

from crc_prune_stale.slurm import normalize_job_id

from .common import THROTTLED_ARRAY_ID, THROTTLED_ARRAY_ID_NORMALIZED, UNTHROTTLED_ARRAY_ID


class ThrottledArrayJobs(TestCase):
    """Verify the concurrency limit is stripped from throttled array job IDs."""

    def test_array_task_throttle_is_removed(self) -> None:
        """Verify the concurrency limit is stripped from a throttled array job ID."""

        self.assertEqual(THROTTLED_ARRAY_ID_NORMALIZED, normalize_job_id(THROTTLED_ARRAY_ID))

    def test_single_digit_throttle_is_removed(self) -> None:
        """Verify a single digit concurrency limit is stripped."""

        self.assertEqual("3237889_[0-15]", normalize_job_id("3237889_[0-15%1]"))

    def test_multi_range_throttle_is_removed(self) -> None:
        """Verify the concurrency limit is stripped from an array job with several task ranges."""

        self.assertEqual("3237889_[1-3,7,9-11]", normalize_job_id("3237889_[1-3,7,9-11%4]"))


class UnmodifiedJobIds(TestCase):
    """Verify job IDs without a concurrency limit are returned unchanged."""

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

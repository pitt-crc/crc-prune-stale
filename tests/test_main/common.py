"""Shared fixtures and mock data for the `__main__` module tests."""

from datetime import datetime, timedelta, timezone

from crc_prune_stale.__main__ import run
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
        reason="Resources",
    )


class RunTestCase:
    """Mixin providing a `run` invocation populated with default test arguments."""

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

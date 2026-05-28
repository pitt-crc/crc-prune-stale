"""Slurm job data types and subprocess wrappers for `squeue` and `scancel`."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .shell import run_subprocess

__all__ = ("JobRecord", "cancel_job", "fetch_pending_jobs")

SLURM_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

logger = logging.getLogger(__name__)


@dataclass
class JobRecord:
    """Metadata for a single Slurm job."""

    job_id: str
    username: str
    submit_time: datetime
    job_name: str
    partition: str


def fetch_pending_jobs() -> list[JobRecord]:
    """Query squeue and return all currently pending jobs.

    Returns:
        jobs: A list of JobRecord instances, one per pending job.
    """

    slurm_cmd = run_subprocess([
        "squeue",
        "--states=PENDING",
        "--noheader",
        "--Format=JobID,UserName,SubmitTime,Name,Partition",
        "--delimiter=|",
    ])

    jobs: list[JobRecord] = []
    for line in slurm_cmd.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("|")
        if len(parts) != 5:
            logger.warning("Skipping malformed squeue output line: %r", line)
            continue

        job_id, username, submit_time_str, job_name, partition = parts
        try:
            submit_time = datetime.strptime(
                submit_time_str.strip(), SLURM_TIME_FORMAT
            ).replace(tzinfo=timezone.utc)

        except ValueError:
            logger.warning(
                "Could not parse submit time %r for job %s; skipping.",
                submit_time_str,
                job_id,
            )
            continue

        jobs.append(JobRecord(
            job_id=job_id.strip(),
            username=username.strip(),
            submit_time=submit_time,
            job_name=job_name.strip(),
            partition=partition.strip(),
        ))

    logger.debug("Found %d pending job(s).", len(jobs))
    return jobs


def cancel_job(job: JobRecord, *, dry_run: bool = False) -> bool:
    """Cancel a single Slurm job by ID using scancel.

    Args:
        job: The JobRecord of the job to cancel.
        dry_run: If True, log the intended cancellation without calling scancel.

    Returns:
        success: True if scancel exited without error, or if dry_run is True.
    """

    if dry_run:
        logger.info(
            "Dry run — would cancel job %s submitted by %s on %s.",
            job.job_id,
            job.username,
            job.submit_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        return True

    # noinspection PyBroadException
    try:
        run_subprocess(["scancel", job.job_id])

    except:
        return False

    logger.info(
        "Cancelled job %s submitted by %s on %s (name=%r, partition=%r).",
        job.job_id,
        job.username,
        job.submit_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        job.job_name,
        job.partition,
    )

    return True

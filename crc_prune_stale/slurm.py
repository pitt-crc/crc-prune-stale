"""Slurm job data types and subprocess wrappers for `squeue` and `scancel`."""

import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

__all__ = [
    "JobRecord",
    "cancel_job",
    "fetch_pending_jobs",
]

SLURM_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"

logger = logging.getLogger(__name__)


@dataclass
class JobRecord:
    """A lightweight container for a single Slurm job's metadata."""

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

    command = [
        "squeue",
        "--states=PENDING",
        "--noheader",
        "--Format=JobID,UserName,SubmitTime,Name,Partition",
        "--delimiter=|",
    ]

    logger.debug("Running squeue command: %s", " ".join(command))

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )

    except subprocess.CalledProcessError as exc:
        logger.error(
            "squeue exited with return code %d. stderr: %s",
            exc.returncode,
            exc.stderr.strip(),
        )
        raise

    jobs: list[JobRecord] = []

    for line in result.stdout.splitlines():
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


def cancel_job(job: JobRecord) -> bool:
    """Cancel a single Slurm job by ID using scancel.

    Args:
        job: The JobRecord of the job to cancel.

    Returns:
        success: True if scancel exited without error, False otherwise.
    """

    command = ["scancel", job.job_id]
    logger.debug("Running scancel for job %s.", job.job_id)

    try:
        subprocess.run(command, capture_output=True, text=True, check=True)

    except subprocess.CalledProcessError as exc:
        logger.error(
            "scancel failed for job %s (user %s). Return code: %d. stderr: %s",
            job.job_id,
            job.username,
            exc.returncode,
            exc.stderr.strip(),
        )

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

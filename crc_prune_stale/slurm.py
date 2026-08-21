"""Slurm job data types and subprocess wrappers for `squeue` and `scancel`."""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .shell import run_subprocess

__all__ = ("JobRecord", "cancel_job", "fetch_cluster_name", "fetch_partition_names", "fetch_pending_jobs")

SLURM_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
CLUSTER_CONFIG_KEY = "ClusterName"
CLUSTER_BANNER_PREFIX = "CLUSTER:"

logger = logging.getLogger(__name__)


@dataclass
class JobRecord:
    """Metadata for a single Slurm job."""

    job_id: str
    username: str
    submit_time: datetime
    job_name: str
    partition: str
    state: str


def fetch_cluster_name() -> str:
    """Query `scontrol` and return the cluster name defined by the local node configuration.

    Returns:
        cluster: The name of the cluster the local node belongs to.

    Raises:
        RuntimeError: If the Slurm configuration does not define a cluster name.
    """

    slurm_cmd = run_subprocess(["scontrol", "show", "config"])

    for line in slurm_cmd.stdout.splitlines():
        key, _, value = line.partition("=")
        if key.strip() == CLUSTER_CONFIG_KEY and value.strip():
            return value.strip()

    raise RuntimeError("Could not determine the cluster name from the local Slurm configuration")


def fetch_pending_jobs(cluster: str | None = None, partitions: list[str] | None = None) -> list[JobRecord]:
    """Query `squeue` and return all currently pending jobs.

    Arguments left as `None` are omitted from the `squeue` call, deferring to the
    default Slurm configuration of the local node.

    Args:
        cluster: The name of the cluster to query.
        partitions: The names of the partitions to query.

    Returns:
        jobs: A list with one `JobRecord` instances per pending job.
    """

    squeue_args = [
        "squeue",
        "--state=PENDING",
        "--noheader",
        "--format=%i|%u|%V|%j|%P|%T",
    ]

    if cluster:
        squeue_args.append(f"--clusters={cluster}")

    if partitions:
        squeue_args.append(f"--partition={','.join(partitions)}")

    slurm_cmd = run_subprocess(squeue_args)

    jobs: list[JobRecord] = []
    for line in slurm_cmd.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith(CLUSTER_BANNER_PREFIX):
            continue

        parts = line.split("|")
        if len(parts) != 6:
            logger.warning("Skipping malformed squeue output line: %r", line)
            continue

        job_id, username, submit_time_str, job_name, partition, state = parts
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
            state=state.strip(),
        ))

    return jobs


def cancel_job(job: JobRecord, *, cluster: str | None = None, dry_run: bool = False) -> bool:
    """Cancel a single Slurm job by ID using scancel.

    Args:
        job: The JobRecord of the job to cancel.
        cluster: The name of the cluster the job was submitted to.
        dry_run: If `True`, log the intended cancellation without calling scancel.

    Returns:
        success: `True` if `scancel` exited without error, or if `dry_run` is `True`.
    """

    if dry_run:
        age = datetime.now(tz=timezone.utc) - job.submit_time
        logger.info(
            "Dry run — would cancel job %s submitted by %s on %s (age: %d days).",
            job.job_id,
            job.username,
            job.submit_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            age.days,
        )

        return True

    scancel_args = ["scancel", job.job_id]
    if cluster:
        scancel_args.append(f"--clusters={cluster}")

    # noinspection PyBroadException
    try:
        run_subprocess(scancel_args)

    except Exception:
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

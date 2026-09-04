"""Slurm job data types and subprocess wrappers for `squeue` and `scancel`."""

import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone

from .shell import run_subprocess

__all__ = (
    "JobRecord",
    "cancel_job",
    "fetch_cluster_name",
    "fetch_pending_jobs",
    "normalize_job_id",
)

SLURM_TIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
CLUSTER_CONFIG_KEY = "ClusterName"

# Fields requested from `squeue`, in the order they are parsed
SQUEUE_FORMAT = "%i|%u|%V|%j|%P|%T|%r"
SQUEUE_FIELD_COUNT = 7

# Label used in log records when a cancellation defers to the local node
LOCAL_CLUSTER_LABEL = "local"

# Slurm client commands log failures to stderr as `<command>: error: <message>`
SLURM_ERROR_PATTERN = re.compile(
    r"^\s*(?:\S+:\s*)?(?:error|fatal):\s*(?P<message>.+?)\s*$", re.MULTILINE
)

# `squeue` renders the concurrency limit of a throttled array job as
# `<id>_[<range>%<limit>]`, but the `%<limit>` suffix is rejected as
# invalid input by the Slurm client commands
ARRAY_THROTTLE_PATTERN = re.compile(r"%\d+(?=])")

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
    reason: str


def _describe_job(job: JobRecord, cluster: str | None) -> str:
    """Return a summary of the metadata identifying a job in log records.

    Args:
        job: The job to describe.
        cluster: The name of the cluster the job was targeted on.

    Returns:
        description: A summary of the job and the scope it was targeted in.
    """

    return (
        f"job {job.job_id} submitted by {job.username} "
        f"(cluster={cluster or LOCAL_CLUSTER_LABEL}, partition={job.partition}, "
        f"name={job.job_name!r}, reason={job.reason!r})"
    )


def normalize_job_id(job_id: str) -> str:
    """Rewrite a job ID into a format accepted by the Slurm client commands.

    Args:
        job_id: A job ID as reported by `squeue`.

    Returns:
        job_id: The job ID with any array task concurrency limit removed.
    """

    return ARRAY_THROTTLE_PATTERN.sub("", job_id)


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
        f"--format={SQUEUE_FORMAT}",
    ]

    if cluster:
        squeue_args.append(f"--clusters={cluster}")

    if partitions:
        squeue_args.append(f"--partition={','.join(partitions)}")

    slurm_cmd = run_subprocess(squeue_args)

    jobs: list[JobRecord] = []
    for line in slurm_cmd.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("|")
        if len(parts) != SQUEUE_FIELD_COUNT:
            logger.warning("Skipping malformed squeue output line: %r", line)
            continue

        job_id, username, submit_time_str, job_name, partition, state, reason = parts
        try:
            # Slurm renders submit times in the local time of the node, so the
            # parsed value is localized before being normalized to UTC
            submit_time = datetime.strptime(
                submit_time_str.strip(), SLURM_TIME_FORMAT
            ).astimezone(timezone.utc)

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
            reason=reason.strip(),
        ))

    return jobs


def cancel_job(job: JobRecord, *, cluster: str | None = None, dry_run: bool = False) -> bool:
    """Cancel a single Slurm job by ID using scancel.

    Args:
        job: The JobRecord of the job to cancel.
        cluster: The name of the cluster the job was submitted to.
        dry_run: If `True`, log the intended cancellation without calling scancel.

    Returns:
        success: `True` if the job was canceled, or if `dry_run` is `True`.
    """

    if dry_run:
        age = datetime.now(tz=timezone.utc) - job.submit_time
        logger.info(
            "Dry run — would cancel %s on %s (age: %d days).",
            _describe_job(job, cluster),
            job.submit_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            age.days,
        )

        return True

    scancel_args = ["scancel", normalize_job_id(job.job_id)]
    if cluster:
        scancel_args.append(f"--clusters={cluster}")

    try:
        slurm_cmd = run_subprocess(scancel_args)

    except (OSError, subprocess.CalledProcessError) as exc:
        logger.error("Could not cancel %s: %s", _describe_job(job, cluster), exc)
        return False

    # A zero exit status does not imply the job was canceled, so the stderr
    # stream is checked for the per-job errors returned by the controller
    error = SLURM_ERROR_PATTERN.search(slurm_cmd.stderr)
    if error:
        logger.error(
            "Could not cancel %s: %s",
            _describe_job(job, cluster),
            error.group("message"),
        )

        return False

    logger.info(
        "Cancelled %s on %s.",
        _describe_job(job, cluster),
        job.submit_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    return True

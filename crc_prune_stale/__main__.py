"""Primary entrypoint for parsing and executing CLI inputs.

This module wires together the CLI, logging, Slurm, and notification layers.
It contains no business logic of its own; every substantive operation is
delegated to a sibling module.
"""

import logging
from datetime import datetime, timedelta, timezone

from .cli import create_parser
from .log import configure_logging
from .notify import notify_users
from .slurm import cancel_job, fetch_cluster_name, fetch_pending_jobs

__all__ = ("main", "run")

logger = logging.getLogger(__name__)


def run(
    *,
    cluster: str,
    partitions: list[str] | None,
    dry_run: bool,
    threshold: int,
    smtp_host: str | None,
    smtp_port: int,
    email_from: str,
    email_domain: str,
) -> None:
    """Cancel all pending Slurm jobs exceeding the threshold and notify affected users.

    Fetches all pending jobs from Slurm older than the given threshold, cancels
    them, and notifies affected users by email. Notifications are skipped when
    `smtp_host=None` or `dry-run=True`.

    Args:
        cluster: Name of the cluster to query.
        partitions: Names of the partitions to query, or `None` for all partitions.
        dry_run: If True, log intended cancellations without calling scancel.
        threshold: Number of days a job must have been pending before cancellation.
        smtp_host: Hostname of the SMTP server, or `None` to disable notifications.
        smtp_port: Port of the SMTP server.
        email_from: Sender address for notification emails.
        email_domain: Domain appended to usernames when constructing recipient addresses.
    """

    logger.info(
        "Targeting cluster %s, partition(s) %s.",
        cluster,
        ", ".join(partitions) if partitions else "all",
    )

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=threshold)
    logger.info(
        "Cancelling jobs pending since before %s (dry_run=%s).",
        cutoff.strftime("%Y-%m-%d %H:%M:%S UTC"),
        dry_run,
    )

    all_pending = fetch_pending_jobs(cluster=cluster, partitions=partitions)
    logger.info("Found %d pending jobs.", len(all_pending))

    stale_jobs = [job for job in all_pending if job.submit_time < cutoff]
    logger.info("Found %d stale jobs older than cutoff.", len(stale_jobs))

    cancelled_jobs = [job for job in stale_jobs if cancel_job(job, cluster=cluster, dry_run=dry_run)]
    logger.info("Marked %d jobs for cancellation without errors.", len(cancelled_jobs))

    if smtp_host and not dry_run:
        notify_users(
            jobs=cancelled_jobs,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            email_from=email_from,
            email_domain=email_domain,
            threshold=threshold,
        )

    if dry_run:
        logger.info(
            "Dry run complete. Would have cancelled: %d  Errors: %d  Skipped (not stale): %d",
            len(cancelled_jobs),
            len(stale_jobs) - len(cancelled_jobs),
            len(all_pending) - len(stale_jobs),
        )

    else:
        logger.info(
            "Run complete. Cancelled: %d  Errors: %d  Skipped (not stale): %d",
            len(cancelled_jobs),
            len(stale_jobs) - len(cancelled_jobs),
            len(all_pending) - len(stale_jobs),
        )


def main() -> None:
    """Invoke the cancellation pipeline and handle top-level exceptions.

    The primary application entry point. Initializes application logging, parses
    commandline arguments, and executes the `run` command with appropriate arguments.
    """

    configure_logging()

    try:
        default_cluster = fetch_cluster_name()
        parser = create_parser(default_cluster)

        args = parser.parse_args()
        run(
            cluster=args.cluster,
            partitions=args.partitions,
            dry_run=args.dry_run,
            threshold=args.threshold,
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            email_from=args.email_from,
            email_domain=args.email_dmn,
        )

    except KeyboardInterrupt:
        pass

    except Exception as exc:
        logger.critical(exc)

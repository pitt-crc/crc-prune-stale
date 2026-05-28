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
from .slurm import cancel_jobs, fetch_pending_jobs, filter_stale_jobs

__all__ = ("main", "run")

logger = logging.getLogger(__name__)


def run(
    *,
    dry_run: bool,
    threshold: int,
    smtp_host: str | None,
    smtp_port: int,
    email_from: str,
    email_domain: str,
) -> None:
    """Cancel all pending Slurm jobs exceeding the staleness threshold and notify affected users.

    Fetches all pending jobs from Slurm older than the given threshold, cancels
    them, and notifies affected users by email. Notifications are skipped when
    `smtp_host=None` or `dry-run=True`.

    Args:
        dry_run: If True, log intended cancellations without calling scancel.
        threshold: Number of days a job must have been pending before cancellation.
        smtp_host: Hostname of the SMTP server, or `None` to disable notifications.
        smtp_port: Port of the SMTP server.
        email_from: Sender address for notification emails.
        email_domain: Domain appended to usernames when constructing recipient addresses.
    """

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=threshold)
    logger.info(
        "Terminating pending jobs submitted before %s (dry_run=%s).",
        cutoff.strftime("%Y-%m-%d %H:%M:%S UTC"),
        dry_run,
    )

    all_pending = fetch_pending_jobs()
    stale_jobs = filter_stale_jobs(all_pending, cutoff)
    cancelled_jobs = cancel_jobs(stale_jobs, dry_run=dry_run)

    if smtp_host and not dry_run:
        notify_users(
            cancelled_jobs,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            email_from=email_from,
            email_domain=email_domain,
            threshold=threshold,
        )

    logger.info(
        "Run complete. Cancelled: %d  Errors: %d  Skipped (not stale): %d",
        len(cancelled_jobs),
        len(stale_jobs) - len(cancelled_jobs),
        len(all_pending) - len(stale_jobs),
    )


def main() -> None:
    """Invoke the cancellation pipeline and handle top-level exceptions.

    The primary application entry point used to wrap the `run` method with
    user-friendly log handling.
    """

    configure_logging()
    args = create_parser().parse_args()

    try:
        run(
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
        logger.critical(exc, exc_info=True)

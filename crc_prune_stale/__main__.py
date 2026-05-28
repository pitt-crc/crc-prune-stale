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

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the stale pending job cancellation workflow."""

    configure_logging()
    args = create_parser().parse_args()
    threshold = datetime.now(tz=timezone.utc) - timedelta(days=args.threshold)

    logger.info(
        "Starting stale-job cancellation run (dry_run=%s). Threshold: jobs pending before %s.",
        args.dry_run,
        threshold.strftime("%Y-%m-%d %H:%M:%S UTC"),
    )

    all_pending = fetch_pending_jobs()
    stale_jobs = filter_stale_jobs(all_pending, threshold)
    cancelled_jobs = cancel_jobs(stale_jobs, dry_run=args.dry_run)
    if not args.dry_run:
        notify_users(
            cancelled_jobs,
            smtp_host=args.smtp_host,
            smtp_port=args.smtp_port,
            email_from=args.email_from,
            email_domain=args.email_dmn,
            threshold=args.threshold,
        )

    logger.info(
        "Run complete. Cancelled: %d  Errors: %d  Skipped (not stale): %d",
        len(cancelled_jobs),
        len(stale_jobs) - len(cancelled_jobs),
        len(all_pending) - len(stale_jobs),
    )


if __name__ == "__main__":
    main()

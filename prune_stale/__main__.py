"""Primary entrypoint for parsing and executing CLI inputs.

This module wires together the CLI, logging, Slurm, and notification layers.
It contains no business logic of its own; every substantive operation is
delegated to a sibling module.
"""

import logging
import subprocess
from datetime import datetime, timedelta

from .cli import create_parser
from .log import configure_logging as configure_logging
from .notify import notify_user
from .slurm import cancel_job, fetch_pending_jobs

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the stale pending job cancellation workflow."""

    configure_logging()
    args = create_parser().parse_args()

    threshold = datetime.now() - timedelta(days=args.threshold_days)
    logger.info(
        'Starting stale-job cancellation run (dry_run=%s). '
        'Threshold: jobs pending before %s.',
        args.dry_run,
        threshold.strftime('%Y-%m-%d %H:%M:%S UTC'),
    )

    try:
        all_pending = fetch_pending_jobs()

    except subprocess.CalledProcessError:
        logger.critical('Could not retrieve pending jobs from squeue. Aborting.')
        return

    stale_jobs = [job for job in all_pending if job.submit_time < threshold]
    logger.info('Found %d pending job(s) older than %d days.', len(stale_jobs), args.threshold_days)

    cancelled_count = 0
    failed_count = 0
    for job in stale_jobs:
        if args.dry_run:
            logger.info(
                'Dry run — would cancel job %s submitted by %s on %s.',
                job.job_id,
                job.username,
                job.submit_time.strftime('%Y-%m-%d %H:%M:%S UTC'),
            )
            continue

        success = cancel_job(job)
        if success:
            cancelled_count += 1
            notify_user(
                job,
                smtp_host=args.smtp_host,
                smtp_port=args.smtp_port,
                email_from=args.email_from,
                email_domain=args.email_dmn,
                threshold_days=args.threshold_days,
            )

        else:
            failed_count += 1

    logger.info(
        'Run complete. Cancelled: %d  Errors: %d  Skipped (not stale): %d',
        cancelled_count,
        failed_count,
        len(all_pending) - len(stale_jobs),
    )


if __name__ == '__main__':
    main()

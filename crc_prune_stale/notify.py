"""Email and SMTP logic for notifying users."""

import logging
import smtplib
from collections import defaultdict
from email.message import EmailMessage

from .slurm import JobRecord

__all__ = ("notify_users",)

logger = logging.getLogger(__name__)


def _build_email_body(
    username: str,
    jobs: list[JobRecord],
    threshold: int,
) -> str:
    """Render the full plain-text email body including a fixed-width job table.

    The table uses column widths derived from the widest value in each column
    so all rows align regardless of job name or partition length.

    Args:
        username: The Slurm username of the recipient.
        jobs: All canceled jobs belonging to this user.
        threshold: Number of pending days stated in the notification body.

    Returns:
        body: A complete plain-text string suitable for use as a MIME fallback.
    """

    table_columns = ("Job ID", "Job Name", "Partition", "Submitted (UTC)")
    rows = [
        (
            job.job_id,
            job.job_name,
            job.partition,
            job.submit_time.strftime("%Y-%m-%d %H:%M:%S")
        ) for job in jobs
    ]

    col_widths = [
        max(len(header), max(len(row[i]) for row in rows))
        for i, header in enumerate(table_columns)
    ]

    format_row = lambda cells: "  ".join(cell.ljust(width) for cell, width in zip(cells, col_widths))
    separator = "  ".join("-" * width for width in col_widths)
    table = f"{format_row(table_columns)}\n{separator}\n" + "\n".join(format_row(row) for row in rows)

    return (
        f"Dear {username},\n"
        f"\n"
        f"This is an automated notice that one or more of your CRCD Slurm jobs have been\n"
        f"cancelled after remaining in a PENDING state for more than {threshold} days\n"
        f"without being scheduled to run.\n"
        f"\n"
        f"Jobs that remain pending for an extended period are typically stalled due to\n"
        f"a resource request that cannot be satisfied. This commonly includes requesting\n"
        f"more nodes than are available on the partition, or specifying constraints that\n"
        "no current node can meet. Cancelling these jobs helps keep the scheduler queue\n"
        "healthy and ensures other users' work can be scheduled efficiently.\n"
        f"\n"
        f"If you believe your job was cancelled in error, or if you would like help\n"
        f"reviewing your submission and resubmitting it, please open a support ticket\n"
        f"with the CRCD team.\n"
        f"\n"
        f"A summary of cancelled jobs is provided below:\n"
        f"\n"
        f"{table}\n"
        f"\n"
        f"Best regards,\n"
        f"Pitt CRCD\n"
    )


def _notify_user(
    username: str,
    jobs: list[JobRecord],
    smtp_host: str,
    smtp_port: int,
    email_from: str,
    email_domain: str,
    threshold: int,
) -> None:
    """Send a single notification email listing all canceled jobs for one user.

    The message is sent as a multipart/alternative with a plain-text fallback
    and an HTML primary part so clients that do not render HTML still receive
    readable content.

    Args:
        username: The Slurm username of the recipient.
        jobs: All canceled jobs belonging to this user.
        smtp_host: Hostname of the SMTP server.
        smtp_port: Port of the SMTP server.
        email_from: Sender address for the notification.
        email_domain: Domain appended to the username to form the recipient address.
        threshold: Number of pending days stated in the notification body.
    """

    job_count = len(jobs)

    recipient = f"{username}@{email_domain}"
    subject = "Your pending Slurm job(s) have been cancelled"
    plain_body = _build_email_body(username, jobs, threshold)

    message = EmailMessage()
    message["From"] = email_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(plain_body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.send_message(message)

    except smtplib.SMTPException as exc:
        logger.error(
            "Failed to send notification to %s (%d job(s)): %s",
            recipient,
            job_count,
            exc,
        )

    else:
        logger.info(
            "Notification sent to %s for %d cancelled job(s).",
            recipient,
            job_count,
        )


def notify_users(
    jobs: list[JobRecord],
    smtp_host: str,
    smtp_port: int,
    email_from: str,
    email_domain: str,
    threshold: int,
) -> None:
    """Send one notification email per affected user summarizing their canceled jobs.

    Users who had multiple stale jobs canceled receive a single email
    detailing all terminated jobs.

    Args:
        jobs: The full list of successfully canceled jobs.
        smtp_host: Hostname of the SMTP server.
        smtp_port: Port of the SMTP server.
        email_from: Sender address for the notification.
        email_domain: Domain appended to the username to form the recipient address.
        threshold: Number of pending days stated in the notification body.
    """

    jobs_by_user: dict[str, list[JobRecord]] = defaultdict(list)
    for job in jobs:
        jobs_by_user[job.username].append(job)

    for username, user_jobs in jobs_by_user.items():
        _notify_user(
            username=username,
            jobs=user_jobs,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            email_from=email_from,
            email_domain=email_domain,
            threshold=threshold,
        )

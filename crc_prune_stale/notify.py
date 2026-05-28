"""Email and SMTP logic for notifying users."""

import logging
import smtplib
from collections import defaultdict
from email.message import EmailMessage

from .slurm import JobRecord

__all__ = ("notify_users",)

logger = logging.getLogger(__name__)


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
        jobs: The full list of successfully cancelled jobs.
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

    Args:
        username: The Slurm username of the recipient.
        jobs: All canceled jobs belonging to this user.
        smtp_host: Hostname of the SMTP server.
        smtp_port: Port of the SMTP server.
        email_from: Sender address for the notification.
        email_domain: Domain appended to the username to form the recipient address.
        threshold: Number of pending days stated in the notification body.
    """

    recipient = f"{username}@{email_domain}"
    job_count = len(jobs)
    subject = (
        f"Pending Slurm jobs cancelled"
    )

    job_lines = "\n".join(
        f"  Job ID   : {job.job_id}\n"
        f"  Job name : {job.job_name}\n"
        f"  Partition: {job.partition}\n"
        f"  Submitted: {job.submit_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        for job in jobs
    )

    body = (
        f"Dear {username},\n\n"
        f"The following Slurm job(s) have been automatically cancelled because they\n"
        f"remained in the PENDING state for more than {threshold} days without starting.\n\n"
        f"{job_lines}\n"
        f"If you believe any of these cancellations were in error, or if you require\n"
        f"assistance re-submitting your jobs, please submit a CRCD support ticket.\n\n"
        f"Yours,\n"
        f"Pitt CRCD\n"
    )

    message = EmailMessage()
    message["From"] = email_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

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

"""Email and SMTP logic for notifying users."""

import logging
import smtplib
from email.message import EmailMessage

from .slurm import JobRecord

__all__ = ["notify_user"]

logger = logging.getLogger(__name__)


def notify_user(
    job: JobRecord,
    smtp_host: str,
    smtp_port: int,
    email_from: str,
    email_domain: str,
    threshold: int,
) -> None:
    """Send an email notification to the job owner.

    Args:
        job: The JobRecord of the canceled job.
        smtp_host: Hostname of the SMTP server.
        smtp_port: Port of the SMTP server.
        email_from: Sender address for the notification.
        email_domain: Domain appended to the username to form the recipient address.
        threshold: Number of pending days stated in the notification body.
    """

    recipient = f"{job.username}@{email_domain}"
    subject = f"[Slurm] Pending job {job.job_id} cancelled after {threshold} days"

    body = (
        f"Dear {job.username},\n\n"
        f"Your Slurm job has been automatically cancelled because it remained in the\n"
        f"PENDING state for more than {threshold} days without starting.\n\n"
        f"  Job ID   : {job.job_id}\n"
        f"  Job name : {job.job_name}\n"
        f"  Partition: {job.partition}\n"
        f"  Submitted: {job.submit_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        f"If you believe this cancellation was in error, or if you require assistance\n"
        f"re-submitting your job, please submit a CRCD support ticket.\n\n"
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
        logger.error("Failed to send notification to %s for job %s: %s", recipient, job.job_id, exc)

    else:
        logger.info("Notification sent to %s for job %s.", recipient, job.job_id)

"""Email and SMTP logic for notifying users."""

import html
import logging
import smtplib
from collections import defaultdict
from email.message import EmailMessage

import html2text

from .slurm import JobRecord

__all__ = ("notify_users",)

_TABLE_COLUMNS = ("Job ID", "Job Name", "Partition", "Pending Reason", "Submitted (UTC)")

logger = logging.getLogger(__name__)


def _html_to_plain(html: str) -> str:
    """Convert an HTML email body to plain text.

    Args:
        html: A complete HTML document string.

    Returns:
        plain: A plain-text representation of the HTML content.
    """

    converter = html2text.HTML2Text()
    converter.ignore_links = True
    converter.body_width = 0
    return converter.handle(html)


def _build_email_body(username: str, jobs: list[JobRecord], threshold: int) -> str:
    """Render the full HTML email body.

    All styles are inlined so the email renders correctly in clients that strip
    <style> blocks.

    Args:
        username: The Slurm username of the recipient.
        jobs: All canceled jobs belonging to this user.
        threshold: Number of pending days stated in the notification body.

    Returns:
        The HTML email content.
    """

    job_count = len(jobs)
    job_noun = "job" if job_count == 1 else "jobs"
    job_verb = "was" if job_count == 1 else "were"

    header_cells = "".join(
        f'<th style="background:#2c3e50;color:#fff;padding:8px 12px;'
        f'text-align:left;white-space:nowrap;">{col}</th>'
        for col in _TABLE_COLUMNS
    )

    data_rows = ""
    for i, job in enumerate(jobs):
        row_bg = "#f9f9f9" if i % 2 == 0 else "#ffffff"

        # Job names, partitions, and pending reasons are user influenced and
        # must not be interpolated into the message body as markup
        cells = (
            html.escape(job.job_id),
            html.escape(job.job_name),
            html.escape(job.partition),
            html.escape(job.reason),
            job.submit_time.strftime("%Y-%m-%d %H:%M:%S"),
        )

        data_cells = "".join(
            f'<td style="padding:7px 12px;border-bottom:1px solid #e0e0e0;'
            f'white-space:nowrap;font-family:monospace;">{cell}</td>'
            for cell in cells
        )

        data_rows += f'<tr style="background:{row_bg};">{data_cells}</tr>\n'

    return (
        f"<!DOCTYPE html>\n"
        f"<html lang=\"en\">\n"
        f"<head><meta charset=\"UTF-8\"></head>\n"
        f"<body style=\"font-family:Arial,sans-serif;font-size:14px;color:#333;\n"
        f"             max-width:760px;margin:0 auto;padding:24px;\">\n"
        f"\n"
        f"  <p>Dear {html.escape(username)},</p>\n"
        f"\n"
        f"  <p>\n"
        f"    This is an automated notice that one or more of your CRCD Slurm jobs have been\n"
        f"    cancelled after remaining in a <strong>PENDING</strong> state for more than\n"
        f"    {threshold} days without being scheduled to run.\n"
        f"  </p>\n"
        f"\n"
        f"  <p>\n"
        f"    Jobs that remain pending for an extended period are typically stalled due to\n"
        f"    a resource request that cannot be satisfied. This commonly includes requesting\n"
        f"    more nodes than are available on the partition, or specifying constraints that\n"
        f"    no current node can meet. Cancelling these jobs helps keep the scheduler queue\n"
        f"    healthy and ensures other users' work can be scheduled efficiently.\n"
        f"  </p>\n"
        f"\n"
        f"  <p>\n"
        f"    If you believe your {job_noun} {job_verb} cancelled in error, or if you would\n"
        f"    like help reviewing your submission and resubmitting it, please open a support\n"
        f"    ticket with the CRCD team.\n"
        f"  </p>\n"
        f"\n"
        f"  <p style=\"margin-bottom:6px;\"><strong>Cancelled jobs ({job_count}):</strong></p>\n"
        f"\n"
        f"  <table style=\"border-collapse:collapse;width:100%;font-size:13px;\">\n"
        f"    <thead>\n"
        f"      <tr>{header_cells}</tr>\n"
        f"    </thead>\n"
        f"    <tbody>\n"
        f"      {data_rows}\n"
        f"    </tbody>\n"
        f"  </table>\n"
        f"\n"
        f"  <p style=\"margin-top:24px;\">\n"
        f"    Best regards,<br>\n"
        f"    Pitt CRCD\n"
        f"  </p>\n"
        f"\n"
        f"</body>\n"
        f"</html>"
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

    The message is sent as a multipart HTML message with a plain-text fallback
    so clients that do not render HTML still receive readable content.

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
    html_body = _build_email_body(username, jobs, threshold)
    plain_body = _html_to_plain(html_body)

    message = EmailMessage()
    message["From"] = email_from
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")

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

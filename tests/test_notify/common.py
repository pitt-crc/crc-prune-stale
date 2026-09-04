"""Shared fixtures and mock data for the `notify` module tests."""

from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale.notify import notify_users
from crc_prune_stale.slurm import JobRecord

# A job name containing markup, used to verify user controlled values are escaped
MARKUP_JOB_NAME = "<script>alert(1)</script>"


def _make_job(
    job_id: str = "12345",
    username: str = "testuser",
    job_name: str = "my_job",
    partition: str = "gpu",
    state: str = "PENDING",
    reason: str = "Resources",
) -> JobRecord:
    """Return a `JobRecord` populated with mock data."""

    return JobRecord(
        job_id=job_id,
        username=username,
        submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        job_name=job_name,
        partition=partition,
        state=state,
        reason=reason,
    )


def _get_plain_body(message: EmailMessage) -> str:
    """Return the plain-text body from a multipart email message."""

    for part in message.walk():
        if part.get_content_type() == "text/plain":
            return part.get_content()

    return ""


def _get_html_body(message: EmailMessage) -> str:
    """Return the HTML body from a multipart email message."""

    for part in message.walk():
        if part.get_content_type() == "text/html":
            return part.get_content()

    return ""


class NotifyUsersTestCase(TestCase):
    """Base class providing a mock SMTP server and a default notification call."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.job = _make_job()

        self.smtp_patch = patch("smtplib.SMTP")
        self.mock_smtp = self.smtp_patch.start()
        self.mock_smtp_instance = MagicMock()
        self.mock_smtp.return_value.__enter__.return_value = self.mock_smtp_instance

    def tearDown(self) -> None:
        """Close any open server connections."""

        self.smtp_patch.stop()

    def _call(self, **kwargs) -> None:
        """Call `notify_users` with default test arguments, allowing overrides."""

        defaults = dict(
            jobs=[self.job],
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
            threshold=10,
        )

        notify_users(**{**defaults, **kwargs})

    def _sent_messages(self) -> list:
        """Return all `EmailMessage` objects passed to `send_message`."""

        return [call.args[0] for call in self.mock_smtp_instance.send_message.call_args_list]

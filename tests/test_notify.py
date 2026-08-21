"""Unit tests for the `notify` module."""

import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale.notify import notify_users
from crc_prune_stale.slurm import JobRecord


def _make_job(
    job_id: str = "12345",
    username: str = "testuser",
    job_name: str = "my_job",
    partition: str = "gpu",
    state: str = "PENDING",
) -> JobRecord:
    """Return a `JobRecord` populated with mock data."""

    return JobRecord(
        job_id=job_id,
        username=username,
        submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        job_name=job_name,
        partition=partition,
        state=state,
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


class NotifyUsers(TestCase):
    """Verify the email construction and SMTP behaviour of `notify_users`."""

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

    def test_recipient_address_combines_username_and_domain(self) -> None:
        """Verify the `To` field is constructed from the username and domain."""

        self._call()
        message = self._sent_messages()[0]
        self.assertEqual("testuser@example.com", message["To"])

    def test_sender_address_matches_email_from_argument(self) -> None:
        """Verify the `From` field matches the `email_from` argument."""

        self._call()
        message = self._sent_messages()[0]
        self.assertEqual("noreply@example.com", message["From"])

    def test_subject_matches_expected_format(self) -> None:
        """Verify the `Subject` field matches the expected format exactly."""

        self._call()
        message = self._sent_messages()[0]
        self.assertEqual("Your pending Slurm job(s) have been cancelled", message["Subject"])

    def test_message_is_multipart_alternative(self) -> None:
        """Verify the sent message uses multipart/alternative encoding."""

        self._call()
        message = self._sent_messages()[0]
        self.assertEqual("multipart/alternative", message.get_content_type())

    def test_plain_body_contains_job_metadata(self) -> None:
        """Verify the plain-text part contains the job ID, name, partition, and submit time."""

        self._call()
        body = _get_plain_body(self._sent_messages()[0])
        self.assertIn("12345", body)
        self.assertIn("my_job", body)
        self.assertIn("gpu", body)
        self.assertIn("2024-01-01 12:00:00", body)

    def test_html_body_contains_job_metadata(self) -> None:
        """Verify the HTML part contains the job ID, name, partition, and submit time."""

        self._call()
        body = _get_html_body(self._sent_messages()[0])
        self.assertIn("12345", body)
        self.assertIn("my_job", body)
        self.assertIn("gpu", body)
        self.assertIn("2024-01-01 12:00:00", body)

    def test_plain_body_contains_threshold(self) -> None:
        """Verify the plain-text part references the configured threshold."""

        self._call(threshold=14)
        body = _get_plain_body(self._sent_messages()[0])
        self.assertIn("14 days", body)

    def test_html_body_contains_threshold(self) -> None:
        """Verify the HTML part references the configured threshold."""

        self._call(threshold=14)
        body = _get_html_body(self._sent_messages()[0])
        self.assertIn("14 days", body)

    def test_smtp_connected_with_host_and_port(self) -> None:
        """Verify the SMTP client is opened with the provided host and port."""

        self._call(smtp_host="mail.pitt.edu", smtp_port=587)
        self.mock_smtp.assert_called_with("mail.pitt.edu", 587)

    def test_single_user_receives_one_message(self) -> None:
        """Verify one email is sent per call when only one user is affected."""

        self._call()
        self.mock_smtp_instance.send_message.assert_called_once()

    def test_smtp_exception_does_not_propagate(self) -> None:
        """Verify an `SMTPException` is caught and does not propagate to the caller."""

        self.mock_smtp_instance.send_message.side_effect = smtplib.SMTPException("connection refused")
        try:
            self._call()

        except smtplib.SMTPException:
            self.fail("SMTPException propagated out of notify_users")

    def test_empty_job_list_sends_no_messages(self) -> None:
        """Verify no emails are sent when the job list is empty."""

        self._call(jobs=[])
        self.mock_smtp_instance.send_message.assert_not_called()

    def test_one_email_per_user(self) -> None:
        """Verify one email is sent per distinct username, regardless of job count."""

        jobs = [
            _make_job(job_id="1", username="alice"),
            _make_job(job_id="2", username="alice"),
            _make_job(job_id="3", username="bob"),
        ]
        self._call(jobs=jobs)

        recipients = sorted(message["To"] for message in self._sent_messages())
        self.assertEqual(["alice@example.com", "bob@example.com"], recipients)

    def test_multiple_jobs_per_user_appear_in_single_message(self) -> None:
        """Verify all of a user's jobs are listed in their single notification email."""

        jobs = [
            _make_job(job_id="111", username="alice", job_name="train", partition="gpu"),
            _make_job(job_id="222", username="alice", job_name="eval", partition="cpu"),
        ]
        self._call(jobs=jobs)

        messages = self._sent_messages()
        self.assertEqual(1, len(messages), "alice should receive exactly one email")

        body = _get_plain_body(messages[0])
        self.assertIn("111", body)
        self.assertIn("222", body)
        self.assertIn("train", body)
        self.assertIn("eval", body)
        self.assertIn("gpu", body)
        self.assertIn("cpu", body)

    def test_smtp_failure_for_one_user_does_not_block_others(self) -> None:
        """Verify an SMTP failure sending to one user does not prevent sending to others."""

        self.mock_smtp_instance.send_message.side_effect = [
            smtplib.SMTPException("boom"),
            None,
        ]
        jobs = [
            _make_job(job_id="1", username="alice"),
            _make_job(job_id="2", username="bob"),
        ]

        self._call(jobs=jobs)

        self.assertEqual(2, self.mock_smtp_instance.send_message.call_count)

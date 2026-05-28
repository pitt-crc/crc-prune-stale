"""Tests for the `notify` module."""

import smtplib
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale.notify import notify_users
from crc_prune_stale.slurm import JobRecord


@patch("smtplib.SMTP")
class NotifyUsers(TestCase):
    """Verify the email construction and SMTP behaviour of `notify_users`."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.job = JobRecord(
            job_id="12345",
            username="testuser",
            submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            job_name="my_job",
            partition="gpu",
        )

    @staticmethod
    def _smtp_instance(mock_smtp: MagicMock) -> MagicMock:
        """Return the mock SMTP instance returned by the `with` context manager."""

        return mock_smtp.return_value.__enter__.return_value

    @staticmethod
    def _sent_messages(mock_smtp: MagicMock) -> list:
        """Return all `EmailMessage` objects passed to `send_message`."""

        smtp_instance = mock_smtp.return_value.__enter__.return_value
        return [call.args[0] for call in smtp_instance.send_message.call_args_list]

    def test_recipient_address_matches_call_args(self, mock_smtp: MagicMock) -> None:
        """Verify the `To` field is constructed from the username and domain arguments."""

        notify_users(
            jobs=[self.job],
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
            threshold=10,
        )

        message = self._sent_messages(mock_smtp)[0]
        self.assertEqual(message["To"], "testuser@example.com")

    def test_sender_address_matches_call_args(self, mock_smtp: MagicMock) -> None:
        """Verify the `From` field matches the `email_from` argument."""

        notify_users(
            jobs=[self.job],
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
            threshold=10,
        )

        message = self._sent_messages(mock_smtp)[0]
        self.assertEqual(message["From"], "noreply@example.com")

    def test_subject_matches_expected_format(self, mock_smtp: MagicMock) -> None:
        """Verify the `Subject` field matches the expected format."""

        notify_users(
            jobs=[self.job],
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
            threshold=10,
        )

        message = self._sent_messages(mock_smtp)[0]
        self.assertEqual(message["Subject"], "Pending Slurm jobs cancelled")

    def test_body_contains_job_metadata(self, mock_smtp: MagicMock) -> None:
        """Verify the email body contains the job ID, name, partition, and submit time."""

        notify_users(
            jobs=[self.job],
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
            threshold=10,
        )

        body = self._sent_messages(mock_smtp)[0].get_content()
        self.assertIn("12345", body)
        self.assertIn("my_job", body)
        self.assertIn("gpu", body)
        self.assertIn("2024-01-01 12:00:00 UTC", body)

    def test_smtp_host_and_port(self, mock_smtp: MagicMock) -> None:
        """Verify the SMTP client is opened with the provided host and port."""

        notify_users(
            jobs=[self.job],
            smtp_host="mail.pitt.edu",
            smtp_port=587,
            email_from="noreply@example.com",
            email_domain="example.com",
            threshold=10,
        )

        mock_smtp.assert_called_with("mail.pitt.edu", 587)

    def test_empty_job_list_sends_no_messages(self, mock_smtp: MagicMock) -> None:
        """Verify no emails are sent when the job list is empty."""

        notify_users(
            jobs=[],
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
            threshold=10,
        )

        self._smtp_instance(mock_smtp).send_message.assert_not_called()

    def test_one_email_per_user(self, mock_smtp: MagicMock) -> None:
        """Verify one email is sent per distinct username, regardless of job count."""

        jobs = [
            JobRecord(
                job_id="1",
                username="alice",
                submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                job_name="my_job",
                partition="gpu",
            ),
            JobRecord(
                job_id="2",
                username="alice",
                submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                job_name="my_job",
                partition="gpu",
            ),
            JobRecord(
                job_id="3",
                username="bob",
                submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                job_name="my_job",
                partition="gpu",
            ),
        ]
        notify_users(
            jobs=jobs,
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
            threshold=10,
        )

        recipients = sorted(message["To"] for message in self._sent_messages(mock_smtp))
        self.assertEqual(recipients, ["alice@example.com", "bob@example.com"])

    def test_smtp_failure_for_one_user_does_not_block_others(self, mock_smtp: MagicMock) -> None:
        """Verify an SMTP failure sending to one user does not prevent sending to others."""

        self._smtp_instance(mock_smtp).send_message.side_effect = [
            smtplib.SMTPException("boom"),
            None,
        ]
        jobs = [
            JobRecord(
                job_id="1",
                username="alice",
                submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                job_name="my_job",
                partition="gpu",
            ),
            JobRecord(
                job_id="2",
                username="bob",
                submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                job_name="my_job",
                partition="gpu",
            ),
        ]
        notify_users(
            jobs=jobs,
            smtp_host="smtp.example.com",
            smtp_port=25,
            email_from="noreply@example.com",
            email_domain="example.com",
            threshold=10,
        )

        self.assertEqual(self._smtp_instance(mock_smtp).send_message.call_count, 2)

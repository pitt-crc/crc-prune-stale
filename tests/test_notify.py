"""Tests for the `notify` module."""

import smtplib
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from crc_prune_stale.notify import notify_users
from crc_prune_stale.slurm import JobRecord


def _make_job(
    job_id: str = "12345",
    username: str = "testuser",
    job_name: str = "my_job",
    partition: str = "gpu",
) -> JobRecord:
    """Return a `JobRecord` populated with mock data."""

    return JobRecord(
        job_id=job_id,
        username=username,
        submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        job_name=job_name,
        partition=partition,
    )


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
        """Verify that the `To` field is constructed from the username and domain."""

        self._call()
        message = self._sent_messages()[0]
        self.assertEqual(message["To"], "testuser@example.com")

    def test_sender_address_matches_email_from_argument(self) -> None:
        """Verify that the `From` field matches the `email_from` argument."""

        self._call()
        message = self._sent_messages()[0]
        self.assertEqual(message["From"], "noreply@example.com")

    def test_subject_matches_expected_format(self) -> None:
        """Verify that the `Subject` field matches the expected format exactly."""

        self._call()
        message = self._sent_messages()[0]
        self.assertEqual(message["Subject"], "Pending Slurm jobs cancelled")

    def test_body_contains_job_metadata(self) -> None:
        """Verify that the email body contains the job ID, name, partition, and submit time."""

        self._call()
        body = self._sent_messages()[0].get_content()
        self.assertIn("12345", body)
        self.assertIn("my_job", body)
        self.assertIn("gpu", body)
        self.assertIn("2024-01-01 12:00:00 UTC", body)

    def test_body_contains_threshold(self) -> None:
        """Verify that the email body references the configured threshold."""

        self._call(threshold=14)
        body = self._sent_messages()[0].get_content()
        self.assertIn("14 days", body)

    def test_smtp_connected_with_host_and_port(self) -> None:
        """Verify that the SMTP client is opened with the provided host and port."""

        self._call(smtp_host="mail.pitt.edu", smtp_port=587)
        self.mock_smtp.assert_called_with("mail.pitt.edu", 587)

    def test_single_user_receives_one_message(self) -> None:
        """Verify that one email is sent per call when only one user is affected."""

        self._call()
        self.mock_smtp_instance.send_message.assert_called_once()

    def test_smtp_exception_does_not_propagate(self) -> None:
        """Verify that an `SMTPException` is caught and does not propagate to the caller."""

        self.mock_smtp_instance.send_message.side_effect = smtplib.SMTPException("connection refused")
        try:
            self._call()

        except smtplib.SMTPException:
            self.fail("SMTPException propagated out of notify_users")

    def test_empty_job_list_sends_no_messages(self) -> None:
        """Verify that no emails are sent when the job list is empty."""

        self._call(jobs=[])
        self.mock_smtp_instance.send_message.assert_not_called()

    def test_one_email_per_user(self) -> None:
        """Verify that one email is sent per distinct username, regardless of job count."""

        jobs = [
            _make_job(job_id="1", username="alice"),
            _make_job(job_id="2", username="alice"),
            _make_job(job_id="3", username="bob"),
        ]
        self._call(jobs=jobs)

        recipients = sorted(message["To"] for message in self._sent_messages())
        self.assertEqual(recipients, ["alice@example.com", "bob@example.com"])

    def test_multiple_jobs_per_user_appear_in_single_message(self) -> None:
        """Verify that all of a user's jobs are listed in their single notification email."""

        jobs = [
            _make_job(job_id="111", username="alice", job_name="train", partition="gpu"),
            _make_job(job_id="222", username="alice", job_name="eval", partition="cpu"),
        ]
        self._call(jobs=jobs)

        messages = self._sent_messages()
        self.assertEqual(len(messages), 1, "alice should receive exactly one email")

        body = messages[0].get_content()
        self.assertIn("111", body)
        self.assertIn("222", body)
        self.assertIn("train", body)
        self.assertIn("eval", body)
        self.assertIn("gpu", body)
        self.assertIn("cpu", body)

    def test_smtp_failure_for_one_user_does_not_block_others(self) -> None:
        """Verify that an SMTP failure sending to one user does not prevent sending to others."""

        self.mock_smtp_instance.send_message.side_effect = [
            smtplib.SMTPException("boom"),
            None,
        ]
        jobs = [
            _make_job(job_id="1", username="alice"),
            _make_job(job_id="2", username="bob"),
        ]

        self._call(jobs=jobs)

        self.assertEqual(self.mock_smtp_instance.send_message.call_count, 2)
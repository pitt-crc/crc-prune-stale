"""Tests for the `notify` module."""

import smtplib
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch

from prune_stale.notify import notify_user
from prune_stale.slurm import JobRecord


class NotifyUser(TestCase):
    """Verify the email construction and SMTP behaviour of `notify_user`."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.job = JobRecord(
            job_id='12345',
            username='testuser',
            submit_time=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            job_name='my_job',
            partition='gpu',
        )

        self.smtp_patch = patch('smtplib.SMTP')
        self.mock_smtp = self.smtp_patch.start()
        self.mock_smtp_instance = MagicMock()
        self.mock_smtp.return_value.__enter__.return_value = self.mock_smtp_instance

    def tearDown(self) -> None:
        """Close any open server connections."""

        self.smtp_patch.stop()

    def _call(self, **kwargs) -> None:
        """Call `notify_user` with default test arguments, allowing overrides."""

        defaults = dict(
            job=self.job,
            smtp_host='smtp.example.com',
            smtp_port=25,
            email_from='noreply@example.com',
            email_domain='example.com',
            threshold=10,
        )

        notify_user(**{**defaults, **kwargs})

    def test_recipient_address_combines_username_and_domain(self) -> None:
        """Verify that the `To` field is constructed from the username and domain."""

        self._call()
        message = self.mock_smtp_instance.send_message.call_args[0][0]
        self.assertEqual(message['To'], 'testuser@example.com')

    def test_sender_address_matches_email_from_argument(self) -> None:
        """Verify that the `From` field matches the `email_from` argument."""

        self._call()
        message = self.mock_smtp_instance.send_message.call_args[0][0]
        self.assertEqual(message['From'], 'noreply@example.com')

    def test_subject_matches_expected_format(self) -> None:
        """Verify that the `Subject` field matches the expected format exactly."""

        self._call()
        message = self.mock_smtp_instance.send_message.call_args[0][0]
        self.assertEqual(message['Subject'], '[Slurm] Pending job 12345 cancelled after 10 days')

    def test_body_contains_job_metadata(self) -> None:
        """Verify that the email body contains the job ID, name, partition, and submit time."""

        self._call()
        body = self.mock_smtp_instance.send_message.call_args[0][0].get_content()
        self.assertIn('12345', body)
        self.assertIn('my_job', body)
        self.assertIn('gpu', body)
        self.assertIn('2024-01-01 12:00:00 UTC', body)

    def test_smtp_connected_with_host_and_port(self) -> None:
        """Verify that the SMTP client is opened with the provided host and port."""

        self._call(smtp_host='mail.pitt.edu', smtp_port=587)
        self.mock_smtp.assert_called_once_with('mail.pitt.edu', 587)

    def test_send_message_called_once(self) -> None:
        """Verify that `send_message` is called exactly once per notification."""

        self._call()
        self.mock_smtp_instance.send_message.assert_called_once()

    def test_smtp_exception_does_not_propagate(self) -> None:
        """Verify that an `SMTPException` is caught and does not propagate to the caller."""

        self.mock_smtp_instance.send_message.side_effect = smtplib.SMTPException('connection refused')
        try:
            self._call()

        except smtplib.SMTPException:
            self.fail('SMTPException propagated out of notify_user')

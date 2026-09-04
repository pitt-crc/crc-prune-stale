"""Unit tests for the `notify_users` function."""

import smtplib

from .common import _get_html_body, _get_plain_body, _make_job, MARKUP_JOB_NAME, NotifyUsersTestCase


class MessageHeaders(NotifyUsersTestCase):
    """Verify the headers and structure of the generated message."""

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
        """Verify the message uses multipart/alternative encoding."""

        self._call()
        message = self._sent_messages()[0]
        self.assertEqual("multipart/alternative", message.get_content_type())


class MessageBody(NotifyUsersTestCase):
    """Verify the job metadata rendered into the message body."""

    def test_plain_body_contains_job_metadata(self) -> None:
        """Verify the plain-text part contains the job ID, name, partition, reason, and submit time."""

        self._call()
        body = _get_plain_body(self._sent_messages()[0])
        self.assertIn("12345", body)
        self.assertIn("my_job", body)
        self.assertIn("gpu", body)
        self.assertIn("Resources", body)
        self.assertIn("2024-01-01 12:00:00", body)

    def test_html_body_contains_job_metadata(self) -> None:
        """Verify the HTML part contains the job ID, name, partition, reason, and submit time."""

        self._call()
        body = _get_html_body(self._sent_messages()[0])
        self.assertIn("12345", body)
        self.assertIn("my_job", body)
        self.assertIn("gpu", body)
        self.assertIn("Resources", body)
        self.assertIn("2024-01-01 12:00:00", body)

    def test_html_body_contains_pending_reason_column(self) -> None:
        """Verify the table includes a column header for the pending reason."""

        self._call()
        self.assertIn("Pending Reason", _get_html_body(self._sent_messages()[0]))

    def test_html_body_contains_reason_per_job(self) -> None:
        """Verify each job in a multi job message lists its own pending reason."""

        jobs = [
            _make_job(job_id="111", job_name="train", reason="Resources"),
            _make_job(job_id="222", job_name="eval", reason="QOSMaxJobsPerUserLimit"),
        ]
        self._call(jobs=jobs)
        body = _get_html_body(self._sent_messages()[0])

        self.assertIn("Resources", body)
        self.assertIn("QOSMaxJobsPerUserLimit", body)

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


class BodyEscaping(NotifyUsersTestCase):
    """Verify user controlled values are escaped before reaching the message body."""

    def test_html_body_escapes_job_name(self) -> None:
        """Verify markup in a job name is escaped in the HTML part."""

        self._call(jobs=[_make_job(job_name=MARKUP_JOB_NAME)])
        body = _get_html_body(self._sent_messages()[0])

        self.assertNotIn(MARKUP_JOB_NAME, body, "A job name must not be interpolated as markup")
        self.assertIn("&lt;script&gt;", body)

    def test_html_body_escapes_partition(self) -> None:
        """Verify markup in a partition name is escaped in the HTML part."""

        self._call(jobs=[_make_job(partition=MARKUP_JOB_NAME)])
        body = _get_html_body(self._sent_messages()[0])

        self.assertNotIn(MARKUP_JOB_NAME, body)

    def test_html_body_escapes_job_id(self) -> None:
        """Verify markup in a job ID is escaped in the HTML part."""

        self._call(jobs=[_make_job(job_id=MARKUP_JOB_NAME)])
        body = _get_html_body(self._sent_messages()[0])

        self.assertNotIn(MARKUP_JOB_NAME, body)

    def test_html_body_escapes_username(self) -> None:
        """Verify markup in a username is escaped in the HTML part."""

        self._call(jobs=[_make_job(username="alice<b>")])
        body = _get_html_body(self._sent_messages()[0])

        self.assertNotIn("alice<b>", body, "A username must not be interpolated as markup")
        self.assertIn("alice&lt;b&gt;", body)

    def test_html_body_escapes_pending_reason(self) -> None:
        """Verify markup in a pending reason is escaped in the HTML part."""

        self._call(jobs=[_make_job(reason=MARKUP_JOB_NAME)])
        body = _get_html_body(self._sent_messages()[0])

        self.assertNotIn(MARKUP_JOB_NAME, body, "A pending reason must not be interpolated as markup")

    def test_html_body_escapes_ampersand_in_job_name(self) -> None:
        """Verify an ampersand in a job name is escaped rather than read as a character reference."""

        self._call(jobs=[_make_job(job_name="fit_a&b")])
        body = _get_html_body(self._sent_messages()[0])

        self.assertIn("fit_a&amp;b", body)

    def test_plain_body_renders_job_name_literally(self) -> None:
        """Verify an escaped job name is rendered as literal text in the plain-text part."""

        self._call(jobs=[_make_job(job_name=MARKUP_JOB_NAME)])
        body = _get_plain_body(self._sent_messages()[0])

        self.assertIn(MARKUP_JOB_NAME, body, "The plain-text part should show the name the user chose")


class SmtpDelivery(NotifyUsersTestCase):
    """Verify how messages are handed to the SMTP server."""

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


class RecipientGrouping(NotifyUsersTestCase):
    """Verify how canceled jobs are grouped into messages per recipient."""

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

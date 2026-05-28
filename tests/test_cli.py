"""Tests for the `cli` module."""

from unittest import TestCase

from crc_prune_stale.cli import (
    create_parser,
    DEFAULT_APPEND_DOMAIN,
    DEFAULT_EMAIL_FROM,
    DEFAULT_SMTP_PORT,
    DEFAULT_THRESHOLD
)


class ParserConfig(TestCase):
    """Verify `create_parser` returns a correctly configured `ArgumentParser` instance."""

    def test_parser_prog_name(self) -> None:
        """Verify the parser program name is set to `prune-stale`."""

        self.assertEqual(create_parser().prog, "prune-stale")


class DryRunFlag(TestCase):
    """Verify parsing behavior of the `--dry-run` flag."""

    def setUp(self) -> None:
        """Instantiate a parser instance."""

        self.parser = create_parser(exit_on_error=False)

    def test_dry_run_defaults_to_false(self) -> None:
        """Verify the `--dry-run` flag defaults to `False`."""

        args = self.parser.parse_args([])
        self.assertFalse(args.dry_run)

    def test_dry_run_flag_sets_true(self) -> None:
        """Verify passing `--dry-run` sets `dry_run` to `True`."""

        args = self.parser.parse_args(["--dry-run"])
        self.assertTrue(args.dry_run)


class ThresholdArgument(TestCase):
    """Verify parsing behavior of the `--threshold` argument."""

    def setUp(self) -> None:
        """Instantiate a parser instance."""

        self.parser = create_parser(exit_on_error=False)

    def test_threshold_defaults_to_module_constant(self) -> None:
        """Verify `--threshold` defaults to `DEFAULT_THRESHOLD`."""

        args = self.parser.parse_args([])
        self.assertEqual(args.threshold, DEFAULT_THRESHOLD)

    def test_threshold_accepts_integer(self) -> None:
        """Verify `--threshold` parses a valid integer into `threshold_days`."""

        args = self.parser.parse_args(["--threshold", "30"])
        self.assertEqual(args.threshold, 30)


class SmtpHostArgument(TestCase):
    """Verify parsing behavior of the `--smtp-host` argument."""

    def setUp(self) -> None:
        """Instantiate a parser instance."""

        self.parser = create_parser(exit_on_error=False)

    def test_smtp_host_defaults_to_none(self) -> None:
        """Verify `--smtp-host` defaults to `None` when not provided."""

        args = self.parser.parse_args([])
        self.assertIsNone(args.smtp_host)

    def test_smtp_host_accepts_hostname(self) -> None:
        """Verify `--smtp-host` stores the provided hostname string."""

        args = self.parser.parse_args(["--smtp-host", "mail.example.com"])
        self.assertEqual(args.smtp_host, "mail.example.com")


class SmtpPortArgument(TestCase):
    """Verify parsing behavior of the `--smtp-port` argument."""

    def setUp(self) -> None:
        """Instantiate a parser instance."""

        self.parser = create_parser(exit_on_error=False)

    def test_smtp_port_defaults_to_module_constant(self) -> None:
        """Verify `--smtp-port` defaults to `DEFAULT_SMTP_PORT`."""

        args = self.parser.parse_args([])
        self.assertEqual(args.smtp_port, DEFAULT_SMTP_PORT)

    def test_smtp_port_accepts_integer(self) -> None:
        """Verify `--smtp-port` parses a valid integer."""

        args = self.parser.parse_args(["--smtp-port", "587"])
        self.assertEqual(args.smtp_port, 587)


class EmailFromArgument(TestCase):
    """Verify parsing behavior of the `--email-from` argument."""

    def setUp(self) -> None:
        """Instantiate a parser instance."""

        self.parser = create_parser(exit_on_error=False)

    def test_email_from_defaults_to_module_constant(self) -> None:
        """Verify `--email-from` defaults to `DEFAULT_EMAIL_FROM`."""

        args = self.parser.parse_args([])
        self.assertEqual(args.email_from, DEFAULT_EMAIL_FROM)

    def test_email_from_accepts_address(self) -> None:
        """Verify `--email-from` stores the provided address string."""

        args = self.parser.parse_args(["--email-from", "admin@example.com"])
        self.assertEqual(args.email_from, "admin@example.com")


class EmailDomainArgument(TestCase):
    """Verify parsing behavior of the `--email-dmn` argument."""

    def setUp(self) -> None:
        """Instantiate a parser instance."""

        self.parser = create_parser(exit_on_error=False)

    def test_email_dmn_defaults_to_module_constant(self) -> None:
        """Verify `--email-dmn` defaults to `DEFAULT_APPEND_DOMAIN`."""

        args = self.parser.parse_args([])
        self.assertEqual(args.email_dmn, DEFAULT_APPEND_DOMAIN)

    def test_email_dmn_accepts_bare_domain(self) -> None:
        """Verify a domain without a leading `@` is stored as-is."""

        args = self.parser.parse_args(["--email-dmn", "example.com"])
        self.assertEqual(args.email_dmn, "example.com")

    def test_email_dmn_strips_leading_at_symbol(self) -> None:
        """Verify a leading `@` is stripped from the domain value."""

        args = self.parser.parse_args(["--email-dmn", "@example.com"])
        self.assertEqual(args.email_dmn, "example.com", "Leading @ should be stripped from email domain")

    def test_email_dmn_strips_only_leading_at_symbol(self) -> None:
        """Verify only the leading `@` is stripped, not internal `@` characters."""

        args = self.parser.parse_args(["--email-dmn", "@sub.example.com"])
        self.assertEqual(args.email_dmn, "sub.example.com")

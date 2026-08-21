"""Tests for the `cli` module."""

from argparse import ArgumentError
from unittest import TestCase

from crc_prune_stale.cli import *

DEFAULT_CLUSTER = "development"
DEFAULT_PARTITIONS = ["partition1", "partition2"]


class ParserConfig(TestCase):
    """Verify `create_parser` returns a correctly configured `ArgumentParser` instance."""

    def test_parser_prog_name(self) -> None:
        """Verify the parser program name is set to `prune-stale`."""

        self.assertEqual("prune-stale", create_parser(DEFAULT_CLUSTER, DEFAULT_PARTITIONS).prog)


class ClusterArgument(TestCase):
    """Verify parsing behavior of the `--cluster` argument."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.parser = create_parser(DEFAULT_CLUSTER, DEFAULT_PARTITIONS, exit_on_error=False)

    def test_cluster_defaults_to_provided_value(self) -> None:
        """Verify `--cluster` defaults to the cluster name given to `create_parser`."""

        args = self.parser.parse_args([])
        self.assertEqual(DEFAULT_CLUSTER, args.cluster)

    def test_cluster_accepts_name(self) -> None:
        """Verify `--cluster` stores the provided cluster name."""

        args = self.parser.parse_args(["--cluster", "mpi"])
        self.assertEqual("mpi", args.cluster)

    def test_cluster_is_never_none(self) -> None:
        """Verify `--cluster` is not left unresolved when the argument is omitted."""

        args = self.parser.parse_args([])
        self.assertIsNotNone(args.cluster, "Cluster name should always resolve to a concrete value")


class PartitionArgument(TestCase):
    """Verify parsing behavior of the `--partition` argument."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.parser = create_parser(DEFAULT_CLUSTER, DEFAULT_PARTITIONS, exit_on_error=False)

    def test_partitions_default_to_provided_value(self) -> None:
        """Verify `--partition` defaults to the partition names given to `create_parser`."""

        args = self.parser.parse_args([])
        self.assertEqual(DEFAULT_PARTITIONS, args.partitions)

    def test_single_partition_stored_as_list(self) -> None:
        """Verify a single `--partition` value is stored as a single element list."""

        args = self.parser.parse_args(["--partition", "smp"])
        self.assertEqual(["smp"], args.partitions)

    def test_multiple_partitions_preserve_order(self) -> None:
        """Verify multiple `--partition` values are stored in the order they are given."""

        args = self.parser.parse_args(["--partition", "gpu", "smp", "opa"])
        self.assertEqual(["gpu", "smp", "opa"], args.partitions)

    def test_partitions_stored_under_plural_destination(self) -> None:
        """Verify parsed partition names are stored on the `partitions` attribute."""

        args = self.parser.parse_args(["--partition", "smp"])
        self.assertFalse(hasattr(args, "partition"), "Partition names should be stored as `partitions`")

    def test_partition_requires_a_value(self) -> None:
        """Verify `--partition` without a value produces a parsing error."""

        with self.assertRaises(ArgumentError):
            self.parser.parse_args(["--partition"])


class DryRunFlag(TestCase):
    """Verify parsing behavior of the `--dry-run` flag."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.parser = create_parser(DEFAULT_CLUSTER, DEFAULT_PARTITIONS, exit_on_error=False)

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
        """Create test fixtures using mock data."""

        self.parser = create_parser(DEFAULT_CLUSTER, DEFAULT_PARTITIONS, exit_on_error=False)

    def test_threshold_defaults_to_module_constant(self) -> None:
        """Verify `--threshold` defaults to `DEFAULT_THRESHOLD`."""

        args = self.parser.parse_args([])
        self.assertEqual(DEFAULT_THRESHOLD, args.threshold)

    def test_threshold_accepts_integer(self) -> None:
        """Verify `--threshold` parses a valid integer into `threshold_days`."""

        args = self.parser.parse_args(["--threshold", "30"])
        self.assertEqual(30, args.threshold)


class SmtpHostArgument(TestCase):
    """Verify parsing behavior of the `--smtp-host` argument."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.parser = create_parser(DEFAULT_CLUSTER, DEFAULT_PARTITIONS, exit_on_error=False)

    def test_smtp_host_defaults_to_none(self) -> None:
        """Verify `--smtp-host` defaults to `None` when not provided."""

        args = self.parser.parse_args([])
        self.assertIsNone(args.smtp_host)

    def test_smtp_host_accepts_hostname(self) -> None:
        """Verify `--smtp-host` stores the provided hostname string."""

        args = self.parser.parse_args(["--smtp-host", "mail.example.com"])
        self.assertEqual("mail.example.com", args.smtp_host)


class SmtpPortArgument(TestCase):
    """Verify parsing behavior of the `--smtp-port` argument."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.parser = create_parser(DEFAULT_CLUSTER, DEFAULT_PARTITIONS, exit_on_error=False)

    def test_smtp_port_defaults_to_module_constant(self) -> None:
        """Verify `--smtp-port` defaults to `DEFAULT_SMTP_PORT`."""

        args = self.parser.parse_args([])
        self.assertEqual(DEFAULT_SMTP_PORT, args.smtp_port)

    def test_smtp_port_accepts_integer(self) -> None:
        """Verify `--smtp-port` parses a valid integer."""

        args = self.parser.parse_args(["--smtp-port", "587"])
        self.assertEqual(587, args.smtp_port)


class EmailFromArgument(TestCase):
    """Verify parsing behavior of the `--email-from` argument."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.parser = create_parser(DEFAULT_CLUSTER, DEFAULT_PARTITIONS, exit_on_error=False)

    def test_email_from_defaults_to_module_constant(self) -> None:
        """Verify `--email-from` defaults to `DEFAULT_EMAIL_FROM`."""

        args = self.parser.parse_args([])
        self.assertEqual(DEFAULT_EMAIL_FROM, args.email_from)

    def test_email_from_accepts_address(self) -> None:
        """Verify `--email-from` stores the provided address string."""

        args = self.parser.parse_args(["--email-from", "admin@example.com"])
        self.assertEqual("admin@example.com", args.email_from)


class EmailDomainArgument(TestCase):
    """Verify parsing behavior of the `--email-dmn` argument."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.parser = create_parser(DEFAULT_CLUSTER, DEFAULT_PARTITIONS, exit_on_error=False)

    def test_email_dmn_defaults_to_module_constant(self) -> None:
        """Verify `--email-dmn` defaults to `DEFAULT_APPEND_DOMAIN`."""

        args = self.parser.parse_args([])
        self.assertEqual(DEFAULT_APPEND_DOMAIN, args.email_dmn)

    def test_email_dmn_accepts_bare_domain(self) -> None:
        """Verify a domain without a leading `@` is stored as-is."""

        args = self.parser.parse_args(["--email-dmn", "example.com"])
        self.assertEqual("example.com", args.email_dmn)

    def test_email_dmn_strips_leading_at_symbol(self) -> None:
        """Verify a leading `@` is stripped from the domain value."""

        args = self.parser.parse_args(["--email-dmn", "@sub.example.com"])
        self.assertEqual("sub.example.com", args.email_dmn)

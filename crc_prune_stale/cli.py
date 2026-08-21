"""The application command line interface."""

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

__all__ = (
    "DEFAULT_APPEND_DOMAIN",
    "DEFAULT_EMAIL_FROM",
    "DEFAULT_SMTP_PORT",
    "DEFAULT_THRESHOLD",
    "create_parser",
)

DEFAULT_THRESHOLD = 10  # Days
DEFAULT_SMTP_PORT = 25
DEFAULT_EMAIL_FROM = "slurm-noreply@crc.pitt.edu"
DEFAULT_APPEND_DOMAIN = "pitt.edu"


def create_parser(default_cluster: str, exit_on_error: bool = True) -> ArgumentParser:
    """Create the application argument parser.

    Args:
        default_cluster: Cluster name used when the `--cluster` argument is omitted.
        exit_on_error: Whether to exit the Python runtime when a parsing error occurs.

    Returns:
        parser: An argument parser configured with application specific arguments.
    """

    parser = ArgumentParser(
        prog="prune-stale",
        description="Cancel Slurm jobs that have been PENDING for longer than a given threshold.",
        exit_on_error=exit_on_error,
        formatter_class=ArgumentDefaultsHelpFormatter,
    )

    targeting = parser.add_argument_group("targeting", "Controls which cluster and partitions are queried for jobs.")

    targeting.add_argument(
        "--cluster", metavar="NAME", default=default_cluster,
        help="cluster name to query for jobs.")

    targeting.add_argument(
        "--partition", metavar="NAME", nargs="+", dest="partitions", default=None,
        help="partition names to query for jobs. Omit for all partitions.")

    cancelling = parser.add_argument_group("cancelling", "Controls which jobs are selected for cancellation.")

    cancelling.add_argument(
        "--dry-run", action="store_true",
        help="log stale jobs without actually canceling them.")

    cancelling.add_argument(
        "--threshold", metavar="DAYS", type=int, default=DEFAULT_THRESHOLD,
        help="number of days a job must be pending before it is cancelled.")

    notifications = parser.add_argument_group("notifications", "Controls outbound email notifications.")

    notifications.add_argument(
        "--smtp-host", metavar="HOST", default=None,
        help="SMTP server hostname. Omit to disable email notifications.")

    notifications.add_argument(
        "--smtp-port", metavar="PORT", type=int, default=DEFAULT_SMTP_PORT,
        help="SMTP server port.")

    notifications.add_argument(
        "--email-from", metavar="ADDRESS", default=DEFAULT_EMAIL_FROM,
        help="sender address for notification emails.")

    notifications.add_argument(
        "--email-dmn", metavar="DOMAIN", type=lambda x: x.lstrip("@"), default=DEFAULT_APPEND_DOMAIN,
        help="domain appended to usernames when constructing email addresses.")

    return parser

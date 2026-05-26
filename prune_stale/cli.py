"""The application command line interface."""

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

__all__ = [
    "DEFAULT_APPEND_DOMAIN",
    "DEFAULT_EMAIL_FROM",
    "DEFAULT_SMTP_PORT",
    "DEFAULT_THRESHOLD",
    "create_parser",
]

DEFAULT_THRESHOLD = 10  # Days
DEFAULT_SMTP_PORT = 25
DEFAULT_EMAIL_FROM = "slurm-noreply@pitt.edu"
DEFAULT_APPEND_DOMAIN = "pitt.edu"


def create_parser(exit_on_error: bool = True) -> ArgumentParser:
    """Create the application argument parser.

    Args:
        exit_on_error: Whether to exit the Python runtime when a parsing error occurs.

    Returns:
        parser: An argument parser configured with application specific arguments.
    """

    parser = ArgumentParser(
        prog="prune-stale",
        description="cancel Slurm jobs that have been in a given state for longer than a given threshold.",
        exit_on_error=exit_on_error,
        formatter_class=ArgumentDefaultsHelpFormatter,
    )

    pruning = parser.add_argument_group("pruning", "Controls which jobs are selected for cancellation.")

    pruning.add_argument(
        "--dry-run", action="store_true",
        help="log which jobs would be cancelled without actually canceling them.")

    pruning.add_argument(
        "--threshold", metavar="DAYS", type=int, default=DEFAULT_THRESHOLD,
        help="number of days a job must have been pending before it is cancelled.")

    notifications = parser.add_argument_group("notifications", "controls outbound email notifications.")
    notifications.add_argument("--smtp-host", metavar="HOST", help="SMTP server hostname.")
    notifications.add_argument("--smtp-port", metavar="PORT", type=int, default=DEFAULT_SMTP_PORT, help="SMTP server port.")

    notifications.add_argument(
        "--email-from", metavar="ADDRESS", default=DEFAULT_EMAIL_FROM,
        help="sender address for notification emails.")

    notifications.add_argument(
        "--email-dmn", metavar="DOMAIN", type=lambda x: x.lstrip("@"), default=DEFAULT_APPEND_DOMAIN,
        help="domain appended to usernames when constructing email addresses.")

    return parser

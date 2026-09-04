"""Shared fixtures and mock data for the `slurm` module tests."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

# Logger name targeted when asserting against emitted log records
SLURM_LOGGER = "crc_prune_stale.slurm"

# Local timezone applied when parsing mock `squeue` output. A zone with a
# non-zero, seasonally varying offset keeps UTC conversion errors visible
NODE_TIMEZONE = "America/New_York"

# Mock stdout streams returned by `squeue` and `scontrol`
PENDING_LINE = "12345|testuser|2024-01-01T12:00:00|my_job|gpu|PENDING|Resources\n"
CLUSTER_BANNER = "CLUSTER: htc\n"
SCONTROL_OUTPUT = (
    "Configuration data as of 2024-01-01T12:00:00\n"
    "AccountingStorageHost   = mgmt01\n"
    "ClusterName             = htc\n"
    "ControlMachine          = mgmt01\n"
)

# Mock stderr streams returned by `scancel` alongside a zero exit status
SCANCEL_DENIED_STDERR = "scancel: error: Kill job error on job id 12345: Access/permission denied\n"
SCANCEL_FATAL_STDERR = "scancel: fatal: Unable to contact slurm controller (connect failure)\n"
SCANCEL_VERBOSE_STDERR = "scancel: verbose: Terminating job 12345\n"

# Array job IDs as reported by `squeue`, with and without a concurrency limit
THROTTLED_ARRAY_ID = "3237889_[0-15%16]"
THROTTLED_ARRAY_ID_NORMALIZED = "3237889_[0-15]"
UNTHROTTLED_ARRAY_ID = "20916495_[100-140]"


def _make_result(stdout: str = "", stderr: str = "") -> MagicMock:
    """Return a mock `subprocess.CompletedProcess` with the given output streams.

    Args:
        stdout: The standard output captured from the mock process.
        stderr: The standard error captured from the mock process.

    Returns:
        result: A mock completed process.
    """

    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    return result


class SubprocessTestCase(TestCase):
    """Base class patching the subprocess wrapper used by the Slurm commands."""

    def setUp(self) -> None:
        """Create test fixtures using mock data."""

        self.subprocess_patch = patch("crc_prune_stale.slurm.run_subprocess")
        self.mock_run = self.subprocess_patch.start()

    def tearDown(self) -> None:
        """Close any open server connections."""

        self.subprocess_patch.stop()

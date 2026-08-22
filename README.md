# Slurm Job Pruning

A maintenance tool for canceling stale jobs on Slurm clusters.

A command-line utility for Slurm administrators that identifies and cancels
jobs which have been stuck in the PENDING state for longer than a configurable
threshold. Affected users are notified by email, with all of their canceled
jobs batched into a single message, and a dry-run mode is provided for
previewing changes before applying them.

## Install and Setup

Install the utility from the CRCD Python repository using pipx:

```shell
pipx install crc-prune-stale
```

Confirm the `prune-stale` utility is available in your runtime environment:

```shell
prune-stale --help
```

Optionally, create the application log directory to enable persistent file
logging. If the directory is not present, or the log file cannot be opened,
the application emits a warning and falls back to console-only logging:

```shell
mkdir -p /var/log/prune_stale
```

Logs are written to `/var/log/prune_stale/prune_stale.log`.

## Usage

```
prune-stale [OPTIONS]
```

### Targeting options

Control which cluster and partitions are queried for jobs.

| Option                 | Default        | Description                                                   |
|------------------------|----------------|---------------------------------------------------------------|
| `--cluster NAME`       | local cluster  | Cluster name to query for jobs                                |
| `--partition NAME ...` | all partitions | One or more partition names to query. Omit for all partitions |

The default cluster is resolved at startup from the local node's Slurm
configuration (`scontrol show config`). If no cluster name can be determined,
the application exits with an error.

### Pruning options

Control which jobs are selected for cancellation.

| Option             | Default | Description                                                 |
|--------------------|---------|-------------------------------------------------------------|
| `--threshold DAYS` | `10`    | Days a job must have been pending before cancellation       |
| `--dry-run`        | off     | Log which jobs would be cancelled without taking any action |

Job age is measured against the job's submit time as reported by `squeue`.
Jobs with malformed or unparsable `squeue` output are skipped and logged as
warnings.

### Notification options

Control outbound email notifications.

| Option                 | Default                      | Description                                              |
|------------------------|------------------------------|----------------------------------------------------------|
| `--smtp-host HOST`     | —                            | SMTP relay hostname. Omit to disable email notifications |
| `--smtp-port PORT`     | `25`                         | SMTP relay port                                          |
| `--email-from ADDRESS` | `slurm-noreply@crc.pitt.edu` | Sender address for notification emails                   |
| `--email-dmn DOMAIN`   | `pitt.edu`                   | Domain appended to usernames to form recipient addresses |

Notifications are only sent when `--smtp-host` is provided **and** `--dry-run`
is not set. SMTP failures are logged and do not abort the run.

Pass `--help` to see all options with their current defaults.

## Examples

Cancel all jobs that have been pending for more than 10 days (no email notification):

```bash
prune-stale --threshold 10
```

Cancel jobs and issue an email notification to the job submitter:

```bash
prune-stale --threshold 10 --smtp-host mailrelay.pitt.edu
```

Restrict the run to specific partitions on a specific cluster:

```bash
prune-stale --cluster htc --partition standard high-mem
```

Preview what would be canceled without making any changes:

```bash
prune-stale --dry-run
```

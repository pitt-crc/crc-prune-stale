# crc-prune-stale

A maintenance tool for canceling stale jobs on Slurm clusters. 

A command-line utility for Slurm administrators that identifies and 
cancels jobs which have been stuck in the PENDING state for longer
than a configurable threshold. Affected users are notified by email,
with all of their cancelled jobs batched into a single message, and
a dry-run mode is provided for previewing changes before applying them.

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
logging. If the directory is not present, the application will fall back to
console-only logging:

```shell
sudo mkdir -p /var/log/prune_stale
```

## Usage

```
prune-stale [OPTIONS]
```

### Pruning options

| Option             | Default | Description                                                 |
|--------------------|---------|-------------------------------------------------------------|
| `--threshold DAYS` | `10`    | Days a job must have been pending before cancellation       |
| `--dry-run`        | off     | Log which jobs would be cancelled without taking any action |

### Notification options

| Option                 | Default                  | Description                                              |
|------------------------|--------------------------|----------------------------------------------------------|
| `--smtp-host HOST`     | —                        | SMTP relay hostname. Omit to disable email notifications |
| `--smtp-port PORT`     | `25`                     | SMTP relay port                                          |
| `--email-from ADDRESS` | `slurm-noreply@pitt.edu` | Sender address for notification emails                   |
| `--email-dmn DOMAIN`   | `pitt.edu`               | Domain appended to usernames to form recipient addresses |

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

Preview what would be cancelled without making any changes:

```bash
prune-stale --dry-run
```

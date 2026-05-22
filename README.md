# Canceling Pending Slurm Jobs
A maintenance tool for canceling pending SLURM jobs older than a certain age
and notifying the submitting user.

## Installation

Install the package from the CRCD package repository:

```bash
pip install crc-prune-stale
```

The tool is intended to run as a scheduled cron job on a head or management node.
Ensure the log directory exists and is writable before deploying:

```bash
sudo mkdir -p /var/log/prune_stale
sudo chown <service-user> /var/log/prune_stale
```

## Usage
The `prune-stale` command automatically identifies any stale pending jobs,
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
| `--smtp-host HOST`     | —                        | SMTP relay hostname (required)                           |
| `--smtp-port PORT`     | `25`                     | SMTP relay port                                          |
| `--email-from ADDRESS` | `slurm-noreply@pitt.edu` | Sender address for notification emails                   |
| `--email-dmn DOMAIN`   | `pitt.edu`               | Domain appended to usernames to form recipient addresses |

## Examples

Cancel all jobs that have been pending for more than 10 days and notify their owners:

```bash
prune-stale --smtp-host mailrelay.domain.com
```

Preview what would be cancelled without making any changes:

```bash
prune-stale --dry-run
```

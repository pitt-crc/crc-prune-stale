# prune-stale

A maintenance tool for Pitt CRCD Slurm clusters. It queries all
pending jobs, cancels any that have been waiting longer than a configurable
threshold, and emails the submitting user at their `@pitt.edu` address.

## Usage

```
python -m cancel_stale_pending_jobs [OPTIONS]
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

Pass `--help` to see all options with their current defaults.

## Examples

Cancel all jobs that have been pending for more than 10 days and notify their owners:

```bash
python -m cancel_stale_pending_jobs --smtp-host mailrelay.pitt.edu
```

Preview what would be cancelled without making any changes:

```bash
python -m cancel_stale_pending_jobs --dry-run --smtp-host mailrelay.pitt.edu
```

Tighten the threshold to 5 days:

```bash
python -m cancel_stale_pending_jobs --threshold 5 --smtp-host mailrelay.pitt.edu
```

## Logging

Two handlers are configured at startup:

- **Console** — `INFO` and above, written to stdout.
- **File** — `DEBUG` and above, written to `/var/log/prune_stale/prune_stale.log`.

Ensure the log directory exists and is writable before running:

```bash
sudo mkdir -p /var/log/prune_stale
sudo chown <service-user> /var/log/prune_stale
```

## Scheduling

To run nightly at 02:00 as a cron job:

```
0 2 * * * <service-user> python -m cancel_stale_pending_jobs --smtp-host mailrelay.pitt.edu
```

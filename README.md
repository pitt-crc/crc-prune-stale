# prune-stale

A maintenance tool for Pitt CRCD Slurm clusters. It queries all
pending jobs, cancels any that have been waiting longer than a configurable
threshold, and emails the submitting user at their `@pitt.edu` address.

## Install and Setup

Install the utility from the CRCD Python repository using pipx:

```shell
pipx install crc-prune-stale
```

Before running for the first time, create the application log directory:

```shell
sudo mkdir -p /var/log/prune_stale
```

Confirm the `prune-stale` utility is availible in your runtime environment:

```shell
prune-stale --help
```

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
python -m cancel_stale_pending_jobs --threshold 10 --smtp-host mailrelay.pitt.edu
```

Preview what would be canceled without making any changes:

```bash
python -m cancel_stale_pending_jobs --dry-run --smtp-host mailrelay.pitt.edu
```

To schedule twice daily execution at 10:00 AM/PM, add the following entry to your crontab:

```
0 10,22 * * * <service-user> python -m cancel_stale_pending_jobs --smtp-host mailrelay.pitt.edu
```

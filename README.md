🦊

## Development

### Setup

Use `pipenv`:

```bash
pipenv install --dev
pipenv run redbot-setup
```

### Running

```bash
pipenv run redbot <name> --dev --debug
```

First run will have you provide a token. [Grab one here after adding a bot user.](https://discord.com/developers/applications/)

### Formatting

Use [black](https://pypi.org/project/black/).

## Deployment

### Inventory

In `ansible/hosts`:

```ini
[crow]
host.name.here ansible_user=gcp_username_com
```

### Deployment

```bash
./scripts/deploy.sh
```

### Post-deploy

Follow [Red-DiscordBot's setup](https://docs.discord.red/en/stable/getting_started.html#getting-started), and use `/usr/local/share/Red-DiscordBot` as a data directory.

The systemd instance will be broken until this is configured.
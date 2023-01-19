🦊

## Development

### Setup

Use `pipenv`:

```bash
pipenv install --dev
pipenv run redbot-setup
```

Name your bot instance `dev`, ideally, for the built-in scripts here to work as-is.

### Running

```bash
pipenv run bot
```

First run will have you provide a token. [Grab one here after adding a bot user.](https://discord.com/developers/applications/)

### Formatting, linting, tests

Use [black](https://pypi.org/project/black/). `pipenv run style` to auto-format all files.

`pyright` is used for type checking. `pipenv run check` to run.

Similarly, `pipenv run test` to run `pytest` tests.

To validate that things will work on CI, you can use `pipenv run ci`.

## Deployment

### Inventory

In `ansible/hosts`:

```ini
[crow]
host.name.here ansible_user=gcp_username_com
```

### Deployment

```bash
./scripts/deploy
```

#### Docker

First-run:

```bash
docker run --name kenku -it -v /opt/kenku:/data --restart unless-stopped ghcr.io/mtkanjon/kenku:main
```

Subsequent:

```bash
docker start kenku
```

### Post-deploy

Follow [Red-DiscordBot's setup](https://docs.discord.red/en/stable/getting_started.html#getting-started), and use `/usr/local/share/Red-DiscordBot` as a data directory.

The systemd instance will be broken until this is configured.
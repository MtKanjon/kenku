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

Use Docker!

First-run:

```bash
docker run --name kenku -it -v /opt/kenku:/data --restart unless-stopped ghcr.io/mtkanjon/kenku:main
```

Subsequent runs:

```bash
docker start kenku
```

### GitHub Actions

In addition to style checks, GitHub actions will also deploy this project on push to the main branch.
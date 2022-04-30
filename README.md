🦊

## Development

### Setup

```bash
python3 -m venv red
./red/bin/pip3 install -r requirements.txt
./red/bin/redbot-setup
```

### Running

```bash
./red/bin/redbot <name>
```

First run will have you provide a token. [Grab one here after adding a bot user.](https://discord.com/developers/applications/).

## Deployment

### Inventory

In `ansible/hosts`:

```ini
[crow]
host.name.here ansible_user=gcp_username_com
```

### Deployment

```bash
cd ansible
ansible-playbook crow.yml
```

### Post-deploy

Follow [Red-DiscordBot's setup](https://docs.discord.red/en/stable/getting_started.html#getting-started), and use `/usr/local/share/Red-DiscordBot` as a data directory.

The systemd instance will be broken until this is configured.
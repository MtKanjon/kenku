🦊

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
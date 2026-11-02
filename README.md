# codex-daemon-update-hook

A pacman hook that keeps Codex's managed background daemon package in sync with the Arch Linux `openai-codex` package.

Codex can keep a separate, pinned daemon binary under `~/.codex/packages/app-server-daemon`. Upgrading the system CLI can leave that daemon on an older version, including an older model catalogue.

## Installation and configuration

Once the first release is published to AUR:

```sh
yay -S codex-daemon-update-hook
sudoedit /etc/codex-daemon-update-hook/users
```

Add one participating username per line. Blank lines and `#` comments are allowed. No users are enabled by default; root accounts are rejected. Home directories and IDs are resolved through the system account database. Configuration is preserved across upgrades.

The hook runs after `openai-codex` installation or upgrade. It supports Arch Linux with systemd, the official CLI package layout and the default `~/.codex` directory. It only updates existing daemon installations. Custom `CODEX_HOME` directories and alternative CLI packages are outside the current scope.

## What happens during an upgrade

Already matching packages are skipped. Stopped daemons update automatically. A running daemon produces an amber warning identifying its user:

```text
============================================================
  CODEX BACKGROUND DAEMON UPDATE: alice
============================================================

Codex has been upgraded, but its background daemon is still using
the previous version.

Updating it will interrupt active daemon sessions.

Update and restart the daemon now? [y/N]
```

Enter, `n` or end of input skips the update. Only `y` or `yes` confirms. Without a controlling terminal, a running daemon is skipped with a reminder. `NO_COLOR` and `TERM=dumb` disable colours.

Updates run as the affected user in a temporary systemd service. This lets the updater finish even if restarting Codex terminates the session that launched pacman. It does **not** preserve active daemon sessions: confirming a restart interrupts them. No service is enabled at boot. Per-user unit names prevent overlapping updates.

To update later, run as the affected user from a terminal independent of the daemon, for example a `codex --no-daemon` session:

```sh
codex app-server daemon update --from-cli -y
```

Failed updates are reported without preventing processing of other configured users. Inspect the indicated unit, replacing `1000` with that user's UID:

```sh
sudo journalctl -u codex-daemon-update-hook-1000.service
```

The updater copies and pins the installed CLI package. This hook refreshes that pin on subsequent package upgrades.

## Migrating from a manually installed hook

Remove the earlier local hook and helper before enabling this package, to avoid duplicate execution:

```sh
sudo rm /etc/pacman.d/hooks/95-codex-daemon-update.hook
sudo rm /usr/local/libexec/codex-daemon-pacman-update
```

These paths refer to the original manual installation. Check their contents before removal if your setup differs.

## Development and releases

```sh
bash -n src/update scripts/*.sh
shellcheck src/update scripts/*.sh tests/*.sh
python -m unittest discover -s tests -v
scripts/package.sh 0.1.0
cd build && makepkg --force --nodeps
```

Packaging requires Arch's `makepkg`; archives are generated from committed sources. CI also builds and inspects the package in an Arch container, including configuration preservation during reinstall.

Successful pushes to `main` automatically create a GitHub release and publish its `PKGBUILD` and `.SRCINFO` to AUR. Conventional `feat:` commits bump the minor version, `!` or `BREAKING CHANGE:` bumps the major version, and other changes bump the patch version. The first release is `0.1.0`. A commit containing `[skip release]` runs validation but skips publication. Pull requests never publish.

Publishing requires repository secrets `AUR_USERNAME`, `AUR_EMAIL` and `AUR_SSH_PRIVATE_KEY`, matching the existing `sudo-mcp` publishing setup. Release archives use SHA-256 verification; `.SRCINFO` is generated with `makepkg`.

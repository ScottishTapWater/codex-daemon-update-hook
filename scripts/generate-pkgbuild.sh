#!/bin/bash
set -euo pipefail
if (( $# != 2 )) || [[ ! $1 =~ ^[0-9]+\.[0-9]+\.[0-9]+$ || ! $2 =~ ^[0-9a-f]{64}$ ]]; then
    printf 'Usage: %s VERSION SHA256\n' "$0" >&2
    exit 1
fi
cat <<EOF
# Maintainer: James Hughes <james@pyrosoftsolutions.co.uk>
pkgname=codex-daemon-update-hook
pkgver=$1
pkgrel=1
pkgdesc='Keep managed Codex daemon packages in sync with pacman upgrades'
arch=('any')
url='https://github.com/ScottishTapWater/codex-daemon-update-hook'
license=('MIT')
depends=('bash' 'coreutils' 'procps-ng' 'systemd' 'openai-codex')
backup=('etc/codex-daemon-update-hook/users')
source=("\$pkgname-\$pkgver.tar.gz::\$url/releases/download/v\$pkgver/\$pkgname-\$pkgver.tar.gz")
sha256sums=('$2')

package() {
    cd "\$pkgname-\$pkgver"
    install -Dm755 src/update "\$pkgdir/usr/lib/\$pkgname/update"
    install -Dm644 packaging/95-codex-daemon-update-hook.hook "\$pkgdir/usr/share/libalpm/hooks/95-codex-daemon-update-hook.hook"
    install -Dm644 packaging/users "\$pkgdir/etc/\$pkgname/users"
    install -Dm644 README.md "\$pkgdir/usr/share/doc/\$pkgname/README.md"
    install -Dm644 LICENSE "\$pkgdir/usr/share/licenses/\$pkgname/LICENSE"
}
EOF

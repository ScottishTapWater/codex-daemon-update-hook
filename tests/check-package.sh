#!/bin/bash
set -euo pipefail
package=${1:?Usage: check-package.sh PACKAGE}
staging=$(mktemp -d)
trap 'rm -rf "$staging"' EXIT
bsdtar -xf "$package" -C "$staging"
test -x "$staging/usr/lib/codex-daemon-update-hook/update"
test -f "$staging/usr/share/libalpm/hooks/95-codex-daemon-update-hook.hook"
test -f "$staging/etc/codex-daemon-update-hook/users"
test -f "$staging/usr/share/licenses/codex-daemon-update-hook/LICENSE"
grep -Fx 'arch = any' "$staging/.PKGINFO"
grep -Fx 'backup = etc/codex-daemon-update-hook/users' "$staging/.PKGINFO"
! grep -Eq '^[^#[:space:]]' "$staging/etc/codex-daemon-update-hook/users"

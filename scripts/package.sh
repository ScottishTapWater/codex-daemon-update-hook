#!/bin/bash
set -euo pipefail
version=${1:?Usage: package.sh VERSION}
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 1
cd "$(dirname "$0")/.."
mkdir -p build
archive="codex-daemon-update-hook-$version.tar.gz"
# Use committed sources so local scratch files never enter release archives.
git archive --format=tar --prefix="codex-daemon-update-hook-$version/" HEAD | gzip -n >"build/$archive"
checksum=$(sha256sum "build/$archive")
scripts/generate-pkgbuild.sh "$version" "${checksum%% *}" >build/PKGBUILD
(cd build && makepkg --printsrcinfo >.SRCINFO)

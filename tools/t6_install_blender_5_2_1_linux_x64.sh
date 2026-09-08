#!/usr/bin/env bash
set -euo pipefail

VERSION="5.2.1"
SERIES="5.2"
ARCHIVE="blender-${VERSION}-linux-x64.tar.xz"
EXPECTED_SHA256="a31f524fa99a527d3d52b7f5aaa68c34e1a19d5a1c9473f79c5cc610fd5b10e9"
ROOT="${RUNNER_TEMP:-/tmp}/blender-${VERSION}-runtime"
CACHE="${RUNNER_TEMP:-/tmp}/${ARCHIVE}"

urls=(
  "https://mirror.blender.org/release/Blender${SERIES}/${ARCHIVE}"
  "https://download.blender.org/release/Blender${SERIES}/${ARCHIVE}"
  "https://mirror.nju.edu.cn/blender/release/Blender${SERIES}/${ARCHIVE}"
)

if [[ ! -s "$CACHE" ]] || [[ "$(sha256sum "$CACHE" | awk '{print $1}')" != "$EXPECTED_SHA256" ]]; then
  rm -f "$CACHE"
  ok=0
  for url in "${urls[@]}"; do
    if curl --fail --location --retry 4 --retry-delay 2 --connect-timeout 30 --output "$CACHE" "$url"; then
      ok=1
      break
    fi
  done
  test "$ok" -eq 1
fi

echo "$EXPECTED_SHA256  $CACHE" | sha256sum -c -
rm -rf "$ROOT"
mkdir -p "$ROOT"
tar -xJf "$CACHE" -C "$ROOT" --strip-components=1
BLENDER="$ROOT/blender"
test -x "$BLENDER"
version_line="$($BLENDER --version | head -1)"
test "$version_line" = "Blender ${VERSION} LTS" || test "$version_line" = "Blender ${VERSION}"
"$BLENDER" --version | head -3

if [[ -n "${GITHUB_ENV:-}" ]]; then
  echo "BLENDER=$BLENDER" >> "$GITHUB_ENV"
  echo "T6_BLENDER_VERSION=$VERSION" >> "$GITHUB_ENV"
  echo "T6_BLENDER_ARCHIVE_SHA256=$EXPECTED_SHA256" >> "$GITHUB_ENV"
else
  printf '%s\n' "$BLENDER"
fi

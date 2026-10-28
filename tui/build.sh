#!/bin/sh
# Builds the TUI from our opencode code in tui/opencode (DEC-025, DEC-027)
# into tui/bin/opencode (opencode.exe on Windows). Bun is fetched at the
# pinned version and checksum (build.env) into ~/.watterson/bun/ when missing.
# Runs on Linux and macOS (x64, arm64), and on Windows under Git Bash.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
. "$here/build.env"

case $(uname -s) in
  Linux) os=linux ;;
  Darwin) os=darwin ;;
  MINGW*|MSYS*|CYGWIN*) os=windows ;;
  *) echo "build: unsupported OS $(uname -s)" >&2; exit 1 ;;
esac
case $(uname -m) in
  x86_64|amd64) arch=x64 ;;
  arm64|aarch64) arch=aarch64 ;;
  *) echo "build: unsupported CPU $(uname -m)" >&2; exit 1 ;;
esac
exe=; [ "$os" = windows ] && exe=.exe
eval "bun_sha256=\${bun_sha256_${os}_${arch}:-}"
[ -n "$bun_sha256" ] || { echo "build: no Bun checksum for $os-$arch in build.env" >&2; exit 1; }

sha256() {
  if command -v sha256sum >/dev/null 2>&1 && sha256sum --version 2>/dev/null | grep -q GNU; then
    sha256sum "$1"
  else
    shasum -a 256 "$1"
  fi
}

bun_dir=$HOME/.watterson/bun/$bun
if [ ! -x "$bun_dir/bun$exe" ]; then
  tmp=$(mktemp -d)
  zip=bun-$os-$arch
  curl -fsSL -o "$tmp/bun.zip" "https://github.com/oven-sh/bun/releases/download/bun-v$bun/$zip.zip"
  got=$(sha256 "$tmp/bun.zip" | cut -d' ' -f1)
  if [ "$got" != "$bun_sha256" ]; then
    echo "build: $zip.zip checksum mismatch: got $got, want $bun_sha256" >&2
    rm -rf "$tmp"
    exit 1
  fi
  unzip -q "$tmp/bun.zip" -d "$tmp"
  mkdir -p "$bun_dir"
  mv "$tmp/$zip/bun$exe" "$bun_dir/bun$exe"
  rm -rf "$tmp"
fi
export PATH="$bun_dir:$PATH" BUN_INSTALL_CACHE_DIR="$HOME/.watterson/bun/cache"

cd "$here/opencode"
bun install --frozen-lockfile
cd packages/cli
OPENCODE_CHANNEL=watterson OPENCODE_VERSION=$version bun run script/build.ts --single --skip-web-ui --skip-install
mkdir -p "$here/bin"
cp dist/*/bin/opencode$exe "$here/bin/opencode$exe.new"
mv "$here/bin/opencode$exe.new" "$here/bin/opencode$exe"
echo "build: tui/bin/opencode$exe"

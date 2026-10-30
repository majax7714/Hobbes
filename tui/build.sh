#!/bin/sh
# Builds the TUI from our opencode code in tui/opencode (DEC-025, DEC-027)
# into tui/bin/opencode (opencode.exe on Windows). install.sh fetches Bun at the
# pinned version and checksum (build.env) and installs the workspace.
# Runs on Linux and macOS (x64, arm64), and on Windows under Git Bash.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
. "$here/install.sh"
cd packages/cli
OPENCODE_CHANNEL=watterson OPENCODE_VERSION=$version bun run script/build.ts --single --skip-web-ui --skip-install
mkdir -p "$here/bin"
cp dist/*/bin/opencode$exe "$here/bin/opencode$exe.new"
mv "$here/bin/opencode$exe.new" "$here/bin/opencode$exe"
echo "build: tui/bin/opencode$exe"

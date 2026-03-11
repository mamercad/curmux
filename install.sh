#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"

command -v python3 >/dev/null 2>&1 || { echo "python3 required"; exit 1; }
command -v tmux    >/dev/null 2>&1 || { echo "tmux required";    exit 1; }
command -v cursor-agent >/dev/null 2>&1 || echo "warning: cursor-agent CLI not found (needed at runtime)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="${SCRIPT_DIR}/curmux"

if [ ! -f "$SRC" ]; then
  echo "curmux not found in ${SCRIPT_DIR} — run from the repo root"
  exit 1
fi

# Bake version from git so installed copy shows correct version when run outside repo
V="$(
  cd "$SCRIPT_DIR"
  git describe --tags --exact-match 2>/dev/null | sed 's/^v//' \
  || git describe --tags 2>/dev/null | sed 's/^v//' \
  || echo "0.0.0-dev"
)"

if [ -w "$INSTALL_DIR" ]; then
  sed "s/^VERSION = .*/VERSION = \"$V\"  # fallback when not in git; release workflow and install.sh bake the tag/" "$SRC" > "${INSTALL_DIR}/curmux"
  chmod +x "${INSTALL_DIR}/curmux"
else
  sed "s/^VERSION = .*/VERSION = \"$V\"  # fallback when not in git; release workflow and install.sh bake the tag/" "$SRC" | sudo tee "${INSTALL_DIR}/curmux" >/dev/null
  sudo chmod +x "${INSTALL_DIR}/curmux"
fi

echo "curmux installed to ${INSTALL_DIR}/curmux"
echo "run: curmux --help"

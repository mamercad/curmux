#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"

command -v python3 >/dev/null 2>&1 || { echo "python3 required"; exit 1; }
command -v tmux    >/dev/null 2>&1 || { echo "tmux required";    exit 1; }
command -v cursor  >/dev/null 2>&1 || echo "warning: cursor CLI not found (needed at runtime)"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="${SCRIPT_DIR}/curmux"

if [ ! -f "$SRC" ]; then
  echo "curmux not found in ${SCRIPT_DIR} — run from the repo root"
  exit 1
fi

if [ -w "$INSTALL_DIR" ]; then
  cp "$SRC" "${INSTALL_DIR}/curmux"
  chmod +x "${INSTALL_DIR}/curmux"
else
  sudo cp "$SRC" "${INSTALL_DIR}/curmux"
  sudo chmod +x "${INSTALL_DIR}/curmux"
fi

echo "curmux installed to ${INSTALL_DIR}/curmux"
echo "run: curmux --help"

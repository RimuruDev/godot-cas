#!/usr/bin/env bash
# Linux entry point. All the real work lives in tools/cas.py.
#
#   ./update.sh                 build + install, then ask about publishing
#   ./update.sh --no-release    build + install only
#   ./update.sh --godot4 4.7.1  bump the Godot 4 compile target
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
	echo "python3 not found."
	echo "Install it with:  sudo apt install python3   (or your distro's equivalent)"
	exit 1
fi

exec python3 tools/cas.py update "$@"

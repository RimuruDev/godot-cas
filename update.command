#!/bin/bash
# Double-click this in Finder to update the CAS fork.
# All the real work lives in tools/cas.py — this only locates python3 and keeps
# the Terminal window open long enough to read the result.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
	echo "python3 not found."
	echo "Install it with:  brew install python"
	read -r -p "Press Enter to close..." _
	exit 1
fi

python3 tools/cas.py update "$@"
status=$?

echo
read -r -p "Press Enter to close..." _
exit $status

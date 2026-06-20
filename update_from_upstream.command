#!/bin/bash
# Update the Abyss Moth Godot CAS fork from damnedpie/godot-cas upstream.
#
# What it intentionally does:
# - fetch upstream/main;
# - copy upstream version metadata, adapters-list and Godot 4 gdap;
# - keep this fork's GodotCas.java / AndroidManifest.xml changes;
# - rebuild the Godot 4 AAR from local fork sources;
# - install the AAR and dependency versions into MurderDronesCatClicker addon.
#
# Requirements: git, python3, Android SDK, JDK 17-21.
set -euo pipefail

FORK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$FORK_DIR"

UPSTREAM_REMOTE="${GODOT_CAS_UPSTREAM_REMOTE:-upstream}"
UPSTREAM_URL="${GODOT_CAS_UPSTREAM_URL:-https://github.com/damnedpie/godot-cas.git}"
GAME_DIR="${MURDER_DRONES_CAT_CLICKER_DIR:-/Users/rimurutempest/RimuruDev/GodotProjects/MurderDronesCatClicker}"
ADDON_DIR="${GODOT_CAS_ADDON_DIR:-$GAME_DIR/addons/godot_cas/android}"

if ! git remote get-url "$UPSTREAM_REMOTE" >/dev/null 2>&1; then
  git remote add "$UPSTREAM_REMOTE" "$UPSTREAM_URL"
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "[CAS update] ERROR: godot-cas has uncommitted changes. Commit or stash them first."
  git status --short
  exit 1
fi

echo "[CAS update] Fetching $UPSTREAM_REMOTE/main..."
git fetch "$UPSTREAM_REMOTE" main:refs/remotes/"$UPSTREAM_REMOTE"/main --no-tags

UPSTREAM_REF="refs/remotes/$UPSTREAM_REMOTE/main"
VERSION="$(git show "$UPSTREAM_REF:build.gradle" | awk -F'"' '/pluginVersionName/ { print $2; exit }')"
REVISION="$(git show "$UPSTREAM_REF:build.gradle" | awk '/pluginVersionCode/ { print $3; exit }')"
GODOT_VERSION="$(git show "$UPSTREAM_REF:godot4/build.gradle" | awk -F'"' '/ext.godotVersion/ { print $2; exit }')"

if [[ -z "$VERSION" || -z "$REVISION" || -z "$GODOT_VERSION" ]]; then
  echo "[CAS update] ERROR: failed to parse upstream version metadata."
  exit 1
fi

echo "[CAS update] Upstream SDK=$VERSION rev=$REVISION Godot=$GODOT_VERSION"

python3 - "$VERSION" "$REVISION" "$GODOT_VERSION" <<'PY'
from pathlib import Path
import re
import sys

version, revision, godot_version = sys.argv[1:4]

def rewrite(path: str, replacements: list[tuple[str, str]]) -> None:
    file_path = Path(path)
    text = file_path.read_text()
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.M)
    file_path.write_text(text)

rewrite("build.gradle", [
    (r'ext\.pluginVersionName = "[^"]+"', f'ext.pluginVersionName = "{version}"'),
    (r'ext\.pluginVersionCode = \d+', f'ext.pluginVersionCode = {revision}'),
])

rewrite("godot4/build.gradle", [
    (r'ext\.godotVersion = "[^"]+"', f'ext.godotVersion = "{godot_version}"'),
    (
        r"compileOnly ['\"]com\.cleveradssolutions:cas-sdk:[^'\"]+['\"]",
        'compileOnly "com.cleveradssolutions:cas-sdk:${pluginVersionName}"',
    ),
])

rewrite("README.md", [
    (r'CAS \d+\.\d+\.\d+ tested only', f'CAS {version} tested only'),
    (r'Godot CAS \d+\.\d+\.\d+ \(Abyss Moth fork\)', f'Godot CAS {version} (Abyss Moth fork)'),
    (r'CAS\.AI_SDK_\d+\.\d+\.\d+', f'CAS.AI_SDK_{version}'),
    (r'CAS SDK \d+\.\d+\.\d+ Android plugin', f'CAS SDK {version} Android plugin'),
])

rewrite("README_RU.md", [
    (r'Godot CAS \d+\.\d+\.\d+ — форк Abyss Moth', f'Godot CAS {version} — форк Abyss Moth'),
    (r'CAS\.ai SDK \d+\.\d+\.\d+', f'CAS.ai SDK {version}'),
    (r'CAS SDK \d+\.\d+\.\d+', f'CAS SDK {version}'),
])
PY

git show "$UPSTREAM_REF:release/adapters-list.txt" > release/adapters-list.txt
git show "$UPSTREAM_REF:release/godot4/GodotCas.gdap" > release/godot4/GodotCas.gdap

echo "[CAS update] Rebuilding fork AAR..."
GODOT_CAS_ADDON_DIR="$ADDON_DIR" ./rebuild_aar.command

AAR_NAME="GodotCas.$VERSION.release.aar"
AAR_PATH="$ADDON_DIR/$AAR_NAME"
if [[ ! -f "$AAR_PATH" ]]; then
  echo "[CAS update] ERROR: expected addon AAR was not installed: $AAR_PATH"
  exit 1
fi

echo "[CAS update] Removing stale addon AAR files..."
find "$ADDON_DIR" -name 'GodotCas.*.release.aar' ! -name "$AAR_NAME" -delete

python3 - "$GAME_DIR" "$VERSION" "$AAR_NAME" "$FORK_DIR/release/adapters-list.txt" <<'PY'
from pathlib import Path
import re
import sys

game_dir = Path(sys.argv[1])
version = sys.argv[2]
aar_name = sys.argv[3]
adapters_path = Path(sys.argv[4])

plugin_path = game_dir / "addons/godot_cas/godot_cas_export_plugin.gd"
cfg_path = game_dir / "addons/godot_cas/plugin.cfg"
readme_path = game_dir / "addons/godot_cas/README_RU.md"

adapters = adapters_path.read_text()
match = re.search(r"OptimalAds dependencies:\s*\n(?P<body>.*?)(?:\n\n|$)", adapters, re.S)
if not match:
    raise SystemExit("Failed to parse OptimalAds dependencies from adapters-list.txt")

dependencies = re.findall(r'"([^"]+)"', match.group("body"))
cas_sdk = next((item for item in dependencies if item.startswith("com.cleveradssolutions:cas-sdk:")), "")
if not cas_sdk:
    raise SystemExit("Failed to find cas-sdk dependency in adapters-list.txt")

artifact_to_key = {
    "google": "google",
    "applovin": "applovin",
    "unity": "unity",
    "ironsource": "ironsource",
    "vungle": "vungle",
    "inmobi": "inmobi",
    "mintegral": "mintegral",
    "pangle": "pangle",
    "bigo": "bigo",
    "yango": "yango",
    "facebook": "facebook",
    "ysonetwork": "ysonetwork",
    "cas-exchange": "cas_exchange",
    "maticoo": "maticoo",
    "monetrix": "monetrix",
}
network_by_key = {}
for dependency in dependencies:
    parts = dependency.split(":")
    if len(parts) != 3 or parts[0] != "com.cleveradssolutions":
        continue
    key = artifact_to_key.get(parts[1])
    if key:
        network_by_key[key] = dependency

text = plugin_path.read_text()
text = re.sub(
    r'const RELEASE_AAR := "godot_cas/android/GodotCas\.[^"]+\.release\.aar"',
    f'const RELEASE_AAR := "godot_cas/android/{aar_name}"',
    text,
)
text = re.sub(
    r'GodotCas \d+\.\d+\.\d+',
    f'GodotCas {version}',
    text,
)
text = re.sub(
    r'"com\.cleveradssolutions:cas-sdk:[^"]+"',
    f'"{cas_sdk}"',
    text,
    count=1,
)
for key, dependency in network_by_key.items():
    text = re.sub(
        rf'"{re.escape(key)}": "com\.cleveradssolutions:[^"]+"',
        f'"{key}": "{dependency}"',
        text,
    )
plugin_path.write_text(text)

cfg = cfg_path.read_text()
cfg = re.sub(r'version="[^"]+"', f'version="{version}"', cfg)
cfg_path.write_text(cfg)

readme = readme_path.read_text()
readme = re.sub(r'CAS\.ai SDK \d+\.\d+\.\d+', f'CAS.ai SDK {version}', readme)
readme_path.write_text(readme)
PY

echo "[CAS update] Done."
echo "[CAS update] Review diffs:"
echo "  git -C \"$FORK_DIR\" diff --stat"
echo "  git -C \"$GAME_DIR\" diff --stat addons/godot_cas"

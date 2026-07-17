#!/usr/bin/env python3
"""Godot CAS (Abyss Moth fork) — build and release tool.

Subcommands:
    check      report versions and toolchain, change nothing
    update     pick the CAS SDK version, build both AARs, install into a game addon
    release    build the release zip, commit, tag, push, create the GitHub release

Platform launchers: update.command (macOS), update.sh (Linux), update.bat (Windows).

Version ownership — the rule this tool exists to enforce:
    pluginVersionName  follows CAS upstream (the mediation list, see below)
    pluginVersionCode  belongs to THIS fork; never copied from damnedpie/godot-cas
    godotVersion       belongs to THIS fork; never copied from damnedpie/godot-cas

The old update_from_upstream.command copied all three from upstream, which reset the
fork revision and reverted the Godot bump on every run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

FORK_DIR = Path(__file__).resolve().parents[1]

# CAS publishes adapter versions here; parseAdaptersList in build.gradle reads the same
# file, so this — not the GitHub release list — decides which SDK we can actually pin.
MEDIATION_LIST_URL = (
    "https://raw.githubusercontent.com/cleveradssolutions/CAS-Unity"
    "/refs/heads/master/Editor/BuildConfig/CASAndroidMediation.list"
)
CAS_RELEASES_API = "https://api.github.com/repos/cleveradssolutions/CAS-Android/releases"
GODOT_MAVEN_METADATA = "https://repo1.maven.org/maven2/org/godotengine/godot/maven-metadata.xml"
MAVEN_BASE = "https://repo1.maven.org/maven2"

# Gradle 8.7 refuses to run on JDK 22+.
JDK_MIN, JDK_MAX = 17, 21

REQUIRED_SDK_PACKAGES = ("platforms;android-35", "build-tools;35.0.0")
TAG_TEMPLATE = "v{name}-rev{code}"

# Everything a release commit may touch. `git add -A` would also sweep up whatever else
# happens to be dirty in the working tree, so stage this list instead.
RELEASE_PATHS = (
    ".gitignore",
    "README.md",
    "README_RU.md",
    "build.gradle",
    "settings.gradle",
    "gradle.properties",
    "proguard-rules.pro",
    "godot3",
    "godot4",
    "release",
    "tools",
    "update.command",
    "update.sh",
    "update.bat",
)

# Not an adapter, so it never appears in the mediation list, but the export needs it.
GDAP_EXTRA_DEPS = ("com.google.android.gms:play-services-ads-identifier:18.1.0",)

# Artifact id -> key used in the game addon's NETWORK_DEPENDENCIES dictionary.
ARTIFACT_TO_KEY = {
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


class CasError(Exception):
    """Anything that should stop the run with a readable message."""


# --------------------------------------------------------------------------- console


class Console:
    _CODES = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "cyan": "\033[36m",
    }

    def __init__(self) -> None:
        self.color = self._enable_color()
        self.rich = self._supports("▶")
        self.assume_yes = False

    @staticmethod
    def _enable_color() -> bool:
        if os.environ.get("NO_COLOR"):
            return False
        if not sys.stdout.isatty():
            return False
        if os.name == "nt":
            # Turn on ENABLE_VIRTUAL_TERMINAL_PROCESSING, otherwise cmd.exe prints raw escapes.
            try:
                import ctypes

                kernel32 = ctypes.windll.kernel32
                handle = kernel32.GetStdHandle(-11)
                mode = ctypes.c_uint32()
                if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    return False
                return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
            except Exception:
                return False
        return True

    @staticmethod
    def _supports(text: str) -> bool:
        try:
            text.encode(sys.stdout.encoding or "ascii")
            return True
        except (UnicodeEncodeError, LookupError):
            return False

    def paint(self, text: str, *styles: str) -> str:
        if not self.color:
            return text
        prefix = "".join(self._CODES[s] for s in styles)
        return f"{prefix}{text}{self._CODES['reset']}"

    def _mark(self, rich: str, plain: str) -> str:
        return rich if self.rich else plain

    def step(self, text: str) -> None:
        print(f"\n{self.paint(self._mark('▶', '>'), 'cyan', 'bold')} {self.paint(text, 'bold')}")

    def ok(self, text: str) -> None:
        print(f"  {self.paint(self._mark('✓', '+'), 'green')} {text}")

    def warn(self, text: str) -> None:
        print(f"  {self.paint(self._mark('!', '!'), 'yellow', 'bold')} {self.paint(text, 'yellow')}")

    def fail(self, text: str) -> None:
        print(f"  {self.paint(self._mark('✗', 'x'), 'red', 'bold')} {self.paint(text, 'red')}")

    def info(self, text: str) -> None:
        print(f"    {self.paint(text, 'dim')}")

    def value(self, label: str, value: str, *styles: str) -> None:
        print(f"  {label:<24} {self.paint(value, *(styles or ('bold',)))}")

    def confirm(self, question: str, default: bool = False) -> bool:
        if self.assume_yes:
            print(f"  {self.paint('?', 'blue', 'bold')} {question} {self.paint('yes (--yes)', 'dim')}")
            return True
        if not sys.stdin.isatty():
            return default
        suffix = "[Y/n]" if default else "[y/N]"
        prompt = f"  {self.paint('?', 'blue', 'bold')} {question} {self.paint(suffix, 'dim')} "
        while True:
            try:
                answer = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return False
            if not answer:
                return default
            if answer in ("y", "yes", "д", "да"):
                return True
            if answer in ("n", "no", "н", "нет"):
                return False


con = Console()


# ----------------------------------------------------------------------------- utils


def version_key(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", text))


def run(
    args: list[str],
    *,
    cwd: Path = FORK_DIR,
    env: dict[str, str] | None = None,
    capture: bool = True,
    check: bool = True,
) -> str:
    result = subprocess.run(
        args,
        cwd=str(cwd),
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )
    if check and result.returncode != 0:
        detail = (result.stdout or "").strip()
        raise CasError(
            f"command failed ({result.returncode}): {' '.join(args)}"
            + (f"\n{detail}" if detail else "")
        )
    return (result.stdout or "").strip()


def http_get(url: str, *, headers: dict[str, str] | None = None, timeout: int = 30) -> bytes:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        raise CasError(f"HTTP {error.code} for {url}") from error
    except urllib.error.URLError as error:
        raise CasError(f"network error for {url}: {error.reason}") from error


def maven_exists(group: str, artifact: str, version: str) -> bool:
    path = group.replace(".", "/")
    url = f"{MAVEN_BASE}/{path}/{artifact}/{version}/{artifact}-{version}.pom"
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False


# ------------------------------------------------------------------ repo metadata io


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _sub_once(pattern: str, replacement: str, text: str, *, what: str) -> str:
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.M)
    if count == 0:
        raise CasError(f"could not find {what} — the file layout changed, refusing to guess")
    return new_text


def read_plugin_version() -> tuple[str, int]:
    text = read_text(FORK_DIR / "build.gradle")
    name = re.search(r'ext\.pluginVersionName\s*=\s*"([^"]+)"', text)
    code = re.search(r"ext\.pluginVersionCode\s*=\s*(\d+)", text)
    if not name or not code:
        raise CasError("build.gradle: pluginVersionName/pluginVersionCode not found")
    return name.group(1), int(code.group(1))


def write_plugin_version(name: str, code: int) -> None:
    path = FORK_DIR / "build.gradle"
    text = read_text(path)
    text = _sub_once(
        r'ext\.pluginVersionName\s*=\s*"[^"]+"',
        f'ext.pluginVersionName = "{name}"',
        text,
        what="pluginVersionName",
    )
    text = _sub_once(
        r"ext\.pluginVersionCode\s*=\s*\d+",
        f"ext.pluginVersionCode = {code}",
        text,
        what="pluginVersionCode",
    )
    write_text(path, text)


def read_godot_version(module: str) -> str:
    text = read_text(FORK_DIR / module / "build.gradle")
    match = re.search(r'ext\.godotVersion\s*=\s*"([^"]+)"', text)
    if not match:
        raise CasError(f"{module}/build.gradle: ext.godotVersion not found")
    return match.group(1)


def write_godot_version(module: str, version: str) -> None:
    path = FORK_DIR / module / "build.gradle"
    text = _sub_once(
        r'ext\.godotVersion\s*=\s*"[^"]+"',
        f'ext.godotVersion = "{version}"',
        read_text(path),
        what=f"{module} ext.godotVersion",
    )
    write_text(path, text)


# ------------------------------------------------------------- upstream version data


def cas_version_from_mediation_list() -> tuple[str, dict[str, str], list[str]]:
    """Return (sdk_version, {artifact: coordinate}, repositories) from CAS's live list."""
    data = json.loads(http_get(MEDIATION_LIST_URL).decode("utf-8"))
    version = data["version"]

    optimal = next((f for f in data.get("simple", []) if f.get("name") == "OptimalAds"), None)
    if optimal is None:
        raise CasError("mediation list has no OptimalAds filter — CAS changed the format")

    included = set(optimal.get("contains", []))
    dependencies: dict[str, str] = {"cas-sdk": f"com.cleveradssolutions:cas-sdk:{version}"}
    repositories: list[str] = []
    for adapter in data.get("adapters", []):
        if adapter.get("id") not in included:
            continue
        lib = adapter["libs"][0]
        coordinate = f"{lib['name']}{lib['version']}"
        artifact = coordinate.split(":")[1] if coordinate.count(":") >= 2 else coordinate
        dependencies[artifact] = coordinate
        source = adapter.get("source")
        if source and source not in repositories:
            repositories.append(source)
    return version, dependencies, repositories


def _first_stable_tag(releases: list[dict]) -> str | None:
    for release in releases:
        if not release.get("prerelease") and not release.get("draft"):
            return release.get("tag_name")
    return None


def cas_latest_stable_on_github() -> str | None:
    """Latest non-prerelease CAS-Android tag, or None if it could not be determined.

    Anonymous GitHub API calls are capped at 60/hour per IP and that budget is routinely
    already spent, so prefer the authenticated `gh` CLI when it is available.
    """
    if shutil.which("gh"):
        try:
            payload = run(["gh", "api", "repos/cleveradssolutions/CAS-Android/releases"])
            return _first_stable_tag(json.loads(payload))
        except (CasError, json.JSONDecodeError):
            pass  # fall through to a plain HTTP call

    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        return _first_stable_tag(json.loads(http_get(CAS_RELEASES_API, headers=headers).decode("utf-8")))
    except (CasError, json.JSONDecodeError) as error:
        con.warn(f"could not read CAS-Android releases ({error})")
        con.info("skipping the mediation-list cross-check; `gh auth login` raises the rate limit")
        return None


def godot_latest_stable() -> str | None:
    try:
        metadata = http_get(GODOT_MAVEN_METADATA).decode("utf-8")
    except CasError as error:
        con.warn(f"could not read Godot versions from Maven Central ({error})")
        return None
    match = re.search(r"<release>([^<]+)</release>", metadata)
    return match.group(1).replace(".stable", "") if match else None


# ------------------------------------------------------------------------- toolchain


def _jdk_version(home: Path) -> int | None:
    release = home / "release"
    if release.is_file():
        match = re.search(r'JAVA_VERSION="(\d+)', release.read_text(encoding="utf-8", errors="ignore"))
        if match:
            return int(match.group(1))
    binary = home / "bin" / ("java.exe" if os.name == "nt" else "java")
    if not binary.is_file():
        return None
    try:
        output = subprocess.run(
            [str(binary), "-version"], capture_output=True, text=True, timeout=20
        )
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r'version "(\d+)', (output.stderr or "") + (output.stdout or ""))
    return int(match.group(1)) if match else None


def _jdk_candidates() -> list[Path]:
    candidates: list[Path] = []
    for name in ("JAVA_HOME", "JDK_HOME"):
        value = os.environ.get(name)
        if value:
            candidates.append(Path(value))

    if sys.platform == "darwin":
        helper = Path("/usr/libexec/java_home")
        if helper.is_file():
            for major in range(JDK_MAX, JDK_MIN - 1, -1):
                try:
                    found = subprocess.run(
                        [str(helper), "-v", str(major)], capture_output=True, text=True, timeout=20
                    )
                except (OSError, subprocess.SubprocessError):
                    continue
                if found.returncode == 0 and found.stdout.strip():
                    candidates.append(Path(found.stdout.strip()))
    elif os.name == "nt":
        for root in (r"C:\Program Files\Java", r"C:\Program Files\Eclipse Adoptium",
                     r"C:\Program Files\Microsoft\jdk", r"C:\Program Files\Android\Android Studio\jbr"):
            base = Path(root)
            if base.is_dir():
                candidates.extend(child for child in base.iterdir() if child.is_dir())
                candidates.append(base)
    else:
        for root in ("/usr/lib/jvm", "/usr/java", str(Path.home() / ".sdkman/candidates/java")):
            base = Path(root)
            if base.is_dir():
                candidates.extend(child for child in base.iterdir() if child.is_dir())

    java_on_path = shutil.which("java")
    if java_on_path:
        candidates.append(Path(java_on_path).resolve().parent.parent)
    return candidates


def find_jdk() -> Path:
    seen: set[Path] = set()
    best: tuple[int, Path] | None = None
    for candidate in _jdk_candidates():
        if not candidate.is_dir() or candidate in seen:
            continue
        seen.add(candidate)
        major = _jdk_version(candidate)
        if major is None or not (JDK_MIN <= major <= JDK_MAX):
            continue
        # Prefer the newest JDK inside the supported window.
        if best is None or major > best[0]:
            best = (major, candidate)
    if best is None:
        raise CasError(
            f"no JDK {JDK_MIN}-{JDK_MAX} found (Gradle 8.7 will not run on JDK 22+).\n"
            "    Install Temurin 21: https://adoptium.net/temurin/releases/?version=21\n"
            "    macOS: brew install --cask temurin@21 | Linux: sdk install java 21-tem\n"
            "    Then re-run, or set JAVA_HOME to that JDK."
        )
    con.info(f"JDK {best[0]} at {best[1]}")
    return best[1]


def default_sdk_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Android/sdk"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Android/Sdk"
    return Path.home() / "Android/Sdk"


def _sdkmanager(sdk_root: Path) -> Path | None:
    suffix = ".bat" if os.name == "nt" else ""
    for relative in ("cmdline-tools/latest/bin", "cmdline-tools/bin", "tools/bin"):
        candidate = sdk_root / relative / f"sdkmanager{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _missing_packages(sdk_root: Path) -> list[str]:
    missing = []
    for package in REQUIRED_SDK_PACKAGES:
        relative = package.replace(";", "/")
        if not (sdk_root / relative).is_dir():
            missing.append(package)
    return missing


def find_android_sdk(*, jdk: Path) -> Path:
    for name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        value = os.environ.get(name)
        if value and Path(value).is_dir():
            sdk_root = Path(value)
            break
    else:
        sdk_root = default_sdk_root()

    if not sdk_root.is_dir():
        raise CasError(
            f"Android SDK not found at {sdk_root}.\n"
            "    Install Android Studio (https://developer.android.com/studio) or the\n"
            "    command line tools, then set ANDROID_HOME and re-run."
        )

    missing = _missing_packages(sdk_root)
    if missing:
        con.warn(f"Android SDK is missing: {', '.join(missing)}")
        manager = _sdkmanager(sdk_root)
        if manager is None:
            raise CasError(
                f"sdkmanager not found under {sdk_root}/cmdline-tools.\n"
                "    Install it via Android Studio > SDK Manager > SDK Tools >\n"
                '    "Android SDK Command-line Tools", then re-run.'
            )
        if not con.confirm(f"Install {len(missing)} missing SDK package(s) now?", default=True):
            raise CasError("missing Android SDK packages; cannot build")
        env = dict(os.environ, JAVA_HOME=str(jdk), ANDROID_HOME=str(sdk_root))
        con.info(f"running {manager.name} {' '.join(missing)}")
        run([str(manager), f"--sdk_root={sdk_root}", *missing], env=env, capture=False)
        still_missing = _missing_packages(sdk_root)
        if still_missing:
            raise CasError(f"still missing after install: {', '.join(still_missing)}")
        con.ok("SDK packages installed")

    con.info(f"Android SDK at {sdk_root}")
    return sdk_root


def build_env(jdk: Path, sdk_root: Path) -> dict[str, str]:
    return dict(os.environ, JAVA_HOME=str(jdk), ANDROID_HOME=str(sdk_root), ANDROID_SDK_ROOT=str(sdk_root))


def gradle(args: list[str], env: dict[str, str], *, capture: bool = True) -> str:
    wrapper = FORK_DIR / ("gradlew.bat" if os.name == "nt" else "gradlew")
    if not wrapper.is_file():
        raise CasError(f"gradle wrapper not found: {wrapper}")
    if os.name != "nt" and not os.access(wrapper, os.X_OK):
        wrapper.chmod(0o755)
    command = [str(wrapper) if os.name == "nt" else f"./{wrapper.name}", *args, "--no-daemon"]
    return run(command, env=env, capture=capture)


# ---------------------------------------------------------------------- gdap writing


def render_gdap(*, aar_name: str, dependencies: list[str], repositories: list[str]) -> str:
    remote = "".join(f'\t"{item}",\n' for item in dependencies)
    repos = "".join(f'\t"{item}",\n' for item in repositories)
    return (
        "[config]\n\n"
        'name="GodotCas"\n'
        'binary_type="local"\n'
        f'binary="{aar_name}"\n\n'
        "[dependencies]\n\n"
        f"remote=[\n{remote}\t]\n\n"
        f"custom_maven_repos=[\n{repos}]\n"
    )


def write_gdaps(version: str, dependencies: dict[str, str], repositories: list[str]) -> None:
    ordered = [*GDAP_EXTRA_DEPS, *dependencies.values()]
    aar_name = f"GodotCas.{version}.release.aar"
    for module in ("godot3", "godot4"):
        target = FORK_DIR / "release" / module / "GodotCas.gdap"
        if not target.parent.is_dir():
            continue
        write_text(target, render_gdap(aar_name=aar_name, dependencies=ordered, repositories=repositories))
        con.ok(f"{module}/GodotCas.gdap -> {aar_name}, {len(ordered)} deps")


# --------------------------------------------------------------------- addon install


def resolve_addon_dir(explicit: str | None) -> Path | None:
    """Find the game addon to install into. Never hardcode a personal path here."""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_dir():
            raise CasError(f"--addon-dir does not exist: {path}")
        return path

    env_value = os.environ.get("GODOT_CAS_ADDON_DIR")
    if env_value:
        path = Path(env_value).expanduser()
        if not path.is_dir():
            raise CasError(f"GODOT_CAS_ADDON_DIR does not exist: {path}")
        return path

    local_config = FORK_DIR / "cas.local.json"
    if local_config.is_file():
        try:
            configured = json.loads(read_text(local_config)).get("addon_dir")
        except json.JSONDecodeError as error:
            raise CasError(f"cas.local.json is not valid JSON: {error}") from error
        if configured:
            path = Path(configured).expanduser()
            if not path.is_dir():
                raise CasError(f"cas.local.json addon_dir does not exist: {path}")
            return path

    # Skip the copy that ships inside this repo (addons/godot_cas is the
    # distributable addon consumed via abyss-moth-kit): it is a build output,
    # not somebody's game, and would otherwise show up as a phantom candidate.
    matches = sorted(
        match
        for match in FORK_DIR.parent.glob("*/addons/godot_cas/android")
        if FORK_DIR not in match.parents
    )
    if len(matches) == 1:
        con.info(f"auto-detected addon: {matches[0]}")
        return matches[0]
    if len(matches) > 1:
        con.warn(f"{len(matches)} candidate addons found; set addon_dir in cas.local.json")
    return None


def install_into_addon(addon_dir: Path, aar_source: Path) -> None:
    target = addon_dir / aar_source.name
    shutil.copyfile(aar_source, target)
    con.ok(f"installed {aar_source.name} -> {addon_dir}")
    for stale in addon_dir.glob("GodotCas.*.release.aar"):
        if stale.name != aar_source.name:
            stale.unlink()
            con.info(f"removed stale {stale.name}")


def update_game_addon(addon_dir: Path, version: str, aar_name: str, dependencies: dict[str, str]) -> None:
    """Rewrite the consuming project's export plugin so its pins match the AAR."""
    root = addon_dir.parent  # addons/godot_cas
    plugin_gd = root / "godot_cas_export_plugin.gd"
    if plugin_gd.is_file():
        text = read_text(plugin_gd)
        text = re.sub(
            r'const RELEASE_AAR := "godot_cas/android/GodotCas\.[^"]+\.release\.aar"',
            f'const RELEASE_AAR := "godot_cas/android/{aar_name}"',
            text,
        )
        text = re.sub(r"GodotCas \d+\.\d+\.\d+", f"GodotCas {version}", text)
        cas_sdk = dependencies.get("cas-sdk")
        if cas_sdk:
            text = re.sub(r'"com\.cleveradssolutions:cas-sdk:[^"]+"', f'"{cas_sdk}"', text, count=1)
        for artifact, coordinate in dependencies.items():
            key = ARTIFACT_TO_KEY.get(artifact)
            if key:
                text = re.sub(
                    rf'"{re.escape(key)}": "com\.cleveradssolutions:[^"]+"',
                    f'"{key}": "{coordinate}"',
                    text,
                )
        write_text(plugin_gd, text)
        con.ok(f"updated {plugin_gd.name}")

    plugin_cfg = root / "plugin.cfg"
    if plugin_cfg.is_file():
        write_text(plugin_cfg, re.sub(r'version="[^"]+"', f'version="{version}"', read_text(plugin_cfg)))
        con.ok(f"updated {plugin_cfg.name}")

    readme = root / "README_RU.md"
    if readme.is_file():
        write_text(readme, re.sub(r"CAS\.ai SDK \d+\.\d+\.\d+", f"CAS.ai SDK {version}", read_text(readme)))
        con.ok(f"updated {readme.name}")


# ------------------------------------------------------------------------- git / gh


def git(args: list[str], *, check: bool = True) -> str:
    return run(["git", *args], check=check)


def stage_release_paths() -> str:
    """Stage only what this tool owns, so unrelated edits stay out of the release commit."""
    existing = [name for name in RELEASE_PATHS if (FORK_DIR / name).exists()]
    git(["add", "--", *existing])
    return git(["diff", "--cached", "--stat"])


def gh_available() -> bool:
    if not shutil.which("gh"):
        return False
    return subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0


# -------------------------------------------------------------------------- commands


def report_versions() -> dict:
    con.step("Versions")
    name, code = read_plugin_version()
    con.value("fork CAS SDK", name)
    con.value("fork revision", str(code))
    for module in ("godot3", "godot4"):
        if (FORK_DIR / module / "build.gradle").is_file():
            con.value(f"{module} builds against", read_godot_version(module))

    list_version, dependencies, repositories = cas_version_from_mediation_list()
    con.value("CAS mediation list", list_version, "cyan")

    github_version = cas_latest_stable_on_github()
    if github_version:
        con.value("CAS latest stable (GH)", github_version, "cyan")
        if version_key(github_version) > version_key(list_version):
            con.warn(
                f"CAS-Android published {github_version} but the mediation list still pins "
                f"{list_version}. Adapter versions are keyed to the list, so pinning "
                f"{github_version} now would mismatch them. Waiting is correct."
            )

    godot_stable = godot_latest_stable()
    if godot_stable:
        con.value("Godot latest stable", godot_stable, "cyan")
        current_godot = read_godot_version("godot4")
        if version_key(godot_stable) > version_key(current_godot):
            con.warn(
                f"Godot {godot_stable} is out; godot4 builds against {current_godot}. "
                f"Bump deliberately with: update --godot4 {godot_stable}"
            )

    return {
        "name": name,
        "code": code,
        "list_version": list_version,
        "dependencies": dependencies,
        "repositories": repositories,
        "github_version": github_version,
    }


def cmd_check(args: argparse.Namespace) -> int:
    state = report_versions()
    con.step("Toolchain")
    try:
        jdk = find_jdk()
        find_android_sdk(jdk=jdk)
        con.ok("toolchain is ready")
    except CasError as error:
        con.fail(str(error))
    con.step("Target")
    target = state["list_version"]
    if version_key(target) > version_key(state["name"]):
        con.value("would move to", f"CAS {target} rev 1", "green")
    else:
        con.value("would rebuild", f"CAS {state['name']} rev {state['code']}", "green")
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    state = report_versions()
    current_name, current_code = state["name"], state["code"]
    target_name = args.cas or state["list_version"]

    con.step("Toolchain")
    jdk = find_jdk()
    sdk_root = find_android_sdk(jdk=jdk)
    env = build_env(jdk, sdk_root)

    con.step("Plan")
    if version_key(target_name) > version_key(current_name):
        # A new SDK line restarts the fork revision, mirroring upstream's convention.
        target_code = 1
        con.value("CAS SDK", f"{current_name} -> {target_name}", "green")
    elif version_key(target_name) < version_key(current_name):
        # Only reachable via --cas: the mediation list never moves backwards on its own.
        target_code = 1
        con.warn(f"downgrading CAS {current_name} -> {target_name} (requested via --cas)")
        if not con.confirm("Really pin the older SDK?", default=False):
            raise CasError("aborted")
    else:
        target_code = current_code
        con.value("CAS SDK", f"{target_name} (unchanged)")
    con.value("fork revision", str(target_code))

    if not maven_exists("com.cleveradssolutions", "cas-sdk", target_name):
        raise CasError(f"com.cleveradssolutions:cas-sdk:{target_name} is not on Maven Central yet")
    con.ok(f"cas-sdk:{target_name} resolves on Maven Central")

    for module, requested in (("godot3", args.godot3), ("godot4", args.godot4)):
        if not (FORK_DIR / module / "build.gradle").is_file():
            continue
        if requested:
            if not maven_exists("org.godotengine", "godot", f"{requested}.stable"):
                raise CasError(f"org.godotengine:godot:{requested}.stable is not on Maven Central")
            write_godot_version(module, requested)
            con.value(f"{module} godot", f"-> {requested}", "green")
        else:
            con.value(f"{module} godot", read_godot_version(module))

    if target_name != current_name or target_code != current_code:
        write_plugin_version(target_name, target_code)

    con.step("Generating .gdap from the CAS mediation list")
    write_gdaps(target_name, state["dependencies"], state["repositories"])

    con.step("Building AARs (this takes a few minutes)")
    modules = [f":{m}:assembleRelease" for m in ("godot3", "godot4") if (FORK_DIR / m).is_dir()]
    gradle([*modules, "parseAdaptersList"], env, capture=False)

    con.step("Collecting artifacts")
    aar_name = f"GodotCas.{target_name}.release.aar"
    built: dict[str, Path] = {}
    for module in ("godot3", "godot4"):
        source = FORK_DIR / module / "build/outputs/aar" / aar_name
        if not source.is_file():
            raise CasError(f"expected AAR was not produced: {source}")
        destination = FORK_DIR / "release" / module / aar_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        built[module] = destination
        con.ok(f"{module}: {destination.relative_to(FORK_DIR)}")
        for stale in destination.parent.glob("GodotCas.*.release.aar"):
            if stale.name != aar_name:
                stale.unlink()
                con.info(f"removed stale {stale.name}")

    con.step("Installing into the game addon")
    addon_dir = resolve_addon_dir(args.addon_dir)
    if addon_dir is None:
        con.warn("no addon directory configured — skipping install")
        con.info('set one via cas.local.json: {"addon_dir": "/path/to/game/addons/godot_cas/android"}')
    else:
        install_into_addon(addon_dir, built["godot4"])
        update_game_addon(addon_dir, target_name, aar_name, state["dependencies"])

    # The addon shipped from this repo is what abyss-moth-kit installs for the
    # rest of the studio. Refresh it from the same build, otherwise it silently
    # keeps serving whatever AAR happened to be committed last.
    repo_addon_dir = FORK_DIR / "addons" / "godot_cas" / "android"
    if repo_addon_dir.is_dir():
        con.step("Refreshing the distributable addon in this repo")
        install_into_addon(repo_addon_dir, built["godot4"])
        update_game_addon(repo_addon_dir, target_name, aar_name, state["dependencies"])

    con.step("Done")
    con.ok(f"CAS {target_name} rev {target_code} built and installed")

    if args.no_release:
        return 0
    print()
    if not con.confirm(f"Publish {TAG_TEMPLATE.format(name=target_name, code=target_code)} to GitHub?", default=False):
        con.info("skipped; run `release` later to publish")
        return 0
    return do_release(env, target_name, target_code, bump=version_key(target_name) == version_key(current_name))


def do_release(env: dict[str, str], name: str, code: int, *, bump: bool) -> int:
    if bump:
        code += 1
        con.step(f"Bumping fork revision -> {code}")
        write_plugin_version(name, code)

    tag = TAG_TEMPLATE.format(name=name, code=code)
    if git(["tag", "-l", tag]).strip():
        raise CasError(f"tag {tag} already exists — bump the revision or delete the tag")

    con.step("Building release zip")
    gradle(["buildGithubRelease"], env, capture=False)
    zip_path = FORK_DIR / "release" / f"godot-cas-{name}-rev{code}.zip"
    if not zip_path.is_file():
        raise CasError(f"release zip was not produced: {zip_path}")
    con.ok(f"{zip_path.name} ({zip_path.stat().st_size // 1024} KiB)")

    con.step("Committing")
    staged = stage_release_paths()
    if not staged.strip():
        con.warn("nothing to commit")
    else:
        print(staged)
        message = f"CAS SDK {name} rev.{code}\n\nGodot 4: {read_godot_version('godot4')}"
        if (FORK_DIR / "godot3/build.gradle").is_file():
            message += f"\nGodot 3: {read_godot_version('godot3')}"
        git(["commit", "-m", message])
        con.ok("committed")

    git(["tag", "-a", tag, "-m", f"CAS SDK {name} rev.{code}"])
    con.ok(f"tagged {tag}")

    branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
    if not con.confirm(f"Push {branch} and {tag} to origin, then create the GitHub release?", default=False):
        con.warn("stopped before push — local commit and tag are in place")
        con.info(f"to undo: git -C {FORK_DIR} tag -d {tag} && git -C {FORK_DIR} reset --hard HEAD~1")
        return 0

    con.step("Pushing")
    git(["push", "origin", branch])
    git(["push", "origin", tag])
    con.ok("pushed")

    if not gh_available():
        con.warn("gh CLI not available/authenticated — create the release manually")
        con.info(f"gh release create {tag} {zip_path} --title 'CAS SDK {name} rev.{code}'")
        return 0

    con.step("Creating the GitHub release")
    notes = render_release_notes(name, code)
    run(["gh", "release", "create", tag, str(zip_path), "--title", f"CAS SDK {name} rev.{code}", "--notes", notes])
    con.ok(f"released {tag}")
    return 0


def render_release_notes(name: str, code: int) -> str:
    lines = [
        f"CAS.ai SDK **{name}**, fork revision **{code}**.",
        "",
        "Built against:",
        f"- Godot 4: `org.godotengine:godot:{read_godot_version('godot4')}.stable`",
    ]
    if (FORK_DIR / "godot3/build.gradle").is_file():
        lines.append(f"- Godot 3: `org.godotengine:godot:{read_godot_version('godot3')}.stable`")
    lines += [
        "",
        "Differences from [damnedpie/godot-cas](https://github.com/damnedpie/godot-cas):",
        "- `isVpnActive()` — reports whether any active network uses a VPN transport.",
        "- `AD_ID` permission is declared instead of removed (ads need the advertising id).",
        "- `ACCESS_COARSE_LOCATION` / `READ_PHONE_STATE` stay removed.",
        "",
        "Unofficial fork, maintained for Abyss Moth projects. Use at your own risk.",
    ]
    return "\n".join(lines)


def cmd_release(args: argparse.Namespace) -> int:
    con.step("Toolchain")
    jdk = find_jdk()
    sdk_root = find_android_sdk(jdk=jdk)
    env = build_env(jdk, sdk_root)
    name, code = read_plugin_version()
    return do_release(env, name, code, bump=args.bump)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cas",
        description="Build and release the Abyss Moth godot-cas fork.",
    )
    parser.add_argument("--yes", action="store_true", help="answer every prompt with yes")
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="report versions and toolchain, change nothing")
    check.set_defaults(func=cmd_check)

    update = subparsers.add_parser("update", help="build both AARs and install into the addon")
    update.add_argument("--cas", help="force a CAS SDK version instead of the mediation list one")
    update.add_argument("--godot4", help="bump the Godot 4 compile target, e.g. 4.7.1")
    update.add_argument("--godot3", help="bump the Godot 3 compile target, e.g. 3.6.2")
    update.add_argument("--addon-dir", help="game addons/godot_cas/android directory")
    update.add_argument("--no-release", action="store_true", help="never prompt to publish")
    update.set_defaults(func=cmd_update)

    release = subparsers.add_parser("release", help="commit, tag, push and publish")
    release.add_argument("--bump", action="store_true", help="increment the fork revision first")
    release.set_defaults(func=cmd_release)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args([*(argv or []), "update"])
    con.assume_yes = args.yes

    try:
        return args.func(args)
    except CasError as error:
        con.fail(str(error))
        return 1
    except KeyboardInterrupt:
        print()
        con.warn("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())

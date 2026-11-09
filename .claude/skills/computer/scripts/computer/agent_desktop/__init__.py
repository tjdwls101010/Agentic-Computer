"""Everything that depends on agent-desktop, a program this skill does not own: the pinned release, where it lives, how it is called, and how to read its output and help text."""
import fcntl
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import stat
import subprocess
import tarfile
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

VERSION = "1.2.0"
BINARY = "agent-desktop"
HELPER = "agent-desktop-macos-helper"
DEFAULT_RELEASE_BASE_URL = f"https://github.com/vercel-labs/agent-desktop/releases/download/v{VERSION}"
ASSETS = {
    "aarch64": {
        "archive": "219813428bb1ad8decae172faed05c5964a2415170df402e2786ccfa6452ba82",
        BINARY: "dec75e0bba0d1f9b589bdb88188770ad1a199cde9e02cf0a5b94175491f738e9",
        HELPER: "4a795a40ba7fc93b726b0834342f0225779c30d83e28f1f219db479860c38a78",
    },
    "x86_64": {
        "archive": "d9dc50226f28d7fc86a2f5b0945f0c206dff6c31e418907749f493b6f9e773e6",
        BINARY: "5dae755fee4af37d1a245f058139b262d358352cce15aeb49d0100ff46b12156",
        HELPER: "bdf060658b93f326efa06ac24d521e88025bf88109cecc257fa7fa40e65801cd",
    },
}
_MACHINE_TO_ARCH = {"arm64": "aarch64", "aarch64": "aarch64", "x86_64": "x86_64"}
_REFUSED_FLAGS = ("--trace", "--trace-strict", "--debug", "--screenshot")
_GUIDANCE = re.compile(r"For AI agents, read this first:.*?always match this exact version\.\s*", re.S)
_USAGE_CALL = re.compile(r"^Usage: agent-desktop(?= |$)", re.M)
_EXAMPLE_CALL = re.compile(r"^(\s+)agent-desktop ", re.M)
_SUGGESTION = re.compile(r'("suggestion"\s*:\s*")((?:[^"\\]|\\.)*)(")')
# 성진: suggestion 안의 호출은 "Run agent-desktop …"과 "agent-desktop permissions …"만 있어서(1.2.0 소스 전수) 이 둘만 바꾼다. 판을 올릴 때 다른 호출 문구가 생기면 넓힌다.
_SUGGESTION_CALL = re.compile(r"(?<=Run )agent-desktop |agent-desktop (?=permissions\b)")


class NotInstalled(Exception):
    """The pinned binary or its helper is not at the install location."""


class InstallError(Exception):
    """A release could not be downloaded, verified or published."""


@dataclass
class Result:
    stdout: str
    exit_code: int
    envelope: dict | None


def refused_flag(argv):
    """Return the first argument before `--` that names a debug flag writing to an arbitrary path, or None."""
    for token in argv:
        if token == "--":
            return None
        if token.split("=", 1)[0] in _REFUSED_FLAGS:
            return token
    return None


def run(argv, cli_call=""):
    """Run the pinned binary with argv unchanged; stdin and stderr are inherited, stdout is captured."""
    install_dir = _final_dir()
    if not all((install_dir / name).exists() for name in (BINARY, HELPER)):
        raise NotInstalled(str(install_dir))
    completed = subprocess.run([str(install_dir / BINARY), *argv], stdout=subprocess.PIPE)
    stdout = completed.stdout.decode("utf-8", "surrogateescape")
    if cli_call:
        stdout = _rewrite_suggestions(stdout, cli_call)
    return Result(stdout, completed.returncode, _parse_envelope(stdout))


def help_kind(stdout):
    """Say whether stdout is the binary's help: "top", "command", or None for anything else."""
    if stdout.lstrip().startswith("{"):
        return None
    first_usage = _USAGE_CALL.search(stdout)
    if first_usage is None:
        return None
    return "top" if "Usage: agent-desktop [OPTIONS] [COMMAND]" in stdout else "command"


def present_help(stdout, cli_call):
    """Drop the upstream reading guidance and make every example call go through this skill's entry point."""
    text = _GUIDANCE.sub("", stdout, count=1)
    text = _USAGE_CALL.sub(f"Usage: {cli_call}", text)
    return _EXAMPLE_CALL.sub(lambda match: f"{match.group(1)}{cli_call} ", text)


def install():
    """Install the pinned release if it is not already there. Returns True when something changed."""
    parent = _install_parent()
    parent.mkdir(parents=True, exist_ok=True)
    final = _final_dir()
    asset = _asset()
    with _install_lock(parent):
        _remove_leftovers(parent)
        if _is_verified(final, asset):
            return False
        _quarantine(final, parent)
        staging = parent / f".staging-{secrets.token_hex(4)}"
        try:
            staging.mkdir()
            _fetch_release(staging, asset)
            os.rename(staging, final)
        finally:
            _remove(staging)
        _remove_leftovers(parent)
    return True


def status():
    """Report the install location and whether the binary, helper and hashes are as pinned."""
    final = _final_dir()
    report = {
        "install_dir": str(final),
        "expected_version": VERSION,
        "binary_present": (final / BINARY).exists(),
        "helper_present": (final / HELPER).exists(),
    }
    report["hashes_match"] = _is_verified(final, _asset())
    if report["binary_present"]:
        version = _ask_engine(final, "version")
        report["version"] = (version or {}).get("version")
        permissions = _ask_engine(final, "permissions") or {}
        for name in ("accessibility", "screen_recording"):
            report[name] = (permissions.get(name) or {}).get("state")
    return report


def _install_parent():
    configured = os.environ.get("COMPUTER_INSTALL_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".cache/computer"


def _final_dir():
    return _install_parent() / f"agent-desktop-{VERSION}"


def _asset():
    machine = platform.machine()
    arch = _MACHINE_TO_ARCH.get(machine)
    if arch is None or arch not in ASSETS:
        raise InstallError(f"no agent-desktop {VERSION} release for this machine ({machine})")
    return {"arch": arch, **ASSETS[arch]}


def _parse_envelope(stdout):
    try:
        parsed = json.loads(stdout)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) and "ok" in parsed else None


def _rewrite_suggestions(stdout, cli_call):
    escaped_call = json.dumps(f"{cli_call} ", ensure_ascii=False)[1:-1]

    def rewrite(match):
        replaced = _SUGGESTION_CALL.sub(lambda _: escaped_call, match.group(2))
        return f"{match.group(1)}{replaced}{match.group(3)}"

    return _SUGGESTION.sub(rewrite, stdout)


def _ask_engine(final, command):
    try:
        completed = subprocess.run([str(final / BINARY), command], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    envelope = _parse_envelope(completed.stdout.decode("utf-8", "replace"))
    return envelope.get("data") if envelope and envelope.get("ok") else None


def _is_verified(directory, asset):
    if directory.is_symlink() or not directory.is_dir():
        return False
    for name in (BINARY, HELPER):
        path = directory / name
        try:
            mode = path.lstat().st_mode
        except OSError:
            return False
        if not stat.S_ISREG(mode) or stat.S_IMODE(mode) != 0o755:
            return False
        try:
            data = path.read_bytes()
        except OSError:
            return False
        if _sha256(data) != asset[name]:
            return False
    return True


def _fetch_release(staging, asset):
    base_url = os.environ.get("COMPUTER_RELEASE_BASE_URL", DEFAULT_RELEASE_BASE_URL).rstrip("/")
    url = f"{base_url}/agent-desktop-v{VERSION}-{asset['arch']}-apple-darwin.tar.gz"
    with tempfile.TemporaryDirectory() as download_dir:
        archive = Path(download_dir) / "release.tar.gz"
        _download(url, archive)
        if _sha256(archive.read_bytes()) != asset["archive"]:
            raise InstallError(f"archive sha256 does not match the pinned value: {url}")
        with tarfile.open(archive, "r:gz") as tar:
            _extract_members(tar, staging, asset)


def _download(url, destination):
    # curl을 쓰는 이유: python.org·uv 빌드의 urllib은 맥 시스템 인증서를 보지 않아 인증서 오류가 날 수 있다.
    completed = subprocess.run(["curl", "-fsSL", "--max-time", "300", "-o", str(destination), url], capture_output=True, text=True)
    if completed.returncode != 0:
        raise InstallError(f"download failed: {url}: {completed.stderr.strip()}")


def _extract_members(tar, staging, asset):
    members = tar.getmembers()
    if sorted(member.name for member in members) != sorted((BINARY, HELPER)) or not all(member.isreg() for member in members):
        raise InstallError(f"archive must hold exactly two regular files named {BINARY} and {HELPER}")
    for member in members:
        data = tar.extractfile(member).read()
        if _sha256(data) != asset[member.name]:
            raise InstallError(f"{member.name} sha256 does not match the pinned value")
        destination = staging / member.name
        destination.write_bytes(data)
        destination.chmod(0o755)


@contextmanager
def _install_lock(parent):
    with open(parent / ".lock", "w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _quarantine(final, parent):
    """Take a final directory that failed verification out of the path run() executes."""
    if not os.path.lexists(final):
        return
    try:
        os.rename(final, parent / f".broken-{secrets.token_hex(4)}")
    except OSError:
        _remove(final)
    if os.path.lexists(final):
        raise InstallError(f"cannot remove the unverified install at {final}")


def _remove_leftovers(parent):
    for entry in parent.iterdir():
        if entry.name.startswith((".staging-", ".broken-")):
            _remove(entry)


def _remove(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.lexists(path):
        path.unlink()


def _sha256(data):
    return hashlib.sha256(data).hexdigest()

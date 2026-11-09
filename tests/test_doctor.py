"""`cli.main(["doctor", ...])`로 설치 규칙을 본다. 상수를 재정의해야 하므로 같은 프로세스에서 진입점을 부른다."""
import hashlib
import io
import json
import os
import stat
import sys
import tarfile
from pathlib import Path

import pytest

import cli
from computer import agent_desktop

ARCHIVE = "agent-desktop-v1.2.0-{arch}-apple-darwin.tar.gz"
ENGINE_SCRIPT = """#!{python}
import json, sys
if sys.argv[1:] == ["version"]:
    print(json.dumps({{"version": "2.6", "ok": True, "command": "version", "data": {{"version": "1.2.0"}}}}))
elif sys.argv[1:] == ["permissions"]:
    print(json.dumps({{"version": "2.6", "ok": True, "command": "permissions", "data": {{"accessibility": {{"state": "granted"}}, "screen_recording": {{"state": "denied"}}}}}}))
"""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def add_file(tar, name, data, kind=tarfile.REGTYPE, link=""):
    info = tarfile.TarInfo(name)
    info.size = len(data) if kind == tarfile.REGTYPE else 0
    info.mode = 0o644
    info.type = kind
    info.linkname = link
    tar.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)


def write_archive(path, entries):
    with tarfile.open(path, "w:gz") as tar:
        for entry in entries:
            add_file(tar, *entry)


class Release:
    def __init__(self, tmp_path, monkeypatch):
        self.dir = tmp_path / "release"
        self.dir.mkdir()
        self.parent = tmp_path / "install"
        self.final = self.parent / "agent-desktop-1.2.0"
        self.binary = ENGINE_SCRIPT.format(python=sys.executable).encode()
        self.helper = b"helper bytes"
        self.monkeypatch = monkeypatch
        monkeypatch.setenv("COMPUTER_INSTALL_DIR", str(self.parent))
        monkeypatch.setenv("COMPUTER_RELEASE_BASE_URL", self.dir.as_uri())
        monkeypatch.setattr("platform.machine", lambda: "arm64")
        self.publish()

    def publish(self, entries=None, arch="aarch64"):
        entries = entries if entries is not None else [("agent-desktop", self.binary), ("agent-desktop-macos-helper", self.helper)]
        path = self.dir / ARCHIVE.format(arch=arch)
        write_archive(path, entries)
        self.pin(arch, sha(path.read_bytes()))
        return path

    def pin(self, arch, archive_hash, binary=None, helper=None):
        assets = dict(agent_desktop.ASSETS)
        assets[arch] = {"archive": archive_hash, "agent-desktop": binary or sha(self.binary), "agent-desktop-macos-helper": helper or sha(self.helper)}
        self.monkeypatch.setattr(agent_desktop, "ASSETS", assets)

    def leftovers(self):
        return [p.name for p in self.parent.iterdir() if p.name.startswith((".staging-", ".broken-"))]

    def assert_verified(self):
        assert (self.final / "agent-desktop").read_bytes() == self.binary
        assert (self.final / "agent-desktop-macos-helper").read_bytes() == self.helper
        for name in ("agent-desktop", "agent-desktop-macos-helper"):
            mode = (self.final / name).lstat().st_mode
            assert stat.S_ISREG(mode) and stat.S_IMODE(mode) == 0o755


@pytest.fixture
def release(tmp_path, monkeypatch):
    return Release(tmp_path, monkeypatch)


def run_doctor(capsys, *args):
    code = cli.main(["doctor", *args])
    return code, json.loads(capsys.readouterr().out)


def test_fix_installs_both_files_0755_and_reports_healthy_state(release, capsys):
    code, out = run_doctor(capsys, "--fix")
    assert code == 1  # 가짜 엔진은 screen_recording을 denied로 답한다
    release.assert_verified()
    assert out["installed"] is True
    assert out["version"] == "1.2.0"
    assert out["hashes_match"] is True
    assert out["accessibility"] == "granted"
    assert out["screen_recording"] == "denied"
    assert "Screen Recording" in out["fix"]
    assert release.leftovers() == []


def test_doctor_without_install_says_how_and_exits_3(release, capsys):
    code, out = run_doctor(capsys)
    assert code == 3
    assert out["ok"] is False
    assert "doctor --fix" in out["fix"]


def test_doctor_reports_a_tampered_install(release, capsys):
    run_doctor(capsys, "--fix")
    (release.final / "agent-desktop-macos-helper").write_bytes(b"tampered")
    code, out = run_doctor(capsys)
    assert code == 1
    assert out["hashes_match"] is False
    assert "doctor --fix" in out["fix"]


def test_architecture_picks_its_own_asset(release, capsys, monkeypatch):
    release.publish(arch="x86_64")
    (release.dir / ARCHIVE.format(arch="aarch64")).unlink()
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    run_doctor(capsys, "--fix")
    release.assert_verified()


def test_second_fix_changes_nothing_and_needs_no_download(release, capsys):
    run_doctor(capsys, "--fix")
    before = (release.final / "agent-desktop").stat().st_mtime_ns
    (release.dir / ARCHIVE.format(arch="aarch64")).unlink()
    _, out = run_doctor(capsys, "--fix")
    assert out["installed"] is False
    assert (release.final / "agent-desktop").stat().st_mtime_ns == before


@pytest.mark.parametrize("mismatch", ["archive", "binary", "helper"])
def test_hash_mismatch_installs_nothing(release, capsys, mismatch):
    good = sha((release.dir / ARCHIVE.format(arch="aarch64")).read_bytes())
    release.pin("aarch64", "0" * 64 if mismatch == "archive" else good, binary="0" * 64 if mismatch == "binary" else None, helper="0" * 64 if mismatch == "helper" else None)
    code, out = run_doctor(capsys, "--fix")
    assert code == 1
    assert out["ok"] is False
    assert not release.final.exists()
    assert release.leftovers() == []


def test_mismatched_download_keeps_a_verified_install(release, capsys):
    run_doctor(capsys, "--fix")
    release.pin("aarch64", "0" * 64)
    # 아카이브 핀만 틀렸고 설치된 두 파일은 맞으므로 내려받지 않고 그대로 둔다
    code, out = run_doctor(capsys, "--fix")
    assert out["installed"] is False
    release.assert_verified()


@pytest.mark.parametrize(
    "entries",
    [
        [("agent-desktop", b"a")],
        [("agent-desktop", b"a"), ("agent-desktop-macos-helper", b"b"), ("extra", b"c")],
        [("../agent-desktop", b"a"), ("agent-desktop-macos-helper", b"b")],
        [("./agent-desktop", b"a"), ("agent-desktop-macos-helper", b"b")],
        [("agent-desktop", b"", tarfile.SYMTYPE, "/bin/sh"), ("agent-desktop-macos-helper", b"b")],
        [("agent-desktop", b"", tarfile.DIRTYPE), ("agent-desktop-macos-helper", b"b")],
    ],
)
def test_archive_shape_is_enforced(release, capsys, entries):
    release.publish(entries)
    code, out = run_doctor(capsys, "--fix")
    assert code == 1
    assert out["ok"] is False
    assert not release.final.exists()
    assert release.leftovers() == []


def test_broken_final_is_replaced(release, capsys):
    release.final.mkdir(parents=True)
    (release.final / "agent-desktop").write_bytes(b"wrong")
    (release.final / "stale").write_bytes(b"x")
    run_doctor(capsys, "--fix")
    release.assert_verified()
    assert not (release.final / "stale").exists()
    assert release.leftovers() == []


def test_a_final_path_that_is_a_file_is_replaced(release, capsys):
    release.parent.mkdir(parents=True)
    release.final.write_bytes(b"not a directory")
    run_doctor(capsys, "--fix")
    release.assert_verified()
    assert release.leftovers() == []


def test_failed_download_never_leaves_an_unverified_final(release, capsys):
    release.final.mkdir(parents=True)
    (release.final / "agent-desktop").write_bytes(b"wrong")
    (release.final / "agent-desktop-macos-helper").write_bytes(b"wrong")
    (release.dir / ARCHIVE.format(arch="aarch64")).unlink()
    code, out = run_doctor(capsys, "--fix")
    assert code == 1
    assert not release.final.exists()


@pytest.mark.parametrize("fail_on_call", [1, 2])
def test_interrupted_publish_leaves_verified_or_nothing_and_rerun_recovers(release, capsys, monkeypatch, fail_on_call):
    release.final.mkdir(parents=True)
    (release.final / "agent-desktop").write_bytes(b"wrong")
    (release.final / "agent-desktop-macos-helper").write_bytes(b"wrong")
    real_rename = os.rename
    calls = {"n": 0}

    def flaky_rename(src, dst):
        calls["n"] += 1
        if calls["n"] == fail_on_call:
            raise OSError("interrupted")
        return real_rename(src, dst)

    monkeypatch.setattr(agent_desktop.os, "rename", flaky_rename)
    code, out = run_doctor(capsys, "--fix")
    if fail_on_call == 2:
        assert code == 1 and out["ok"] is False
    monkeypatch.setattr(agent_desktop.os, "rename", real_rename)
    if fail_on_call == 2:
        assert not release.final.exists()
    assert not release.final.exists() or (release.final / "agent-desktop").read_bytes() == release.binary
    run_doctor(capsys, "--fix")
    release.assert_verified()
    assert release.leftovers() == []


def test_interrupt_between_renames_makes_forwarding_exit_3(release, capsys, monkeypatch):
    release.final.mkdir(parents=True)
    (release.final / "agent-desktop").write_bytes(b"wrong")
    (release.final / "agent-desktop-macos-helper").write_bytes(b"wrong")
    real_rename = os.rename
    calls = {"n": 0}

    def flaky_rename(src, dst):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("interrupted")
        return real_rename(src, dst)

    monkeypatch.setattr(agent_desktop.os, "rename", flaky_rename)
    run_doctor(capsys, "--fix")
    assert cli.main(["version"]) == 3
    assert "doctor --fix" in capsys.readouterr().err


def test_unreadable_install_is_reported_instead_of_crashing(release, capsys, monkeypatch):
    run_doctor(capsys, "--fix")
    real = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda self: (_ for _ in ()).throw(PermissionError("denied")) if self.name == "agent-desktop" else real(self))
    code, out = run_doctor(capsys)
    assert code == 1
    assert out["hashes_match"] is False


def test_leftovers_from_an_earlier_crash_are_removed(release, capsys):
    release.parent.mkdir(parents=True)
    (release.parent / ".staging-old").mkdir()
    (release.parent / ".broken-old").mkdir()
    (release.parent / ".broken-old" / "x").write_bytes(b"x")
    run_doctor(capsys, "--fix")
    assert release.leftovers() == []


@pytest.mark.slow
def test_real_release_downloads_and_matches_the_pinned_hashes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("COMPUTER_INSTALL_DIR", str(tmp_path / "install"))
    monkeypatch.delenv("COMPUTER_RELEASE_BASE_URL", raising=False)
    code, out = run_doctor(capsys, "--fix")
    assert out["hashes_match"] is True
    assert out["version"] == "1.2.0"
    assert out["install_dir"].endswith("agent-desktop-1.2.0")

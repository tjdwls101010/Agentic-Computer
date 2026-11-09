"""시험 공용 준비: 가짜 agent-desktop과 고정 설치 위치."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / ".claude/skills/computer/scripts/cli.py"
FIXTURES = Path(__file__).parent / "fixtures"
PINNED_DIR = "agent-desktop-1.2.0"

_STUB = """#!{python}
import json, os, sys
stdin = sys.stdin.read() if not sys.stdin.isatty() else ""
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({{"argv": sys.argv[1:], "stdin": stdin, "home": os.environ.get("AGENT_DESKTOP_HOME")}}, ensure_ascii=False) + "\\n")
with open(os.environ["FAKE_RESPONSE"], encoding="utf-8") as f:
    response = json.load(f)
sys.stdout.write(response["stdout"])
sys.stderr.write(response.get("stderr", ""))
sys.exit(response.get("exit", 0))
"""


class FakeEngine:
    """cli.py를 하위 프로세스로 돌리고, 가짜 바이너리가 받은 것과 낼 것을 관리한다."""

    def __init__(self, tmp_path):
        self.install_parent = tmp_path / "install"
        self.dir = self.install_parent / PINNED_DIR
        self.dir.mkdir(parents=True)
        self.log = tmp_path / "calls.jsonl"
        self.response = tmp_path / "response.json"
        self.home = tmp_path / "home"
        binary = self.dir / "agent-desktop"
        binary.write_text(_STUB.format(python=sys.executable), encoding="utf-8")
        binary.chmod(0o755)
        helper = self.dir / "agent-desktop-macos-helper"
        helper.write_text("helper", encoding="utf-8")
        helper.chmod(0o755)
        self.respond("{}")

    def respond(self, stdout, exit_code=0, stderr=""):
        self.response.write_text(json.dumps({"stdout": stdout, "exit": exit_code, "stderr": stderr}), encoding="utf-8")

    def env(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("COMPUTER_", "AGENT_DESKTOP_"))}
        env.update(COMPUTER_INSTALL_DIR=str(self.install_parent), FAKE_LOG=str(self.log), FAKE_RESPONSE=str(self.response))
        env.update(extra)
        return env

    def cli(self, *args, stdin="", **env):
        return subprocess.run([sys.executable, str(CLI), *args], input=stdin, capture_output=True, text=True, env=self.env(**env), timeout=30)

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]


@pytest.fixture
def engine(tmp_path):
    return FakeEngine(tmp_path)


@pytest.fixture
def fixture_text():
    return lambda name: (FIXTURES / name).read_text(encoding="utf-8")

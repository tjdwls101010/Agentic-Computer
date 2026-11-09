"""cli.py를 하위 프로세스로 돌려 전달·거부·도움말·종료 코드 계약을 본다."""
import json

import pytest

from tests.conftest import CLI

ENVELOPE = '{"version":"2.6","ok":true,"command":"version","data":{"version":"1.2.0"}}\n'
CALL = f'uv run "{CLI}"'


def test_arguments_reach_the_binary_unchanged(engine):
    args = ["type", "@s1:e1", "two words", 'quo"te', "한글 값", "--json", "raw", "doctor", "--", "--trace"]
    engine.respond(ENVELOPE)
    result = engine.cli(*args)
    assert result.returncode == 0, result.stderr
    assert engine.calls()[0]["argv"] == args


def test_stdin_and_environment_reach_the_binary(engine):
    engine.respond(ENVELOPE)
    engine.cli("type", "@s1:e1", "--stdin", stdin="첫 줄\n둘째 줄\n", AGENT_DESKTOP_HOME="/x/y")
    call = engine.calls()[0]
    assert call["stdin"] == "첫 줄\n둘째 줄\n"
    assert call["home"] == "/x/y"


@pytest.mark.parametrize("code", [0, 1, 2, 7])
def test_exit_code_and_stdout_are_kept(engine, code):
    engine.respond('{"ok":false,"command":"x","error":{"code":"INVALID_ARGS","message":"m"}}\n', code)
    result = engine.cli("raw", "snapshot", "--bogus")
    assert result.returncode == code
    assert json.loads(result.stdout)["error"]["code"] == "INVALID_ARGS"


def test_raw_first_token_is_consumed_and_output_is_byte_exact(engine):
    original = '{ "version":"2.6",  "ok":true, "command":"snapshot", "data":{"tree":{"role":"window"}} }\n'
    engine.respond(original)
    result = engine.cli("raw", "snapshot", "--app", "TextEdit")
    assert engine.calls()[0]["argv"] == ["snapshot", "--app", "TextEdit"]
    assert result.stdout == original


def test_raw_is_only_reserved_as_first_token(engine):
    engine.respond(ENVELOPE)
    engine.cli("type", "@s1:e1", "raw")
    assert engine.calls()[0]["argv"] == ["type", "@s1:e1", "raw"]


def test_computer_raw_env_behaves_like_raw(engine):
    original = '{ "version":"2.6", "ok":true, "command":"snapshot", "data":{} }\n'
    engine.respond(original)
    result = engine.cli("snapshot", COMPUTER_RAW="1")
    assert engine.calls()[0]["argv"] == ["snapshot"]
    assert result.stdout == original


@pytest.mark.parametrize("args", [["snapshot", "--trace", "/tmp/x"], ["snapshot", "--trace=/tmp/x"], ["click", "@s1:e1", "--trace-strict"], ["--debug", "snapshot"], ["snapshot", "--screenshot", "a.html"], ["snapshot", "--screenshot=a.html"], ["raw", "snapshot", "--trace", "/tmp/x"]])
def test_debug_flags_are_refused_before_the_binary_runs(engine, args):
    result = engine.cli(*args)
    assert result.returncode == 2
    assert engine.calls() == []
    assert "--" in result.stderr and "refused" in result.stderr


def test_refused_names_after_double_dash_are_values(engine):
    engine.respond(ENVELOPE)
    result = engine.cli("type", "@s1:e1", "--", "--trace")
    assert result.returncode == 0
    assert engine.calls()[0]["argv"] == ["type", "@s1:e1", "--", "--trace"]


@pytest.mark.parametrize("missing", ["agent-desktop", "agent-desktop-macos-helper"])
def test_missing_install_exits_3_with_the_remedy(engine, missing):
    (engine.dir / missing).unlink()
    result = engine.cli("version")
    assert result.returncode == 3
    assert "doctor --fix" in result.stderr


def test_non_json_output_without_usage_passes_through(engine):
    engine.respond("agent-desktop 1.2.0\n")
    result = engine.cli("-V")
    assert result.stdout == "agent-desktop 1.2.0\n"


@pytest.mark.parametrize("args", [["--help"], ["-h"], ["help"], []])
def test_top_level_help_drops_upstream_guidance_and_prepends_the_map(engine, fixture_text, args):
    engine.respond(fixture_text("help_top.txt"))
    result = engine.cli(*args)
    assert result.returncode == 0
    out = result.stdout
    assert "For AI agents" not in out
    assert "skills get desktop" not in out
    assert "Skills are compiled into this binary" not in out
    assert f"Usage: {CALL} [OPTIONS] [COMMAND]" in out
    assert f"  {CALL} snapshot --app Finder --skeleton -i --compact" in out
    assert "Usage: agent-desktop" not in out
    head = out[: out.index("Usage: ")]
    for word in ("doctor", "raw", "COMPUTER_RAW", "--trace", "--screenshot", "COMPUTER_INSTALL_DIR", "--stdin"):
        assert word in head, word
    assert "Exit codes" in head


@pytest.mark.parametrize("args", [["snapshot", "--help"], ["help", "snapshot"]])
def test_command_help_gets_the_call_name_and_output_shape(engine, fixture_text, args):
    engine.respond(fixture_text("help_snapshot.txt"))
    out = engine.cli(*args).stdout
    assert f"Usage: {CALL} snapshot [OPTIONS]" in out
    assert "Usage: agent-desktop" not in out
    assert "Output:" in out[out.index("Print help") :]


def test_prose_that_names_the_binary_is_not_rewritten(engine, fixture_text):
    engine.respond(fixture_text("help_skills.txt"))
    out = engine.cli("skills", "--help").stdout
    assert "agent-desktop version. Each command" in out
    assert f"  {CALL} skills get desktop" in out


def test_suggestion_call_names_are_rewritten_and_other_prose_is_not(engine):
    suggestion = "Run agent-desktop permissions --guide. It opens a guide; the app that launches agent-desktop in System Settings."
    body = {"version": "2.6", "ok": False, "command": "snapshot", "error": {"code": "PERM_DENIED", "message": "launches agent-desktop now", "suggestion": suggestion}}
    engine.respond(json.dumps(body), 1)
    result = engine.cli("raw", "snapshot")
    parsed = json.loads(result.stdout)
    assert result.returncode == 1
    assert parsed["error"]["suggestion"] == f"Run {CALL} permissions --guide. It opens a guide; the app that launches agent-desktop in System Settings."
    assert parsed["error"]["message"] == "launches agent-desktop now"


def test_doctor_is_cli_own_help(engine):
    result = engine.cli("doctor", "--help")
    assert result.returncode == 0
    assert "--fix" in result.stdout
    assert engine.calls() == []


def test_doctor_rejects_unknown_arguments(engine):
    assert engine.cli("doctor", "--nope").returncode == 2

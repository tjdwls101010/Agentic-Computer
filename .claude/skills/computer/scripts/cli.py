#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""The computer skill's only entry point: forwards a command to the pinned agent-desktop and reports what it returned."""
import argparse
import json
import os
import sys

from computer import agent_desktop, doctor

EXIT_USAGE = 2
EXIT_NOT_INSTALLED = 3

_CLI_CALL = f'uv run "{os.path.abspath(__file__)}"'

_MAP = f"""computer: see and operate native macOS apps through agent-desktop {agent_desktop.VERSION}, pinned by this skill.

Call:
  {_CLI_CALL} <agent-desktop command> [args...]

Everything is forwarded unchanged to the pinned binary, except two reserved first tokens:
  doctor   Report the install, hashes and macOS permissions; --fix installs the pinned release.
  raw      Forward the command that follows and print agent-desktop's raw envelope.

Output: agent-desktop's JSON envelope on stdout, unchanged except that call names in help and in error suggestions go through this entry point.

Environment:
  COMPUTER_RAW=1          Same as the raw first token.
  COMPUTER_INSTALL_DIR    Replaces the install parent (~/.cache/computer). The pinned-version guarantee then depends on what that directory holds.

Refused: --trace, --trace-strict, --debug and --screenshot (and their =value forms) write private content to arbitrary paths, so they exit 2 before the binary runs. Only tokens before `--` are checked; to send one of those strings as text, use `type --stdin`.

Exit codes: 0 success; 1 structured error envelope; 2 argument or parse error or refused flag; 3 the pinned binary is not installed (run doctor --fix). doctor exits 0 when healthy, 1 when a problem is reported, 3 when nothing is installed.

"""

_COMMAND_OUTPUT = """
Output: agent-desktop's JSON envelope on stdout, unchanged except that call names in error suggestions go through this entry point.
"""

_DOCTOR_DESCRIPTION = """Report as one JSON document on stdout: install_dir, expected_version, version, binary_present, helper_present, hashes_match, accessibility, screen_recording, ok, and fix (what to do) when something is wrong.

With --fix, download the pinned release, verify its sha256 values and install it first; adds "installed": whether anything changed. Reinstalls only when the install is missing or does not match. A failed --fix reports ok false and error.

Exit codes: 0 healthy; 1 a problem is reported or --fix failed; 2 bad arguments; 3 nothing is installed."""


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["doctor"]:
        return _doctor(args[1:])
    if args[:1] == ["raw"]:
        args = args[1:]
    refused = agent_desktop.refused_flag(args)
    if refused:
        print(f"computer: {refused} is refused: debug flags write private content to arbitrary paths", file=sys.stderr)
        return EXIT_USAGE
    try:
        result = agent_desktop.run(args, _CLI_CALL)
    except agent_desktop.NotInstalled as missing:
        print(f"computer: agent-desktop {agent_desktop.VERSION} is not installed at {missing}. Run: {_CLI_CALL} doctor --fix", file=sys.stderr)
        return EXIT_NOT_INSTALLED
    _write(_with_help_framing(result.stdout))
    return result.exit_code


def _with_help_framing(stdout):
    kind = agent_desktop.help_kind(stdout)
    if kind is None:
        return stdout
    text = agent_desktop.present_help(stdout, _CLI_CALL)
    return _MAP + text if kind == "top" else text + _COMMAND_OUTPUT


def _doctor(args):
    parser = argparse.ArgumentParser(prog=f"{_CLI_CALL} doctor", description=_DOCTOR_DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fix", action="store_true", help="install the pinned release when it is missing or does not match")
    parsed = parser.parse_args(args)
    payload, code = doctor.fix() if parsed.fix else doctor.report()
    _write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return code


def _write(text):
    # surrogateescape로 디코드한 출력이라 비 UTF-8 바이트까지 그대로 돌려놓아야 한다.
    sys.stdout.buffer.write(text.encode("utf-8", "surrogateescape"))
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    sys.exit(main())
